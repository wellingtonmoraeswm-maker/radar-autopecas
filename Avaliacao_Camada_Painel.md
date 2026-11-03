# Avaliação: Metabase × Superset × painel próprio

**Data:** 01/11/2026 · **Para:** decisão de arquitetura da Etapa 3 · **Situação:** recomendação. Ainda precisa de um teste prático e da resposta da TI do cliente.

## 1. A pergunta certa

Ferramenta de BI resolve **gráfico de série histórica e exploração livre de dados**. A maior parte do valor do Radar está em outra coisa. Separando os módulos do plano:

| Módulo do plano | O que é na prática | BI resolve? |
|---|---|---|
| 1. Painel principal: cartões e gráficos | ~15 a 25 séries mensais (sai da matriz de decisão) | **Sim** |
| 1. Painel principal: notícias, sinais, "última atualização" | Feed classificado, com fonte e três datas | Mal (vira uma tabela) |
| 2. Gerenciador de fontes | Cadastro, teste de conexão, histórico | Não |
| 3. Personalização e visões | O diretor escolhe os cartões, sem montar consulta | Parcial: editar painel de BI é tarefa de analista, não de diretor |
| 4. Resumo executivo | Texto gerado, auditado, com links | Não |
| 5. Pesquisa por período e por pergunta | Filtro de datas + busca em notícias e séries | Filtro sim; busca não |
| 6. Alertas | Limites da matriz + notícias de concorrente | Só os alertas numéricos, e no Metabase gratuito de forma limitada |

**Conclusão:** um BI cobriria cerca de um terço do produto, e justamente a parte mais barata de construir. As partes que diferenciam o Radar (fontes, taxonomia, resumo auditado, alertas por notícia, visões simples para o diretor) precisam ser feitas sob medida de qualquer jeito.

## 2. Comparação

| Critério | Metabase (gratuito) | Apache Superset | Painel próprio (Next.js + biblioteca de gráficos) |
|---|---|---|---|
| Licença | AGPL v3 | Apache 2.0 | Seu código, cedido ao cliente |
| Efeito da licença na cessão | Sem problema se o cliente usar sem alterar o código do Metabase | Sem restrição | Sem restrição |
| Embutir no app | Só incorporação estática, com filtros travados e o selo "Powered by Metabase". Incorporação interativa, SSO SAML/JWT e permissão por linha só nos planos pagos. | SDK de incorporação com token de convidado, gratuito | Nativo |
| Login corporativo (Entra ID) | Pago (SAML/JWT); no gratuito, só Google e LDAP | Via OAuth do Flask AppBuilder (configurar e testar) | O que a nuvem do cliente oferecer |
| Português | Bom | Parcial | Total |
| Operação | Simples (um contêiner) | Pesada (Python, Redis, Celery para relatórios e alertas) | Média (faz parte do app) |
| Exploração livre por analistas | **Excelente** | Excelente | Não (e não deveria tentar) |
| Experiência do diretor | Cara de ferramenta de BI | Cara de ferramenta de BI | Feita para ele |
| Custo de construir os gráficos | Quase zero | Baixo | Baixo: são poucas séries, todas no mesmo formato (data, valor) |

Fontes sobre o Metabase: blogs de terceiros que divergem nos preços. **Confirmar em metabase.com/pricing antes de citar valores ao cliente.**

## 3. Recomendação: híbrido em duas camadas

1. **O Radar (Next.js) é a experiência do diretor:** painel, notícias, resumo, alertas, visões, gerenciador de fontes. Os gráficos são feitos com uma biblioteca (ECharts ou Recharts) lendo a API do Radar. Como todas as séries têm o mesmo formato, **um componente de gráfico serve para todos os indicadores**. A matriz de decisão diz quais aparecem.
2. **Uma ferramenta de BI fica ao lado, para os analistas** (planejamento, compras), conectada ao mesmo PostgreSQL **por um usuário só de leitura**, sem incorporação no app. Ela atende "quero cruzar essa série com aquela" sem você construir um editor de consultas.
   - **Se o cliente já usa Power BI** (comum em distribuidora nacional): usar o Power BI. O cliente já paga e já sabe usar.
   - **Se não usa:** Metabase gratuito, num contêiner na nuvem do cliente.
   - **Superset só se** a TI exigir Apache 2.0 ou quiser incorporação gratuita. O custo de operação não compensa no início.

**O que se ganha:** o diretor tem uma experiência simples e própria; os analistas têm BI completo de graça ou com uma ferramenta que já usam; e nenhuma funcionalidade do produto fica refém de plano pago.

**O que se perde:** os 15 a 25 gráficos do Radar precisam ser programados. Isso é pouco trabalho, porque é um componente reutilizado.

## 4. Antes da Etapa 3

- [ ] **Na entrevista de TI**, perguntar se usam Power BI ou outra ferramenta de BI, com quantas licenças, e quem administra.
- [ ] **Protótipo de validação** (Etapa 1, sessão 6): um Streamlit de um dia com 3 ou 4 séries do Aftermarket Preditivo, só para o diretor reagir. É descartável e não vira produto.
- [ ] **Teste prático de meio dia:** subir o Metabase em Docker apontando para uma cópia dos dados do Aftermarket Preditivo e ver se os analistas do cliente o usariam.
- [ ] Confirmar preços e a licença do Metabase no site oficial.

## Fontes consultadas

- [Metabase pricing 2026 (Coefficient)](https://coefficient.io/metabase-pricing)
- [Metabase no Vendr](https://www.vendr.com/marketplace/metabase)
- [DashboardFox × Metabase](https://dashboardfox.com/vs-metabase/)
- [Superset: documentação de incorporação](https://superset.apache.org/user-docs/using-superset/embedding)
- [Superset Embedded SDK (README)](https://apache.googlesource.com/superset/+show/HEAD/superset-embedded-sdk/README.md)
