"""Catalogo de fontes do Radar: valida o CSV, testa uma URL, verifica as fontes cadastradas e
inclui, pausa, reativa ou exclui fontes (usado pelo painel e pela skill curador-fontes-mercado).

Uso (na raiz do repositorio; a skill chama este mesmo codigo):
    python fontes.py validar
    python fontes.py testar <url>
    python fontes.py verificar [--ids S01,S16] [--gravar]

`verificar` testa as fontes com status ativa, candidata ou quebrada. Com --gravar, atualiza
ultima_verificacao e resultado_verificacao, e marca como quebrada uma fonte ativa que falhou.
Codigos de saida: 0 = ok, 1 = erros ou falhas, 2 = uso incorreto ou arquivo ausente.
So usa a biblioteca padrao.
"""

import csv
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "config" / "fontes.csv"
ENTIDADES = RAIZ / "config" / "taxonomia" / "entidades.csv"
TEMAS = RAIZ / "config" / "taxonomia" / "temas.csv"
COLUNAS = ["id", "nome", "entidade", "tipo", "url", "metodo", "formato", "frequencia", "blocos", "temas", "escopo",
           "confiabilidade", "licenca", "status", "conector", "ultima_verificacao", "resultado_verificacao",
           "observacao"]
OBRIGATORIAS = ["id", "nome", "tipo", "url", "formato", "frequencia", "escopo", "confiabilidade", "licenca", "status"]
TIPOS = {"api", "rss", "site", "arquivo", "pdf", "upload", "contratada"}
FORMATOS = {"json", "rss", "csv", "xlsx", "pdf", "html", "xml"}
FREQUENCIAS = {"diaria", "semanal", "mensal", "trimestral", "anual", "eventual"}
CONFIABILIDADE = {"A", "B", "C"}
ESCOPOS = {"setorial", "geral"}
STATUS = {"candidata", "ativa", "pausada", "quebrada", "descartada"}
AGENTE = "RadarAutopecas/0.1 (monitoramento de mercado; contato pelo administrador da instancia)"
TIMEOUT = 30
CAMINHOS_FEED = ["/feed/", "/rss", "/feed", "/rss.xml", "/atom.xml"]


# --------------------------------------------------------------------------- leitura

def ler_csv(caminho: Path) -> tuple[list[str], list[dict]]:
    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"{caminho}: codificacao desconhecida (use UTF-8 ou Windows-1252)")
    leitor = csv.reader(io.StringIO(texto), delimiter=";")
    cabecalho = next(leitor, [])
    linhas = []
    for n, valores in enumerate(leitor, start=2):
        if not any(v.strip() for v in valores):
            continue
        linha = {k: v.strip() for k, v in zip(cabecalho, valores)}
        linha["_n"] = n
        linha["_ncols"] = len(valores)
        linhas.append(linha)
    return cabecalho, linhas


def ids_de(caminho: Path) -> set[str]:
    if not caminho.exists():
        return set()
    return {l["id"] for l in ler_csv(caminho)[1]}


# --------------------------------------------------------------------------- validar

