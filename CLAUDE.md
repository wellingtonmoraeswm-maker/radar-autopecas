# Radar Autopeças

Plataforma de inteligência de mercado do aftermarket automotivo para a diretoria de uma distribuidora de autopeças. Cada cliente recebe uma instância própria, nas contas dele.

- Plano do produto: `Plano_Radar_Autopecas.md`
- Roteiro da descoberta: `Roteiro_Descoberta.md`

## Situação

Etapa 1 (descoberta), com a base de coleta pronta: conectores `radar:rss` e `radar:bcb_sgs` funcionando para 7 fontes, classificação determinística das notícias (`python -m processamento.classificar`) e camada de IA que refina essa classificação (`processamento/ia.py`, com dois provedores: Anthropic e Google Gemini; testada offline; chave Gemini cadastrada, mas a conta está sem créditos). Resumo executivo (Flash e Executivo, por visão e período) gerado com auditoria dos números (`python -m processamento.briefing`). Protótipo local do painel funcionando (`painel/`). O painel definitivo, na nuvem do cliente, é da Etapa 3.

**Decisões de 01/11/2026:** usuários principais = presidente e diretor comercial · **só dados públicos** (nada de fonte paga nem ERP) · nuvem padrão Azure + Entra ID na conta do cliente, plano B Supabase + Vercel (confirmar com a TI) · orçamento em aberto · projeto personalizado com propriedade da instância. Detalhes na seção 12 do plano.

O código de coleta e o monitor existentes estão em `../Aftermarket Preditivo/` e serão trazidos para `coleta/` na Etapa 3.

## Mapa do repositório

| Pasta | Conteúdo |
|---|---|
| `config/` | Configuração lida pelo Radar: `fontes.csv`, `visoes.csv`, `indicadores.csv`, `matriz_decisao.csv`, `taxonomia/` (temas, famílias × NCM, entidades, concorrentes) |
| `descoberta/<cliente>/` | Material da Etapa 1 de cada cliente: entrevistas, fichas, matriz |
| `.claude/skills/` | Skills de operação do Radar (vão junto com o repositório) |
| `coleta/` | Conectores (`conectores/`), base comum (`base.py`), executor (`rodar.py`), testes offline (`testes/`) |
| `processamento/` | Classificação por regras (`classificar.py`), refinamento por IA (`ia.py`), provedores de IA (`provedores/`), cadastro de chaves (`credenciais.py`), indicadores (`indicadores.py`), resumo executivo (`briefing.py`), auditor (`auditor.py`) e testes |
| `dados_brutos/`, `dados_processados/`, `saidas/` | Gerados pela coleta, pelo processamento e pelos resumos. Fora do Git (`.gitignore`) |
| `painel/` | Protótipo local do painel (servidor Python sem dependências + HTML/CSS/JS). Abre em http://127.0.0.1:8765 com `.venv/Scripts/python painel/iniciar.py` |
| `.github/workflows/radar-diario.yml` | Rotina diária no GitHub Actions: coleta, IA, resumos, testes e publicação da demonstração no GitHub Pages. Passo a passo em `PUBLICAR.md` |
| `site/` | Gerado por `python -m painel.exportar`: o painel estático, só leitura, publicado no Pages. Fora do Git |
| `app/`, `api/` | Painel definitivo (Next.js, na nuvem do cliente, com login), na Etapa 3 |

## Regras inegociáveis

1. **A IA não calcula números.** Variações, médias, limites e notas são calculados em código. A IA só interpreta o que já está calculado.
2. **Todo número de um resumo existe no banco**, com fonte e data.
3. **Hipótese não é fato:** interpretação aparece marcada como interpretação.
4. **Primeiro guarda o original, depois processa.** Cada item tem a origem registrada.
5. **Três datas por item:** quando aconteceu, quando foi publicado, quando foi coletado.
6. **Licenças:** de notícias, só título, link e resumo próprio. Dados pagos seguem a licença de quem fornece. Números do Sindipeças sempre com "Fonte: Sindipeças", e o PDF nunca fica disponível no Radar.
7. **ERP só em modo de leitura.**
8. **Nenhum indicador entra no painel sem uma linha aprovada em `config/matriz_decisao.csv`.**
9. **Exemplo para o cliente usa `[X]`**, nunca números que pareçam reais sem fonte.
10. **Respeitar robots.txt e termos de uso.** Nunca se passar por navegador para contornar bloqueio.
11. **Nada da Negócio em Ordem** (BrandDNA, outros clientes) nos arquivos de cliente.

