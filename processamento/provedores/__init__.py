"""Provedores de IA do Radar. Cada um expoe a mesma interface:

    classificar(sistema: str, esquema: dict, mensagem: str, max_tokens: int = ...) -> (dict | None, meta: dict)
    testar() -> (ok: bool, mensagem: str)

`meta["status"]` e sempre um destes: ok, recusa, resposta_cortada, json_invalido, sem_credencial,
sem_credito, limite_de_requisicoes, sem_conexao, erro_api_<codigo>.
O resto do Radar nao sabe qual provedor esta em uso.
"""

from __future__ import annotations

from processamento import credenciais

STATUS_QUE_INTERROMPEM = ("sem_credencial", "sem_credito", "limite_de_requisicoes", "sem_conexao")


def obter(provedor: str | None = None):
    provedor = provedor or credenciais.provedor_ativo() or "anthropic"
    if provedor == "gemini":
        from processamento.provedores.gemini import Gemini
        return Gemini()
    if provedor == "anthropic":
        from processamento.provedores.anthropic_claude import AnthropicClaude
        return AnthropicClaude()
    raise ValueError(f"provedor desconhecido: {provedor}")
