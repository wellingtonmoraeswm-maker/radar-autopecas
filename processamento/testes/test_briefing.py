"""Testes do resumo executivo: indicadores, selecao, auditor e montagem do texto (sem chamar IA)."""

import unittest
from datetime import date

from processamento import auditor, briefing, indicadores

FATOS = {
    "I_cambio": {"tipo": "indicador", "frase": "Câmbio R$/US$ (média mensal): R$ 5,14 em set/2026; -0,2% sobre ago/2026; "
                 "-4,1% sobre set/2025", "referencia_fmt": "set/2026", "fonte": "Banco Central do Brasil (SGS)"},
    "N1": {"tipo": "noticia", "titulo": "Mercedes-Benz revela descontos em peças para linha Sprinter",
           "trecho": "Descontos de até 50% em mais de 200 itens até dezembro de 2026.", "data": "27/10/2026",
           "fonte": "O Mecânico", "url": "https://ex.com/n1"},
}


def item(refs, **campos):
    base = {"refs": refs, "o_que_aconteceu": "Fato.", "o_que_mudou": "Mudou.", "por_que_importa": "Importa.",
            "classificacao": "atencao", "o_que_acompanhar": "Acompanhar."}
    base.update(campos)
    return base


class TestAuditor(unittest.TestCase):
    def test_aprova_numeros_das_proprias_referencias(self):
        r = {"manchete": "Câmbio a R$ 5,14", "itens": [
            item(["I_cambio"], o_que_mudou="-4,1% sobre set/2025"),
            item(["N1"], o_que_aconteceu="Descontos de até 50% em mais de 200 itens")]}
        self.assertTrue(auditor.auditar(r, FATOS, 3)["aprovado"])

    def test_bloqueia_numero_inventado(self):
        r = {"manchete": "x", "itens": [item(["I_cambio"], por_que_importa="Pode reduzir custos em 8%")]}
        a = auditor.auditar(r, FATOS, 3)
        self.assertFalse(a["aprovado"])
        self.assertIn("8", a["problemas"][0])

    def test_bloqueia_numero_de_outro_item(self):
        # 50 existe nos fatos, mas nao na referencia deste item
        r = {"manchete": "x", "itens": [item(["I_cambio"], o_que_aconteceu="Câmbio e descontos de 50%")]}
        self.assertFalse(auditor.auditar(r, FATOS, 3)["aprovado"])

    def test_bloqueia_referencia_vazia_inexistente_campo_vazio_e_excesso(self):
        r = {"manchete": "x", "itens": [item([]), item(["N9"]), item(["N1"], o_que_mudou=" "),
                                        item(["N1"]), item(["N1"])]}
        p = " ".join(auditor.auditar(r, FATOS, 3)["problemas"])
        for trecho in ("sem referencia", "inexistente", "campo vazio", "limite"):
            self.assertIn(trecho, p)

    def test_bloqueia_numero_sem_origem_na_manchete(self):
        self.assertFalse(auditor.auditar({"manchete": "Mercado cresce 7%", "itens": [item(["N1"])]}, FATOS, 3)["aprovado"])

    def test_milhar_e_decimal_em_formato_brasileiro(self):
        self.assertEqual(auditor.numeros("R$ 348.745 mi e 5,14"), {"348745", "5.14"})


class TestIndicadores(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(indicadores.fmt_numero(348745.0, 0), "348.745")
        self.assertEqual(indicadores.fmt_numero(5.1447, 2), "5,14")
        self.assertEqual(indicadores.fmt_variacao(-0.165, "pct"), "-0,2%")
        self.assertEqual(indicadores.fmt_variacao(1.1, "pp"), "+1,10 p.p.")
        self.assertEqual(indicadores.fmt_mes("2026-09"), "set/2026")

    def test_mes_anterior_atravessa_o_ano(self):
        self.assertEqual(indicadores.mes_anterior("2026-01", 1), "2025-12")
        self.assertEqual(indicadores.mes_anterior("2026-09", 12), "2025-09")

    def test_variacao(self):
        self.assertAlmostEqual(indicadores.variacao(5.1447, 5.3674, "pct"), -4.149, places=2)
        self.assertAlmostEqual(indicadores.variacao(5.99, 4.89, "pp"), 1.10, places=2)
        self.assertIsNone(indicadores.variacao(1, None, "pct"))


class TestSelecao(unittest.TestCase):
    VISAO = {"temas_prioritarios": "T21", "familias_prioritarias": "", "relevancia_minima": "40"}

    def test_nota_da_ia_com_bonus_da_visao(self):
        regras = {"relevancia": 45, "temas": ["T21"], "familias": []}
        ia = {"resultado": {"usar": True, "relevancia": 25, "temas": ["T21"]}}
        self.assertEqual(briefing.nota_final(regras, ia, self.VISAO)[:1], (40,))

    def test_ia_reprovada_volta_para_as_regras(self):
        regras = {"relevancia": 45, "temas": ["T02"], "familias": []}
        ia = {"resultado": {"usar": False, "relevancia": 90, "temas": ["T21"]}}
        self.assertEqual(briefing.nota_final(regras, ia, self.VISAO)[0], 45)

    def test_data_de_coleta_quando_falta_publicacao(self):
        self.assertEqual(briefing.data_da_noticia({"coletado_em": "2026-10-30T10:00:00-03:00"}), (date(2026, 10, 30), True))
        self.assertEqual(briefing.data_da_noticia({"publicado_em": "2026-10-29T17:03:19+00:00"})[1], False)


class TestRenderizar(unittest.TestCase):
    CAB = {"versao": "flash", "visao": "Presidência", "periodo": "p", "gerado_em": "g", "provedor": "x", "modelo": "m",
           "contagem": {"acima_do_corte": 1, "do_setor": 2}}

    def test_link_vem_do_codigo_e_fonte_nao_repete(self):
        r = {"manchete": "m", "nota_sobre_os_dados": "n", "itens": [item(["N1", "I_cambio", "I_cambio"])]}
        texto = briefing.renderizar(r, FATOS, [], self.CAB, {"aprovado": True, "problemas": []})
        self.assertIn("(https://ex.com/n1)", texto)
        self.assertEqual(texto.count("Banco Central do Brasil (SGS)"), 1)

    def test_bloqueado_fica_visivel(self):
        r = {"manchete": "m", "nota_sobre_os_dados": "n", "itens": []}
        texto = briefing.renderizar(r, FATOS, [], self.CAB, {"aprovado": False, "problemas": ["resumo sem itens"]})
        self.assertIn("BLOQUEADO", texto)
        self.assertIn("resumo sem itens", texto)


if __name__ == "__main__":
    unittest.main()
