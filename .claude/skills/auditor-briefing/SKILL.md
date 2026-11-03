---
name: auditor-briefing
description: Confere se um resumo executivo do Radar Autopeças pode sair. Verifica, em código, que todo item cita fontes existentes, que todo número do texto aparece nas fontes daquele item, que os campos obrigatórios estão preenchidos e que o tamanho respeita a versão. Explica um resumo BLOQUEADO e orienta a correção. Acione quando o usuário disser "por que o resumo foi bloqueado?", "audita esse briefing", "esse número está certo?", "confere o resumo antes de mandar", ou quando a briefing-executivo-mercado terminar com BLOQUEADO. Não redige nem reescreve o resumo.
---

# Auditor do resumo

**Código:** `processamento/auditor.py` (função `auditar(resumo, fatos, max_itens)`), chamado automaticamente por `processamento.briefing`.
**Evidência:** o `.json` ao lado de cada resumo em `saidas/briefings/` guarda os fatos enviados, cada tentativa da IA e o resultado da auditoria.

## As regras

| # | Regra | Por quê |
|---|---|---|
| 1 | Todo item tem ao menos uma referência, e todas existem nos fatos enviados | Nada sem fonte |
| 2 | Todo número de um item aparece no texto das referências **daquele item** | Impede número inventado e número "emprestado" de outro fato |
| 3 | Número da manchete aparece em algum fato | A manchete também é afirmação |
| 4 | Campos obrigatórios preenchidos e classificação válida | Estrutura fixa do resumo |
| 5 | Quantidade de itens dentro do limite da versão | Flash é Flash |

Números são comparados em formato brasileiro: `348.745` e `348745` são o mesmo; `5,14` e `5.14` também.

## Quando um resumo é bloqueado

1. Abrir o `.json` correspondente e ler `tentativas[-1].auditoria.problemas`.
2. Para cada problema, achar a causa:
   - **número sem origem** → a IA calculou, arredondou ou trouxe de fora. Ver se o prompt precisa de instrução mais clara (`montar_sistema()` em `briefing.py`). **Nunca** afrouxar o auditor para aceitar o número.
   - **referência inexistente** → normalmente não acontece (as referências são lista fechada no esquema); se acontecer, o provedor ignorou o esquema. Registrar e testar outro modelo.
   - **número do indicador diferente** → conferir `python -m processamento.indicadores` contra a fonte oficial. Se o cálculo estiver errado, o problema é dos dados, não do texto.
3. Gerar de novo. Se continuar bloqueando, relatar ao usuário com os problemas e a hipótese de causa.

## O que o auditor NÃO verifica

Dizer isso ao usuário quando for relevante:
- Se a **interpretação** faz sentido (por que importa, risco ou oportunidade). Isso é julgamento: leitura humana.
- Datas e meses escritos por extenso ("dezembro") só têm o ano conferido.
- Se a notícia original é verdadeira. O auditor garante fidelidade às fontes, não a verdade das fontes.

## Regras

- O auditor só fica mais rígido, nunca mais permissivo, sem decisão explícita do usuário.
- Toda mudança em `auditor.py` vem com teste em `processamento/testes/test_briefing.py`.
