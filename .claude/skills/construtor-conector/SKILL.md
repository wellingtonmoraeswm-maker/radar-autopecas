---
name: construtor-conector
description: Cria e conserta conectores de coleta do Radar Autopeças seguindo o padrão do repositório (coleta/base.py), com guarda do original, três datas, respeito ao robots.txt, teste offline e ensaio real antes de ativar a fonte. Acione quando o usuário disser "cria o conector da fonte X", "essa fonte precisa de conector", "o conector da ANP quebrou", "a fonte mudou de formato", "lê esse site que não tem RSS", "traz a coleta do Aftermarket Preditivo para o Radar", ou quando a curador-fontes-mercado deixar uma fonte como candidata por falta de conector. Não decide se a fonte entra (é da curador-fontes-mercado) e não classifica as notícias (é da taxonomia e do processamento).
---

# Construtor de conectores

**Projeto:** raiz do repositório do Radar.
**Código:** `coleta/base.py` (contrato e utilitários), `coleta/conectores/<nome>.py` (um módulo por conector), `coleta/rodar.py` (executor), `coleta/testes/` (testes offline).
**Comandos** (no Windows, `py` no lugar de `python`):
- `python -m coleta.rodar --ids S20 --ensaio`: coleta de verdade, **sem gravar**, e mostra exemplos
- `python -m coleta.rodar --ids S20`: coleta e grava
- `python -m unittest discover -s coleta/testes -t .`: testes offline

## O contrato

Todo conector é um módulo com **uma função**:

```python
def coletar(fonte: dict, ctx: Contexto) -> Resultado
```

| Regra | Como cumprir |
|---|---|
| Baixar só por `ctx.baixar(url)` | Ele se identifica como RadarAutopecas e **recusa** caminho proibido pelo robots.txt (`ColetaBloqueada`). Nunca usar `urllib`/`requests` direto, nunca trocar o User-Agent. |
| Guardar o original antes de interpretar | `ctx.guardar_bruto(conteudo, "xml")` logo depois de baixar. Conteúdo idêntico não é duplicado. |
| Notícia → `Noticia(url, titulo, publicado_em, ocorrido_em, trecho_interno)` | `trecho_interno` com no máximo 300 caracteres (use `cortar()`), só para classificar, nunca exibido. |
| Série → `Ponto(serie_id, ocorrido_em, valor, unidade, publicado_em)` | `ocorrido_em` = período de referência (`AAAA-MM` para mensal). `serie_id` estável: `<fonte>_<codigo>`. |
| Data desconhecida | `None`. **Nunca inventar** (ex.: não usar a data da coleta como data de publicação). |
| Problema não fatal | `res.avisos.append(...)`, e segue. Problema fatal: levantar exceção com mensagem clara. |
| Sem efeitos colaterais | O conector não grava em `dados_processados/` nem mexe no catálogo. Quem grava é o executor. |

O executor cuida do resto: `coletado_em`, deduplicação de notícias pelo URL normalizado (sem `utm_*`), **revisões** de série (valor diferente para o mesmo período vira nova versão com `revisao_de`), e o registro de cada execução em `execucoes.jsonl`.

## Conectores existentes

| Conector | Serve para |
|---|---|
| `radar:rss` | Qualquer feed RSS 2.0 ou Atom. Com `python -m coleta.rodar --historico DIAS`, segue as páginas do feed (`?paged=2`, padrão WordPress) até a data-limite, com 1 s de pausa entre páginas |
| `radar:bcb_sgs` | Qualquer série do SGS do Banco Central (o código vem da URL) |
| `radar:oficina_brasil` | Portal Oficina Brasil (sem RSS): página inicial + metadados públicos de cada matéria (og:title, og:description, datePublished) |
| `radar:anip_infografico` | Infográfico mensal da ANIP (PDF): manchete e destaques da página 1 viram séries de pneus (acumulado do ano). Precisa de `pypdf` (.venv) |

**Antes de criar um conector novo, veja se um genérico resolve.** Uma fonte RSS nova não precisa de código: é só cadastrar com `conector=radar:rss`.

## Procedimento: conector novo

1. **Ler a linha da fonte** em `config/fontes.csv` e o resultado do `testar` da curador-fontes-mercado. Se o robots.txt bloqueia ou o site tem firewall, **pare**: não existe conector para isso. Proponha `upload` manual.
2. **Baixar uma amostra** com `ctx.baixar` (ou o `testar`) e olhar a estrutura real. Não escrever o parser de memória.
3. **Criar** `coleta/conectores/<nome>.py` a partir de `templates/conector_modelo.py`. Nome em minúsculas, sem acento, descrevendo a **origem** (`fenabrave_pdf`, `anp_vendas`), não o cliente.
4. **Criar o teste offline** em `coleta/testes/test_conectores.py`: um trecho real e pequeno da amostra como fixture, `CtxFalso`, e asserts de pelo menos um item, das datas e dos avisos. Fixture com dado público e curto; nunca colar uma página inteira de notícia.
5. `python -m unittest discover -s coleta/testes -t .` até passar.
6. **Ensaio real:** `python -m coleta.rodar --ids <id> --ensaio`. Conferir com o usuário os exemplos: título, data e valor batem com o site?
7. **Ligar no catálogo:** `conector=radar:<nome>`. A **curador-fontes-mercado** decide se passa para `ativa` (licença confirmada).
8. **Primeira coleta real** sem `--ensaio`, e rodar de novo para confirmar `0 novos` (deduplicação funcionando).

## Procedimento: conector quebrado

1. Ler `dados_processados/execucoes.jsonl` (último erro da fonte) e o último arquivo de `dados_brutos/<id>/`.
2. Rodar `--ensaio` e comparar o conteúdo novo com o bruto antigo: mudou a URL, o formato ou o layout?
3. Atualizar a fixture do teste com o formato novo **mantendo** o teste do formato antigo, se a fonte puder alternar.
4. Ensaio, coleta real, e avisar a curador-fontes-mercado para tirar a fonte de `quebrada`.

## Migração do Aftermarket Preditivo

As fontes S06 a S10 ainda usam `aftermarket:*` (código em `../Aftermarket Preditivo/src/coleta.py` e `sindipecas_mensal.py`). Para trazer cada uma: reescrever no contrato acima (sem pandas e sem requests enquanto a regra da biblioteca padrão valer), comparar a saída com a do Aftermarket (mesmos valores nos mesmos meses) e só então trocar o `conector` no catálogo. A validação do Sindipeças (6 linhas, tolerância de 0,15 p.p.) precisa vir junto.

## Regras

- Nunca contornar robots.txt, login, firewall ou limite de requisições. Erro 429: esperar e tentar mais tarde, no máximo uma vez por execução.
- Nada de credenciais no código. Fonte que exige chave lê de variável de ambiente, e a chave fica no cofre da nuvem do cliente.
- Notícias: só título, link, datas e `trecho_interno` curto.
- Endereços com acento são codificados por `url_codificada()` em `coleta/base.py`; não codificar de novo no conector.
- Conector que lê arquivo grande (PDF) deve consultar `ler_series_existentes()` ou `urls_coletadas()` para não baixar de novo o que já leu.
- Documento sem data de publicação (PDF): só a edição mais recente vira notícia; as anteriores entram só como série.

## Critério de sucesso

Teste offline passando, ensaio conferido pelo usuário, primeira coleta real gravada e a segunda com `0 novos`.
