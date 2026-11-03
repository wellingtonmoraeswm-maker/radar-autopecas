---
name: matriz-indicador-decisao
description: Conduz a descoberta do Radar Autopeças e produz a matriz indicador → decisão, que define o que entra no painel. Prepara o kit de entrevistas para um cliente, transforma anotações ou transcrições de entrevista em fichas de decisão, consolida e prioriza a matriz (impacto × frequência × viabilidade), valida com script e verifica se a Etapa 1 pode ser encerrada. Acione quando o usuário disser "prepara a descoberta do cliente X", "tenho as anotações da entrevista com o diretor", "registra essa entrevista", "monta a matriz de decisão", "prioriza os indicadores", "o que entra no MVP", "a descoberta está pronta?". Não coleta dados de mercado, não cadastra fontes e não desenha o painel; isso é de outras skills do Radar.
---

# Matriz indicador → decisão

**Projeto:** a raiz do repositório do Radar Autopeças (a pasta que contém esta `.claude/`).
**Saídas:** `descoberta/<cliente>/`, sendo `<cliente>` um slug em minúsculas e com hífen (ex.: `distribuidora-x`).
**Script:** `python .claude/skills/matriz-indicador-decisao/scripts/validar_matriz.py descoberta/<cliente>/matriz_decisao.csv`. Usa só a biblioteca padrão do Python. No Windows, troque `python` por `py` (ver `CLAUDE.md`).

## Por que esta skill existe

Sem a matriz, o Radar vira uma coleção de gráficos. A regra do produto é: **nenhum indicador entra no painel sem uma decisão do cliente que o use.** A matriz é a única porta de entrada. Ela também alimenta os alertas (gatilhos), a taxonomia (concorrentes e temas) e a lista de fontes que a Etapa 2 vai validar.

## Modos

Identifique em qual modo o usuário está. Se não estiver claro, pergunte uma vez.

### Modo 1: preparar a descoberta

Entrada: nome do cliente e, se houver, o que já se sabe (porte, linhas, regiões, ERP, quem são os entrevistados).

1. Criar `descoberta/<cliente>/` com `fichas/`, `entrevistas/` e `kit/`.
2. Gerar `kit/agenda.md` a partir de `references/roteiro.md`, seção 2, com os nomes reais dos entrevistados quando informados.
3. Gerar `kit/roteiros.md`: copiar os roteiros por sessão de `references/roteiro.md` e **ajustar ao cliente** (ex.: tirar a linha pesada se ele não atua nela, citar as regiões dele). Não inventar fatos sobre o cliente. O que for suposição vai marcado como `[CONFIRMAR]`.
4. Gerar `kit/cartoes_indicadores.md` a partir de `references/indicadores-candidatos.md`, já filtrado para o cliente.
5. Gerar `kit/exemplo_resumo.md` a partir do modelo em `references/roteiro.md`, seção 6. **Os números ficam como `[X]`.** Nunca preencher com valores que pareçam reais.
6. Copiar `templates/matriz_decisao.csv` (só o cabeçalho) para `descoberta/<cliente>/matriz_decisao.csv`.
7. Mostrar ao usuário a lista "Antes das entrevistas" (roteiro, seção 3) como checklist.

### Modo 2: registrar uma entrevista

Entrada: anotações, transcrição, áudio transcrito ou fotos das anotações de uma sessão.

1. Salvar o material bruto **sem editar** em `entrevistas/AAAA-MM-DD_<sessao>.md`. Ex.: `2026-11-10_diretoria.md`. O original sempre fica guardado.
2. Extrair cada **decisão concreta** mencionada e criar uma ficha em `fichas/Dnn_<slug>.md` usando `templates/ficha-decisao.md`.
3. Para cada ficha:
   - **Origem obrigatória:** sessão, entrevistado e o trecho que sustenta a ficha (citação curta ou paráfrase fiel).
   - O que o entrevistado **disse** vai num campo; o que **você deduziu** (indicador sugerido, fonte provável) vai marcado como `[SUGESTÃO]`.
   - Notas de impacto e frequência: só preencher se o entrevistado deu base para isso. Caso contrário, `[A DEFINIR]`.
   - Viabilidade: usar a escala de `references/criterios-priorizacao.md`.
