"""Executor de coleta: roda os conectores do Radar para as fontes do catalogo.

Uso (na raiz do repositorio):
    python -m coleta.rodar                    todas as fontes ativas com conector radar:*
    python -m coleta.rodar --ids S20,S21      fontes especificas (qualquer status)
    python -m coleta.rodar --ids S20 --ensaio testa sem gravar nada e mostra exemplos

Grava em dados_processados/: noticias.jsonl, series.jsonl e execucoes.jsonl.
Noticias repetidas (mesmo id) sao ignoradas. Ponto de serie com valor diferente do ja
gravado entra como nova versao (revisao da fonte), sem apagar a anterior.
Codigos de saida: 0 = ok, 1 = alguma fonte falhou, 2 = uso incorreto.
"""

from __future__ import annotations

import csv
import importlib
import io
import json
import sys
import traceback
from dataclasses import asdict

from coleta.base import PROCESSADOS, RAIZ, ColetaBloqueada, Contexto, agora

CATALOGO = RAIZ / "config" / "fontes.csv"
PREFIXO = "radar:"


def ler_catalogo() -> list[dict]:
    bruto = CATALOGO.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    return [{k: (v or "").strip() for k, v in l.items()} for l in csv.DictReader(io.StringIO(texto), delimiter=";")]


def ler_jsonl(nome: str) -> list[dict]:
    caminho = PROCESSADOS / nome
    if not caminho.exists():
        return []
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def anexar_jsonl(nome: str, registros: list[dict]) -> None:
    if not registros:
        return
    PROCESSADOS.mkdir(parents=True, exist_ok=True)
    with (PROCESSADOS / nome).open("a", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def executar(fonte: dict, ensaio: bool) -> dict:
    nome = fonte["conector"][len(PREFIXO):]
    inicio = agora()
    registro = {"fonte_id": fonte["id"], "conector": fonte["conector"], "inicio": inicio, "ensaio": ensaio}
    try:
        modulo = importlib.import_module(f"coleta.conectores.{nome}")
        res = modulo.coletar(fonte, Contexto(fonte["id"], ensaio=ensaio))
    except ColetaBloqueada as exc:
        return {**registro, "ok": False, "erro": f"BLOQUEADO: {exc}"}
    except Exception as exc:
        return {**registro, "ok": False, "erro": f"{type(exc).__name__}: {exc}",
                "detalhe": traceback.format_exc(limit=3)}

    coletado = agora()
    ids_noticias = {n["id"] for n in ler_jsonl("noticias.jsonl")}
    ultimo_valor = {p["id"]: p["valor"] for p in ler_jsonl("series.jsonl")}  # o ultimo gravado vence

    noticias_novas, pontos_novos, revisoes = [], [], 0
    for n in res.noticias:
        if n.id in ids_noticias:
            continue
        ids_noticias.add(n.id)
        noticias_novas.append({"id": n.id, "fonte_id": fonte["id"], **asdict(n), "coletado_em": coletado,
                               "confiabilidade": fonte.get("confiabilidade", "")})
    for p in res.pontos:
        anterior = ultimo_valor.get(p.id)
        if anterior is not None and abs(anterior - p.valor) < 1e-9:
            continue
        revisoes += anterior is not None
        ultimo_valor[p.id] = p.valor
        pontos_novos.append({"id": p.id, "fonte_id": fonte["id"], **asdict(p), "coletado_em": coletado,
                             "revisao_de": anterior})

    if not ensaio:
        anexar_jsonl("noticias.jsonl", noticias_novas)
        anexar_jsonl("series.jsonl", pontos_novos)
    return {**registro, "ok": True, "fim": coletado, "brutos": res.brutos, "avisos": res.avisos,
            "lidos": len(res.noticias) + len(res.pontos), "novos": len(noticias_novas) + len(pontos_novos),
            "revisoes": revisoes, "_exemplos": (noticias_novas or pontos_novos)[:3]}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    ensaio = "--ensaio" in args
    ids = None
    if "--ids" in args:
        try:
            ids = set(args[args.index("--ids") + 1].split(","))
        except IndexError:
            print(__doc__)
            return 2

    fontes = [f for f in ler_catalogo()
              if (f["id"] in ids if ids is not None else f["status"] == "ativa")
              and f["conector"].startswith(PREFIXO)]
    if ids is not None:
        sem_conector = ids - {f["id"] for f in fontes}
        for i in sorted(sem_conector):
            print(f"[AVISO] {i}: nao existe ou nao tem conector {PREFIXO}*")
    if not fontes:
        print("Nenhuma fonte para coletar.")
        return 0

    falhas = 0
    for fonte in fontes:
        r = executar(fonte, ensaio)
        exemplos = r.pop("_exemplos", [])
        if not ensaio:
            anexar_jsonl("execucoes.jsonl", [r])
        if not r["ok"]:
            falhas += 1
            print(f"[FALHA] {fonte['id']} {fonte['nome']}: {r['erro']}")
            continue
        print(f"[OK]    {fonte['id']} {fonte['nome']}: {r['lidos']} lidos, {r['novos']} novos"
              + (f", {r['revisoes']} revisoes" if r["revisoes"] else "") + (" (ensaio)" if ensaio else ""))
        for a in r["avisos"]:
            print(f"        aviso: {a}")
        if ensaio:
            for e in exemplos:
                campos = ("titulo", "publicado_em", "url") if "titulo" in e else ("serie_id", "ocorrido_em", "valor")
                resumo = {k: e[k] for k in campos}
                print(f"        exemplo: {json.dumps(resumo, ensure_ascii=False)}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
