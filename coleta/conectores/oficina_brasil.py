"""Conector do portal Oficina Brasil (sem RSS).

1. Le a pagina inicial (url do catalogo) e pega os links de materia (/noticia/<categoria>/<titulo>).
2. Para cada materia ainda nao coletada (no maximo MAX_NOVAS por execucao), le a pagina e extrai os
   metadados publicos que o proprio site declara: og:title, og:description e a data de publicacao
   (datePublished do JSON-LD ou article:published_time).
Guarda como original a pagina inicial e um JSON com os metadados extraidos de cada materia.
O robots.txt do site permite /noticia/ (bloqueia /api/, /login, /cadastro e a busca).
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from datetime import datetime

from coleta.base import Contexto, Noticia, Resultado, cortar, normalizar_url, urls_coletadas

MAX_NOVAS = 12
LINK = re.compile(r'href=["\']((?:https://oficinabrasil\.com\.br)?/noticia/[a-z0-9-]+/[a-z0-9-]+)["\']', re.I)


def meta(pagina: str, nome: str) -> str | None:
    for padrao in (r'<meta[^>]+(?:property|name)=["\']' + re.escape(nome) + r'["\'][^>]*content=["\']([^"\']*)',
                   r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']' + re.escape(nome) + r'["\']'):
        m = re.search(padrao, pagina, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return None


def data_publicacao(pagina: str) -> str | None:
    """Prefere o JSON-LD (com fuso); cai para article:published_time. Sem data valida: None."""
    candidatos = re.findall(r'"datePublished"\s*:\s*"([^"]+)"', pagina) + [meta(pagina, "article:published_time") or ""]
    for bruto in candidatos:
        try:
            return datetime.fromisoformat(bruto.replace("Z", "+00:00")).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def titulo_limpo(titulo: str) -> str:
    return re.sub(r"\s*[-|]\s*Oficina Brasil\s*$", "", titulo).strip()


def coletar(fonte: dict, ctx: Contexto) -> Resultado:
    inicial = ctx.baixar(fonte["url"])
    res = Resultado(brutos=[ctx.guardar_bruto(inicial, "html")])
    links = list(dict.fromkeys(urllib.parse.urljoin(fonte["url"], l) for l in LINK.findall(inicial.decode("utf-8", "ignore"))))
    if not links:
        res.avisos.append("nenhum link de materia na pagina inicial: o layout pode ter mudado")
        return res
    conhecidas = urls_coletadas(fonte["id"])
    novas = [l for l in links if normalizar_url(l) not in conhecidas][:MAX_NOVAS]
    extraidos = []
    for url in novas:
        try:
            pagina = ctx.baixar(url).decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001 - uma materia com erro nao derruba as outras
            res.avisos.append(f"{url}: {type(exc).__name__}")
            continue
        titulo = titulo_limpo(meta(pagina, "og:title") or "")
        if not titulo:
            res.avisos.append(f"{url}: sem og:title")
            continue
        n = Noticia(url=url, titulo=titulo, publicado_em=data_publicacao(pagina),
                    trecho_interno=cortar(meta(pagina, "og:description") or ""))
        res.noticias.append(n)
        extraidos.append({"url": url, "titulo": n.titulo, "publicado_em": n.publicado_em, "descricao": n.trecho_interno})
    if extraidos:
        res.brutos.append(ctx.guardar_bruto(json.dumps(extraidos, ensure_ascii=False, indent=1).encode("utf-8"), "json"))
    return res
