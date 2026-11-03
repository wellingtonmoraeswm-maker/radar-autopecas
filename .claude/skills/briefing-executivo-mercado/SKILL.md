---
name: briefing-executivo-mercado
description: Gera o resumo executivo do Radar Autopeças (Flash de 1 minuto ou Executivo de 3 minutos) para uma visão (Presidência, Comercial) e um período (dia, semana, mês ou datas), a partir das notícias classificadas e dos indicadores calculados, com auditoria automática dos números antes de sair. Acione quando o usuário disser "gera o Flash da semana", "resumo para o presidente", "briefing do comercial de outubro", "o que mudou no mercado nos últimos 7 dias", "prepara o resumo para a reunião", ou quando for preciso mostrar um resumo real ao diretor na descoberta. Não coleta notícias (é da coleta), não classifica (é do processamento) e não muda a taxonomia.
---

# Resumo executivo

**Projeto:** raiz do repositório do Radar. **Comando:** `python -m processamento.briefing` (no Windows, `py`).

| Opção | Valores | Padrão |
|---|---|---|
| `--visao` | ids de `config/visoes.csv` (V01 Presidência, V02 Comercial) | V01 |
| `--versao` | `flash` (3 itens, 1 minuto) · `executivo` (6 itens, 3 minutos) | flash |
| `--periodo` | `dia` · `semana` · `mes` | semana |
| `--de` / `--ate` | AAAA-MM-DD | — |
| `--selecao` | só mostra o que seria enviado à IA, sem chamar a IA | — |

Saída: `saidas/briefings/<data>_<visao>_<versao>.md` (leitura) e `.json` (fatos enviados, resposta, auditoria, modelo, tokens).

## Antes de gerar

1. Dados em dia: `python -m coleta.rodar`, depois `python -m processamento.classificar` e `.venv/Scripts/python -m processamento.ia` (ou `py -m processamento.ia`, se o provedor ativo for o Gemini).
2. Provedor de IA com crédito: `python -m processamento.credenciais testar`.
3. Rodar com `--selecao` e olhar a lista. Se vierem poucas notícias, **diga isso ao usuário** em vez de baixar o corte da visão por conta própria. O corte é decisão do cliente (`relevancia_minima` em `visoes.csv`).

## Como o resumo é montado

1. **Indicadores**: `processamento/indicadores.py` calcula valor, variação no mês e em 12 meses (em % ou p.p., conforme `config/indicadores.csv`). Séries sem ajuste sazonal são comparadas só com o mesmo mês do ano anterior. **A tabela de indicadores do resumo não passa pela IA.**
2. **Notícias**: do período, do setor, ordenadas pela nota da IA (ou das regras, se a IA reprovou) **mais o bônus da visão** para temas prioritários. Ficam as que passam do corte.
3. **IA**: recebe só esses fatos e redige os itens na estrutura fixa (o que aconteceu, o que mudou, por que importa, risco/oportunidade/atenção, o que acompanhar). As referências são uma lista fechada; **os links são colocados pelo código**.
4. **Auditor** (`processamento/auditor.py`, skill `auditor-briefing`): reprovado uma vez, a IA recebe os problemas e tenta de novo; reprovado de novo, o arquivo sai como **BLOQUEADO** e o comando termina com erro.

## Ao apresentar ao usuário

- Mostre o arquivo `.md` e diga se foi **APROVADO** ou **BLOQUEADO**.
- Diga quantas notícias havia no período e quantas passaram do corte (está no rodapé).
- Nunca edite à mão o texto de um resumo aprovado para "melhorar" números. Se algo estiver errado, o problema está nos dados ou no prompt: corrija lá e gere de novo.
- Resumo bloqueado **não** é enviado. Mostre os problemas e investigue.

## Ajustes possíveis

| Quer mudar | Onde |
|---|---|
| Temas prioritários ou corte de uma visão | `config/visoes.csv` |
| Indicadores, unidades, casas decimais, comparação | `config/indicadores.csv` |
| Tamanho das versões | `VERSOES` em `processamento/briefing.py` |
| Tom e regras de redação | `montar_sistema()` em `processamento/briefing.py` (mudar o prompt muda a `versao_prompt` gravada no `.json`) |

## Critério de sucesso

Resumo APROVADO pelo auditor, com cada item ligado a uma fonte clicável, e o leitor da visão consegue dizer o que fazer com cada item.
