"""Testes offline do historico paginado do conector RSS."""

import io
import unittest
import urllib.error
from datetime import date, timedelta

from coleta.conectores import rss


def feed(dias_atras: list[int]) -> bytes:
    itens = "".join(
        f"<item><title>Noticia {d}</title><link>https://ex.com/{d}</link>"
        f"<pubDate>{(date.today() - timedelta(days=d)).strftime('%a, %d %b %Y')} 12:00:00 +0000</pubDate></item>"
        for d in dias_atras)
    return f"<rss><channel>{itens}</channel></rss>".encode()


class CtxPaginas:
    def __init__(self, paginas: dict[int, bytes], historico_dias: int):
        self.paginas, self.historico_dias, self.pedidos, self.pausas = paginas, historico_dias, [], 0

    def baixar(self, url, dados=None, cabecalhos=None):
        self.pedidos.append(url)
        n = int(url.split("paged=")[1]) if "paged=" in url else 1
        if n not in self.paginas:
            raise urllib.error.HTTPError(url, 404, "nao achou", {}, io.BytesIO(b""))
        return self.paginas[n]

    def guardar_bruto(self, conteudo, extensao):
        return "memoria"

    def pausar(self, segundos):
        self.pausas += 1


class TestHistorico(unittest.TestCase):
    def test_para_na_data_limite_e_descarta_o_excedente(self):
        ctx = CtxPaginas({1: feed([0, 3]), 2: feed([10, 20]), 3: feed([30, 45]), 4: feed([60, 90])}, historico_dias=40)
        res = rss.coletar({"url": "https://ex.com/feed/"}, ctx)
        self.assertEqual(len(ctx.pedidos), 3)  # pagina 3 ja passa do limite: nao pede a 4
        self.assertEqual(sorted(n.titulo for n in res.noticias), ["Noticia 0", "Noticia 10", "Noticia 20", "Noticia 3", "Noticia 30"])
        self.assertEqual(ctx.pausas, 2)

    def test_para_quando_acabam_as_paginas(self):
        ctx = CtxPaginas({1: feed([0]), 2: feed([5])}, historico_dias=180)
        res = rss.coletar({"url": "https://ex.com/feed/"}, ctx)
        self.assertEqual(len(res.noticias), 2)
        self.assertEqual(ctx.pedidos[-1], "https://ex.com/feed/?paged=3")

    def test_sem_historico_le_so_a_primeira_pagina(self):
        ctx = CtxPaginas({1: feed([0]), 2: feed([5])}, historico_dias=0)
        rss.coletar({"url": "https://ex.com/feed/"}, ctx)
        self.assertEqual(ctx.pedidos, ["https://ex.com/feed/"])

    def test_url_com_parametro_usa_e_comercial(self):
        ctx = CtxPaginas({1: feed([0])}, historico_dias=30)
        rss.coletar({"url": "https://ex.com/feed/?cat=3"}, ctx)
        self.assertEqual(ctx.pedidos[-1], "https://ex.com/feed/?cat=3&paged=2")


if __name__ == "__main__":
    unittest.main()
