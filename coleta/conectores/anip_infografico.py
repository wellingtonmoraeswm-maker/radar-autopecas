"""Conector ANIP: infografico mensal de vendas de pneus (PDF), publicado em anip-em-numeros/publicacoes/.

O PDF e um infografico: o texto sai embaralhado, mas a manchete e os destaques da pagina 1 sao frases
completas e estaveis, por exemplo:
    "VENDAS TOTAIS DE PNEUS CAEM 8,6% ATÉ AGOSTO DE 2026"
    "Vendas para reposição retraíram 13,3%"
Sao essas frases que viram dados. Tudo e acumulado no ano contra o mesmo periodo do ano anterior, em
unidades, so da industria associada (nao inclui pneus importados por terceiros).
Frase com verbo desconhecido nao vira numero: vira aviso, para nao inventar o sinal.
Precisa de pypdf (ambiente .venv do projeto).
"""

from __future__ import annotations

import io
import re
import unicodedata
import urllib.parse

from coleta.base import Contexto, Noticia, Ponto, Resultado, cortar, ler_series_existentes

MAX_PDFS = 12
MESES = {"jan": 1, "janeiro": 1, "fev": 2, "fevereiro": 2, "mar": 3, "marco": 3, "abr": 4, "abril": 4, "mai": 5,
         "maio": 5, "jun": 6, "junho": 6, "jul": 7, "julho": 7, "ago": 8, "agosto": 8, "set": 9, "setembro": 9,
         "out": 10, "outubro": 10, "nov": 11, "novembro": 11, "dez": 12, "dezembro": 12}
NEGATIVOS = {"cai", "caem", "caiu", "cairam", "recua", "recuam", "recuou", "recuaram", "retrai", "retraem", "retraiu",
             "retrairam", "diminui", "diminuem", "diminuiu", "diminuiram", "despenca", "despencam", "despencou"}
POSITIVOS = {"sobe", "sobem", "subiu", "subiram", "cresce", "crescem", "cresceu", "cresceram", "aumenta", "aumentam",
             "aumentou", "aumentaram", "avanca", "avancam", "avancou", "avancaram"}
SERIES = {"total": "anip_total_acum", "montadoras": "anip_montadoras_acum", "reposicao": "anip_reposicao_acum",
          "exportacoes": "anip_exportacoes_acum"}
# Importacoes NAO e lida: o infografico nao deixa claro se o numero e em unidades ou em dolares, nem de quem
# (a balanca comercial vem do Comex Stat). Decisao de 2026-11-01: fica fora do Radar.
UNIDADE = "% no acumulado do ano, contra o mesmo período do ano anterior (unidades)"


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()


