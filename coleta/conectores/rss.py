"""Conector generico de RSS 2.0 e Atom. Serve para qualquer fonte com tipo=rss.

Historico (so quando o executor pede, com --historico DIAS): feeds WordPress aceitam ?paged=2, 3...
O conector segue as paginas, com uma pausa entre elas, ate passar da data-limite, a pagina vir vazia,
o site responder erro ou chegar a MAX_PAGINAS. Feed que nao pagina simplesmente para na primeira.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import urllib.error
from datetime import date, timedelta

from coleta.base import Contexto, Noticia, Resultado, cortar

MAX_PAGINAS = 400
PAUSA_ENTRE_PAGINAS = 1.0  # segundos: cortesia com o site

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
    _ler(conteudo, res)
    dias = getattr(ctx, "historico_dias", 0)
    if dias and res.noticias:
        _historico(fonte["url"], ctx, res, date.today() - timedelta(days=dias))
    if not res.noticias:
        res.avisos.append("feed sem itens: verifique se a URL ainda e um feed")
    return res


def _mais_antiga(noticias: list[Noticia]) -> str | None:
    datas = [n.publicado_em[:10] for n in noticias if n.publicado_em]
    return min(datas) if datas else None


def _historico(url: str, ctx: Contexto, res: Resultado, limite: date) -> None:
    separador = "&" if "?" in url else "?"
    paginas = 1
    for pagina in range(2, MAX_PAGINAS + 1):
        antiga = _mais_antiga(res.noticias)
        if antiga is None or antiga < limite.isoformat():
            break
        ctx.pausar(PAUSA_ENTRE_PAGINAS)
        try:
            conteudo = ctx.baixar(f"{url}{separador}paged={pagina}")
        except urllib.error.HTTPError as exc:  # 404 = acabaram as paginas (ou o feed nao pagina)
            if exc.code != 404:
                res.avisos.append(f"historico parou na pagina {pagina}: HTTP {exc.code}")
            break
        antes = len(res.noticias)
        res.brutos.append(ctx.guardar_bruto(conteudo, "xml"))
        _ler(conteudo, res)
        if len(res.noticias) == antes:
            break
        paginas = pagina
    # descarta o que passou da data-limite na ultima pagina
    res.noticias = [n for n in res.noticias if not n.publicado_em or n.publicado_em[:10] >= limite.isoformat()]
    res.avisos.append(f"historico: {paginas} pagina(s) lidas, ate {_mais_antiga(res.noticias) or '?'}")


def _ler(conteudo: bytes, res: Resultado) -> None:
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