def validar(cabecalho: list[str], linhas: list[dict]) -> tuple[list[str], list[str]]:
    erros, avisos = [], []
    faltando = [c for c in COLUNAS if c not in cabecalho]
    if faltando:
        return [f"colunas ausentes no cabecalho: {', '.join(faltando)}"], []
    entidades, temas = ids_de(ENTIDADES), ids_de(TEMAS)
    vistos, urls = set(), {}
    for l in linhas:
        ref = f"linha {l['_n']} ({l.get('id') or 'sem id'})"
        if l["_ncols"] != len(cabecalho):
            erros.append(f"{ref}: {l['_ncols']} colunas, esperado {len(cabecalho)} (ponto e virgula dentro de um campo?)")
            continue
        for campo in OBRIGATORIAS:
            if not l.get(campo):
                erros.append(f"{ref}: campo obrigatorio vazio: {campo}")
        if l["id"]:
            if not re.fullmatch(r"S\d{2,3}", l["id"]):
                erros.append(f"{ref}: id deve ser S seguido de 2 ou 3 digitos")
            if l["id"] in vistos:
                erros.append(f"{ref}: id repetido")
            vistos.add(l["id"])
        for campo, validos in (("tipo", TIPOS), ("formato", FORMATOS), ("frequencia", FREQUENCIAS),
                               ("confiabilidade", CONFIABILIDADE), ("status", STATUS), ("escopo", ESCOPOS)):
            if l.get(campo) and l[campo] not in validos:
                erros.append(f"{ref}: {campo} invalido '{l[campo]}' (use {', '.join(sorted(validos))})")
        if l["metodo"] and l["metodo"] not in ("GET", "POST"):
            erros.append(f"{ref}: metodo deve ser GET ou POST")
        if l["url"] and not l["url"].startswith("https://"):
            avisos.append(f"{ref}: url sem https://")
        if l["status"] != "descartada":
            if l["url"] in urls:
                avisos.append(f"{ref}: mesma url de {urls[l['url']]}")
            urls.setdefault(l["url"], l["id"])
        if l["entidade"] and entidades and l["entidade"] not in entidades:
            erros.append(f"{ref}: entidade '{l['entidade']}' nao existe em entidades.csv")
        for t in filter(None, l["temas"].split("|")):
            if temas and t not in temas:
                erros.append(f"{ref}: tema '{t}' nao existe em temas.csv")
        if l["status"] == "ativa" and not l["conector"]:
            erros.append(f"{ref}: fonte ativa sem conector")
        if l["status"] == "ativa" and l["licenca"].startswith("a confirmar"):
            avisos.append(f"{ref}: fonte ativa com licenca ainda a confirmar")
    return erros, avisos


# --------------------------------------------------------------------------- testar

def baixar(url: str) -> tuple[int, str, bytes, str]:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "*/*"})
    with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read(5_000_000), r.geturl()


def robots_permite(url: str) -> str:
    partes = urllib.parse.urlsplit(url)
    # Baixa o robots.txt com o nosso agente: o rp.read() padrao usa "Python-urllib", que muitos
    # sites recusam com 403, e a biblioteca entende isso como "tudo proibido".
    rp = urllib.robotparser.RobotFileParser()
    try:
        _, _, corpo, _ = baixar(f"{partes.scheme}://{partes.netloc}/robots.txt")
    except urllib.error.HTTPError as exc:
        return "sem robots.txt (permitido)" if exc.code == 404 else f"robots.txt inacessivel (HTTP {exc.code})"
    except Exception:
        return "robots.txt inacessivel"
    rp.parse(corpo.decode("utf-8", "ignore").splitlines())
    return "permitido" if rp.can_fetch(AGENTE, url) else "BLOQUEADO pelo robots.txt"


def detectar_formato(tipo_conteudo: str, corpo: bytes, url: str) -> str:
    inicio = corpo[:600].lstrip().lower()
    if corpo[:4] == b"%PDF":
        return "pdf"
    if corpo[:2] == b"PK":
        return "xlsx" if url.lower().endswith(".xlsx") or "spreadsheet" in tipo_conteudo else "zip"
    if b"<rss" in inicio or b"<feed" in inicio or b"<rdf:rdf" in inicio:
        return "rss"
    if inicio[:1] in (b"{", b"["):
        return "json"
    if b"<html" in inicio or b"<!doctype html" in inicio or "html" in tipo_conteudo:
        return "html"
    if inicio.startswith(b"<?xml"):
        return "xml"
    if "csv" in tipo_conteudo or url.lower().endswith(".csv"):
        return "csv"
    return "desconhecido"


def resumir_feed(corpo: bytes) -> str:
    try:
        raiz = ElementTree.fromstring(corpo)
    except ElementTree.ParseError as exc:
        return f"feed ilegivel ({exc})"
    itens = raiz.findall(".//item") or raiz.findall(".//{http://www.w3.org/2005/Atom}entry")
    datas, titulos = [], []
    for item in itens:
        titulo = item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or ""
        titulos.append(titulo.strip())
        bruto = item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}updated") or ""
        try:
            datas.append(parsedate_to_datetime(bruto).date() if "," in bruto else date.fromisoformat(bruto[:10]))
        except (TypeError, ValueError):
            pass
    texto = f"{len(itens)} itens"
    if datas:
        texto += f", mais recente em {max(datas).isoformat()}"
    exemplos = [t for t in titulos[:3] if t]
    if exemplos:
        texto += "\n    exemplos: " + "\n              ".join(exemplos)
    return texto


