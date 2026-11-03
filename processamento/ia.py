"""Camada de IA: refina a classificacao por regras das noticias com o provedor de IA ativo.

Uso (na raiz do repositorio, com o ambiente do projeto: .venv/Scripts/python no Windows):
    python -m processamento.ia                 refina as noticias pendentes
    python -m processamento.ia --limite 5      no maximo 5 chamadas
    python -m processamento.ia --ensaio        chama a API e mostra, sem gravar
    python -m processamento.ia --paralelo 6    6 chamadas ao mesmo tempo (para lotes grandes, ex.: historico)
    python -m processamento.ia --mostrar       lista o resultado gravado

O que a IA faz e o que NAO faz:
- Recebe a noticia, a classificacao por regras e a taxonomia. Devolve JSON validado por esquema:
  se e do setor, temas (SO ids da taxonomia: o esquema usa enum), nota, tipo e justificativa.
- NAO calcula indicadores. A nota por regras continua gravada ao lado.
- Toda justificativa passa por uma checagem: numero que nao aparece no titulo ou no trecho da
  noticia marca a resposta como "numero_sem_origem" e ela nao e usada.
- Divergencia com as regras (setor sim x nao) fica marcada para revisao.

Provedor, chave e modelo: cadastrados com `python -m processamento.credenciais` (Anthropic ou Gemini).
Em producao, variaveis de ambiente do cofre da nuvem tem prioridade (ver processamento/credenciais.py).
Grava dados_processados/classificacoes_ia.jsonl (anexa; a ultima linha de cada noticia vale).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from processamento import provedores
from processamento.classificar import PROCESSADOS, Classificador, ler_jsonl, ultimas_classificacoes
TIPOS = ["fato", "evento", "lancamento_produto", "opiniao_analise", "publicidade", "outro"]
NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


# --------------------------------------------------------------------------- prompt e esquema

def montar_sistema(cl: Classificador) -> str:
    """Prompt de sistema estavel (vai para o cache). So muda quando a taxonomia muda."""
    temas = "\n".join(
        f"- {t['id']} {t['tema']}" + (" [define o setor]" if t["ancora"] == "sim" else " [contexto]")
        + f": {', '.join(t['palavras_chave'].split('|')[:8])}"
        for t in cl.temas)
    visoes = "\n".join(f"- {v['id']} {v['nome']} ({v['usuario']}): temas prioritarios {v['temas_prioritarios']}"
                       for v in cl.visoes)
    return f"""Voce classifica noticias para o Radar Autopecas, painel de inteligencia de mercado usado pela \
presidencia e pela diretoria comercial de uma distribuidora de autopecas de porte nacional no Brasil.

Para cada noticia, decida:
1. e_do_setor: a noticia afeta o mercado de reposicao de autopecas (fabricantes, distribuidores, varejo de pecas, \
oficinas, frota, veiculos que geram demanda de pecas)? Varejo em geral, e-commerce em geral, apostas e temas sem \
ligacao com veiculos ou pecas NAO sao do setor, mesmo vindo de portal de varejo.
2. temas: escolha so entre os ids abaixo. Pode ser lista vazia. Nao force tema.
3. relevancia (0 a 100) para a diretoria: 80+ muda decisao (concorrente, tributacao, preco, abastecimento); \
50-79 vale acompanhar; 20-49 informativo; abaixo de 20 ruido. Publicidade e evento promocional ficam abaixo de 30.
4. tipo: {', '.join(TIPOS)}.
5. justificativa: uma frase em portugues do Brasil, com acentuacao correta, dizendo por que importa (ou nao) para uma distribuidora. \
Nao cite numeros que nao estejam no titulo ou no trecho, nem os ids dos temas (T01, T02...). Nao invente fatos. Se o trecho for insuficiente, diga isso.

Temas da taxonomia:
{temas}

Visoes do painel:
{visoes}

