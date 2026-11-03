"""Resumo executivo do Radar (Flash e Executivo), auditado antes de sair.

Uso (na raiz do repositorio):
    python -m processamento.briefing                                  Flash da Presidencia, ultimos 7 dias
    python -m processamento.briefing --visao V02 --versao executivo
    python -m processamento.briefing --periodo dia|semana|mes
    python -m processamento.briefing --de 2026-10-01 --ate 2026-10-31
    python -m processamento.briefing --selecao                        so mostra o que seria enviado a IA

Etapas:
1. Indicadores: calculados em codigo (processamento/indicadores.py).
2. Noticias: do periodo (pela data de publicacao; sem ela, pela data de coleta, com aviso), do setor,
   ordenadas pela nota da IA (ou das regras, se a IA nao avaliou) + bonus da visao. Corte minimo da visao.
3. A IA redige os itens na estrutura fixa. Ela so pode citar os fatos enviados: as referencias sao uma
   lista fechada (enum) e os links sao colocados pelo codigo, nunca pela IA.
4. O auditor confere numeros e referencias. Reprovado: uma nova tentativa com os problemas apontados;
   reprovado de novo: o resumo sai marcado como BLOQUEADO e o comando termina com erro.
Saidas: saidas/briefings/<data>_<visao>_<versao>.md (leitura) e .json (rastreabilidade completa).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone

from processamento import auditor, indicadores, provedores
from processamento.classificar import CONFIG, PESOS, RAIZ, ler_csv, ler_jsonl, lista, ultimas_classificacoes

SAIDAS = RAIZ / "saidas" / "briefings"
VERSOES = {"flash": {"itens": 3, "palavras": 150, "leitura": "1 minuto", "max_tokens": 8000},
           "executivo": {"itens": 6, "palavras": 450, "leitura": "3 minutos", "max_tokens": 12000}}
PERIODOS = {"dia": 1, "semana": 7, "mes": 30, "semestre": 182}
FONTES_INDICADOR = {"E12": "Banco Central do Brasil (SGS)", "E09": "ANIP (infográfico mensal)",
                    "E13": "IBGE", "E14": "ANP", "E11": "Comex Stat", "E15": "ABCR", "E01": "Sindipeças"}
ROTULOS = {"risco": "🔴 Risco", "oportunidade": "🟢 Oportunidade", "atencao": "🟡 Atenção", "neutro": "⚪ Informativo"}


# --------------------------------------------------------------------------- selecao (deterministica)

def data_da_noticia(n: dict) -> tuple[date | None, bool]:
    """(data, estimada). Sem data de publicacao, usa a de coleta e avisa (regra das tres datas)."""
    for campo, estimada in (("publicado_em", False), ("coletado_em", True)):
        if n.get(campo):
            return datetime.fromisoformat(n[campo]).date(), estimada
    return None, True


def nota_final(regras: dict, ia: dict | None, visao: dict) -> tuple[int, list[str], str]:
    """Nota usada no resumo: a da IA quando aprovada, senao a das regras; mais o bonus da visao."""
    res = (ia or {}).get("resultado")
    if res and res.get("usar"):
        base, temas, origem = res["relevancia"], res["temas"], "ia"
    else:
        base, temas, origem = regras["relevancia"], regras["temas"], "regras"
    prioritarios = set(lista(visao["temas_prioritarios"])) | set(lista(visao["familias_prioritarias"]))
    alvo = set(temas) | set(regras.get("familias", []))
    bonus = PESOS["bonus_visao"] if prioritarios & alvo else 0
    return min(100, base + bonus), temas, origem


def selecionar(inicio: date, fim: date, visao: dict, limite: int) -> tuple[list[dict], dict]:
    noticias = {n["id"]: n for n in ler_jsonl("noticias.jsonl")}
    regras = ultimas_classificacoes()
    ias = {c["noticia_id"]: c for c in ler_jsonl("classificacoes_ia.jsonl")}
    corte = int(visao["relevancia_minima"] or 0)
    candidatas, contagem = [], {"no_periodo": 0, "do_setor": 0, "acima_do_corte": 0}
    for i, n in noticias.items():
        dia, estimada = data_da_noticia(n)
        if dia is None or not inicio <= dia <= fim or i not in regras:
            continue
        contagem["no_periodo"] += 1
        ia = ias.get(i)
        do_setor = ia["resultado"]["e_do_setor"] if ia and ia.get("resultado") else regras[i]["setorial"]
        if not do_setor:
            continue
        contagem["do_setor"] += 1
        nota, temas, origem = nota_final(regras[i], ia, visao)
        if nota < corte:
            continue
        contagem["acima_do_corte"] += 1
        candidatas.append({"noticia": n, "nota": nota, "origem_nota": origem, "temas": temas, "data": dia,
                           "data_estimada": estimada, "ia": (ia or {}).get("resultado")})
    candidatas.sort(key=lambda c: (-c["nota"], c["data"]), reverse=False)
    return candidatas[:limite], contagem


# --------------------------------------------------------------------------- fatos e prompt

def montar_fatos(selecionadas: list[dict], inds: list[dict], fontes: dict, nomes_temas: dict) -> dict[str, dict]:
    fatos = {}
    for ind in inds:
        fatos[ind["id"]] = {"tipo": "indicador", "frase": ind["frase"], "contexto": ind["observacao"],
                            "referencia_fmt": ind["referencia_fmt"],
                            "fonte": FONTES_INDICADOR.get(fontes.get(ind["fonte_id"], {}).get("entidade", ""),
                                                          fontes.get(ind["fonte_id"], {}).get("nome", ind["fonte_id"])),
                            "fonte_id": ind["fonte_id"]}
    for s in selecionadas:
        n = s["noticia"]
        fatos[n["id"]] = {"tipo": "noticia", "titulo": n["titulo"], "trecho": n.get("trecho_interno", ""),
                          "data": s["data"].strftime("%d/%m/%Y") + (" (data de coleta)" if s["data_estimada"] else ""),
                          "fonte": fontes.get(n["fonte_id"], {}).get("nome", n["fonte_id"]), "url": n["url"],
                          "temas": [nomes_temas.get(t, t) for t in s["temas"]],
                          "leitura_previa": (s["ia"] or {}).get("justificativa", ""), "nota": s["nota"]}
    return fatos


def montar_sistema() -> str:
    return """Voce redige o resumo executivo do Radar Autopecas para a diretoria de uma distribuidora de \