def procurar_feed(url_base: str, html: bytes) -> list[str]:
    achados = []
    texto = html.decode("utf-8", "ignore")
    for tag in re.findall(r"<link[^>]+>", texto, flags=re.I):
        if re.search(r"application/(rss|atom)\+xml", tag, flags=re.I):
            href = re.search(r'href=["\']([^"\']+)', tag, flags=re.I)
            if href:
                achados.append(urllib.parse.urljoin(url_base, href.group(1)))
    if achados:
        return list(dict.fromkeys(achados))
    for caminho in CAMINHOS_FEED:
        candidato = urllib.parse.urljoin(url_base, caminho)
        try:
            _, tipo, corpo, final = baixar(candidato)
        except Exception:
            continue
        if detectar_formato(tipo, corpo, final) == "rss":
            return [final]
    return []


def testar_url(url: str, metodo: str = "GET") -> tuple[bool, str]:
    """Retorna (ok, relatorio)."""
    if metodo == "POST":
        return True, "POST: nao testado aqui, use o conector"
    robots = robots_permite(url)
    linhas = [f"URL: {url}", f"robots.txt: {robots}"]
    try:
        status, tipo, corpo, final = baixar(url)
    except urllib.error.HTTPError as exc:
        linhas.append(f"FALHA: HTTP {exc.code}" + (" (o site recusa acesso automatizado)" if exc.code in (401, 403) else ""))
        return False, "\n".join(linhas)
    except Exception as exc:
        linhas.append(f"FALHA: {type(exc).__name__}: {exc}")
        return False, "\n".join(linhas)
    formato = detectar_formato(tipo, corpo, final)
    linhas.append(f"HTTP {status} - {tipo or 'sem content-type'} - {len(corpo):,} bytes - formato detectado: {formato}")
    if final != url:
        linhas.append(f"redirecionou para: {final}")
    if formato == "rss":
        linhas.append("feed: " + resumir_feed(corpo))
    elif formato == "json":
        try:
            dados = json.loads(corpo)
            linhas.append(f"json: {type(dados).__name__} com {len(dados)} elementos")
        except ValueError:
            linhas.append("json invalido")
            return False, "\n".join(linhas)
    elif formato == "html":
        feeds = procurar_feed(final, corpo)
        linhas.append("feeds encontrados: " + (", ".join(feeds) if feeds else "nenhum (precisaria de conector de site)"))
    if robots.startswith("BLOQUEADO"):
        linhas.append("NAO USAR: o site proibe coleta automatizada deste caminho")
        return False, "\n".join(linhas)
    return True, "\n".join(linhas)


# --------------------------------------------------------------------------- verificar e gravar

def gravar(cabecalho: list[str], linhas: list[dict]) -> None:
    with CATALOGO.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(cabecalho)
        for l in linhas:
            w.writerow([l.get(c, "") for c in cabecalho])


# --------------------------------------------------------------------------- inclusao e exclusao

class ErroCatalogo(ValueError):
    pass