A classificacao por regras (palavras-chave) vem junto como referencia. Voce pode discordar dela; \
quando discordar sobre e_do_setor, explique na justificativa."""


def esquema(cl: Classificador) -> dict:
    ids = [t["id"] for t in cl.temas]
    return {
        "type": "object",
        "properties": {
            "e_do_setor": {"type": "boolean"},
            "temas": {"type": "array", "items": {"type": "string", "enum": ids}},
            "relevancia": {"type": "integer"},
            "tipo": {"type": "string", "enum": TIPOS},
            "justificativa": {"type": "string"},
        },
        "required": ["e_do_setor", "temas", "relevancia", "tipo", "justificativa"],
        "additionalProperties": False,
    }


def montar_mensagem(noticia: dict, regras: dict) -> str:
    return json.dumps({
        "titulo": noticia.get("titulo", ""),
        "trecho": noticia.get("trecho_interno", ""),
        "fonte": noticia.get("fonte_id", ""),
        "publicado_em": noticia.get("publicado_em"),
        "regras": {"do_setor": regras.get("setorial"), "temas": regras.get("temas"),
                   "familias": regras.get("familias"), "relevancia": regras.get("relevancia")},
    }, ensure_ascii=False)


# --------------------------------------------------------------------------- validacao (deterministica)

def numeros_sem_origem(texto: str, fonte: str) -> list[str]:
    na_fonte = {n.replace(",", ".") for n in NUMERO.findall(fonte)}
    return [n for n in NUMERO.findall(texto) if n.replace(",", ".") not in na_fonte]


def validar(resposta: dict, noticia: dict, regras: dict, ids_temas: set[str]) -> dict:
    alertas = []
    temas = [t for t in resposta["temas"] if t in ids_temas]  # o enum garante; isto e a rede de seguranca
    if len(temas) != len(resposta["temas"]):
        alertas.append("tema_fora_da_taxonomia")
    nota = resposta["relevancia"]
    if not 0 <= nota <= 100:
        alertas.append("nota_fora_da_escala")
        nota = max(0, min(100, nota))
    if not resposta["e_do_setor"]:
        nota = min(nota, 10)
    sobra = numeros_sem_origem(resposta["justificativa"],
                               f"{noticia.get('titulo', '')} {noticia.get('trecho_interno', '')}")
    if sobra:
        alertas.append("numero_sem_origem: " + ", ".join(sobra))
    divergencia = bool(regras) and resposta["e_do_setor"] != regras.get("setorial")
    return {"e_do_setor": resposta["e_do_setor"], "temas": temas, "relevancia": nota, "tipo": resposta["tipo"],
            "justificativa": resposta["justificativa"], "alertas": alertas, "divergencia_regras": divergencia,
            "usar": not any(a.startswith(("numero_sem_origem", "tema_fora")) for a in alertas)}


# --------------------------------------------------------------------------- chamada

def candidatas(noticias: dict[str, dict], regras: dict[str, dict]) -> list[str]:
    """Vai para a IA: o que as regras aceitaram e o caso duvidoso (fonte geral com algum tema)."""
    return [i for i, c in regras.items() if i in noticias and (c["setorial"] or c["temas"])]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    noticias = {n["id"]: n for n in ler_jsonl("noticias.jsonl")}
    regras = ultimas_classificacoes()
    feitas = {c["noticia_id"]: c for c in ler_jsonl("classificacoes_ia.jsonl")}

    if "--mostrar" in args:
        for c in sorted(feitas.values(), key=lambda c: -(c.get("resultado") or {}).get("relevancia", -1)):
            n, res = noticias.get(c["noticia_id"], {}), c.get("resultado")
            if not res:
                print(f"  ! [{c['status']}] {n.get('titulo', '?')[:90]}")
                continue
            marca = "" if res["usar"] else " (NAO USAR)"
            print(f"{res['relevancia']:>3} {'setor' if res['e_do_setor'] else 'fora '} {n.get('titulo', '?')[:80]}{marca}")
            print(f"      {res['justificativa']}" + (" | DIVERGE DAS REGRAS" if res["divergencia_regras"] else ""))
        return 0

    cl = Classificador()
    sistema, formato = montar_sistema(cl), esquema(cl)
    versao_prompt = hashlib.sha1((sistema + json.dumps(formato, sort_keys=True)).encode()).hexdigest()[:10]
    pendentes = [i for i in candidatas(noticias, regras)
                 if feitas.get(i, {}).get("versao_prompt") != versao_prompt or feitas[i].get("status") != "ok"]
    if "--limite" in args:
        pendentes = pendentes[:int(args[args.index("--limite") + 1])]
    print(f"prompt {versao_prompt}: {len(pendentes)} noticia(s) para a IA")
    if not pendentes:
        return 0

    provedor = provedores.obter()
    paralelo = max(1, int(args[args.index("--paralelo") + 1])) if "--paralelo" in args else 1
    print(f"provedor {provedor.nome}, modelo {provedor.modelo}, {paralelo} chamada(s) por vez")
    # mais recentes primeiro: se parar no meio (credito, limite), o que importa agora ja foi avaliado
    pendentes.sort(key=lambda i: noticias[i].get("publicado_em") or noticias[i].get("coletado_em") or "", reverse=True)

    ids_temas = {t["id"] for t in cl.temas}
    ensaio = "--ensaio" in args
    trava = threading.Lock()
    parar = threading.Event()
    gravados, motivo = [], {}
    arquivo = PROCESSADOS / "classificacoes_ia.jsonl"
    PROCESSADOS.mkdir(parents=True, exist_ok=True)

    def avaliar(i: str) -> None:
        if parar.is_set():
            return
        n, reg = noticias[i], regras[i]
        resposta, meta = provedor.classificar(sistema, formato, montar_mensagem(n, reg))
        resultado = validar(resposta, n, reg, ids_temas) if resposta else None
        registro = {"noticia_id": i, "versao_prompt": versao_prompt, "versao_regras": reg["versao_regras"],
                    "classificado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                    **meta, "resultado": resultado}
        interrompe = meta["status"] in provedores.STATUS_QUE_INTERROMPEM or meta["status"].startswith("erro_api_4")
        with trava:
            if interrompe:
                motivo.setdefault("status", meta["status"])
                motivo.setdefault("detalhe", meta.get("detalhe", ""))
                parar.set()
                return
            gravados.append(registro)
            if not ensaio:  # grava na hora: uma interrupcao nao perde o que ja foi avaliado
                with arquivo.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            if paralelo == 1 and resultado:
                print(f"{resultado['relevancia']:>3} (regras {reg['relevancia']:>3}) {n['titulo'][:80]}")
                print(f"      {resultado['justificativa']}" + (f" | alertas: {resultado['alertas']}" if resultado["alertas"] else ""))
            elif paralelo == 1:
                print(f"  ! {meta['status']}: {n['titulo'][:80]}")
            elif len(gravados) % 100 == 0:
                print(f"{len(gravados)}/{len(pendentes)} avaliadas", flush=True)

    with ThreadPoolExecutor(max_workers=paralelo) as executor:
        list(executor.map(avaliar, pendentes))

    if motivo:
        dica = {"sem_credencial": "cadastre a chave: python -m processamento.credenciais cadastrar <provedor>",
                "sem_credito": "a conta do provedor esta sem creditos",
                "limite_de_requisicoes": "limite de requisicoes; tente mais tarde ou use menos --paralelo",
                "sem_conexao": "sem conexao"}.get(motivo["status"], motivo["detalhe"][:200])
        print(f"Interrompido ({provedor.nome}, {provedor.modelo}): {dica}")
    uso = [g.get("uso", {}) for g in gravados]
    print(f"\n{len(gravados)} avaliada(s). tokens: entrada {sum(u.get('entrada', 0) for u in uso)}, "
          f"saida {sum(u.get('saida', 0) for u in uso)}, cache lido {sum(u.get('cache_lido', 0) for u in uso)}"
          + (" (ensaio, nada gravado)" if ensaio else ""))
    if motivo.get("status") in ("sem_credencial", "sem_credito"):
        return 2
    return 0 if not motivo and all(g["status"] == "ok" for g in gravados) else 1

if __name__ == "__main__":
    sys.exit(main())
