"""Auditor do resumo executivo: confere o texto da IA contra os fatos que ela recebeu.

Regras (todas deterministicas):
1. Todo item cita pelo menos uma referencia, e toda referencia existe nos fatos enviados.
2. Todo numero de um item aparece no texto das referencias DAQUELE item
   (frase do indicador, ou titulo e trecho da noticia). Numero da manchete aparece em algum fato.
3. Campos obrigatorios preenchidos; classificacao dentro da lista permitida.
4. Quantidade de itens dentro do limite da versao.
Se qualquer regra falhar, o resumo fica BLOQUEADO: nao e enviado, so fica como rascunho para revisao.
"""

from __future__ import annotations

import re

NUMERO = re.compile(r"\d+(?:[.,]\d+)*")
CAMPOS = ("o_que_aconteceu", "o_que_mudou", "por_que_importa", "o_que_acompanhar")
CLASSIFICACOES = ("risco", "oportunidade", "atencao", "neutro")


def _normalizar(token: str) -> str:
    """'348.745' e '348745' sao o mesmo numero; '5,14' e '5.14' tambem."""
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", token):  # milhar com ponto (pt-BR)
        token = token.replace(".", "")
    return token.replace(",", ".")


def numeros(texto: str) -> set[str]:
    return {_normalizar(t) for t in NUMERO.findall(texto or "")}


def texto_do_fato(fato: dict) -> str:
    return " ".join(str(fato.get(k, "")) for k in ("frase", "titulo", "trecho", "data", "referencia_fmt"))


def auditar(resumo: dict, fatos: dict[str, dict], max_itens: int) -> dict:
    problemas = []
    itens = resumo.get("itens") or []
    if not itens:
        problemas.append("resumo sem itens")
    if len(itens) > max_itens:
        problemas.append(f"{len(itens)} itens, o limite desta versao e {max_itens}")

    todos = set().union(*(numeros(texto_do_fato(f)) for f in fatos.values())) if fatos else set()
    sobra = numeros(resumo.get("manchete", "")) - todos
    if sobra:
        problemas.append(f"manchete: numero(s) sem origem nos fatos: {', '.join(sorted(sobra))}")

    for n, item in enumerate(itens, start=1):
        refs = item.get("refs") or []
        if not refs:
            problemas.append(f"item {n}: sem referencia")
            continue
        invalidas = [r for r in refs if r not in fatos]
        if invalidas:
            problemas.append(f"item {n}: referencia inexistente {invalidas}")
        permitidos = set().union(*(numeros(texto_do_fato(fatos[r])) for r in refs if r in fatos))
        for campo in CAMPOS:
            if not (item.get(campo) or "").strip():
                problemas.append(f"item {n}: campo vazio '{campo}'")
            sobra = numeros(item.get(campo, "")) - permitidos
            if sobra:
                problemas.append(f"item {n}, {campo}: numero(s) que nao estao nas referencias do item: "
                                 f"{', '.join(sorted(sobra))}")
        if item.get("classificacao") not in CLASSIFICACOES:
            problemas.append(f"item {n}: classificacao invalida '{item.get('classificacao')}'")
    return {"aprovado": not problemas, "problemas": problemas}