def inspecionar(url: str) -> dict:
    """Teste de uma URL nova, em formato estruturado (para o painel)."""
    if not url.startswith(("https://", "http://")):
        raise ErroCatalogo("informe uma URL completa, começando com https://")
    r = {"url": url, "robots": robots_permite(url), "ok": False, "formato": None, "feeds": [], "itens": 0,
         "mais_recente": None, "exemplos": [], "url_sugerida": url, "tipo_sugerido": None, "mensagem": ""}
    try:
        status, tipo, corpo, final = baixar(url)
    except urllib.error.HTTPError as exc:
        r["mensagem"] = f"o site respondeu HTTP {exc.code}" + (" (recusa acesso automatizado)" if exc.code in (401, 403, 406) else "")
        return r
    except Exception as exc:  # noqa: BLE001
        r["mensagem"] = f"não foi possível acessar: {type(exc).__name__}"
        return r
    r["formato"] = detectar_formato(tipo, corpo, final)
    r["url_sugerida"] = final
    if r["formato"] == "html":
        r["feeds"] = [f for f in procurar_feed(final, corpo) if "comments" not in f and "web-stories" not in f]
        if r["feeds"]:
            r["url_sugerida"] = r["feeds"][0]
            try:
                corpo, final = baixar(r["url_sugerida"])[2], r["url_sugerida"]
                r["formato"] = detectar_formato("", corpo, final)
            except Exception:  # noqa: BLE001
                pass
    if r["formato"] == "rss":
        try:
            raiz = ElementTree.fromstring(corpo)
            itens = raiz.findall(".//item") or raiz.findall(".//{http://www.w3.org/2005/Atom}entry")
            r["itens"] = len(itens)
            r["exemplos"] = [(i.findtext("title") or i.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                             for i in itens[:3]]
        except ElementTree.ParseError:
            r["formato"] = "xml"
    robots_ok = not r["robots"].startswith("BLOQUEADO")
    if not robots_ok:
        r["mensagem"] = "o robots.txt do site proíbe coleta automatizada: a fonte não pode ser usada"
    elif r["formato"] == "rss":
        r.update(ok=True, tipo_sugerido="rss", mensagem=f"feed RSS encontrado com {r['itens']} itens: pode ser ativada já")
    elif r["formato"] == "json":
        r.update(ok=True, tipo_sugerido="api", mensagem="API em JSON: precisa de um conector específico (fica como candidata)")
    elif r["formato"] in ("pdf", "xlsx", "csv"):
        r.update(ok=True, tipo_sugerido="arquivo", mensagem="arquivo de dados: precisa de um conector específico (fica como candidata)")
    else:
        r.update(ok=True, tipo_sugerido="site", mensagem="site sem RSS: precisa de um conector específico (fica como candidata)")
    return r


def proximo_id(linhas: list[dict]) -> str:
    numeros = [int(l["id"][1:]) for l in linhas if re.fullmatch(r"S\d{2,3}", l.get("id", ""))]
    return f"S{(max(numeros) + 1 if numeros else 1):02d}"


def adicionar(dados: dict) -> dict:
    """Inclui uma fonte. RSS testado vira ativa com o conector generico; o resto entra como candidata."""
    cabecalho, linhas = ler_csv(CATALOGO)
    url = (dados.get("url") or "").strip()
    nome = (dados.get("nome") or "").strip()
    if not url or not nome:
        raise ErroCatalogo("informe nome e URL")
    ativas = [l for l in linhas if l.get("status") != "descartada"]
    if any(l["url"].rstrip("/") == url.rstrip("/") for l in ativas):
        raise ErroCatalogo("essa URL já está no catálogo")
    teste = inspecionar(url)
    if teste["robots"].startswith("BLOQUEADO"):
        raise ErroCatalogo(teste["mensagem"])
    rss = teste["formato"] == "rss"
    nova = {c: "" for c in cabecalho}
    nova.update({
        "id": proximo_id(linhas), "nome": nome, "entidade": dados.get("entidade", ""),
        "tipo": "rss" if rss else (teste["tipo_sugerido"] or "site"), "url": teste["url_sugerida"] if rss else url,
        "metodo": "GET", "formato": teste["formato"] if teste["formato"] in ("json", "rss", "csv", "xlsx", "pdf", "html", "xml") else "html",
        "frequencia": dados.get("frequencia") or ("diaria" if rss else "mensal"), "blocos": dados.get("blocos") or "F",
        "temas": dados.get("temas") or "T01", "escopo": dados.get("escopo") or "setorial",
        "confiabilidade": dados.get("confiabilidade") or "B",
        "licenca": dados.get("licenca") or ("só título, link e resumo próprio" if rss else "a confirmar"),
        "status": "ativa" if rss else "candidata", "conector": "radar:rss" if rss else "",
        "ultima_verificacao": date.today().isoformat(), "resultado_verificacao": ("ok: " + teste["mensagem"])[:150].replace(";", ","),
        "observacao": (dados.get("observacao") or f"Incluída pelo painel em {date.today().isoformat()}").replace(";", ","),
    })
    for campo in ("nome", "observacao"):
        nova[campo] = nova[campo].replace(";", ",")
    nova.update({"_n": len(linhas) + 2, "_ncols": len(cabecalho)})  # posicao que a linha tera no CSV
    linhas.append(nova)
    erros, _ = validar(cabecalho, linhas)
    erros = [e for e in erros if f"({nova['id']})" in e]
    if erros:
        raise ErroCatalogo("; ".join(erros))
    gravar(cabecalho, linhas)
    return {"fonte": nova, "teste": teste}


def mudar_status(fonte_id: str, status: str, motivo: str = "") -> dict:
    """Pausar, reativar ou excluir. Excluir = status descartada: a linha fica, com o motivo, para nao
    ser testada de novo e para o historico ja coletado continuar rastreavel."""
    if status not in ("ativa", "pausada", "descartada"):
        raise ErroCatalogo("ação inválida")
    cabecalho, linhas = ler_csv(CATALOGO)
    fonte = next((l for l in linhas if l["id"] == fonte_id), None)
    if not fonte:
        raise ErroCatalogo(f"fonte {fonte_id} não existe")
    if status == "ativa" and not fonte["conector"]:
        raise ErroCatalogo("essa fonte ainda não tem conector: não pode ser ativada (use a skill construtor-conector)")
    fonte["status"] = status
    if motivo or status == "descartada":
        texto = f"{date.today().isoformat()}: {status}" + (f" ({motivo})" if motivo else " pelo painel")
        fonte["observacao"] = (f"{fonte['observacao']}. {texto}" if fonte["observacao"] else texto).replace(";", ",")
    gravar(cabecalho, linhas)
    return fonte


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if not args or args[0] not in ("validar", "testar", "verificar") or (args[0] == "testar" and len(args) < 2):
        print(__doc__)
        return 2
    if args[0] == "testar":
        ok, relatorio = testar_url(args[1])
        print(relatorio)
        return 0 if ok else 1

    if not CATALOGO.exists():
        print(f"[ERRO] arquivo nao encontrado: {CATALOGO} (rode na raiz do repositorio)")
        return 2
    cabecalho, linhas = ler_csv(CATALOGO)

    if args[0] == "validar":
        erros, avisos = validar(cabecalho, linhas)
        por_status: dict[str, int] = {}
        for l in linhas:
            por_status[l.get("status", "")] = por_status.get(l.get("status", ""), 0) + 1
        print(f"{len(linhas)} fontes - " + " - ".join(f"{k}: {v}" for k, v in sorted(por_status.items())))
        for e in erros:
            print(f"[ERRO]  {e}")
        for a in avisos:
            print(f"[AVISO] {a}")
        print("OK" if not erros else f"{len(erros)} erro(s)")
        return 1 if erros else 0

    ids = None
    if "--ids" in args:
        ids = set(args[args.index("--ids") + 1].split(","))
    falhas = 0
    hoje = date.today().isoformat()
    for l in linhas:
        if ids is not None and l["id"] not in ids:
            continue
        if ids is None and l["status"] not in ("ativa", "candidata", "quebrada"):
            continue
        ok, relatorio = testar_url(l["url"], l.get("metodo") or "GET")
        print(f"\n=== {l['id']} {l['nome']} [{l['status']}]\n{relatorio}")
        resumo = relatorio.splitlines()[-1][:150]
        l["ultima_verificacao"] = hoje
        l["resultado_verificacao"] = ("ok: " if ok else "falha: ") + resumo.replace(";", ",")
        if not ok:
            falhas += 1
            if l["status"] == "ativa":
                l["status"] = "quebrada"
        elif l["status"] == "quebrada":
            print("    (voltou a responder: confira o conector antes de reativar)")
    if "--gravar" in args:
        gravar(cabecalho, linhas)
        print(f"\nCatalogo atualizado: {CATALOGO}")
    print(f"\n{falhas} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