autopecas de porte nacional no Brasil. O leitor tem pouco tempo e decide compras, precos, mix e expansao.

Regras inegociaveis:
- Use SOMENTE os fatos recebidos. Cada item cita em "refs" os ids dos fatos que o sustentam.
- Numeros: copie exatamente como aparecem no fato citado no proprio item (frase do indicador, titulo ou \
trecho da noticia). Nunca calcule, arredonde, some ou estime numeros. Na duvida, escreva sem numero.
- Variacoes ja vem com sinal (+ ou -). Copie o numero com o sinal e sem palavra de direcao redundante: escreva "-0,2% sobre ago/2026", nunca "queda de -0,2%".
- Nao invente causas. Relacao entre fatos e interpretacao: escreva "pode", "sinaliza", "vale verificar".
- Nao repita a mesma informacao em dois itens. Prefira o que muda decisao a o que e so curioso.
- Portugues do Brasil com acentuacao e cedilha corretas (ex.: \"crédito\", \"pressão\", \"reposição\"), direto, sem jargao, frases curtas. Sem emojis.

Estrutura de cada item:
- o_que_aconteceu: o fato, em uma frase.
- o_que_mudou: comparacao com o periodo anterior quando o fato traz isso; senao, o que ha de novo.
- por_que_importa: consequencia possivel para uma distribuidora de autopecas.
- classificacao: risco, oportunidade, atencao ou neutro.
- o_que_acompanhar: o proximo sinal a observar.
manchete: uma frase que resume o periodo para a visao pedida.
nota_sobre_os_dados: limitacoes que o leitor precisa saber (poucas fontes, dados mensais defasados, etc.)."""


def esquema(ids: list[str], max_itens: int) -> dict:
    item = {"type": "object", "properties": {
        "refs": {"type": "array", "items": {"type": "string", "enum": ids}},
        "o_que_aconteceu": {"type": "string"}, "o_que_mudou": {"type": "string"},
        "por_que_importa": {"type": "string"},
        "classificacao": {"type": "string", "enum": list(auditor.CLASSIFICACOES)},
        "o_que_acompanhar": {"type": "string"}},
        "required": ["refs", "o_que_aconteceu", "o_que_mudou", "por_que_importa", "classificacao", "o_que_acompanhar"],
        "additionalProperties": False}
    return {"type": "object", "properties": {
        "manchete": {"type": "string"}, "itens": {"type": "array", "items": item},
        "nota_sobre_os_dados": {"type": "string"}},
        "required": ["manchete", "itens", "nota_sobre_os_dados"], "additionalProperties": False}


def montar_pedido(fatos: dict, visao: dict, versao: str, inicio: date, fim: date, nomes_temas: dict) -> str:
    v = VERSOES[versao]
    return json.dumps({
        "pedido": f"Resumo {versao}: no maximo {v['itens']} itens, cerca de {v['palavras']} palavras no total, "
                  f"leitura de {v['leitura']}. Combine indicador e noticia no mesmo item quando fizer sentido.",
        "visao": {"nome": visao["nome"], "leitor": visao["usuario"],
                  "temas_prioritarios": [nomes_temas.get(t, t) for t in lista(visao["temas_prioritarios"])]},
        "periodo": f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}",
        "fatos": {i: {k: v for k, v in f.items() if k not in ("url", "fonte_id")} for i, f in fatos.items()},
    }, ensure_ascii=False)


# --------------------------------------------------------------------------- saida

def renderizar(resumo: dict, fatos: dict, inds: list[dict], cab: dict, auditoria: dict) -> str:
    status = "✅ Auditado: todos os números conferem com as fontes" if auditoria["aprovado"] else \
        "⛔ BLOQUEADO PELO AUDITOR: não enviar. Problemas listados no fim."
    linhas = [f"# Radar Autopeças · {cab['versao'].capitalize()} · {cab['visao']}", "",
              f"**Período:** {cab['periodo']} · **Gerado em:** {cab['gerado_em']} · {status}", "",
              f"> {resumo.get('manchete', '')}", ""]
    for n, item in enumerate(resumo.get("itens", []), start=1):
        linhas += [f"### {n}. {item['o_que_aconteceu']}", "",
                   f"{ROTULOS.get(item['classificacao'], item['classificacao'])}", "",
                   f"- **O que mudou:** {item['o_que_mudou']}",
                   f"- **Por que importa:** {item['por_que_importa']}",
                   f"- **O que acompanhar:** {item['o_que_acompanhar']}"]
        citadas = []
        for r in item.get("refs", []):
            f = fatos.get(r)
            if not f:
                continue
            if f["tipo"] == "noticia":
                citadas.append(f"- *Fonte:* [{f['titulo']}]({f['url']}) · {f['fonte']} · {f['data']}")
            else:
                citadas.append(f"- *Fonte:* {f['fonte']} · referência {f['referencia_fmt']}")
        linhas += list(dict.fromkeys(citadas)) + [""]  # sem repetir a mesma fonte
    linhas += ["## Indicadores", "", "*Calculados pelo Radar a partir das séries oficiais. Não passam pela IA.*", "",
               "| Indicador | Valor | Referência | No mês | Em 12 meses |", "|---|---|---|---|---|"]
    for i in inds:
        linhas.append(f"| {i['nome']} | {i['valor_fmt']} | {i['referencia_fmt']} | {i['var_mes_fmt'] or '—'} | "
                      f"{i['var_ano_fmt'] or '—'} |")
    linhas += ["", "---", "", f"**Sobre os dados:** {resumo.get('nota_sobre_os_dados', '')}", "",
               f"*{cab['contagem']['acima_do_corte']} notícia(s) acima do corte da visão, de "
               f"{cab['contagem']['do_setor']} do setor no período. Textos redigidos por IA ({cab['provedor']}, "
               f"{cab['modelo']}) a partir dos fatos citados; interpretações não são fatos. Números conferidos "
               f"automaticamente.*"]
    if not auditoria["aprovado"]:
        linhas += ["", "## Problemas encontrados pelo auditor", ""] + [f"- {p}" for p in auditoria["problemas"]]
    return "\n".join(linhas) + "\n"


def argumento(args: list[str], nome: str, padrao: str | None = None) -> str | None:
    return args[args.index(nome) + 1] if nome in args else padrao


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    versao = argumento(args, "--versao", "flash")
    if versao not in VERSOES:
        print(f"[ERRO] versao deve ser {', '.join(VERSOES)}")
        return 2
    visoes = {v["id"]: v for v in ler_csv(CONFIG / "visoes.csv")}
    visao = visoes.get(argumento(args, "--visao", "V01"))
    if not visao:
        print(f"[ERRO] visao deve ser {', '.join(visoes)}")
        return 2
    hoje = date.today()
    if "--de" in args:
        inicio, fim = date.fromisoformat(argumento(args, "--de")), date.fromisoformat(argumento(args, "--ate", hoje.isoformat()))
    else:
        dias = PERIODOS.get(argumento(args, "--periodo", "semana"), 7)
        inicio, fim = hoje - timedelta(days=dias - 1), hoje

    fontes = {f["id"]: f for f in ler_csv(CONFIG / "fontes.csv")}
    nomes_temas = {t["id"]: t["tema"] for t in ler_csv(CONFIG / "taxonomia/temas.csv")}
    max_itens = VERSOES[versao]["itens"]
    # Noticias candidatas: o dobro do limite, para a IA ter escolha sem receber ruido.
    selecionadas, contagem = selecionar(inicio, fim, visao, max_itens * 2)
    inds = indicadores.calcular()
    fatos = montar_fatos(selecionadas, inds, fontes, nomes_temas)
    periodo = f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
    print(f"{visao['nome']} · {versao} · {periodo}: {contagem['no_periodo']} noticias no periodo, "
          f"{contagem['do_setor']} do setor, {contagem['acima_do_corte']} acima do corte "
          f"({visao['relevancia_minima']}); {len(selecionadas)} enviadas + {len(inds)} indicadores")
    for s in selecionadas:
        print(f"  {s['nota']:>3} ({s['origem_nota']}) {s['noticia']['titulo'][:85]}")
    if "--selecao" in args:
        return 0

    provedor = provedores.obter()
    sistema, formato = montar_sistema(), esquema(list(fatos), max_itens)
    pedido = montar_pedido(fatos, visao, versao, inicio, fim, nomes_temas)
    tentativas = []
    for tentativa in (1, 2):
        resumo, meta = provedor.classificar(sistema, formato, pedido, max_tokens=VERSOES[versao]["max_tokens"])
        if meta["status"] != "ok":
            print(f"[ERRO] provedor {provedor.nome}: {meta['status']} {meta.get('detalhe', '')[:200]}")
            return 1
        auditoria = auditor.auditar(resumo, fatos, max_itens)
        tentativas.append({"meta": meta, "resumo": resumo, "auditoria": auditoria})
        print(f"tentativa {tentativa}: {'aprovado' if auditoria['aprovado'] else 'reprovado'} "
              f"({meta.get('uso', {}).get('entrada', 0)} tokens de entrada, {meta.get('uso', {}).get('saida', 0)} de saida)")
        if auditoria["aprovado"]:
            break
        for p in auditoria["problemas"]:
            print(f"   - {p}")
        pedido = json.loads(pedido)
        pedido["correcao"] = ("A versao anterior foi reprovada pelo auditor por estes motivos. Corrija: "
                              + " | ".join(auditoria["problemas"]))
        pedido = json.dumps(pedido, ensure_ascii=False)

    gerado = datetime.now(timezone.utc).astimezone()
    cab = {"versao": versao, "visao": visao["nome"], "periodo": periodo, "gerado_em": gerado.strftime("%d/%m/%Y %H:%M"),
           "provedor": provedor.nome, "modelo": meta.get("modelo_respondeu") or provedor.modelo, "contagem": contagem}
    texto = renderizar(resumo, fatos, inds, cab, auditoria)
    SAIDAS.mkdir(parents=True, exist_ok=True)
    base = SAIDAS / f"{gerado.strftime('%Y-%m-%d_%H%M')}_{visao['id']}_{versao}"
    base.with_suffix(".md").write_text(texto, encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps({
        "cabecalho": cab, "fatos": fatos, "indicadores": inds, "tentativas": tentativas,
        "versao_prompt": hashlib.sha1((sistema + json.dumps(formato, sort_keys=True)).encode()).hexdigest()[:10],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n{'APROVADO' if auditoria['aprovado'] else 'BLOQUEADO'}: {base.with_suffix('.md').relative_to(RAIZ)}")
    return 0 if auditoria["aprovado"] else 1


if __name__ == "__main__":
    sys.exit(main())
