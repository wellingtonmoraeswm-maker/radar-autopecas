# Radar Autopeças: plano consolidado

**Data:** 01/11/2026 · **Situação:** plano, versão 1. Nada foi construído ainda além do que já existe em `Projetos/Aftermarket Preditivo/`.
**Origem:** junção de dois planos (o plano de produto com 12 seções e o plano de arquitetura e pacote com skills), mais o que já está pronto no projeto Aftermarket Preditivo.

> **Rótulos usados:** **[EXISTE]** já está funcionando no Aftermarket Preditivo · **[A VERIFICAR]** afirmação sobre fonte externa que precisa ser confirmada na Etapa 2 · **[DECISÃO]** precisa da resposta do cliente.

---

## 1. Tese do produto

Não é um agregador de notícias com IA. É uma ferramenta para apoiar as decisões do diretor de uma distribuidora nacional. O painel é só a interface.

**Todo dia, o Radar responde a cinco perguntas:**
1. O que está acontecendo no mercado de autopeças?
2. Quais indicadores estão subindo ou caindo?
3. Que mudanças podem ser oportunidade ou ameaça?
4. Como isso pode afetar uma distribuidora?
5. O que merece a atenção da diretoria agora?

**Regra fundadora:** antes de cada indicador entrar no painel, ele precisa ter uma linha na **matriz indicador → decisão** (seção 9). Se nenhuma decisão usa o indicador, ele não entra.

---

## 2. O que o Radar acompanha (seis blocos)

| Bloco | Conteúdo | Fontes principais | Frequência real | Situação |
|---|---|---|---|---|
| **A. Frota** | Tamanho por UF e município, idade, combustível, marca e modelo, ano de fabricação | Senatran (arquivos mensais) [A VERIFICAR o formato]; relatório de frota circulante do Sindipeças | Mensal / anual | Novo |
| **B. Indústria de autopeças** | Faturamento (nominal e real), reposição, segmentos, emprego, investimentos, balança comercial | Sindipeças (relatório conjuntural mensal); Anuário Abipeças/Sindipeças [A VERIFICAR o conteúdo e o acesso] | Mensal / anual | **[EXISTE]** reposição total, leve e pesada, com versões guardadas |
| **C. Veículos novos** | Emplacamentos, produção, categorias, marcas, eletrificados | Fenabrave, Anfavea | Mensal | Novo |
| **D. Comércio exterior e câmbio** | Importação por NCM, país de origem, valor e quantidade, exportações, câmbio | Comex Stat, BCB | Mensal / diário (câmbio) | **[EXISTE]** parcial (Comex SH4, câmbio) |
| **E. Reposição e oficinas** | Movimento das oficinas, canais de compra, falta de peças, marcas lembradas | CINAU / Grupo Oficina Brasil (IGD, Pulso do Aftermarket) [A VERIFICAR o acesso e o custo] | Mensal / pesquisas | **Fora do escopo atual** (dados pagos). As notícias públicas do portal Oficina Brasil entram no Bloco F |
| **F. Notícias e tendências** | Concorrentes, fusões e aquisições, legislação e tributação (IBS/CBS), eletrificação, abastecimento, lançamentos | Imprensa setorial, associações, comunicados, Google News por palavra-chave | Diária | Novo |
| **+ Sinais antecedentes** | Atividade, crédito, diesel, fluxo de rodovias, preços de peças e de conserto | BCB, IBGE (PMC, IPCA), ANP, ABCR | Mensal | **[EXISTE]** monitor IAR, com índices leve, pesada e total |

**Ressalvas metodológicas que o painel precisa mostrar:**
- Frota **registrada** não é frota **circulante**.
- Sindipeças Reposição mede o **sell-in** dos fabricantes associados, não o consumo final.
- O monitor antecedente indica **direção**, não prova faturamento (ver `Monitor_Antecedente_Resultados.md`).
- Cada indicador aparece com a **periodicidade real**. Nada sugere que "está tudo atualizado hoje".

---

## 3. Módulos da ferramenta