4. Acrescentar as fichas como linhas novas em `matriz_decisao.csv`, com `status=candidata`.
5. Registrar à parte, em `entrevistas/achados_<sessao>.md`:
   - concorrentes citados (vão para `config/taxonomia`);
   - fontes que o cliente já usa e em quais confia ou desconfia;
   - preferências de formato (canal, horário, periodicidade);
   - respostas de TI (sessão 5): nuvem, login, repositório, ERP, LGPD, ponto focal.
6. Relatar ao usuário: quantas decisões saíram, quais ficaram com `[A DEFINIR]` e **quais perguntas do roteiro não foram respondidas** (para retomar numa próxima conversa).

**Não transformar desejo em decisão.** "Seria legal ver a frota por estado" não é decisão. Só vira ficha se estiver ligada a algo que a pessoa decide ("decidimos onde abrir filial"). Desejos soltos vão para `achados` como "é bom saber".

### Modo 3: consolidar e priorizar

1. Juntar decisões duplicadas (a mesma decisão citada por pessoas diferentes): uma linha só, com todas as origens.
2. Rodar o validador:
   ```
   python .claude/skills/matriz-indicador-decisao/scripts/validar_matriz.py descoberta/<cliente>/matriz_decisao.csv
   ```
   Ele confere os campos obrigatórios, calcula a **nota** e a **etapa sugerida** e gera `matriz_decisao.md` ordenada por nota. **Não calcule nota nem etapa à mão**; o script é a fonte.
3. Corrigir os erros que o script apontar e rodar de novo até sair sem erros.
4. Preparar `validacao.md` para a sessão 6 (roteiro, seção 9): as 8 a 15 decisões do topo, o esboço da primeira visão (lista dos indicadores sugeridos para o MVP, agrupados por bloco) e as decisões pendentes de orçamento (linhas com viabilidade 1).

### Modo 4: fechar a Etapa 1

1. Depois da sessão 6, atualizar `status` para `aprovada` ou `descartada` conforme o que o diretor decidiu. Ajustar as notas que ele corrigiu.
2. Rodar o validador de novo. Ele verifica se há pelo menos 8 decisões aprovadas.
3. Passar pelo checklist de `references/roteiro.md`, seção 10, item por item, dizendo o que está atendido e o que falta, com o arquivo que comprova cada item.
4. Se tudo estiver atendido, copiar a matriz final para `config/matriz_decisao.csv` (é o arquivo que o Radar lê) e listar para o usuário as fontes que a Etapa 2 precisa validar (coluna `fonte` das linhas aprovadas, sem repetição).

## Regras

- **Nada inventado.** Toda decisão tem origem numa entrevista. Se o usuário pedir para "completar a matriz com decisões típicas de distribuidora", é permitido **sugerir** linhas, mas elas entram com `origem=SUGESTÃO` e `status=candidata`, e só passam a `aprovada` depois de confirmadas pelo cliente.
- **Exemplos sem dados reais.** Em qualquer material para o cliente, número de mercado aparece como `[X]`, a não ser que venha de uma fonte verificada e citada.
- **A matriz é do cliente.** Nada de nome de outro cliente, de dados de outra distribuidora ou do BrandDNA da Negócio em Ordem nos arquivos de `descoberta/`.
- **O CSV é a fonte da verdade.** `matriz_decisao.md` é gerado pelo script; nunca editar o `.md` à mão.
- O CSV pode ser aberto e editado no Excel. O script aceita `;` ou `,` como separador e UTF-8 ou Windows-1252.

## Arquivos desta skill

| Arquivo | Uso |
|---|---|
| `references/roteiro.md` | Agenda, roteiros por sessão, exercícios, exemplo de resumo, sessão de validação, critérios de encerramento |
| `references/indicadores-candidatos.md` | Lista de indicadores por bloco, para o exercício dos cartões |
| `references/criterios-priorizacao.md` | Escalas de impacto, frequência e viabilidade e a regra da etapa sugerida |
| `templates/ficha-decisao.md` | Modelo de ficha |
| `templates/matriz_decisao.csv` | Cabeçalho da matriz |
| `scripts/validar_matriz.py` | Validação, cálculo da nota e da etapa, geração do `.md` |

## Critério de sucesso

O cliente aprovou pelo menos 8 decisões. Cada uma tem origem, pergunta, indicador, fonte, gatilho e nota calculada pelo script. O validador sai sem erros. O usuário sabe exatamente quais fontes a Etapa 2 precisa validar.
