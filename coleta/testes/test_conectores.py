"""Testes offline dos conectores (sem internet). Rodar na raiz: python -m unittest discover coleta/testes"""

import json
import unittest

from coleta.base import Noticia, normalizar_url
from coleta.conectores import bcb_sgs, rss

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>X</title>
<item><title>Distribuidora &amp; pe\xc3\xa7as</title><link>https://ex.com/a?utm_source=x</link>
<pubDate>Wed, 29 Oct 2026 17:03:19 +0000</pubDate><description>&lt;p&gt;Texto &lt;b&gt;longo&lt;/b&gt;&lt;/p&gt;</description></item>
<item><title></title><link>https://ex.com/sem-titulo</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Y</title>
<entry><title>Entrada Atom</title><link rel="alternate" href="https://ex.com/b"/>
<updated>2026-10-30T11:00:00Z</updated><summary>Resumo</summary></entry></feed>"""

SGS = json.dumps([{"data": "01/08/2026", "valor": "5.40"}, {"data": "01/09/2026", "valor": ""}]).encode()


class CtxFalso:
    """Substitui o Contexto: devolve o conteudo fixo e nao grava nada."""

    def __init__(self, conteudo: bytes):
        self.conteudo = conteudo

    def baixar(self, url, dados=None, cabecalhos=None):
        return self.conteudo

    def guardar_bruto(self, conteudo, extensao):
        return f"memoria.{extensao}"


class TestRss(unittest.TestCase):
    def test_rss(self):
        res = rss.coletar({"url": "https://ex.com/feed"}, CtxFalso(RSS))
        self.assertEqual(len(res.noticias), 1)
        n = res.noticias[0]
        self.assertEqual(n.titulo, "Distribuidora & peças")
        self.assertEqual(n.publicado_em, "2026-10-29T17:03:19+00:00")
        self.assertEqual(n.trecho_interno, "Texto longo")
        self.assertIsNone(n.ocorrido_em)
        self.assertEqual(len(res.avisos), 1)  # o item sem titulo

    def test_atom(self):
        res = rss.coletar({"url": "https://ex.com/atom"}, CtxFalso(ATOM))
        self.assertEqual(res.noticias[0].url, "https://ex.com/b")
        self.assertEqual(res.noticias[0].publicado_em, "2026-10-30T11:00:00+00:00")

    def test_id_ignora_rastreio(self):
        self.assertEqual(Noticia("https://ex.com/a?utm_source=x", "t").id, Noticia("https://EX.com/a/", "t").id)
        self.assertEqual(normalizar_url("https://ex.com/a?b=1&utm_medium=y"), "https://ex.com/a?b=1")


class TestBcbSgs(unittest.TestCase):
    def test_mensal(self):
        fonte = {"url": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.3698/dados?formato=json", "frequencia": "mensal"}
        res = bcb_sgs.coletar(fonte, CtxFalso(SGS))
        self.assertEqual(len(res.pontos), 1)
        self.assertEqual(res.pontos[0].id, "bcb_sgs_3698@2026-08")
        self.assertEqual(res.pontos[0].valor, 5.40)
        self.assertEqual(len(res.avisos), 1)  # valor vazio

    def test_url_sem_codigo(self):
        with self.assertRaises(ValueError):
            bcb_sgs.coletar({"url": "https://api.bcb.gov.br/outra"}, CtxFalso(SGS))


if __name__ == "__main__":
    unittest.main()
