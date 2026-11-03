"""Testes da classificacao com a taxonomia real de config/. Rodar: python -m unittest discover -s processamento/testes -t ."""

import unittest

from processamento.classificar import Classificador

CL = Classificador()


def classificar(titulo: str, fonte_id: str = "S20", trecho: str = "") -> dict:
    return CL.classificar({"id": "N-teste", "fonte_id": fonte_id, "titulo": titulo, "trecho_interno": trecho})


class TestPortaDoSetor(unittest.TestCase):
    def test_fonte_geral_sem_ancora_fica_fora(self):
        c = classificar("Intelipost projeta alta de 14% no frete da Black Friday")
        self.assertFalse(c["setorial"])
        self.assertEqual(c["relevancia"], 0)
        self.assertIn("T10", c["temas"])  # o tema e registrado, mas nao torna a noticia relevante

    def test_fonte_geral_com_ancora_entra(self):
        c = classificar("Importação de autopeças sobe e pressiona distribuidoras")
        self.assertTrue(c["setorial"])
        self.assertIn("T01", c["temas"])

    def test_fonte_setorial_entra_sem_ancora(self):
        self.assertTrue(classificar("AutoAju 2026 reunirá a indústria", fonte_id="S21")["setorial"])

    def test_familia_e_ancora(self):
        c = classificar("Falta de amortecedores preocupa lojistas")
        self.assertTrue(c["setorial"])
        self.assertIn("F03", c["familias"])

    def test_sem_acento_e_maiusculas(self):
        self.assertIn("T06", classificar("REFORMA TRIBUTARIA muda autopecas")["temas"])


class TestNota(unittest.TestCase):
    def test_nota_explicada_e_limitada(self):
        c = classificar("Autopeças: dólar, Selic e reforma tributária pressionam freios e pastilhas", fonte_id="S21")
        self.assertLessEqual(c["relevancia"], 100)
        self.assertTrue(all(m.startswith("+") for m in c["motivos"]))

    def test_visao_prioriza_tema(self):
        c = classificar("Reforma tributária: IBS e CBS mudam a distribuição de autopeças")
        self.assertGreater(c["relevancia_visoes"]["V01"], c["relevancia"])

    def test_canal_das_montadoras(self):
        c = classificar("Mercedes-Benz revela descontos em peças para linha Sprinter")
        self.assertIn("T21", c["temas"])
        self.assertTrue(c["setorial"])  # tema ancora: entra mesmo vindo de fonte geral
        self.assertGreater(c["relevancia_visoes"]["V02"], c["relevancia"])

    def test_concessionaria_de_rodovia_nao_e_canal_das_montadoras(self):
        self.assertNotIn("T21", classificar("Concessionária de rodovias registra alta no fluxo")["temas"])
        self.assertNotIn("T21", classificar("Varejo aposta no pós-venda para fidelizar clientes")["temas"])

    def test_palavra_parcial_nao_casa(self):
        self.assertNotIn("T20", classificar("Motorista compra bateria", fonte_id="S21")["temas"])


if __name__ == "__main__":
    unittest.main()
