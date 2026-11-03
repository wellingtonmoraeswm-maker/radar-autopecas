"""Conector de series do SGS do Banco Central (api.bcb.gov.br, formato JSON).

A URL do catalogo ja traz o codigo da serie: .../bcdata.sgs.<codigo>/dados?formato=json...
O id da serie no Radar e `bcb_sgs_<codigo>`.
"""

from __future__ import annotations

import json
import re

from coleta.base import Contexto, Ponto, Resultado


def coletar(fonte: dict, ctx: Contexto) -> Resultado:
    achado = re.search(r"bcdata\.sgs\.(\d+)/", fonte["url"])
    if not achado:
        raise ValueError("URL sem codigo SGS (esperado .../bcdata.sgs.<codigo>/dados...)")
    serie_id = f"bcb_sgs_{achado.group(1)}"

    conteudo = ctx.baixar(fonte["url"], cabecalhos={"Accept": "application/json"})
    res = Resultado(brutos=[ctx.guardar_bruto(conteudo, "json")])

    for registro in json.loads(conteudo):
        dia, mes, ano = registro["data"].split("/")
        bruto = str(registro.get("valor", "")).strip()
        if not bruto:
            res.avisos.append(f"{registro['data']}: valor vazio ignorado")
            continue
        # SGS mensal usa o dia 01: o periodo de referencia e o mes.
        referencia = f"{ano}-{mes}" if dia == "01" and fonte.get("frequencia") == "mensal" else f"{ano}-{mes}-{dia}"
        res.pontos.append(Ponto(serie_id=serie_id, ocorrido_em=referencia, valor=float(bruto)))

    if not res.pontos:
        res.avisos.append("serie sem pontos no periodo da URL")
    return res
