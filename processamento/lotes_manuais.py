"""Avaliacao por lotes fora da API (ex.: pela propria sessao do Claude Code), com a MESMA validacao da IA.

Uso (na raiz do repositorio):
    python -m processamento.lotes_manuais exportar [--tamanho 100] [--corte 40]
        -> lotes/lote_NN.txt com as noticias pendentes que passam do corte de alguma visao
    python -m processamento.lotes_manuais importar --avaliador "claude-code (sessao)"
        -> le lotes/resp_NN.json, valida cada resposta com ia.validar() e grava em classificacoes_ia.jsonl

Formato de resp_NN.json: lista de objetos com as chaves do esquema da IA mais o id:
    {"id": "N...", "e_do_setor": true, "temas": ["T01"], "relevancia": 40, "tipo": "fato", "justificativa": "..."}
Resposta que nao passa no esquema (tema fora da taxonomia, tipo invalido, campo faltando) e recusada.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone

from processamento import ia
from processamento.briefing import nota_final
from processamento.classificar import CONFIG, PROCESSADOS, RAIZ, Classificador, ler_csv, ler_jsonl, ultimas_classificacoes

PASTA = RAIZ / "lotes"


def versao_prompt(cl: Classificador) -> str:
    return hashlib.sha1((ia.montar_sistema(cl) + json.dumps(ia.esquema(cl), sort_keys=True)).encode()).hexdigest()[:10]


def pendentes(corte: int) -> tuple[list[str], dict, dict, str]:
    cl = Classificador()
    versao = versao_prompt(cl)
    noticias = {n["id"]: n for n in ler_jsonl("noticias.jsonl")}
    regras = ultimas_classificacoes()
    feitas = {c["noticia_id"] for c in ler_jsonl("classificacoes_ia.jsonl") if c.get("versao_prompt") == versao and c.get("status") == "ok"}
    visoes = ler_csv(CONFIG / "visoes.csv")
    lista = [i for i in ia.candidatas(noticias, regras) if i not in feitas and regras[i]["setorial"]
             and max(nota_final(regras[i], None, v)[0] for v in visoes) >= corte]
    lista.sort(key=lambda i: noticias[i].get("publicado_em") or "", reverse=True)
    return lista, noticias, regras, versao


def exportar(tamanho: int, corte: int) -> None:
    lista, noticias, regras, _ = pendentes(corte)
    PASTA.mkdir(exist_ok=True)
    for k in range(0, len(lista), tamanho):
        linhas = []
        for i in lista[k:k + tamanho]:
            n = noticias[i]
            trecho = (n.get("trecho_interno") or "")[:200]
            linhas.append(f"{i} | {n['fonte_id']} | {(n.get('publicado_em') or '')[:10]} | {n['titulo']} | {trecho} "
                          f"| regras: {','.join(regras[i]['temas']) or '-'}")
        (PASTA / f"lote_{k // tamanho + 1:02d}.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"{len(lista)} noticia(s) em {-(-len(lista) // tamanho)} lote(s) em {PASTA}")


def importar(avaliador: str) -> int:
    cl = Classificador()
    ids_temas = {t["id"] for t in cl.temas}
    tipos = set(ia.TIPOS)
    _, noticias, regras, versao = pendentes(0)
    gravados, recusados = [], []
    for arq in sorted(PASTA.glob("resp_*.json")):
        for r in json.loads(arq.read_text(encoding="utf-8")):
            i = r.get("id")
            ok = (i in noticias and i in regras and isinstance(r.get("e_do_setor"), bool)
                  and isinstance(r.get("relevancia"), int) and r.get("tipo") in tipos
                  and isinstance(r.get("temas"), list) and all(t in ids_temas for t in r["temas"])
                  and isinstance(r.get("justificativa"), str) and r["justificativa"].strip())
            if not ok:
                recusados.append(f"{arq.name}: {i}")
                continue
            resposta = {k: r[k] for k in ("e_do_setor", "temas", "relevancia", "tipo", "justificativa")}
            gravados.append({"noticia_id": i, "versao_prompt": versao, "versao_regras": regras[i]["versao_regras"],
                             "classificado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                             "provedor": avaliador, "modelo": avaliador, "status": "ok",
                             "resultado": ia.validar(resposta, noticias[i], regras[i], ids_temas)})
    with (PROCESSADOS / "classificacoes_ia.jsonl").open("a", encoding="utf-8") as f:
        for g in gravados:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    nao_usar = sum(1 for g in gravados if not g["resultado"]["usar"])
    print(f"{len(gravados)} gravada(s), {nao_usar} marcada(s) NAO USAR pela validacao, {len(recusados)} recusada(s)")
    for x in recusados[:20]:
        print("  recusada:", x)
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if args[:1] == ["exportar"]:
        tamanho = int(args[args.index("--tamanho") + 1]) if "--tamanho" in args else 100
        corte = int(args[args.index("--corte") + 1]) if "--corte" in args else 40
        exportar(tamanho, corte)
        return 0
    if args[:1] == ["importar"]:
        return importar(args[args.index("--avaliador") + 1] if "--avaliador" in args else "manual")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
