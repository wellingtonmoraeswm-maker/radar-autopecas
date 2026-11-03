# Publicar a demonstração do Radar no GitHub

A demonstração é o mesmo painel, **só leitura**, atualizado **todo dia às 06:00 (Brasília)** pelo GitHub Actions e publicado no GitHub Pages. Endereço final: `https://<seu-usuario>.github.io/radar-autopecas/`.

O que roda sozinho, todo dia: coleta das fontes → classificação → IA (Gemini) → resumos da Presidência e do Comercial → testes → site. Arquivo da rotina: `.github/workflows/radar-diario.yml`.

## Uma vez só (cerca de 10 minutos)

### 1. Criar o repositório vazio
Em **github.com/new**:
- **Nome:** `radar-autopecas`
- **Visibilidade:**
  - **Public:** o GitHub Pages é gratuito, mas **o código fica visível** para qualquer pessoa.
  - **Private:** o código fica protegido, mas o Pages com repositório privado exige o plano pago **GitHub Pro**.
- **Não** marque "Add a README" nem ".gitignore": o repositório precisa nascer vazio.

### 2. Enviar o código
Na pasta do projeto (o Claude Code pode fazer por você):
```
git remote add origin https://github.com/<seu-usuario>/radar-autopecas.git
git push -u origin main
```
Na primeira vez, o Windows abre uma janela para você entrar na sua conta do GitHub.

### 3. Cadastrar a chave do Gemini como segredo
No repositório: **Settings → Secrets and variables → Actions → New repository secret**
- **Name:** `GEMINI_API_KEY`
- **Secret:** a chave do Google AI Studio

Recomendado: gere **uma chave nova** para isso. As chaves usadas até agora passaram pelo chat.

### 4. Ligar o GitHub Pages
**Settings → Pages → Build and deployment → Source: GitHub Actions**

### 5. Rodar pela primeira vez
**Actions → Radar diario → Run workflow**. Em cerca de 5 minutos o site está no ar, e o endereço aparece no resumo da execução (etapa "publicar").

## Depois

- **Todo dia às 06:00** a rotina roda sozinha e grava os dados do dia no repositório (commit "Dados de AAAA-MM-DD").
- **Se a IA falhar** (sem crédito, limite), o site sai assim mesmo, com as notas das regras, e a execução mostra um aviso amarelo.
- **Se um teste falhar**, nada é publicado e o GitHub manda e-mail.
- **Incluir fontes, trocar a chave, gerar resumo na hora:** continuam no painel local (`.venv/Scripts/python painel/iniciar.py`). Depois de mudar fontes ou taxonomia no seu computador, faça commit e push para a rotina diária passar a usar.
- **Custo:** GitHub Actions gratuito para repositório público (para privado, 2.000 minutos por mês gratuitos; a rotina usa cerca de 5 por dia). Gemini: algumas dezenas de chamadas por dia.

## O que o site público mostra e o que não mostra

| Mostra | Não mostra |
|---|---|
| Indicadores, resumos, notícias (título, link, nota e resumo próprio), fontes | Texto das notícias, chave de IA, botões de ação, aba Configurações |
