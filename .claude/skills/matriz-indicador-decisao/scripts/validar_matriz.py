"""Valida a matriz indicador -> decisao, calcula nota e etapa e gera matriz_decisao.md.

Uso:
    python validar_matriz.py descoberta/<cliente>/matriz_decisao.csv

Codigos de saida: 0 = ok, 1 = erros na matriz, 2 = arquivo nao encontrado ou ilegivel.
So usa a biblioteca padrao.
"""

import csv
import io
import sys
from pathlib import Path

COLUNAS = [
    "id", "decisao", "quem_decide", "area", "frequencia_decisao", "pergunta",
    "indicador", "bloco", "fonte", "periodicidade_fonte", "gatilho_alerta",
    "impacto", "frequencia", "viabilidade", "origem", "status", "etapa_override",
]
OBRIGATORIAS = ["id", "decisao", "quem_decide", "pergunta", "indicador", "fonte", "origem", "status"]
NOTAS = ["impacto", "frequencia", "viabilidade"]
STATUS_VALIDOS = {"candidata", "aprovada", "descartada"}
NOTA_MVP = 36
MIN_APROVADAS = 8
TERMOS_INTERNOS = ("erp", "estoque", "venda interna", "vendas internas", "margem", "pedido nao atendido",
                   "pedidos nao atendidos", "pedido não atendido", "pedidos não atendidos")


def ler_csv(caminho: Path) -> list[dict]:
    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("codificacao desconhecida (use UTF-8 ou Windows-1252)")
    primeira = texto.splitlines()[0] if texto else ""
    separador = ";" if primeira.count(";") >= primeira.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=separador)
    faltando = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
    if faltando:
        raise ValueError(f"colunas ausentes no cabecalho: {', '.join(faltando)}")
    return [{k: (v or "").strip() for k, v in linha.items() if k} for linha in leitor
            if any((v or "").strip() for v in linha.values())]


def etapa_sugerida(linha: dict, nota: int) -> str:
    viab = int(linha["viabilidade"])
    if viab >= 3:
        return "MVP" if nota >= NOTA_MVP else "Etapa 4"
    if viab == 2:
        return "Etapa 4"
    texto = f"{linha['indicador']} {linha['fonte']}".lower()
    return "Fora do escopo (ERP)" if any(t in texto for t in TERMOS_INTERNOS) else "Fora do escopo (pago)"


def validar(linhas: list[dict]) -> tuple[list[str], list[str]]:
    erros, avisos = [], []
    vistos = set()
    for n, linha in enumerate(linhas, start=2):
        ref = f"linha {n} ({linha.get('id') or 'sem id'})"
        for campo in OBRIGATORIAS:
            if not linha.get(campo):
                erros.append(f"{ref}: campo obrigatorio vazio: {campo}")
        if linha.get("id"):
            if linha["id"] in vistos:
                erros.append(f"{ref}: id repetido")
            vistos.add(linha["id"])
        if linha.get("status") and linha["status"] not in STATUS_VALIDOS:
            erros.append(f"{ref}: status invalido '{linha['status']}' (use {', '.join(sorted(STATUS_VALIDOS))})")
        for campo in NOTAS:
            valor = linha.get(campo, "")
            if not valor or valor.upper().startswith("[A DEFINIR"):
                if linha.get("status") == "aprovada":
                    erros.append(f"{ref}: {campo} precisa de nota para uma decisao aprovada")
                else:
                    avisos.append(f"{ref}: {campo} ainda sem nota")
                continue
            if not valor.isdigit() or not 1 <= int(valor) <= 5:
                erros.append(f"{ref}: {campo} deve ser inteiro de 1 a 5 (veio '{valor}')")
        origem = linha.get("origem", "").upper()
        if origem.startswith("SUGEST") and linha.get("status") == "aprovada":
            erros.append(f"{ref}: decisao com origem SUGESTAO nao pode estar aprovada sem confirmacao do cliente")
        if not linha.get("gatilho_alerta"):
            avisos.append(f"{ref}: sem gatilho de alerta")
        if "[SUGEST" in (linha.get("indicador", "") + linha.get("fonte", "")).upper() and linha.get("status") == "aprovada":
            avisos.append(f"{ref}: indicador ou fonte ainda marcado como [SUGESTAO] numa decisao aprovada")
    return erros, avisos