## Camada de IA

- Ordem fixa: coleta → `processamento.classificar` (regras) → `processamento.ia` (refino). A IA só recebe o que as regras aceitaram como do setor, mais os casos duvidosos (fonte geral com algum tema).
- A resposta vem em JSON validado por esquema. Os temas são uma lista fechada (`enum`) com os ids da taxonomia, então a IA **não consegue** inventar tema.
- Uma checagem em código bloqueia (`usar=false`) qualquer justificativa com número que não esteja no título ou no trecho da notícia.
- A nota por regras continua gravada ao lado da nota da IA. Divergência sobre "é do setor" fica marcada para revisão.
- **Provedores:** `anthropic` (SDK oficial, `.venv`; padrão `claude-opus-5-5`, esforço `low`, fallback do servidor ligado) e `gemini` (API REST, biblioteca padrão; padrão `gemini-flash-latest`). O resto do Radar não sabe qual está em uso (`processamento/provedores/__init__.py`).
- **Chaves:** `python -m processamento.credenciais cadastrar|ativar|testar|remover|status`. Ficam em `~/.radar-autopecas/credenciais.json`, **fora do repositório e do OneDrive**. A chave é pedida sem aparecer na tela e nunca é exibida inteira. Em produção, variáveis de ambiente do cofre da nuvem têm prioridade (`RADAR_PROVEDOR_IA`, `RADAR_MODELO_IA`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`). A tela de configurações do painel (Etapa 3) usará as mesmas funções.
- Nunca colocar chave no código, nos CSVs, em `.env` dentro do repositório ou em argumento de linha de comando.

## Demonstração pública (GitHub Pages)

- `painel/exportar.py` gera `site/` com as mesmas funções do servidor local. No HTML exportado, `data-modo="estatico"` liga o modo só leitura do `app.js` (lê `dados/*.json`, esconde ações e Configurações).
- Nunca exportar `trecho_interno` das notícias nem o `trecho` dos fatos dos resumos: no site público ficam só título, link, datas, notas e o resumo próprio.
- `dados_processados/` e `saidas/` são versionados (a rotina do GitHub precisa do histórico). `dados_brutos/` fica no cache do Actions.
- Na nuvem, a chave vem do segredo `GEMINI_API_KEY` do repositório.

## Ordem da rotina diária

Use o Python do ambiente do projeto (`.venv/Scripts/python`), que tem o SDK da Anthropic e o `pypdf` (ANIP). Ou use o botão **Atualizar dados** do painel.

1. `.venv/Scripts/python -m coleta.rodar`
2. `.venv/Scripts/python -m processamento.classificar`
3. `.venv/Scripts/python -m processamento.ia` (o provedor ativo vem de `processamento.credenciais`)
4. `.venv/Scripts/python -m processamento.briefing --visao V01` e `--visao V02`

## Convenções

- Configuração em **CSV com `;`**, editável no Excel. Os scripts aceitam UTF-8 ou Windows-1252.
- Scripts usam só a biblioteca padrão do Python, **exceto** a camada de IA (SDK oficial `anthropic`) e o leitor de PDF da ANIP (`pypdf`), num ambiente próprio (`.venv`, ver `requirements.txt`). Comandos da IA: `.venv/Scripts/python -m processamento.ia`.
- Python: no Windows, use `py`; no Linux e no macOS, `python3`. Os comandos das skills aparecem como `python`.
- Datas no formato AAAA-MM-DD. Slugs de cliente em minúsculas, com hífen.

## Skills

| Skill | Para quê |
|---|---|
| `matriz-indicador-decisao` | Descoberta: entrevistas → fichas → matriz priorizada |
| `taxonomia-autopecas` | Temas, famílias × NCM, entidades e concorrentes que alimentam classificação, filtros e alertas |
| `curador-fontes-mercado` | Catálogo de fontes: testar URL, robots.txt, RSS, verificação semanal |
| `construtor-conector` | Criar e consertar conectores no padrão `coleta/base.py` |
| `briefing-executivo-mercado` | Gerar o Flash ou o Executivo de uma visão e período |
| `auditor-briefing` | Explicar e investigar um resumo bloqueado |
