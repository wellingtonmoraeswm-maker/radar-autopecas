"""Provedor Google Gemini, pela API REST (generativelanguage.googleapis.com). So biblioteca padrao.

A chave vai no cabecalho x-goog-api-key, nunca na URL.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from processamento import credenciais

BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_TOKENS = 4000
TIMEOUT = 90


class Gemini:
    nome = "gemini"

    def __init__(self, enviar=None):
        self.modelo = credenciais.modelo(self.nome)
        self._enviar = enviar or self._http  # substituivel nos testes

    def _http(self, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
        chave = credenciais.chave(self.nome)
        if not chave:
            raise PermissionError("sem chave")
        pedido = urllib.request.Request(
            f"{BASE}/{caminho}", method=metodo,
            data=json.dumps(corpo).encode() if corpo is not None else None,
            headers={"x-goog-api-key": chave, "Content-Type": "application/json"})
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
            return json.load(r)

    @staticmethod
    def _status_http(exc: urllib.error.HTTPError) -> str:
        if exc.code in (401, 403):
            return "sem_credencial"
        if exc.code == 402:
            return "sem_credito"
        if exc.code == 429:
            return "limite_de_requisicoes"
        return f"erro_api_{exc.code}"

    def classificar(self, sistema: str, esquema: dict, mensagem: str,
                    max_tokens: int = MAX_TOKENS) -> tuple[dict | None, dict]:
        meta = {"provedor": self.nome, "modelo": self.modelo}
        corpo = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": mensagem}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": esquema,
                                 "maxOutputTokens": max_tokens},
        }
        try:
            d = self._enviar("POST", f"models/{self.modelo}:generateContent", corpo)
        except PermissionError:
            return None, {**meta, "status": "sem_credencial"}
        except urllib.error.HTTPError as exc:
            detalhe = exc.read()[:300].decode("utf-8", "ignore") if exc.fp else ""
            return None, {**meta, "status": self._status_http(exc), "detalhe": detalhe}
        except (urllib.error.URLError, TimeoutError):
            return None, {**meta, "status": "sem_conexao"}

        uso = d.get("usageMetadata", {})
        meta.update(modelo_respondeu=d.get("modelVersion"), request_id=d.get("responseId"),
                    uso={"entrada": uso.get("promptTokenCount", 0), "saida": uso.get("candidatesTokenCount", 0),
                         "raciocinio": uso.get("thoughtsTokenCount", 0), "cache_lido": uso.get("cachedContentTokenCount", 0)})
        if d.get("promptFeedback", {}).get("blockReason"):
            return None, {**meta, "status": "recusa", "detalhe": d["promptFeedback"]["blockReason"]}
        candidatos = d.get("candidates") or []
        if not candidatos:
            return None, {**meta, "status": "recusa", "detalhe": "sem candidatos"}
        fim = candidatos[0].get("finishReason")
        meta["stop_reason"] = fim
        if fim == "MAX_TOKENS":
            return None, {**meta, "status": "resposta_cortada"}
        if fim in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"):
            return None, {**meta, "status": "recusa"}
        texto = "".join(p.get("text", "") for p in candidatos[0].get("content", {}).get("parts", [])
                        if not p.get("thought"))
        try:
            return json.loads(texto), {**meta, "status": "ok"}
        except json.JSONDecodeError:
            return None, {**meta, "status": "json_invalido"}

    def testar(self) -> tuple[bool, str]:
        try:
            self._enviar("GET", f"models/{self.modelo}")
        except PermissionError:
            return False, "nenhuma chave cadastrada"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False, f"modelo {self.modelo} nao existe para esta chave"
            return False, f"chave recusada (HTTP {exc.code})"
        except urllib.error.URLError:
            return False, "sem conexao"
        # Listar modelos e de graca; uma chamada minima confirma se ha credito.
        resposta, meta = self.classificar("Responda em JSON.", {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                                                 "required": ["ok"]}, "ok?")
        if meta["status"] == "sem_credito":
            return False, "chave valida, mas a conta esta SEM CREDITOS (recarregue no Google AI Studio)"
        if meta["status"] != "ok":
            return False, f"chave valida, mas a chamada de teste falhou: {meta['status']} {meta.get('detalhe', '')[:150]}"
        return True, "chave valida, modelo disponivel e com credito"