def tem_notas(linha: dict) -> bool:
    return all(linha.get(c, "").isdigit() and 1 <= int(linha[c]) <= 5 for c in NOTAS)


def gerar_md(linhas: list[dict], destino: Path, erros: list[str], avisos: list[str]) -> None:
    pontuadas, pendentes = [], []
    for linha in linhas:
        if linha["status"] == "descartada":
            continue
        if tem_notas(linha):
            nota = int(linha["impacto"]) * int(linha["frequencia"]) * int(linha["viabilidade"])
            etapa = linha["etapa_override"] or etapa_sugerida(linha, nota)
            pontuadas.append((nota, etapa, linha))
        else:
            pendentes.append(linha)
    pontuadas.sort(key=lambda t: (-t[0], t[2]["id"]))

    aprovadas = sum(1 for l in linhas if l["status"] == "aprovada")
    descartadas = sum(1 for l in linhas if l["status"] == "descartada")
    por_etapa: dict[str, int] = {}
    for _, etapa, _l in pontuadas:
        por_etapa[etapa] = por_etapa.get(etapa, 0) + 1

    def celula(texto: str) -> str:
        return texto.replace("|", "/").replace("\n", " ")

    out = ["# Matriz indicador → decisão", "",
           "> Gerado por `validar_matriz.py`. **Não editar à mão**: edite o CSV e rode o script de novo.", "",
           f"**Decisões:** {len(linhas)} no total · {aprovadas} aprovadas · "
           f"{len(linhas) - aprovadas - descartadas} candidatas · {descartadas} descartadas", "",
           "**Por etapa sugerida:** " + (" · ".join(f"{e}: {q}" for e, q in sorted(por_etapa.items())) or "nenhuma"), "",
           f"**Encerramento da Etapa 1:** {'✅' if aprovadas >= MIN_APROVADAS else '⏳'} "
           f"{aprovadas} de {MIN_APROVADAS} decisões aprovadas no mínimo", "",
           "## Priorizadas", "",
           "| Nota | Etapa | ID | Decisão | Quem | Indicador | Fonte | Gatilho | Status |",
           "|---|---|---|---|---|---|---|---|---|"]
    for nota, etapa, l in pontuadas:
        out.append(f"| {nota} | {etapa} | {l['id']} | {celula(l['decisao'])} | {celula(l['quem_decide'])} | "
                   f"{celula(l['indicador'])} | {celula(l['fonte'])} | {celula(l['gatilho_alerta']) or '—'} | {l['status']} |")
    if pendentes:
        out += ["", "## Sem nota completa", "", "| ID | Decisão | Falta |", "|---|---|---|"]
        for l in pendentes:
            falta = ", ".join(c for c in NOTAS if not (l.get(c, "").isdigit() and 1 <= int(l[c]) <= 5))
            out.append(f"| {l['id']} | {celula(l['decisao'])} | {falta} |")
    fontes = sorted({l["fonte"] for _, _, l in pontuadas if l["status"] == "aprovada" and l["fonte"]})
    if fontes:
        out += ["", "## Fontes a validar na Etapa 2 (decisões aprovadas)", ""] + [f"- {f}" for f in fontes]
    if erros or avisos:
        out += ["", "## Problemas", ""] + [f"- ❌ {e}" for e in erros] + [f"- ⚠️ {a}" for a in avisos]
    destino.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    caminho = Path(sys.argv[1])
    if not caminho.exists():
        print(f"[ERRO] arquivo nao encontrado: {caminho}")
        return 2
    try:
        linhas = ler_csv(caminho)
    except ValueError as exc:
        print(f"[ERRO] {exc}")
        return 2

    erros, avisos = validar(linhas)
    destino = caminho.with_suffix(".md")
    gerar_md(linhas, destino, erros, avisos)

    aprovadas = sum(1 for l in linhas if l["status"] == "aprovada")
    print(f"{len(linhas)} decisoes lidas - {aprovadas} aprovadas (minimo {MIN_APROVADAS})")
    for e in erros:
        print(f"[ERRO]  {e}")
    for a in avisos:
        print(f"[AVISO] {a}")
    print(f"Gerado: {destino}")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