| # | Módulo | O que faz | No MVP? |
|---|---|---|---|
| 1 | **Painel principal** | Cartões de indicadores, séries históricas, sinais de oportunidade e risco, últimas coletas, data da última atualização de cada item. O usuário escolhe, oculta e organiza os widgets. | Sim |
| 2 | **Gerenciador de fontes** (protótipo pronto: aba Fontes do painel) | Adicionar, excluir, ativar e desativar fontes, definir tema, frequência e confiabilidade, testar a conexão, ver o histórico. Aceita RSS, API, site, CSV/Excel, PDF e fonte contratada. | Sim (RSS, API e upload de arquivo) |
| 3 | **Personalização e visões** | Categorias e subcategorias selecionáveis, salvas como visões: Diretoria, Comercial, Compras e abastecimento, Linha pesada, Linha leve, Tendências | Sim (visões pré-montadas e edição simples) |
| 4 | **Resumo executivo** | Periodicidade (diária, semanal ou mensal), tempo de leitura e estilo. Três versões: **Flash** (1 min), **Executivo** (3 min), **Estratégico** (5 min). | Sim |
| 5 | **Pesquisa histórica** | Filtro de período (24h, 7d, 30d, semana, mês, trimestre, ano, personalizado) e perguntas em linguagem natural sobre indicadores e notícias | Filtro sim; perguntas com escopo limitado |
| 6 | **Alertas** | Limites configuráveis: importação de um NCM, câmbio, emplacamentos, concorrente monitorado, legislação, falta de peças. Por e-mail; WhatsApp e Teams depois. | Básicos |
| 7 | **Configurações** | Cadastro da chave de IA pelo próprio usuário (escolher provedor: Anthropic ou Google Gemini; colar a chave; escolher o modelo; botão "testar chave", que avisa também quando a conta está sem crédito; trocar ou remover). A chave nunca aparece inteira na tela e fica no cofre de segredos da nuvem do cliente. | Sim (já existe por linha de comando: `processamento/credenciais.py`) |

**Ao incluir uma fonte:** o usuário cola a URL, o sistema detecta o formato, faz uma coleta de teste e mostra uma prévia antes de ativar. Se o formato não for suportado, a tela diz isso claramente. Uma URL não vira conector automaticamente; cada formato novo exige um conector específico.

**Estrutura fixa de cada item do resumo:**
1. O que aconteceu
2. O que mudou em relação ao período anterior
3. Por que isso importa para uma distribuidora
4. Oportunidade ou risco
5. O que acompanhar
6. Fonte, com link

---

## 4. Regras inegociáveis de dados e IA

1. **A IA não calcula números.** Variações, médias, limites e comparações são feitos em código, de forma determinística. A IA só interpreta resultados que já estão no banco.
2. **Cada número do resumo precisa existir no banco.** Uma checagem automática compara os números do texto com os valores calculados e bloqueia o envio se algum não bater.
3. **Hipótese não é fato.** Uma interpretação aparece marcada como interpretação.
4. **Primeiro guarda o original, depois processa.** Cada item tem a origem registrada: fonte, URL, arquivo bruto e versão.
5. **Três datas por item:** quando aconteceu, quando foi publicado e quando foi coletado. A pesquisa histórica filtra pela data correta.
6. **Licenças:** de notícias, guardar só título, link e resumo próprio. Dados pagos e pesquisas contratadas obedecem à licença de quem fornece. Ser dono do software não dá direito sobre os dados de terceiros.
7. **ERP só em modo de leitura**, quando chegar a Etapa 5.

---

## 5. Propriedade e hospedagem

**Modelo:** uma instância dedicada, na nuvem da própria distribuidora. Nada de programa instalado só no PC do diretor, e nada de SaaS hospedado por você nesta fase.

**Cláusulas de contrato:**
1. O repositório do código fica na organização Git da empresa.
2. A hospedagem, o banco e os backups ficam em contas da empresa.
3. O domínio é registrado em nome da empresa.
4. As chaves de API (incluindo a de IA) são da empresa.
5. A empresa recebe acesso de administrador e a documentação técnica.
6. A propriedade intelectual fica definida no contrato: a **instância** é da empresa; os **componentes reutilizáveis** (conectores, skills, modelo do repositório) são licenciados por você, o que permite replicar o produto depois.
7. Implantação e manutenção são feitas por você, mediante contrato.

---

## 6. O produto leva as skills junto

O produto é **um único repositório**. Quem recebe o código recebe também o manual operacional que o Claude Code executa.

