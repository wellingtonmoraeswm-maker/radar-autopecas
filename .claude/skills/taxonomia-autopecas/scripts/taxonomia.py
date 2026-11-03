"""Valida a taxonomia do Radar e testa a classificacao por palavra-chave.

Uso (na raiz do repositorio):
    python taxonomia.py validar
    python taxonomia.py testar "texto da manchete"
    python taxonomia.py validar --pasta config/taxonomia

Codigos de saida: 0 = ok, 1 = erros, 2 = arquivo ausente ou ilegivel.
So usa a biblioteca padrao.
"""

import csv
import io
import re
import sys
import unicodedata
from pathlib import Path

PASTA_PADRAO = Path("config/taxonomia")

TABELAS = {
    "temas": {
        "colunas": ["id", "tema", "tema_pai", "palavras_chave", "excluir", "linha", "ativo", "ancora", "observacao"],
        "obrigatorias": ["id", "tema", "linha", "ativo", "ancora"],
        "prefixo": "T",
    },
    "familias_ncm": {
        "colunas": ["id", "familia", "termos", "linha", "ncm", "descricao_ncm", "verificado", "observacao"],
        "obrigatorias": ["id", "familia", "linha", "ncm", "verificado"],
        "prefixo": "F",
    },
    "entidades": {
        "colunas": ["id", "nome", "sigla", "tipo", "site", "blocos", "verificado", "observacao"],
        "obrigatorias": ["id", "nome", "tipo", "verificado"],
        "prefixo": "E",
    },
    "concorrentes": {
        "colunas": ["id", "nome", "apelidos", "tipo", "regioes", "linhas", "monitorar", "origem", "observacao"],
        "obrigatorias": ["id", "nome", "monitorar", "origem"],
        "prefixo": "C",
    },
}
LINHAS = {"leve", "pesada", "moto", "ambas"}
SIM_NAO = {"sim", "nao"}
TIPOS_ENTIDADE = {"associação", "governo", "pesquisa", "imprensa", "empresa"}
RE_NCM = re.compile(r"^\d{4}(\.?\d{1,2})?(\.?\d{2})?$")


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def lista(valor: str) -> list[str]:
    return [p.strip() for p in valor.split("|") if p.strip()]


def ler_csv(caminho: Path, colunas: list[str]) -> tuple[list[dict], list[str]]:
    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"{caminho.name}: codificacao desconhecida (use UTF-8 ou Windows-1252)")
    leitor = csv.reader(io.StringIO(texto), delimiter=";")
    cabecalho = next(leitor, [])
    faltando = [c for c in colunas if c not in cabecalho]
    if faltando:
        raise ValueError(f"{caminho.name}: colunas ausentes no cabecalho: {', '.join(faltando)}")
    linhas, erros = [], []
    for n, valores in enumerate(leitor, start=2):
        if not any(v.strip() for v in valores):
            continue
        if len(valores) != len(cabecalho):
            erros.append(f"{caminho.name} linha {n}: {len(valores)} colunas, esperado {len(cabecalho)} "
                         "(ponto e virgula dentro de um campo?)")
            continue
        linha = {k: v.strip() for k, v in zip(cabecalho, valores)}
        linha["_n"] = n
        linhas.append(linha)
    return linhas, erros


def carregar(pasta: Path) -> tuple[dict, list[str]]:
    dados, erros = {}, []
    for nome, spec in TABELAS.items():
        caminho = pasta / f"{nome}.csv"
        if not caminho.exists():
            raise FileNotFoundError(caminho)
        linhas, errs = ler_csv(caminho, spec["colunas"])
        dados[nome] = linhas
        erros += errs
    return dados, erros


