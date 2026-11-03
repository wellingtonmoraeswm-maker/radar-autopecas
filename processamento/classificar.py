"""Classificacao deterministica das noticias pela taxonomia do Radar.

Uso (na raiz do repositorio):
    python -m processamento.classificar                  classifica as noticias ainda nao classificadas
    python -m processamento.classificar --reclassificar  reclassifica tudo (depois de mudar a taxonomia)
    python -m processamento.classificar --mostrar        lista o resultado da ultima classificacao

Regras:
- Tema so vem de config/taxonomia/temas.csv. Nada e inventado.
- Uma noticia e do SETOR quando a fonte tem escopo=setorial ou quando o texto aciona uma ancora:
  tema com ancora=sim, familia de pecas, entidade do tipo associacao ou concorrente monitorado.
  Fora do setor, a relevancia e 0 (ex.: "frete da Black Friday" num portal de varejo geral).
- A nota de relevancia (0 a 100) e calculada aqui, com regras fixas e motivo registrado.
  A IA, quando entrar, refina; nao substitui esta nota.
Grava dados_processados/classificacoes.jsonl (anexa; a ultima linha de cada noticia vale).
So usa a biblioteca padrao.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config"
PROCESSADOS = RAIZ / "dados_processados"
ARQUIVOS_TAXONOMIA = ["taxonomia/temas.csv", "taxonomia/familias_ncm.csv", "taxonomia/entidades.csv",
                      "taxonomia/concorrentes.csv", "fontes.csv", "visoes.csv"]

# Pesos da nota (somam no maximo 100). Mudar aqui muda a versao da classificacao.
PESOS = {"base_setor": 30, "concorrente": 25, "tema": 10, "tema_max": 30, "familia": 10,
         "entidade": 5, "confiabilidade": {"A": 10, "B": 5, "C": 0}, "bonus_visao": 15}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def lista(valor: str) -> list[str]:
    return [p.strip() for p in (valor or "").split("|") if p.strip()]


def ler_csv(caminho: Path) -> list[dict]:
    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    return [{k: (v or "").strip() for k, v in l.items()} for l in csv.DictReader(io.StringIO(texto), delimiter=";")]


def versao_regras() -> str:
    h = hashlib.sha1(json.dumps(PESOS, sort_keys=True).encode())
    for nome in ARQUIVOS_TAXONOMIA:
        h.update((CONFIG / nome).read_bytes())
    return h.hexdigest()[:10]


class Termo:
    """Um termo compilado: casa palavra inteira, sem acento e sem diferenciar maiusculas."""

    def __init__(self, texto: str):
        self.texto = texto
        self.re = re.compile(r"(?<!\w)" + re.escape(normalizar(texto)) + r"(?!\w)")

    def em(self, alvo: str) -> bool:
        return self.re.search(alvo) is not None


class Classificador:
    def __init__(self):
        self.temas = [t for t in ler_csv(CONFIG / "taxonomia/temas.csv") if t["ativo"] == "sim"]
        self.familias = ler_csv(CONFIG / "taxonomia/familias_ncm.csv")
        self.entidades = ler_csv(CONFIG / "taxonomia/entidades.csv")
        self.concorrentes = [c for c in ler_csv(CONFIG / "taxonomia/concorrentes.csv") if c["monitorar"] == "sim"]
        self.fontes = {f["id"]: f for f in ler_csv(CONFIG / "fontes.csv")}
        self.visoes = ler_csv(CONFIG / "visoes.csv")
        self.versao = versao_regras()
        comp = lambda xs: [Termo(x) for x in xs]  # noqa: E731
        self._temas = [(t, comp(lista(t["palavras_chave"])), comp(lista(t["excluir"]))) for t in self.temas]
        self._familias = [(f, comp(lista(f["termos"]))) for f in self.familias]
        self._entidades = [(e, comp([x for x in (e["sigla"], e["nome"]) if x])) for e in self.entidades]
        self._concorrentes = [(c, comp([c["nome"]] + lista(c["apelidos"]))) for c in self.concorrentes]

    def classificar(self, noticia: dict) -> dict:
        alvo = normalizar(f"{noticia.get('titulo', '')} {noticia.get('trecho_interno', '')}")
        gatilhos: dict[str, str] = {}

        def primeiro(termos: list[Termo]) -> str | None:
            return next((t.texto for t in termos if t.em(alvo)), None)

        temas, ancoras = [], []
        for t, palavras, excluir in self._temas:
            achou = primeiro(palavras)
            if achou and not primeiro(excluir):
                temas.append(t["id"])
                gatilhos[t["id"]] = achou
                if t["ancora"] == "sim":
                    ancoras.append(t["id"])
        familias = []
        for f, termos in self._familias:
            if achou := primeiro(termos):
                familias.append(f["id"])
                gatilhos[f["id"]] = achou
        entidades = []
        for e, termos in self._entidades:
            if achou := primeiro(termos):
                entidades.append(e["id"])
                gatilhos[e["id"]] = achou
        concorrentes = []
        for c, termos in self._concorrentes:
            if achou := primeiro(termos):
                concorrentes.append(c["id"])
                gatilhos[c["id"]] = achou

        fonte = self.fontes.get(noticia.get("fonte_id", ""), {})
        associacoes = [e for e in entidades
                       if next((x for x in self.entidades if x["id"] == e), {}).get("tipo") == "associação"]
        motivos_setor = []
        if fonte.get("escopo") == "setorial":
            motivos_setor.append(f"fonte setorial ({fonte.get('id')})")
        motivos_setor += [f"ancora {x} '{gatilhos[x]}'" for x in ancoras + familias + associacoes + concorrentes]
        setorial = bool(motivos_setor)

        motivos, nota = [], 0
        if setorial:
            nota = PESOS["base_setor"]
            motivos.append(f"+{PESOS['base_setor']} do setor")
            if concorrentes:
                nota += PESOS["concorrente"]
                motivos.append(f"+{PESOS['concorrente']} concorrente monitorado")
            pts = min(PESOS["tema_max"], PESOS["tema"] * len(temas))
            if pts:
                nota += pts
                motivos.append(f"+{pts} por {len(temas)} tema(s)")
            if familias:
                nota += PESOS["familia"]
                motivos.append(f"+{PESOS['familia']} familia de pecas")
            if entidades:
                nota += PESOS["entidade"]
                motivos.append(f"+{PESOS['entidade']} entidade do setor")
            conf = PESOS["confiabilidade"].get(noticia.get("confiabilidade") or fonte.get("confiabilidade", ""), 0)
            if conf:
                nota += conf
                motivos.append(f"+{conf} confiabilidade {noticia.get('confiabilidade') or fonte.get('confiabilidade')}")
            nota = min(100, nota)
        else:
            motivos.append("fora do setor: fonte geral e nenhuma ancora no texto")

        visoes = {}
        for v in self.visoes:
            prioritarios = set(lista(v["temas_prioritarios"])) | set(lista(v["familias_prioritarias"]))
            bonus = PESOS["bonus_visao"] if setorial and prioritarios & set(temas + familias) else 0
            visoes[v["id"]] = min(100, nota + bonus)

        return {"noticia_id": noticia["id"], "versao_regras": self.versao, "metodo": "palavras-chave",
                "classificado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "setorial": setorial, "motivo_setor": motivos_setor, "temas": temas, "familias": familias,
                "entidades": entidades, "concorrentes": concorrentes, "gatilhos": gatilhos,
                "relevancia": nota, "motivos": motivos, "relevancia_visoes": visoes}


def ler_jsonl(nome: str) -> list[dict]:
    caminho = PROCESSADOS / nome
    if not caminho.exists():
        return []
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def ultimas_classificacoes() -> dict[str, dict]:
    return {c["noticia_id"]: c for c in ler_jsonl("classificacoes.jsonl")}


def mostrar(noticias: dict[str, dict], classes: dict[str, dict], nomes_temas: dict[str, str]) -> None:
    ordem = sorted(classes.values(), key=lambda c: -c["relevancia"])
    for c in ordem:
        n = noticias.get(c["noticia_id"], {})
        temas = ", ".join(nomes_temas.get(t, t) for t in c["temas"]) or "sem tema"
        marca = f"{c['relevancia']:>3}" if c["setorial"] else "  -"
        print(f"{marca} [{n.get('fonte_id', '?')}] {n.get('titulo', '?')[:90]}")
        print(f"      {temas}" + (f" | familias {', '.join(c['familias'])}" if c["familias"] else "")
              + f" | {'; '.join(c['motivos'])}")
    setor = sum(1 for c in classes.values() if c["setorial"])
    print(f"\n{len(classes)} noticias: {setor} do setor, {len(classes) - setor} fora do setor")
    contagem = Counter(t for c in classes.values() if c["setorial"] for t in c["temas"])
    if contagem:
        print("Temas mais frequentes: " + ", ".join(f"{nomes_temas.get(t, t)} ({q})" for t, q in contagem.most_common(6)))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    noticias = {n["id"]: n for n in ler_jsonl("noticias.jsonl")}
    cl = Classificador()
    nomes_temas = {t["id"]: t["tema"] for t in cl.temas}

    if "--mostrar" in args:
        mostrar(noticias, ultimas_classificacoes(), nomes_temas)
        return 0

    feitas = ultimas_classificacoes()
    reclassificar = "--reclassificar" in args
    pendentes = [n for i, n in noticias.items()
                 if reclassificar or feitas.get(i, {}).get("versao_regras") != cl.versao]
    novas = [cl.classificar(n) for n in pendentes]
    if novas:
        PROCESSADOS.mkdir(parents=True, exist_ok=True)
        with (PROCESSADOS / "classificacoes.jsonl").open("a", encoding="utf-8") as f:
            for c in novas:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"versao das regras {cl.versao}: {len(novas)} classificadas, {len(noticias) - len(novas)} ja estavam em dia")
    if novas:
        mostrar(noticias, {c["noticia_id"]: c for c in novas}, nomes_temas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