```
radar-autopecas/
├── app/                 painel (Next.js + TypeScript)
├── api/                 regras e endpoints (Python + FastAPI)
├── coleta/              conectores e rotinas (absorve o código do Aftermarket Preditivo)
├── config/
│   ├── fontes.yaml          fontes iniciais
│   ├── taxonomia.yaml       temas, NCM/SH, linhas leve e pesada, concorrentes
│   └── matriz_decisao.csv   indicador → decisão (editável no Excel)
├── .claude/
│   ├── skills/          as skills de operação (seção 8)
│   └── agents/          agente "operador do Radar"
├── CLAUDE.md            regras do projeto (seção 4) e mapa do repositório
└── LEIA-ME.md           instalação e uso
```

- **O funcionamento diário** (coleta, cálculo, resumo, alertas) roda sozinho no servidor, chamando a API de IA pelo código. O diretor não precisa de Claude Code.
- **As skills** servem a quem opera e mantém a ferramenta: incluir um conector, consertar uma fonte quebrada, gerar um briefing especial, implantar uma nova instância.
- **Para replicar:** com o 2º ou 3º cliente, as skills viram um plugin do Claude Code versionado por você, com marketplace privado. Cada instância continua sendo do cliente.

---

## 7. Arquitetura técnica

| Componente | Recomendação | Observação |
|---|---|---|
| Interface | Next.js + TypeScript | Já há um molde em `prospeccao-kit-aluno/painel` |
| Gráficos | ECharts ou Recharts, um componente para todas as séries | Ver `Avaliacao_Camada_Painel.md` |
| BI para analistas | Power BI do cliente, se houver; senão Metabase gratuito, só leitura, fora do app | Não é incorporado no Radar. Ver `Avaliacao_Camada_Painel.md` |
| Backend | Python + FastAPI | Reaproveita o Python do Aftermarket Preditivo |
| Banco | PostgreSQL + pgvector | O pgvector cobre a busca semântica sem um serviço a mais |
| Arquivos originais | Azure Blob ou S3 | Guarda PDFs, CSVs e o bruto de cada coleta |
| Agendamento | Agendador da própria nuvem no MVP; Prefect quando passar de ~30 fontes | Não colocar um orquestrador antes de precisar |
| IA | API Claude: modelo pequeno para classificar, modelo maior para resumos | Chave da empresa |
| Login | Microsoft Entra ID (padrão); plano B: login do Supabase | Ver seção 12 |
| Nuvem | Azure na conta do cliente (padrão); plano B: Supabase + Vercel | Ver seção 12. Confirmar com a TI na Etapa 1 |

**Fluxo:** fontes → coleta programada → guarda do bruto → padronização, eliminação de duplicatas e validação → cálculo determinístico dos indicadores → classificação e nota de relevância por visão → resumo e alertas → painel, pesquisa e e-mail.

---

## 8. Competências e skills

O plano de produto lista nove competências e cinco perfis técnicos. Na prática: **você** cobre a parte de negócio (distribuição, planejamento, estoque); **Claude Code com as skills** cobre boa parte da engenharia; **um consultor externo** valida a metodologia dos indicadores. Duas competências seguem pedindo uma pessoa responsável: segurança e conformidade (LGPD, credenciais) e a revisão de arquitetura de nuvem antes de entrar em produção.

### O que já existe
`sindipecas-coletor-mensal`, `monitor-reposicao-mensal`, `prospeccao-de-leads` (molde Next.js + Supabase), agentes `pesquisador-mercado` e `dev-saas-dashboard`, skills `dataviz`, `frontend-design`, `competitor-profiling`, `deep-research`, `claude-api`, `schedule`, `spec`.

### O que falta

