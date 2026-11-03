"""Exporta o painel como site estatico, so leitura, para a demonstracao publica (GitHub Pages).

Uso (na raiz do repositorio):
    python -m painel.exportar            gera site/ (index.html, app.js, estilo.css, dados/*.json)
    python -m painel.exportar --dias 90  janela de noticias exportadas (padrao 90 dias)

Usa as MESMAS funcoes do servidor local (painel/servidor.py), entao a demonstracao mostra exatamente o
que o painel mostra. O que fica de fora de proposito:
- acoes (atualizar, gerar resumo, incluir/pausar/excluir fonte) e a aba Configuracoes (chave de IA);
- o texto bruto das noticias (trecho_interno): so titulo, link, datas, notas e o resumo proprio da IA.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date, timedelta

from painel import servidor
from processamento.classificar import RAIZ

SAIDA = RAIZ / "site"
ESTATICOS = servidor.ESTATICOS


def gravar(nome: str, dados) -> None:
    (SAIDA / "dados" / nome).write_text(json.dumps(dados, ensure_ascii=False, default=str), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    dias = int(sys.argv[sys.argv.index("--dias") + 1]) if "--dias" in sys.argv else 90
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    (SAIDA / "dados").mkdir(parents=True)

    hoje = date.today()
    estado = servidor.api_estado({})
    estado["ia"] = {"provedor": estado["ia"]["provedor"], "modelo": estado["ia"]["modelo"]}  # sem informacao de chave
    estado["exportado_em"] = hoje.isoformat()
    gravar("estado.json", estado)
    gravar("indicadores.json", servidor.api_indicadores({}))
    gravar("temas.json", servidor.api_temas({}))
    gravar("fontes.json", servidor.api_fontes({}))

    inicio = (hoje - timedelta(days=dias - 1)).isoformat()
    total = 0
    for v in estado["visoes"]:
        d = servidor.api_noticias({"visao": v["id"], "de": inicio, "ate": hoje.isoformat()})
        for n in d["noticias"]:
            n.pop("motivos_regras", None)
        gravar(f"noticias-{v['id']}.json", d)
        total = max(total, len(d["noticias"]))

    resumos = []
    for r in servidor.api_resumos({})[:30]:
        partes = r["arquivo"].split("_")
        r["visao"] = partes[2] if len(partes) > 2 else ""
        for f in r["fatos"].values():
            f.pop("trecho", None)  # texto de terceiros: fica so no servidor
        resumos.append(r)
    gravar("resumos.json", resumos)

    for nome in ("app.js", "estilo.css"):
        shutil.copy(ESTATICOS / nome, SAIDA / nome)
    html = (ESTATICOS / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/estilo.css"', 'href="estilo.css"').replace('src="/app.js"', 'src="app.js"')
    html = html.replace("<body>", '<body data-modo="estatico">', 1)
    (SAIDA / "index.html").write_text(html, encoding="utf-8")
    (SAIDA / ".nojekyll").write_text("", encoding="utf-8")  # GitHub Pages: servir os arquivos como estao

    print(f"site/ gerado: {len(estado['visoes'])} visoes, ate {total} noticias por visao, "
          f"{len(resumos)} resumos, dados de {hoje.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
