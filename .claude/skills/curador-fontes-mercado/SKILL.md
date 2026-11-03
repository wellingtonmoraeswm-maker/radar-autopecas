---
name: curador-fontes-mercado
description: Mantém o catálogo de fontes do Radar Autopeças (config/fontes.csv). Testa uma URL nova (formato, RSS, robots.txt, resposta), cadastra a fonte com tema, frequência, confiabilidade e licença, verifica toda semana quais fontes quebraram e decide entre ativar, pausar ou descartar. Acione quando o usuário disser "adiciona essa fonte", "testa esse site", "esse portal tem RSS?", "quais fontes quebraram?", "verifica as fontes", "desativa a fonte X", "por que essa fonte foi descartada?", ou na Etapa 2 do projeto (validação das fontes). Não escreve o conector (é da construtor-conector) e não cria temas (é da taxonomia-autopecas).
---

# Curadoria de fontes

**Projeto:** raiz do repositório do Radar (a pasta que contém esta `.claude/`).
**Catálogo:** `config/fontes.csv` (separador `;`, editável no Excel).
**Código:** `coleta/catalogo.py` (o mesmo usado pela aba **Fontes** do painel). **Atalho da skill:** `python .claude/skills/curador-fontes-mercado/scripts/fontes.py` (no Windows, `py`).

**Pelo painel** (aba Fontes), o usuário testa uma URL, inclui a fonte, pausa, reativa ou exclui. Excluir marca como `descartada` com o motivo; a linha nunca é apagada.

| Comando | O que faz |
|---|---|
| `validar` | Confere colunas, ids, valores permitidos, entidades e temas existentes, fonte ativa sem conector |
| `testar <url>` | Baixa a URL, checa o robots.txt, detecta o formato, procura RSS em páginas HTML e mostra exemplos de itens do feed |
| `verificar [--ids S01,S02] [--gravar]` | Testa as fontes ativas, candidatas e quebradas. Com `--gravar`, registra data e resultado e marca como `quebrada` a fonte ativa que falhou |

## Por que esta skill existe

Adicionar uma URL não significa conseguir coletar dela. Cada fonte precisa passar por quatro perguntas antes de entrar: **responde? em que formato? o site permite coleta automatizada? a licença permite o uso?** E fontes quebram sem avisar (já aconteceu com ABCR e ANP). O painel precisa saber disso antes do diretor.

## Colunas do catálogo

`id; nome; entidade; tipo; url; metodo; formato; frequencia; blocos; temas; escopo; confiabilidade; licenca; status; conector; ultima_verificacao; resultado_verificacao; observacao`

| Coluna | Valores |
|---|---|
| `id` | `Snn`, nunca reaproveitado |
| `entidade` | id de `config/taxonomia/entidades.csv`, ou vazio |
| `tipo` | api, rss, site, arquivo, pdf, upload, contratada |
| `formato` | json, rss, csv, xlsx, pdf, html, xml |
| `frequencia` | diaria, semanal, mensal, trimestral, anual, eventual: a frequência **real** de publicação |
| `temas` | ids de `temas.csv`, separados por `\|` |
| `escopo` | **setorial** (tudo o que publica é do setor, ex.: O Mecânico) ou **geral** (precisa de âncora no texto para a notícia contar, ex.: Novo Varejo) |
| `confiabilidade` | **A** órgão oficial ou associação com metodologia publicada · **B** imprensa especializada · **C** agregador ou fonte sem metodologia |
| `licenca` | o que é permitido (ex.: "dados abertos", "citar a fonte", "só título, link e resumo próprio", "a confirmar") |
| `status` | candidata → ativa → (pausada / quebrada) · descartada |
| `conector` | nome do conector que coleta a fonte; obrigatório para `ativa` |

## Procedimentos

### Adicionar uma fonte

1. Rodar `testar <url>`.
2. Interpretar o resultado:
   - **robots.txt BLOQUEADO** → não cadastrar como ativa. Registrar como `descartada`, com o motivo. Procurar alternativa (feed do próprio veículo, dado aberto oficial, serviço licenciado).
   - **HTTP 401/403 ou firewall** ("Not Acceptable", mod_security) → o site recusa acesso automatizado. **Não tentar contornar** (trocar o agente para se passar por navegador, por exemplo). Registrar e propor download manual (tipo `upload`) ou contato com a entidade.
   - **HTML com feed encontrado** → cadastrar a URL do **feed**, com tipo e formato `rss`. Testar o feed também.
   - **HTML sem feed** → precisa de conector de site. Fica `candidata` até a skill `construtor-conector` resolver.
3. Preencher a linha com o próximo id livre, `status=candidata`. Confiabilidade e licença **não podem ficar vazias**; se não souber a licença, use "a confirmar".
4. Rodar `validar`.
5. Só passar para `ativa` quando existir conector testado. A licença precisa estar confirmada para uma fonte ativa (o validador avisa).

### Verificação semanal

1. `verificar --gravar`.
2. Para cada falha, relatar ao usuário: fonte, o que falhou, desde quando (`ultima_verificacao`), quais indicadores e decisões da `config/matriz_decisao.csv` dependem dela.
3. Causas comuns: URL mudou (ex.: arquivo da ANP muda de nome na virada do ano), site novo, firewall novo, fonte parou de publicar.
4. Uma fonte `quebrada` que voltou a responder **não volta sozinha para `ativa`**: confira o conector primeiro.

### Descartar ou pausar

- `pausada`: problema temporário ou decisão do usuário. Mantém o histórico coletado.
- `descartada`: não serve (bloqueio, licença, irrelevância). **Nunca apagar a linha**: a observação registra o motivo e evita testar de novo.

## Regras

- **Respeitar robots.txt e termos de uso.** O agente do Radar se identifica como `RadarAutopecas`. Nunca se passar por navegador para driblar bloqueio.
- **Licença de notícias:** guardar só título, link, data e resumo próprio. Nunca o texto integral.
- **Fontes pagas** entram como `contratada` e só ficam ativas com contrato e credenciais **do cliente**.
- O catálogo é do cliente: nada de credenciais no CSV. Elas vão para o cofre de segredos da nuvem do cliente.
- A confiabilidade da fonte aparece no painel ao lado de cada item.

## Critério de sucesso

O validador sai sem erros. Toda fonte ativa tem conector, licença confirmada e verificação recente sem falha. Toda fonte descartada tem o motivo registrado.
