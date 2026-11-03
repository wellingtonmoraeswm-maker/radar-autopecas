"""Conector <nome>: <o que coleta, de qual fonte, em que formato>.

Copiar para coleta/conectores/<nome>.py e ligar no catalogo com conector=radar:<nome>.
"""

from __future__ import annotations

from coleta.base import Contexto, Noticia, Ponto, Resultado, cortar  # noqa: F401 (use o que precisar)


def coletar(fonte: dict, ctx: Contexto) -> Resultado:
    conteudo = ctx.baixar(fonte["url"])                       # 1. baixar (respeita robots.txt)
    res = Resultado(brutos=[ctx.guardar_bruto(conteudo, "html")])  # 2. guardar o original

    # 3. interpretar. Datas desconhecidas ficam None.
    # Noticia:
    #   res.noticias.append(Noticia(url=..., titulo=..., publicado_em=..., trecho_interno=cortar(...)))
    # Serie:
    #   res.pontos.append(Ponto(serie_id="<fonte>_<codigo>", ocorrido_em="AAAA-MM", valor=float(...)))

    if not res.noticias and not res.pontos:
        res.avisos.append("nenhum item encontrado: o layout pode ter mudado")
    return res