def numero(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def sinal(verbo: str) -> int | None:
    v = sem_acento(verbo)
    return -1 if v in NEGATIVOS else (1 if v in POSITIVOS else None)


def referencia_do_arquivo(url: str) -> str | None:
    """'.../08-PT_INFOGRAFICO_AGO_26.pdf' -> '2026-08'; 'PT_INFOGRAFICO_julho_26.pdf' -> '2026-07'."""
    nome = sem_acento(urllib.parse.unquote(url.rsplit("/", 1)[-1]))
    achado = re.search(r"infogr\w*?_([a-z]+)_(\d{2,4})", nome)
    if not achado or achado.group(1) not in MESES:
        return None
    ano = int(achado.group(2))
    ref = f"{ano + 2000 if ano < 100 else ano:04d}-{MESES[achado.group(1)]:02d}"
    # Um infografico nunca e de um mes posterior ao da publicacao (pasta uploads/AAAA/MM).
    # Ex.: "FEV_27_03_27" publicado em 2023/03 nao e fevereiro de 2027: o nome nao serve, descarta.
    publicado = re.search(r"uploads/(\d{4})/(\d{2})/", url)
    if publicado and ref > f"{publicado.group(1)}-{publicado.group(2)}":
        return None
    return ref


def extrair(texto: str) -> tuple[dict, str | None, list[str], str]:
    """Le a pagina 1. Devolve ({chave: valor com sinal}, referencia AAAA-MM, avisos, manchete)."""
    valores, avisos = {}, []
    plano = " ".join(texto.split())
    m = re.search(r"VENDAS TOTAIS DE PNEUS (\w+) ([\d.,]+)% AT[ÉE] (\w+) DE (\d{4})", plano, re.I)
    manchete, ref = "", None
    if m:
        manchete = m.group(0)
        mes = MESES.get(sem_acento(m.group(3)))
        ref = f"{m.group(4)}-{mes:02d}" if mes else None
        s = sinal(m.group(1))
        if s is None:
            avisos.append(f"verbo desconhecido na manchete: {m.group(1)}")
        else:
            valores["total"] = s * numero(m.group(2))
    else:
        avisos.append("manchete de vendas totais nao encontrada")
    for chave, padrao in (("montadoras", r"Vendas para montadoras"), ("reposicao", r"Vendas para reposi\w+o"),
                          ("exportacoes", r"Exporta\w+es")):
        m = re.search(padrao + r" (\w+) ([\d.,]+)%", plano, re.I)
        if not m:
            avisos.append(f"destaque de {chave} nao encontrado")
            continue
        s = sinal(m.group(1))
        if s is None:
            avisos.append(f"verbo desconhecido em {chave}: {m.group(1)}")
            continue
        valores[chave] = s * numero(m.group(2))
    return valores, ref, avisos, manchete


def destaques(texto: str) -> str:
    """Frases que vao para o trecho da noticia (e dai para a IA). Importacoes fica de fora (ver SERIES)."""
    plano = " ".join(texto.split())
    frases = re.findall(r"(Vendas para \w+ \w+ [\d.,]+%|Exporta\w+es \w+ [\d.,]+%)", plano)
    return ". ".join(frases)


def coletar(fonte: dict, ctx: Contexto) -> Resultado:
    try:
        import logging

        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos de fonte do PDF nao afetam o texto usado
    except ImportError as exc:
        raise RuntimeError("pypdf nao instalado: rode a coleta com .venv/Scripts/python") from exc

    pagina = ctx.baixar(fonte["url"])
    res = Resultado(brutos=[ctx.guardar_bruto(pagina, "html")])
    html = pagina.decode("utf-8", "ignore")
    links = {urllib.parse.urljoin(fonte["url"], l) for l in re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.I)}
    infograficos = [l for l in links if "infogr" in sem_acento(urllib.parse.unquote(l)) and "/en_" not in l.lower()
                    and "-en-" not in l.lower()]
    datados = sorted((referencia_do_arquivo(l) or "", l) for l in infograficos)
    ja_tem = {p["ocorrido_em"] for p in ler_series_existentes() if p["serie_id"] in SERIES.values()}

    for ref_arquivo, url in [d for d in datados if d[0]][-MAX_PDFS:]:
        if ref_arquivo in ja_tem:
            continue  # edicao ja lida; a ANIP nao revisa o infografico depois de publicado
        conteudo = ctx.baixar(url)
        res.brutos.append(ctx.guardar_bruto(conteudo, "pdf"))
        texto = PdfReader(io.BytesIO(conteudo)).pages[0].extract_text() or ""
        valores, ref, avisos, manchete = extrair(texto)
        ref = ref or ref_arquivo
        if ref != ref_arquivo:
            avisos.append(f"mes do arquivo ({ref_arquivo}) diferente do mes da manchete ({ref}); vale a manchete")
        res.avisos += [f"{url.rsplit('/', 1)[-1]}: {a}" for a in avisos]
        for chave, valor in valores.items():
            res.pontos.append(Ponto(serie_id=SERIES[chave], ocorrido_em=ref, valor=valor, unidade=UNIDADE))
        # So a edicao mais recente vira noticia: o PDF nao traz data de publicacao, e edicoes antigas
        # apareceriam como novidade do dia. As antigas ficam so como pontos da serie.
        if manchete and url == datados[-1][1]:
            titulo = "ANIP: " + manchete[0] + manchete[1:].lower()
            res.noticias.append(Noticia(url=url, titulo=titulo, ocorrido_em=ref,
                                        trecho_interno=cortar(destaques(texto) + ". Dados em unidades, acumulado do ano.")))
    if not infograficos:
        res.avisos.append("nenhum infografico encontrado na pagina: o layout pode ter mudado")
    return res
