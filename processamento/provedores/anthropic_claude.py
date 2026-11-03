"""Provedor Anthropic (API Claude), pelo SDK oficial `anthropic` (ambiente .venv)."""

from __future__ import annotations

import json
import os

from processamento import credenciais

MAX_TOKENS = 4000  # inclui o raciocinio do modelo; a resposta em si e curta


class AnthropicClaude:
    nome = "anthropic"

    def __init__(self, cliente=None):
        self.modelo = credenciais.modelo(self.nome)
        self.esforco = os.environ.get("RADAR_ESFORCO_IA", "low")
        self._cliente = cliente

    def _obter_cliente(self):
        if self._cliente is None:
            import anthropic
            chave = credenciais.chave(self.nome)
            # Sem chave cadastrada, o SDK procura ANTHROPIC_API_KEY ou o perfil do `ant auth login`.
            self._cliente = anthropic.Anthropic(api_key=chave) if chave else anthropic.Anthropic()
        return self._cliente

    def classificar(self, sistema: str, esquema: dict, mensagem: str,
                    max_tokens: int = MAX_TOKENS) -> tuple[dict | None, dict]:
        import anthropic

        meta = {"provedor": self.nome, "modelo": self.modelo, "esforco": self.esforco}
        try:
            r = self._obter_cliente().beta.messages.create(
                model=self.modelo,
                max_tokens=max_tokens,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
                output_config={"effort": self.esforco, "format": {"type": "json_schema", "schema": esquema}},
                messages=[{"role": "user", "content": mensagem}],
            )
        except anthropic.AuthenticationError:
            return None, {**meta, "status": "sem_credencial"}
        except anthropic.RateLimitError:
            return None, {**meta, "status": "limite_de_requisicoes"}
        except anthropic.APIStatusError as exc:
            return None, {**meta, "status": f"erro_api_{exc.status_code}", "detalhe": str(exc.message)[:200]}
        except anthropic.APIConnectionError:
            return None, {**meta, "status": "sem_conexao"}
        except TypeError as exc:  # o SDK so descobre a falta de credencial na hora do envio
            if "authentication" not in str(exc):
                raise
            return None, {**meta, "status": "sem_credencial"}

        meta.update(modelo_respondeu=r.model, request_id=r._request_id, stop_reason=r.stop_reason,
                    uso={"entrada": r.usage.input_tokens, "saida": r.usage.output_tokens,
                         "cache_lido": r.usage.cache_read_input_tokens or 0})
        if r.stop_reason == "refusal":
            return None, {**meta, "status": "recusa"}
        if r.stop_reason == "max_tokens":
            return None, {**meta, "status": "resposta_cortada"}
        texto = next((b.text for b in r.content if b.type == "text"), "")
        try:
            return json.loads(texto), {**meta, "status": "ok"}
        except json.JSONDecodeError:
            return None, {**meta, "status": "json_invalido"}

    def testar(self) -> tuple[bool, str]:
        import anthropic
        try:
            self._obter_cliente().models.retrieve(self.modelo)
        except anthropic.AuthenticationError:
            return False, "chave recusada"
        except anthropic.NotFoundError:
            return False, f"modelo {self.modelo} nao disponivel para esta chave"
        except anthropic.APIConnectionError:
            return False, "sem conexao"
        except TypeError:
            return False, "nenhuma chave cadastrada"
        return True, "chave valida e modelo disponivel"
