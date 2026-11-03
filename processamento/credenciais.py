"""Cadastro das chaves de IA do Radar (provedor ativo, chave e modelo de cada provedor).

Uso (na raiz do repositorio):
    python -m processamento.credenciais status
    python -m processamento.credenciais cadastrar gemini [--modelo gemini-flash-latest]
    python -m processamento.credenciais cadastrar anthropic [--modelo claude-opus-5-5]
    python -m processamento.credenciais ativar gemini
    python -m processamento.credenciais testar [gemini|anthropic]
    python -m processamento.credenciais remover gemini

`cadastrar` pede a chave sem mostrar na tela (ou le de uma linha na entrada padrao). A chave nunca
vai para argumento de linha de comando, para nao ficar no historico do terminal.

Onde fica: fora do repositorio e fora do OneDrive, em ~/.radar-autopecas/credenciais.json, so para
esta maquina. Em producao, as variaveis de ambiente (vindas do cofre da nuvem do cliente) tem
prioridade: RADAR_PROVEDOR_IA, RADAR_MODELO_IA, GEMINI_API_KEY, ANTHROPIC_API_KEY.
A tela de configuracao do painel (Etapa 3) usara estas mesmas funcoes.
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PASTA = Path(os.environ.get("RADAR_PASTA_CREDENCIAIS", Path.home() / ".radar-autopecas"))
ARQUIVO = PASTA / "credenciais.json"
PROVEDORES = {
    "anthropic": {"variavel": "ANTHROPIC_API_KEY", "modelo": "claude-opus-5-5"},
    "gemini": {"variavel": "GEMINI_API_KEY", "modelo": "gemini-flash-latest"},
}


def _ler() -> dict:
    if not ARQUIVO.exists():
        return {"provedor_ativo": None, "provedores": {}}
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def _gravar(dados: dict) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    temporario = ARQUIVO.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(ARQUIVO)
    try:
        os.chmod(ARQUIVO, 0o600)  # efetivo em Linux/macOS; no Windows vale a pasta do usuario
    except OSError:
        pass


def mascarar(chave: str | None) -> str:
    return f"...{chave[-4:]}" if chave and len(chave) > 8 else "(nenhuma)"


def provedor_ativo() -> str | None:
    return os.environ.get("RADAR_PROVEDOR_IA") or _ler().get("provedor_ativo")


def chave(provedor: str) -> str | None:
    return os.environ.get(PROVEDORES[provedor]["variavel"]) or _ler()["provedores"].get(provedor, {}).get("chave")


def modelo(provedor: str) -> str:
    return (os.environ.get("RADAR_MODELO_IA") if provedor_ativo() == provedor else None) \
        or _ler()["provedores"].get(provedor, {}).get("modelo") or PROVEDORES[provedor]["modelo"]


def cadastrar(provedor: str, valor: str, nome_modelo: str | None = None, ativar: bool = True) -> None:
    if provedor not in PROVEDORES:
        raise ValueError(f"provedor desconhecido: {provedor} (use {', '.join(PROVEDORES)})")
    valor = valor.strip()
    if len(valor) < 20 or any(c.isspace() for c in valor):
        raise ValueError("chave com formato invalido")
    dados = _ler()
    atual = dados["provedores"].get(provedor, {})
    dados["provedores"][provedor] = {
        "chave": valor,
        "modelo": nome_modelo or atual.get("modelo") or PROVEDORES[provedor]["modelo"],
        "cadastrada_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    if ativar or not dados.get("provedor_ativo"):
        dados["provedor_ativo"] = provedor
    _gravar(dados)


def ativar(provedor: str) -> None:
    dados = _ler()
    if provedor not in dados["provedores"] and not os.environ.get(PROVEDORES[provedor]["variavel"]):
        raise ValueError(f"cadastre a chave de {provedor} antes de ativar")
    dados["provedor_ativo"] = provedor
    _gravar(dados)


def remover(provedor: str) -> None:
    dados = _ler()
    dados["provedores"].pop(provedor, None)
    if dados.get("provedor_ativo") == provedor:
        dados["provedor_ativo"] = next(iter(dados["provedores"]), None)
    _gravar(dados)


def status() -> list[str]:
    ativo = provedor_ativo()
    linhas = [f"arquivo: {ARQUIVO}", f"provedor ativo: {ativo or '(nenhum)'}"]
    for p, spec in PROVEDORES.items():
        origem = "variavel de ambiente" if os.environ.get(spec["variavel"]) else "arquivo"
        c = chave(p)
        linhas.append(f"  {'*' if p == ativo else ' '} {p:<10} chave {mascarar(c)}"
                      + (f" ({origem})" if c else "") + f"  modelo {modelo(p)}")
    return linhas


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if not args or args[0] not in ("status", "cadastrar", "ativar", "testar", "remover"):
        print(__doc__)
        return 2
    acao, resto = args[0], args[1:]
    try:
        if acao == "status":
            print("\n".join(status()))
        elif acao == "cadastrar":
            provedor = resto[0]
            nome_modelo = resto[resto.index("--modelo") + 1] if "--modelo" in resto else None
            valor = getpass.getpass(f"Chave de {provedor} (nao aparece na tela): ") if sys.stdin.isatty() \
                else sys.stdin.readline()
            cadastrar(provedor, valor, nome_modelo)
            print(f"Chave de {provedor} cadastrada ({mascarar(valor.strip())}) e ativada. "
                  f"Teste com: python -m processamento.credenciais testar")
        elif acao == "ativar":
            ativar(resto[0])
            print(f"Provedor ativo: {resto[0]}")
        elif acao == "remover":
            remover(resto[0])
            print(f"Chave de {resto[0]} removida desta maquina.")
        elif acao == "testar":
            from processamento.provedores import obter
            provedor = resto[0] if resto else provedor_ativo()
            if not provedor:
                print("Nenhum provedor cadastrado.")
                return 1
            ok, mensagem = obter(provedor).testar()
            print(f"{provedor} ({modelo(provedor)}): {mensagem}")
            return 0 if ok else 1
    except (IndexError, ValueError) as exc:
        print(f"[ERRO] {exc or 'faltou o nome do provedor'}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
