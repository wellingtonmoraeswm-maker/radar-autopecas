"""Conector generico de RSS 2.0 e Atom. Serve para qualquer fonte com tipo=rss."""

from __future__ import annotations

import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from coleta.base import Contexto, Noticia, Resultado, cortar

ATOM = "{http://www.w3.org/2005/Atom}"


def _data(texto: str | None) -> str | None:
    if not texto:
        return None
    texto = texto.strip()
    try:
        return parsedate_to_datetime(texto).isoformat(timespec="seconds")  # RSS (RFC 822)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).isoformat(timespec="seconds")  # Atom
    except ValueError:
        return None


def _limpar(texto: str | None) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", texto or "")
    texto = html.unescape(sem_tags).replace("\ufffc", " ").replace("\u200b", "")  # objetos e espacos invisiveis
    return " ".join(texto.split())


def coletar(fonte: dict, ctx: Contexto) -> Resultado:
    conteudo = ctx.baixar(fonte["url"])
    res = Resultado(brutos=[ctx.guardar_bruto(conteudo, "xml")])
    raiz = ElementTree.fromstring(conteudo)

    for item in raiz.iter("item"):
        url = (item.findtext("link") or "").strip()
        titulo = _limpar(item.findtext("title"))
        if not url or not titulo:
            res.avisos.append(f"item sem link ou titulo ignorado: {titulo or url}")
            continue
        res.noticias.append(Noticia(url=url, titulo=titulo, publicado_em=_data(item.findtext("pubDate")),
                                    trecho_interno=cortar(_limpar(item.findtext("description")))))

    for entrada in raiz.iter(f"{ATOM}entry"):
        link = entrada.find(f"{ATOM}link[@rel='alternate']")
        if link is None:
            link = entrada.find(f"{ATOM}link")
        url = (link.get("href") if link is not None else "") or ""
        titulo = _limpar(entrada.findtext(f"{ATOM}title"))
        if not url or not titulo:
            res.avisos.append(f"entrada sem link ou titulo ignorada: {titulo or url}")
            continue
        publicado = entrada.findtext(f"{ATOM}published") or entrada.findtext(f"{ATOM}updated")
        resumo = entrada.findtext(f"{ATOM}summary") or entrada.findtext(f"{ATOM}content")
        res.noticias.append(Noticia(url=url, titulo=titulo, publicado_em=_data(publicado),
                                    trecho_interno=cortar(_limpar(resumo))))

    if not res.noticias:
        res.avisos.append("feed sem itens: verifique se a URL ainda e um feed")
    return res
