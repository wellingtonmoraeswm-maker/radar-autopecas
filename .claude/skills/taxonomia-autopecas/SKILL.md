---
name: taxonomia-autopecas
description: Mantém a taxonomia do Radar Autopeças, que alimenta a classificação de notícias, os filtros do painel e os alertas. São quatro tabelas em config/taxonomia/: temas e palavras-chave, famílias de peças × NCM, entidades do setor e concorrentes monitorados. Acione quando o usuário disser "adiciona o concorrente X", "inclui o tema Y", "essa notícia deveria cair em Z", "monta a lista de concorrentes do cliente", "puxa os concorrentes da descoberta", "qual NCM é de amortecedor", "valida a taxonomia", "testa a classificação dessa manchete". Não cadastra fontes de coleta (é da curador-fontes-mercado) e não monta a matriz de decisão (é da matriz-indicador-decisao).
---

# Taxonomia do aftermarket

**Projeto:** raiz do repositório do Radar (a pasta que contém esta `.claude/`).
**Arquivos:** `config/taxonomia/temas.csv`, `familias_ncm.csv`, `entidades.csv`, `concorrentes.csv`. São CSV com `;`, editáveis no Excel.
**Script:** `python .claude/skills/taxonomia-autopecas/scripts/taxonomia.py` (no Windows, `py`). Só biblioteca padrão.

## Por que esta skill existe

Sem um vocabulário comum, cada notícia é classificada de um jeito e os filtros e alertas não batem com o que o diretor espera. A taxonomia é o dicionário do Radar:
- **temas** dizem em que assunto uma notícia cai, e quais palavras levam a esse assunto;
- **famílias × NCM** ligam a linguagem do comercial ("amortecedor") ao código que o Comex Stat entende (8708.80);
- **entidades** dizem quem é fonte oficial ou associação;
- **concorrentes** dizem de quem o diretor quer saber cada movimento.

A palavra-chave serve como **pré-filtro determinístico**, usado por `processamento/classificar.py`: uma notícia de fonte geral só é considerada do setor se acionar uma **âncora** (tema com `ancora=sim`, família de peças, associação do setor ou concorrente). A IA classifica depois, mas só pode usar temas que existem em `temas.csv`.

## Estrutura das tabelas

| Arquivo | Colunas | Regras |
|---|---|---|
| `temas.csv` | id; tema; tema_pai; palavras_chave; excluir; linha; ativo; ancora; observacao | `id` no formato `Tnn`. Palavras separadas por `\|`. `tema_pai` vazio ou um id existente. `linha` = leve / pesada / moto / ambas. `ativo` = sim / nao. `ancora` = sim quando o tema, sozinho, prova que a notícia é do setor (ex.: Oficinas); nao para temas de contexto (Câmbio, Economia, Logística). |
| `familias_ncm.csv` | id; familia; termos; linha; ncm; descricao_ncm; verificado; observacao | `id` `Fnn`. `termos` = como o comercial e a imprensa chamam a peça, separados por `\|`. NCM com 4, 6 ou 8 dígitos, com ou sem pontos, vários separados por `\|`. `verificado` = sim só depois de conferir no Comex Stat. |
| `entidades.csv` | id; nome; sigla; tipo; site; blocos; verificado; observacao | `id` `Enn`. `tipo` = associação / governo / pesquisa / imprensa / empresa. |
| `concorrentes.csv` | id; nome; apelidos; tipo; regioes; linhas; monitorar; origem; observacao | `id` `Cnn`. `origem` obrigatória: de onde veio (ex.: "2026-11-10 diretoria"). `monitorar` = sim / nao. |

## Procedimentos

### Adicionar ou alterar um item

1. Ler o CSV correspondente antes de mexer.
2. Usar o próximo id livre. **Nunca reaproveitar o id** de um item removido: os itens antigos já classificados apontam para ele. Para tirar um tema de uso, marque `ativo=nao`.
3. Palavras-chave: escreva como aparecem nas notícias, com acento. O script compara sem acento e sem diferenciar maiúsculas.
4. Rodar `python .claude/skills/taxonomia-autopecas/scripts/taxonomia.py validar` e corrigir até sair sem erros.
5. Reclassificar: `python -m processamento.classificar` (a mudança na taxonomia muda a versão das regras e reclassifica sozinha) e conferir com `--mostrar` se o resultado melhorou. Rodar os testes: `python -m unittest discover -s processamento/testes -t .`.

**Cuidado com palavras genéricas como âncora:** "lançamento" casava com palestra de marketing; foi trocada por "lançamento de veículo". Uma palavra âncora precisa ser específica do setor.

### Montar os concorrentes a partir da descoberta

1. Ler `descoberta/<cliente>/entrevistas/achados_*.md` e `descoberta/<cliente>/fichas/`.
2. Para cada concorrente citado, criar uma linha com `origem` = sessão e entrevistado. Apelidos e grafias diferentes (nome fantasia, razão social, sigla) vão em `apelidos`, separados por `|`.
3. **Não incluir concorrentes que o cliente não citou.** Se o usuário pedir sugestões, apresente-as em texto e só grave as que ele confirmar, com `origem=sugerido e confirmado por <quem>`.

### Testar a classificação

```
python .claude/skills/taxonomia-autopecas/scripts/taxonomia.py testar "manchete ou trecho da notícia"
```

Mostra quais temas, famílias, entidades e concorrentes o texto aciona, com a palavra que acionou cada um. Use para:
- conferir se uma manchete real cai onde deveria;
- encontrar palavras genéricas demais (que acionam tudo) e passar para `excluir` ou deixar mais específicas;
- explicar ao usuário por que um item caiu num tema.

Se a manchete não acionou nenhum tema e deveria, proponha a palavra-chave que falta e teste de novo.

### Conferir NCM

Os códigos de `familias_ncm.csv` começaram com `verificado=nao`. Antes de usar uma família num alerta ou num indicador aprovado na matriz:
1. Conferir o código e a descrição na NCM vigente ou no Comex Stat.
2. Ver a observação: rolamentos, juntas, correias e instrumentos incluem uso industrial. O dado de importação dessas famílias **não é só automotivo** e o painel precisa avisar isso.
3. Marcar `verificado=sim` e registrar na observação a data e onde conferiu.

## Regras

- **O CSV é a fonte da verdade.** A IA não cria temas "na hora" para classificar uma notícia. Se faltar um tema, ele é proposto, aprovado e gravado aqui.
- **Uma notícia pode ter vários temas.** O id do tema fica gravado no item classificado.
- Nada de dados de outro cliente em `concorrentes.csv`.
- `verificado=sim` exige registro de onde e quando foi conferido.

## Critério de sucesso

O validador sai sem erros. Os concorrentes citados na descoberta estão todos na tabela, com origem. Dez manchetes reais do setor, testadas com `testar`, caem nos temas que o usuário espera.
