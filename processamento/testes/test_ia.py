"""Testes offline da camada de IA e dos provedores (clientes falsos, sem chamar nenhuma API).
Rodar com o ambiente do projeto: .venv/Scripts/python -m unittest discover -s processamento/testes -t ."""

import io
import json
import unittest
import urllib.error
from types import SimpleNamespace

from processamento import ia
from processamento.classificar import Classificador
from processamento.provedores.anthropic_claude import AnthropicClaude
from processamento.provedores.gemini import Gemini

CL = Classificador()
IDS = {t["id"] for t in CL.temas}
NOTICIA = {"id": "N1", "fonte_id": "S21", "titulo": "Mahle alerta sobre manutenção do ar-condicionado em 2026",
           "trecho_interno": "Com 40% da frota sem revisão, a empresa recomenda checar filtros."}
REGRAS = {"setorial": True, "temas": ["T14"], "familias": ["F16"], "relevancia": 55, "versao_regras": "x"}


def resposta(stop="end_turn", corpo=None):
    texto = json.dumps(corpo or {"e_do_setor": True, "temas": ["T14"], "relevancia": 45, "tipo": "fato",
                                 "justificativa": "Sinaliza demanda de filtros: 40% da frota sem revisão."})
    uso = SimpleNamespace(input_tokens=900, output_tokens=120, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(model="claude-opus-5-5", _request_id="req_x", stop_reason=stop, usage=uso,
                           content=[SimpleNamespace(type="text", text=texto)])


class ClienteFalso:
    def __init__(self, r):
        self.chamadas = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._r = r

    def _create(self, **kw):
        self.chamadas.append(kw)
        return self._r


class TestPrompt(unittest.TestCase):
    def test_esquema_restringe_temas_a_taxonomia(self):
        esq = ia.esquema(CL)
        self.assertEqual(set(esq["properties"]["temas"]["items"]["enum"]), IDS)
        self.assertFalse(esq["additionalProperties"])

    def test_sistema_estavel_e_com_todos_os_temas(self):
        s = ia.montar_sistema(CL)
        self.assertEqual(s, ia.montar_sistema(CL))  # sem data/hora: o cache funciona
        self.assertTrue(all(i in s for i in IDS))


class TestAnthropic(unittest.TestCase):
    def test_ok_envia_parametros_certos(self):
        c = ClienteFalso(resposta())
        dados, meta = AnthropicClaude(cliente=c).classificar("sis", ia.esquema(CL), "msg")
        self.assertEqual(meta["status"], "ok")
        kw = c.chamadas[0]
        self.assertEqual(kw["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", kw["betas"])
        self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("thinking", kw)
        self.assertTrue(dados["e_do_setor"])

    def test_recusa_e_corte(self):
        for stop, status in (("refusal", "recusa"), ("max_tokens", "resposta_cortada")):
            self.assertEqual(AnthropicClaude(cliente=ClienteFalso(resposta(stop))).classificar("s", {}, "m")[1]["status"],
                             status)


def gemini_ok(texto, fim="STOP"):
    return {"candidates": [{"content": {"parts": [{"text": texto}]}, "finishReason": fim}],
            "usageMetadata": {"promptTokenCount": 800, "candidatesTokenCount": 90}, "modelVersion": "gemini-x"}


def erro_http(codigo):
    return urllib.error.HTTPError("https://x", codigo, "erro", {}, io.BytesIO(b'{"error":{}}'))


def enviar_fixo(retorno):
    chamadas = []

    def f(metodo, caminho, corpo=None):
        chamadas.append((metodo, caminho, corpo))
        if isinstance(retorno, Exception):
            raise retorno
        return retorno
    return f, chamadas


class TestGemini(unittest.TestCase):
    def test_ok_usa_esquema_e_instrucao_de_sistema(self):
        f, ch = enviar_fixo(gemini_ok('{"e_do_setor": true, "temas": [], "relevancia": 20, "tipo": "fato", '
                                      '"justificativa": "x"}'))
        dados, meta = Gemini(enviar=f).classificar("sis", ia.esquema(CL), "msg")
        self.assertEqual(meta["status"], "ok")
        corpo = ch[0][2]
        self.assertEqual(corpo["systemInstruction"]["parts"][0]["text"], "sis")
        self.assertEqual(corpo["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("enum", json.dumps(corpo["generationConfig"]["responseJsonSchema"]))
        self.assertEqual(meta["uso"]["entrada"], 800)
        self.assertFalse(dados["e_do_setor"] is None)

    def test_erros_viram_status(self):
        for codigo, status in ((402, "sem_credito"), (403, "sem_credencial"), (429, "limite_de_requisicoes"),
                               (400, "erro_api_400")):
            f, _ = enviar_fixo(erro_http(codigo))
            self.assertEqual(Gemini(enviar=f).classificar("s", {}, "m")[1]["status"], status)

    def test_bloqueio_e_corte(self):
        f, _ = enviar_fixo({"promptFeedback": {"blockReason": "SAFETY"}})
        self.assertEqual(Gemini(enviar=f).classificar("s", {}, "m")[1]["status"], "recusa")
        f, _ = enviar_fixo(gemini_ok("{", fim="MAX_TOKENS"))
        self.assertEqual(Gemini(enviar=f).classificar("s", {}, "m")[1]["status"], "resposta_cortada")

    def test_ignora_partes_de_raciocinio(self):
        d = gemini_ok('{"ok": true}')
        d["candidates"][0]["content"]["parts"].insert(0, {"text": "pensando...", "thought": True})
        f, _ = enviar_fixo(d)
        self.assertEqual(Gemini(enviar=f).classificar("s", {}, "m")[0], {"ok": True})


class TestValidacao(unittest.TestCase):
    def base(self, **muda):
        r = {"e_do_setor": True, "temas": ["T14"], "relevancia": 45, "tipo": "fato", "justificativa": "Ok."}
        r.update(muda)
        return ia.validar(r, NOTICIA, REGRAS, IDS)

    def test_numero_da_noticia_passa(self):
        self.assertTrue(self.base(justificativa="40% da frota sem revisão em 2026.")["usar"])

    def test_numero_inventado_bloqueia(self):
        v = self.base(justificativa="Mercado de filtros cresce 12% ao ano.")
        self.assertFalse(v["usar"])
        self.assertTrue(v["alertas"][0].startswith("numero_sem_origem"))

    def test_fora_do_setor_limita_nota_e_marca_divergencia(self):
        v = self.base(e_do_setor=False, relevancia=70)
        self.assertEqual(v["relevancia"], 10)
        self.assertTrue(v["divergencia_regras"])

    def test_nota_fora_da_escala(self):
        v = self.base(relevancia=140)
        self.assertEqual(v["relevancia"], 100)
        self.assertIn("nota_fora_da_escala", v["alertas"])

    def test_tema_inexistente_bloqueia(self):
        self.assertFalse(self.base(temas=["T99"])["usar"])


class TestCandidatas(unittest.TestCase):
    def test_so_setor_ou_duvidosa(self):
        regras = {"A": {"setorial": True, "temas": []}, "B": {"setorial": False, "temas": ["T10"]},
                  "C": {"setorial": False, "temas": []}}
        self.assertEqual(sorted(ia.candidatas({"A": {}, "B": {}, "C": {}}, regras)), ["A", "B"])


if __name__ == "__main__":
    unittest.main()
