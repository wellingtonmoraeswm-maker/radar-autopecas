"""Testes do cadastro de chaves, numa pasta temporaria (nunca toca o cadastro real)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from processamento import credenciais as cr

CHAVE = "chave-de-teste-0000000000000000wxyz"
VARIAVEIS = ("RADAR_PROVEDOR_IA", "RADAR_MODELO_IA", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")


class TestCredenciais(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pasta = Path(self.tmp.name)
        self.patches = [mock.patch.object(cr, "PASTA", pasta),
                        mock.patch.object(cr, "ARQUIVO", pasta / "credenciais.json"),
                        mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k not in VARIAVEIS},
                                        clear=True)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_cadastrar_ativa_e_guarda(self):
        cr.cadastrar("gemini", CHAVE + "\n", "gemini-flash-latest")
        self.assertEqual(cr.provedor_ativo(), "gemini")
        self.assertEqual(cr.chave("gemini"), CHAVE)
        self.assertEqual(cr.modelo("gemini"), "gemini-flash-latest")

    def test_status_nunca_mostra_a_chave(self):
        cr.cadastrar("gemini", CHAVE)
        texto = "\n".join(cr.status())
        self.assertNotIn(CHAVE, texto)
        self.assertIn("...wxyz", texto)

    def test_variavel_de_ambiente_tem_prioridade(self):
        cr.cadastrar("gemini", CHAVE)
        os.environ["GEMINI_API_KEY"] = "outra-chave-0000000000000000000"
        os.environ["RADAR_PROVEDOR_IA"] = "anthropic"
        self.assertEqual(cr.chave("gemini"), "outra-chave-0000000000000000000")
        self.assertEqual(cr.provedor_ativo(), "anthropic")

    def test_remover_troca_o_ativo(self):
        cr.cadastrar("anthropic", CHAVE)
        cr.cadastrar("gemini", CHAVE)
        cr.remover("gemini")
        self.assertEqual(cr.provedor_ativo(), "anthropic")
        self.assertIsNone(cr.chave("gemini"))

    def test_rejeita_chave_invalida_e_provedor_desconhecido(self):
        with self.assertRaises(ValueError):
            cr.cadastrar("gemini", "curta")
        with self.assertRaises(ValueError):
            cr.cadastrar("openai", CHAVE)


if __name__ == "__main__":
    unittest.main()
