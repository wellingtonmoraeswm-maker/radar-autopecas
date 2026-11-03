# Radar Autopeças

Inteligência de mercado do aftermarket automotivo para a diretoria de distribuidoras de autopeças.

## Situação atual

Etapa 1: descoberta. Este repositório ainda não tem o painel; tem o plano, o roteiro de entrevistas, a configuração inicial e as skills de operação.

## O que tem aqui

- `Plano_Radar_Autopecas.md`: o plano completo do produto.
- `Roteiro_Descoberta.md`: como conduzir as entrevistas da Etapa 1.
- `config/`: matriz de decisão e taxonomia do setor, em CSV (abra no Excel, separador `;`).
- `.claude/skills/`: rotinas que o Claude Code executa para operar o Radar.

## Requisitos

- Python 3.11 ou mais recente (no Windows, comando `py`).
- Claude Code, para usar as skills. Não é necessário para ler os documentos nem editar a configuração.

## Como abrir o painel

```
.venv/Scripts/python painel/iniciar.py
```

Depois abra http://127.0.0.1:8765 no navegador. O painel só funciona nesta máquina. Abas: Painel (indicadores, resumo e destaques), Notícias, Resumos, Fontes e Configurações (chave de IA).

## Como usar as skills

Abra esta pasta no Claude Code e peça, por exemplo:

- "Prepara a descoberta do cliente distribuidora-x"
- "Registra essa entrevista" (cole as anotações)
- "Monta a matriz de decisão"
- "Adiciona o concorrente X na taxonomia"
- "Valida a taxonomia"
