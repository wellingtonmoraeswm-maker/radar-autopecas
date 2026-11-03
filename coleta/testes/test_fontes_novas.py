"""Testes offline: conectores ANIP e Oficina Brasil, codificacao de URL e inclusao/exclusao de fontes."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coleta import catalogo
from coleta.base import url_codificada
from coleta.conectores import anip_infografico as anip
from coleta.conectores import oficina_brasil as ob

PAGINA1 = """4.346.569 -14,8% VENDAS TOTAIS DE PNEUS CAEM 8,6% ATÉ AGOSTO DE 2026
 Vendas para montadoras subiram 0,4%
 Vendas para reposição retraíram 13,3%
  Exportações caíram 6,5%
 Importações subiram 2.124,4%
OS DADOS DO SETOR ESTÃO EXPRESSOS EM UNIDADES"""


class TestAnip(unittest.TestCase):
    def test_extrai_manchete_e_destaques_com_sinal(self):
        valores, ref, avisos, manchete = anip.extrair(PAGINA1)
        self.assertEqual(ref, "2026-08")
        self.assertEqual(valores, {"total": -8.6, "montadoras": 0.4, "reposicao": -13.3, "exportacoes": -6.5})
        self.assertNotIn("Importa", anip.destaques(PAGINA1))  # importacoes fica fora do Radar
        self.assertEqual(avisos, [])
        self.assertTrue(manchete.startswith("VENDAS TOTAIS"))

    def test_verbo_desconhecido_nao_vira_numero(self):
        valores, _, avisos, _ = anip.extrair(PAGINA1.replace("retraíram", "oscilaram"))
        self.assertNotIn("reposicao", valores)
        self.assertTrue(any("verbo desconhecido" in a for a in avisos))

    def test_mes_pelo_nome_do_arquivo(self):
        self.assertEqual(anip.referencia_do_arquivo("https://x/uploads/2026/10/09-PT_INFOGRAFICO_SET_26.pdf"), "2026-09")
        self.assertEqual(anip.referencia_do_arquivo("https://x/uploads/2026/08/PT_INFOGRAFICO_julho_26.pdf"), "2026-07")
        self.assertEqual(anip.referencia_do_arquivo("https://x/uploads/2026/05/PT_INFOGR%C3%81FICO_ABR_26.pdf"), "2026-04")

    def test_mes_posterior_a_publicacao_e_descartado(self):
        self.assertIsNone(anip.referencia_do_arquivo("https://x/uploads/2023/03/ANIP-INFOGRAFICO_FEV_27_03_27.pdf"))


class TestOficinaBrasil(unittest.TestCase):
    PAGINA = ('<meta property="og:title" content="Troca de Suspensão: Guia - Oficina Brasil">'
              '<meta property="og:description" content="Passo a passo &amp; dicas">'
              '<script type="application/ld+json">{"datePublished": "2026-10-28T15:07:08.000Z"}</script>')

    def test_metadados(self):
        self.assertEqual(ob.titulo_limpo(ob.meta(self.PAGINA, "og:title")), "Troca de Suspensão: Guia")
        self.assertEqual(ob.meta(self.PAGINA, "og:description"), "Passo a passo & dicas")
        self.assertEqual(ob.data_publicacao(self.PAGINA), "2026-10-28T15:07:08+00:00")

    def test_sem_data_fica_vazio(self):
        self.assertIsNone(ob.data_publicacao("<html></html>"))

    def test_links_de_materia(self):
        html = '<a href="/noticia/motor/abc-def">x</a><a href="/forum/x">y</a><a href="/noticia/motor/abc-def">z</a>'
        self.assertEqual(ob.LINK.findall(html), ["/noticia/motor/abc-def", "/noticia/motor/abc-def"])


class TestUrl(unittest.TestCase):
    def test_codifica_acento_sem_dupla_codificacao(self):
        self.assertEqual(url_codificada("https://x.br/a/PT_INFOGRÁFICO.pdf"), "https://x.br/a/PT_INFOGR%C3%81FICO.pdf")
        self.assertEqual(url_codificada("https://x.br/a%20b?q=a&b=1"), "https://x.br/a%20b?q=a&b=1")


class TestCatalogo(unittest.TestCase):
    """Usa uma copia do catalogo numa pasta temporaria."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        copia = Path(self.tmp.name) / "fontes.csv"
        shutil.copy(catalogo.CATALOGO, copia)
        self.p = mock.patch.object(catalogo, "CATALOGO", copia)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def resposta_rss(self, url):
        return {"url": url, "robots": "permitido", "ok": True, "formato": "rss", "feeds": [], "itens": 10,
                "exemplos": [], "url_sugerida": url.rstrip("/") + "/feed/", "tipo_sugerido": "rss", "mensagem": "rss"}

    def test_inclui_rss_ativa_e_recusa_repetida(self):
        with mock.patch.object(catalogo, "inspecionar", side_effect=self.resposta_rss):
            r = catalogo.adicionar({"url": "https://novo.com.br/", "nome": "Novo; Portal", "escopo": "geral",
                                    "confiabilidade": "B", "temas": "T01"})
            self.assertEqual((r["fonte"]["status"], r["fonte"]["conector"]), ("ativa", "radar:rss"))
            self.assertEqual(r["fonte"]["nome"], "Novo, Portal")  # ponto e virgula quebraria o CSV
            with self.assertRaises(catalogo.ErroCatalogo):
                catalogo.adicionar({"url": "https://novo.com.br/feed/", "nome": "x"})
        _, linhas = catalogo.ler_csv(catalogo.CATALOGO)
        self.assertEqual(catalogo.validar(*catalogo.ler_csv(catalogo.CATALOGO))[0], [])
        self.assertEqual(linhas[-1]["id"], r["fonte"]["id"])

    def test_bloqueada_pelo_robots_nao_entra(self):
        bloqueio = {**self.resposta_rss("https://x.br"), "robots": "BLOQUEADO pelo robots.txt", "mensagem": "proibido"}
        with mock.patch.object(catalogo, "inspecionar", return_value=bloqueio), self.assertRaises(catalogo.ErroCatalogo):
            catalogo.adicionar({"url": "https://x.br", "nome": "x"})

    def test_excluir_mantem_a_linha_com_motivo(self):
        catalogo.mudar_status("S21", "descartada", "teste")
        fonte = next(l for l in catalogo.ler_csv(catalogo.CATALOGO)[1] if l["id"] == "S21")
        self.assertEqual(fonte["status"], "descartada")
        self.assertIn("teste", fonte["observacao"])

    def test_nao_ativa_sem_conector(self):
        with self.assertRaises(catalogo.ErroCatalogo):
            catalogo.mudar_status("S19", "ativa")


if __name__ == "__main__":
    unittest.main()
