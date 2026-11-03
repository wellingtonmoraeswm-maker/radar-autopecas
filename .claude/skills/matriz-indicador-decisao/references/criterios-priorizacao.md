# Critérios de priorização

**Nota = impacto × frequência × viabilidade** (de 1 a 125). O script calcula; esta página explica as escalas.

## Impacto (o que está em jogo na decisão)

| Nota | Significado |
|---|---|
| 5 | Muda a estratégia ou envolve valor alto: abrir filial, entrar ou sair de uma linha, grande compra de importados |
| 4 | Afeta o resultado de uma área inteira no trimestre |
| 3 | Afeta uma família de produtos ou uma região |
| 2 | Ajuste tático, com efeito pequeno |
| 1 | Curiosidade, sem decisão clara |

## Frequência (com que regularidade a decisão acontece)

| Nota | Significado |
|---|---|
| 5 | Semanal ou mais |
| 4 | Mensal |
| 3 | Trimestral |
| 2 | Semestral ou anual |
| 1 | Rara ou única |

## Viabilidade (dá para alimentar com dado confiável?)

| Nota | Significado |
|---|---|
| 5 | Já existe no Radar / Aftermarket Preditivo (BCB, IBGE, ANP, ABCR, Comex SH4, Sindipeças Reposição) |
| 4 | Fonte pública com API ou arquivo estruturado, ainda sem conector |
| 3 | Fonte pública sem estrutura (site, PDF) ou notícias por palavra-chave |
| 2 | Depende de construção difícil ou de fonte instável |
| 1 | Depende de fonte paga ainda não contratada ou de dados do ERP |

## Etapa sugerida (regra aplicada pelo script)

| Condição | Etapa |
|---|---|
| viabilidade ≥ 3 **e** nota ≥ 36 | `MVP` |
| viabilidade ≥ 3 **e** nota < 36 | `Etapa 4` |
| viabilidade = 2 | `Etapa 4` (exige estudo técnico) |
| viabilidade = 1 e o indicador ou a fonte cita ERP, estoque, venda interna ou margem | `Fora do escopo (ERP)` |
| viabilidade = 1 nos demais casos | `Fora do escopo (pago)` |

O limite de 36 equivale, por exemplo, a 4 × 3 × 3: uma decisão de impacto relevante, que acontece todo trimestre, com fonte pública. O diretor pode puxar uma linha para o MVP na sessão 6; nesse caso, preencher a coluna `etapa_override` com o motivo.

**Escopo atual (decisão de 01/11/2026): só dados públicos.** Fontes pagas e dados do ERP ficam fora. As linhas com viabilidade 1 continuam na matriz como registro do que o cliente pediu, para uma evolução futura.