| # | Skill | Competência coberta | Para que serve | Etapa |
|---|---|---|---|---|
| 1 | `matriz-indicador-decisao` | Inteligência de mercado, BI | Conduz a entrevista de descoberta e gera `matriz_decisao.csv` (editável no Excel): decisão → pergunta → indicador → fonte → limite de alerta | 1 |
| 2 | `taxonomia-autopecas` (referência) | Inteligência de mercado | Temas, sinônimos, NCM/SH por família de peças, linhas leve e pesada, concorrentes. Base para classificação, filtros e alertas. | 1 |
| 3 | `curador-fontes-mercado` | Engenharia de dados, governança | Cadastra a fonte, testa a coleta, avalia licença e confiabilidade e registra no catálogo. Toda semana confere quais fontes quebraram. | 2 |
| 4 | `construtor-conector` | Engenharia de dados | Cria um conector novo (API, RSS, site, PDF, planilha) seguindo o padrão do repositório, com teste e guarda do bruto | 2–3 |
| 5 | `coletor-indicadores-setoriais` | Engenharia de dados, BI | Amplia a coleta atual para Senatran, Fenabrave, Anfavea e Comex por NCM e país | 3 |
| 6 | `briefing-executivo-mercado` | Engenharia de IA | Gera o Flash, o Executivo e o Estratégico na estrutura fixa, com link em cada afirmação | 3 |
| 7 | `auditor-briefing` | Engenharia de IA, governança | Confere se cada número e cada data do resumo existe no banco; marca afirmações sem fonte; bloqueia o envio | 3 |
| 8 | `implantacao-instancia-cliente` | Nuvem, DevOps, segurança | Cria a infraestrutura nas contas do cliente, configura segredos, backup e monitoramento, e entrega o checklist de passagem de propriedade | 3 |
| 9 | `integracao-erp-leitura` | Engenharia de dados | Mapeia vendas, estoque, compras, margem e pedidos não atendidos, sempre em modo de leitura, e cruza com os indicadores de mercado | 5 |

As skills 1, 2, 6 e 7 são as que mais protegem o valor do produto, porque garantem que a ferramenta seja relevante e confiável.

---

## 9. Matriz indicador → decisão (modelo)

| Decisão do diretor | Pergunta | Indicador | Fonte | Gatilho de alerta |
|---|---|---|---|---|
| Ampliar ou reduzir o mix de linha pesada | A demanda de pesados está acelerando? | IAR pesada; diesel ANP; fluxo de pesados ABCR | [EXISTE] | IAR pesada vira de sinal por 2 meses seguidos |
| Antecipar compras importadas | O custo de reposição vai subir? | Câmbio; importação NCM 8708 por país | BCB, Comex | Câmbio +5% em 30 dias |
| Abrir ou ampliar uma filial regional | Onde a frota velha está crescendo? | Frota por UF e ano de fabricação | Senatran | [DECISÃO] |
| Proteger a participação contra um concorrente | O concorrente está se movendo? | Notícias da lista monitorada | Bloco F | Qualquer menção de fusão, aquisição ou expansão |
| Rever o mix de eletrificados | Em quanto tempo isso afeta a reposição? | Participação de eletrificados nos emplacamentos e na frota | Fenabrave, Senatran | [DECISÃO] |

*Preencher com o diretor na Etapa 1. Os limites acima são só exemplos.*

---

## 10. Etapas

| Etapa | Objetivo | Entregáveis | Skills usadas |
|---|---|---|---|
| **1. Descoberta** (1–2 sem.) | Saber quais decisões a presidência e a diretoria comercial tomam | Entrevistas com presidente, diretor comercial e TI (compras e planejamento opcionais); matriz de decisão; confirmação da nuvem | 1, 2 |
| **2. Validação das fontes** (2 sem.) | Confirmar que dá para coletar com confiança | Catálogo de 8 a 12 fontes públicas, testes de coleta, análise de licença e robots.txt | 3, 4 |
| **3. MVP** (4–6 sem.) | Primeira versão em uso | Login, painel, indicadores dos blocos A–D e F, notícias, filtro de período, resumo Flash e Executivo com auditoria, gestão básica de fontes, alertas básicos, implantação na nuvem do cliente | 4, 5, 6, 7, 8 |
| **4. Autonomia** (3–4 sem.) | O usuário configura tudo sozinho | Visões salvas, painéis personalizados, pesquisas salvas, versão Estratégica, alertas configuráveis, busca em linguagem natural mais ampla | 3, 6 |
| **5. Dados internos** (fora do escopo atual) | Comparar o mercado com o desempenho da distribuidora | Integração com o ERP em modo de leitura: vendas, estoque, compras, margem, pedidos não atendidos | 9 |
| **6. Inteligência avançada** | Antecipar | Anomalias, tendência por linha de produto, risco de abastecimento, cenários. O monitor e a previsão do Aftermarket Preditivo entram aqui. | — |

**Corte do MVP em relação ao plano de produto:** monitoramento detalhado de concorrentes, versão Estratégica do resumo e busca ampla ficam para a Etapa 4. O Bloco E (pago) está fora do escopo atual, pela decisão de usar só dados públicos. O objetivo é colocar o MVP em uso em ~6 semanas e medir o uso real.