def validar(dados: dict) -> tuple[list[str], list[str]]:
    erros, avisos = [], []
    for nome, spec in TABELAS.items():
        vistos = set()
        for l in dados[nome]:
            ref = f"{nome}.csv linha {l['_n']} ({l.get('id') or 'sem id'})"
            for campo in spec["obrigatorias"]:
                if not l.get(campo):
                    erros.append(f"{ref}: campo obrigatorio vazio: {campo}")
            ident = l.get("id", "")
            if ident:
                if not re.fullmatch(spec["prefixo"] + r"\d{2,3}", ident):
                    erros.append(f"{ref}: id deve ser {spec['prefixo']} seguido de 2 ou 3 digitos")
                if ident in vistos:
                    erros.append(f"{ref}: id repetido")
                vistos.add(ident)

    ids_temas = {t["id"] for t in dados["temas"]}
    dono_palavra: dict[str, str] = {}
    for t in dados["temas"]:
        ref = f"temas.csv linha {t['_n']} ({t['id']})"
        if t["tema_pai"] and t["tema_pai"] not in ids_temas:
            erros.append(f"{ref}: tema_pai '{t['tema_pai']}' nao existe")
        if t["tema_pai"] == t["id"]:
            erros.append(f"{ref}: tema nao pode ser pai de si mesmo")
        if t["linha"] and t["linha"] not in LINHAS:
            erros.append(f"{ref}: linha invalida '{t['linha']}' (use {', '.join(sorted(LINHAS))})")
        if t["ativo"] and t["ativo"] not in SIM_NAO:
            erros.append(f"{ref}: ativo deve ser sim ou nao")
        if t["ancora"] and t["ancora"] not in SIM_NAO:
            erros.append(f"{ref}: ancora deve ser sim ou nao")
        palavras = lista(t["palavras_chave"])
        if t["ativo"] == "sim" and not palavras:
            erros.append(f"{ref}: tema ativo sem palavras-chave")
        for p in palavras:
            chave = normalizar(p)
            if len(chave) < 3:
                avisos.append(f"{ref}: palavra muito curta '{p}' (vai acionar demais)")
            if chave in dono_palavra and dono_palavra[chave] != t["id"]:
                avisos.append(f"{ref}: palavra '{p}' tambem esta em {dono_palavra[chave]}")
            dono_palavra.setdefault(chave, t["id"])

    dono_termo: dict[str, str] = {}
    for f in dados["familias_ncm"]:
        ref = f"familias_ncm.csv linha {f['_n']} ({f['id']})"
        for termo in lista(f["termos"]):
            chave = normalizar(termo)
            if chave in dono_termo and dono_termo[chave] != f["id"]:
                avisos.append(f"{ref}: termo '{termo}' tambem esta em {dono_termo[chave]}")
            dono_termo.setdefault(chave, f["id"])
        if not f["termos"]:
            avisos.append(f"{ref}: sem termos: a familia nunca sera reconhecida no texto")
        if f["linha"] and f["linha"] not in LINHAS:
            erros.append(f"{ref}: linha invalida '{f['linha']}'")
        for codigo in lista(f["ncm"]):
            if not RE_NCM.match(codigo):
                erros.append(f"{ref}: NCM invalido '{codigo}' (4, 6 ou 8 digitos)")
        if f["verificado"] not in SIM_NAO:
            erros.append(f"{ref}: verificado deve ser sim ou nao")
        elif f["verificado"] == "sim" and not f["observacao"]:
            avisos.append(f"{ref}: verificado=sim sem registro de onde e quando foi conferido")

    for e in dados["entidades"]:
        ref = f"entidades.csv linha {e['_n']} ({e['id']})"
        if e["tipo"] and e["tipo"] not in TIPOS_ENTIDADE:
            erros.append(f"{ref}: tipo invalido '{e['tipo']}' (use {', '.join(sorted(TIPOS_ENTIDADE))})")
        if e["verificado"] not in SIM_NAO:
            erros.append(f"{ref}: verificado deve ser sim ou nao")
        if e["site"] and not e["site"].startswith("https://"):
            avisos.append(f"{ref}: site sem https://")

    for c in dados["concorrentes"]:
        ref = f"concorrentes.csv linha {c['_n']} ({c['id']})"
        if c["monitorar"] and c["monitorar"] not in SIM_NAO:
            erros.append(f"{ref}: monitorar deve ser sim ou nao")
    if not dados["concorrentes"]:
        avisos.append("concorrentes.csv vazio: preencher a partir da descoberta")
    return erros, avisos


def contem(texto_norm: str, termo: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(normalizar(termo)) + r"(?!\w)", texto_norm) is not None


def testar(dados: dict, texto: str) -> list[str]:
    alvo = normalizar(texto)
    saida = []
    temas = {t["id"]: t for t in dados["temas"]}
    for t in dados["temas"]:
        if t["ativo"] != "sim":
            continue
        bloqueio = next((x for x in lista(t["excluir"]) if contem(alvo, x)), None)
        acerto = next((p for p in lista(t["palavras_chave"]) if contem(alvo, p)), None)
        if acerto and not bloqueio:
            pai = temas.get(t["tema_pai"], {}).get("tema", "")
            saida.append(f"TEMA      {t['id']} {t['tema']}" + (f" (em {pai})" if pai else "") + f"  <- '{acerto}'")
        elif acerto and bloqueio:
            saida.append(f"bloqueado {t['id']} {t['tema']}  <- '{acerto}', mas exclui '{bloqueio}'")
    for f in dados["familias_ncm"]:
        acerto = next((x for x in lista(f["termos"]) if contem(alvo, x)), None)
        if acerto:
            saida.append(f"FAMILIA   {f['id']} {f['familia']} [NCM {f['ncm']}]  <- '{acerto}'")
    for e in dados["entidades"]:
        acerto = next((x for x in (e["sigla"], e["nome"]) if x and contem(alvo, x)), None)
        if acerto:
            saida.append(f"ENTIDADE  {e['id']} {e['sigla'] or e['nome']}  <- '{acerto}'")
    for c in dados["concorrentes"]:
        acerto = next((x for x in [c["nome"]] + lista(c["apelidos"]) if contem(alvo, x)), None)
        if acerto:
            marca = "" if c["monitorar"] == "sim" else " (monitorar=nao)"
            saida.append(f"CONCORR.  {c['id']} {c['nome']}{marca}  <- '{acerto}'")
    return saida


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    pasta = PASTA_PADRAO
    if "--pasta" in args:
        i = args.index("--pasta")
        pasta = Path(args[i + 1])
        del args[i:i + 2]
    if not args or args[0] not in ("validar", "testar") or (args[0] == "testar" and len(args) < 2):
        print(__doc__)
        return 2
    try:
        dados, erros_leitura = carregar(pasta)
    except FileNotFoundError as exc:
        print(f"[ERRO] arquivo nao encontrado: {exc}")
        return 2
    except ValueError as exc:
        print(f"[ERRO] {exc}")
        return 2

    if args[0] == "testar":
        resultado = testar(dados, " ".join(args[1:]))
        print("\n".join(resultado) if resultado else "Nenhum tema, familia, entidade ou concorrente acionado.")
        return 0

    erros, avisos = validar(dados)
    erros = erros_leitura + erros
    print(" - ".join(f"{n}: {len(dados[n])}" for n in TABELAS))
    for e in erros:
        print(f"[ERRO]  {e}")
    for a in avisos:
        print(f"[AVISO] {a}")
    print("OK" if not erros else f"{len(erros)} erro(s)")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