---

## 11. Como medir se está funcionando

| Critério | Meta |
|---|---|
| Rastreabilidade | 100% dos indicadores com fonte e metodologia; 0 números sem origem no resumo (auditor-briefing) |
| Atualização | Todo item mostra a data de referência e a periodicidade |
| Confiabilidade | Fonte quebrada detectada em até 24h |
| Uso | O diretor abre o painel pelo menos 3 vezes por semana, ou lê o resumo pelo menos 4 vezes por semana |
| Economia de tempo | O resumo substitui parte da pesquisa manual (pergunta mensal ao diretor) |
| **Utilidade** | **Número de decisões ou investigações iniciadas a partir do Radar** (registrado com um botão "isso virou ação" no painel) |

---

## 12. Decisões tomadas (01/11/2026)

| # | Decisão | Resposta | O que muda no projeto |
|---|---|---|---|
| 1 | Usuário principal | **Presidente e diretor comercial** | Duas visões iniciais: **Presidência** (mercado, risco, concorrência, tributação, resumo Flash) e **Comercial** (frota por região, emplacamentos, linhas, concorrentes, preços). A descoberta prioriza as sessões 1 e 3. Compras e planejamento viram entrevistas opcionais. |
| 2 | Nível de inteligência | **Só dados públicos** | Bloco E (CINAU) e o Anuário pago saem do escopo. Etapa 5 (ERP) fica como evolução futura, fora do desenho atual. Na matriz, viabilidade 1 = "fora do escopo atual". O LGPD fica simples: o único dado pessoal é o cadastro dos usuários. |
| 3 | Nuvem e login | **Recomendação abaixo**, a confirmar com a TI | — |
| 4 | Orçamento | **Em aberto**: estruturar o produto primeiro | Nada é contratado até a Etapa 3. A arquitetura evita qualquer licença paga obrigatória. |
| 5 | Modelo comercial | **Projeto personalizado com propriedade da instância** | Seção 5 vale como está. O repositório-modelo e as skills são componentes seus, licenciados; a instância é do cliente. |

### Recomendação de nuvem e login

**Critério principal:** usar o que a TI da distribuidora já administra. Quem vai ser dono precisa saber operar, e o login corporativo precisa ser o mesmo que os diretores já usam.

**Padrão recomendado (se a empresa usa Microsoft 365, o mais provável numa distribuidora nacional):**

| Peça | Serviço Azure |
|---|---|
| App (Next.js) e API (FastAPI) | Azure Container Apps |
| Coletas agendadas | Container Apps Jobs (agendamento cron) |
| Banco | Azure Database for PostgreSQL, Flexible Server, com a extensão pgvector |
| Arquivos brutos | Blob Storage |
| Segredos (chave da IA, conexões) | Key Vault |
| Login | **Microsoft Entra ID**, com o mesmo usuário e MFA do e-mail corporativo. Quando alguém sai da empresa, perde o acesso automaticamente. |
| E-mail do resumo | Microsoft Graph, saindo de uma caixa da empresa |

**Por que:** a conta é do cliente, o login é o corporativo, os custos entram na fatura que a TI já acompanha e não há fornecedor novo para aprovar.

**Plano B (se a empresa não usa Microsoft ou a TI não quer administrar Azure):** Supabase (PostgreSQL com pgvector, login, armazenamento e agendamento) e Vercel para o app, **as duas contas no e-mail da empresa**. É mais simples de operar e você já conhece pela prospecção. Login por e-mail com link mágico ou Google Workspace.

**O que mantém as duas opções abertas:** tudo roda em contêiner, o banco é PostgreSQL padrão e o login fica isolado num módulo. Trocar de nuvem não exige reescrever o produto.

**Com só dados públicos e dois usuários,** a segurança se resume a login corporativo com MFA, segredos no cofre, backup diário do banco e um usuário só de leitura para o BI.

## 13. Próximos entregáveis

1. **PRD** com a matriz indicador → decisão.
2. **Mapa de fontes:** formato, periodicidade, acesso, licença e custo, com as afirmações [A VERIFICAR] resolvidas.
3. **Protótipo visual e arquitetura técnica**, incluindo a estrutura do repositório com as skills.

> Não começar programando. Começar pelas decisões que o diretor toma.
