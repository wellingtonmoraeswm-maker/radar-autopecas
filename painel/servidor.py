"""Painel local do Radar Autopecas (prototipo da Etapa 1-2, sem dependencias externas).

Uso (na raiz do repositorio):
    .venv/Scripts/python -m painel.servidor            abre em http://127.0.0.1:8765
    .venv/Scripts/python -m painel.servidor --porta 9000

So escuta em 127.0.0.1 (esta maquina). Le os mesmos arquivos do Radar (config/, dados_processados/,
saidas/) e chama os mesmos comandos (coleta, classificacao, IA, resumo). Na Etapa 3, o painel
definitivo (Next.js, na nuvem do cliente, com login) substitui este prototipo usando a mesma logica.
"""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from coleta import catalogo
from processamento import credenciais, indicadores
from processamento.briefing import PERIODOS, SAIDAS, data_da_noticia, nota_final
from processamento.classificar import CONFIG, RAIZ, ler_csv, ler_jsonl, ultimas_classificacoes

ESTATICOS = Path(__file__).resolve().parent / "estatico"
PORTA_PADRAO = 8765
LIMITE_CORPO = 64 * 1024


# --------------------------------------------------------------------------- leitura de dados

def periodo(q: dict) -> tuple[date, date]:
    hoje = date.today()
    if q.get("de"):
        return date.fromisoformat(q["de"]), date.fromisoformat(q.get("ate") or hoje.isoformat())
    dias = PERIODOS.get(q.get("periodo", "semana"), 7)
    return hoje - timedelta(days=dias - 1), hoje


def api_estado(_q: dict) -> dict:
    execucoes = ler_jsonl("execucoes.jsonl")
    ultima = max((e.get("fim") or e.get("inicio") for e in execucoes if e.get("ok")), default=None)
    ativo = credenciais.provedor_ativo()
    return {
        "visoes": [{"id": v["id"], "nome": v["nome"], "usuario": v["usuario"], "corte": v["relevancia_minima"]}
                   for v in ler_csv(CONFIG / "visoes.csv")],
        "ultima_coleta": ultima,
        "ia": {"provedor": ativo, "modelo": credenciais.modelo(ativo) if ativo else None,
               "tem_chave": bool(ativo and credenciais.chave(ativo))},
        "hoje": date.today().isoformat(),
    }


def api_indicadores(_q: dict) -> list[dict]:
    series = indicadores.series_atuais()
    saida = []
    for ind in indicadores.calcular():
        pontos = series.get(ind["serie_id"], {})
        meses = sorted(pontos)[-13:]
        saida.append({**ind, "historico": [{"ref": m, "rotulo": indicadores.fmt_mes(m), "valor": pontos[m]}
                                           for m in meses]})
    return saida


def api_noticias(q: dict) -> dict:
    inicio, fim = periodo(q)
    visoes = {v["id"]: v for v in ler_csv(CONFIG / "visoes.csv")}
    visao = visoes.get(q.get("visao", "V01")) or next(iter(visoes.values()))
    fontes = {f["id"]: f for f in ler_csv(CONFIG / "fontes.csv")}
    nomes = {t["id"]: t["tema"] for t in ler_csv(CONFIG / "taxonomia/temas.csv")}
    regras = ultimas_classificacoes()
    ias = {c["noticia_id"]: c for c in ler_jsonl("classificacoes_ia.jsonl")}
    corte = int(visao["relevancia_minima"] or 0)
    itens = []
    for n in ler_jsonl("noticias.jsonl"):
        dia, estimada = data_da_noticia(n)
        if dia is None or not inicio <= dia <= fim or n["id"] not in regras:
            continue
        reg, ia = regras[n["id"]], ias.get(n["id"])
        res = (ia or {}).get("resultado")
        do_setor = res["e_do_setor"] if res else reg["setorial"]
        nota, temas, origem = nota_final(reg, ia, visao) if do_setor else (0, reg["temas"], "regras")
        fonte = fontes.get(n["fonte_id"], {})
        itens.append({
            "id": n["id"], "titulo": n["titulo"], "url": n["url"], "data": dia.isoformat(), "data_estimada": estimada,
            "fonte": fonte.get("nome", n["fonte_id"]), "confiabilidade": fonte.get("confiabilidade", ""),
            "do_setor": do_setor, "nota": nota, "origem_nota": origem, "acima_do_corte": do_setor and nota >= corte,
            "temas": [{"id": t, "nome": nomes.get(t, t)} for t in temas],
            "justificativa": (res or {}).get("justificativa", ""), "tipo": (res or {}).get("tipo", ""),
            "nota_regras": reg["relevancia"], "motivos_regras": reg["motivos"],
        })
    itens.sort(key=lambda i: (-i["nota"], i["data"]))
    return {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "corte": corte, "visao": visao["nome"],
            "noticias": itens}


def api_resumos(q: dict) -> list[dict]:
    if not SAIDAS.exists():
        return []
    lista_ = []
    for arq in sorted(SAIDAS.glob("*.json"), reverse=True):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ult = d["tentativas"][-1]
        partes = arq.stem.split("_")
        if q.get("visao") and (len(partes) < 3 or partes[2] != q["visao"]):
            continue
        lista_.append({"arquivo": arq.name, "cabecalho": d["cabecalho"], "aprovado": ult["auditoria"]["aprovado"],
                       "problemas": ult["auditoria"]["problemas"], "resumo": ult["resumo"], "fatos": d["fatos"],
                       "indicadores": d.get("indicadores", []), "tentativas": len(d["tentativas"])})
    return lista_


def api_fontes(_q: dict) -> list[dict]:
    return ler_csv(CONFIG / "fontes.csv")


def api_temas(_q: dict) -> list[dict]:
    return [{"id": t["id"], "nome": t["tema"]} for t in ler_csv(CONFIG / "taxonomia/temas.csv") if t["ativo"] == "sim"]


def api_config(_q: dict) -> dict:
    ativo = credenciais.provedor_ativo()
    return {"arquivo": str(credenciais.ARQUIVO), "ativo": ativo,
            "provedores": [{"id": p, "chave": credenciais.mascarar(credenciais.chave(p)),
                            "tem_chave": bool(credenciais.chave(p)), "modelo": credenciais.modelo(p),
                            "por_variavel": bool(os.environ.get(spec["variavel"]))}
                           for p, spec in credenciais.PROVEDORES.items()]}


# --------------------------------------------------------------------------- acoes

def rodar(*modulo_e_args: str, timeout: int = 900) -> dict:
    """Roda um comando do Radar com o mesmo Python do servidor e devolve a saida."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-m", *modulo_e_args], cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return {"comando": " ".join(modulo_e_args), "codigo": r.returncode, "saida": (r.stdout + r.stderr)[-6000:]}


def acao_atualizar(_c: dict) -> dict:
    passos = [rodar("coleta.rodar"), rodar("processamento.classificar")]
    if credenciais.provedor_ativo():
        passos.append(rodar("processamento.ia"))
    return {"ok": all(p["codigo"] in (0,) for p in passos[:2]), "passos": passos}


def acao_gerar_resumo(c: dict) -> dict:
    args = ["processamento.briefing", "--visao", str(c.get("visao", "V01")), "--versao", str(c.get("versao", "flash"))]
    if c.get("de"):
        args += ["--de", str(c["de"]), "--ate", str(c.get("ate") or date.today().isoformat())]
    else:
        args += ["--periodo", str(c.get("periodo", "semana"))]
    r = rodar(*args)
    return {"ok": r["codigo"] == 0, **r}


def acao_cadastrar_chave(c: dict) -> dict:
    credenciais.cadastrar(str(c.get("provedor", "")), str(c.get("chave", "")), c.get("modelo") or None)
    return {"ok": True, "config": api_config({})}


def acao_ativar(c: dict) -> dict:
    credenciais.ativar(str(c.get("provedor", "")))
    return {"ok": True, "config": api_config({})}


def acao_testar(c: dict) -> dict:
    from processamento.provedores import obter
    provedor = str(c.get("provedor") or credenciais.provedor_ativo() or "")
    ok, mensagem = obter(provedor).testar()
    return {"ok": ok, "mensagem": mensagem}


def acao_modelo(c: dict) -> dict:
    provedor, modelo = str(c.get("provedor", "")), str(c.get("modelo", "")).strip()
    chave = credenciais.chave(provedor)
    if not chave or not modelo:
        raise ValueError("cadastre a chave antes de trocar o modelo")
    credenciais.cadastrar(provedor, chave, modelo, ativar=False)
    return {"ok": True, "config": api_config({})}


def acao_testar_fonte(c: dict) -> dict:
    return catalogo.inspecionar(str(c.get("url", "")).strip())


def acao_incluir_fonte(c: dict) -> dict:
    campos = ("url", "nome", "escopo", "confiabilidade", "temas", "observacao")
    return {"ok": True, **catalogo.adicionar({k: str(c.get(k, "")).strip() for k in campos})}


def acao_status_fonte(c: dict) -> dict:
    return {"ok": True, "fonte": catalogo.mudar_status(str(c.get("id", "")), str(c.get("status", "")),
                                                      str(c.get("motivo", "")).strip())}


GETS = {"/api/estado": api_estado, "/api/indicadores": api_indicadores, "/api/noticias": api_noticias,
        "/api/resumos": api_resumos, "/api/fontes": api_fontes, "/api/config": api_config,
        "/api/temas": api_temas}
POSTS = {"/api/atualizar": acao_atualizar, "/api/resumo": acao_gerar_resumo, "/api/config/chave": acao_cadastrar_chave,
         "/api/config/ativar": acao_ativar, "/api/config/testar": acao_testar, "/api/config/modelo": acao_modelo,
         "/api/fontes/testar": acao_testar_fonte, "/api/fontes/incluir": acao_incluir_fonte,
         "/api/fontes/status": acao_status_fonte}


class Painel(BaseHTTPRequestHandler):
    server_version = "RadarPainel/0.1"

    def log_message(self, formato, *args):  # silencia o log por requisicao
        pass

    def _json(self, dados, status=HTTPStatus.OK):
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        if url.path in GETS:
            try:
                return self._json(GETS[url.path](q))
            except Exception as exc:  # noqa: BLE001 - devolve o erro para a tela
                return self._json({"erro": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
        caminho = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
        alvo = (ESTATICOS / caminho).resolve()
        if not alvo.is_file() or ESTATICOS not in alvo.parents:
            return self._json({"erro": "nao encontrado"}, HTTPStatus.NOT_FOUND)
        corpo = alvo.read_bytes()
        self.send_response(HTTPStatus.OK)
        tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", f"{tipo}; charset=utf-8" if tipo.startswith("text/") or tipo.endswith("javascript") else tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_POST(self):
        # Protecao contra outro site no navegador disparar acoes neste painel local.
        origem = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origem and urlparse(origem).netloc != host:
            return self._json({"erro": "origem nao permitida"}, HTTPStatus.FORBIDDEN)
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._json({"erro": "envie JSON"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > LIMITE_CORPO:
            return self._json({"erro": "corpo grande demais"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        rota = urlparse(self.path).path
        if rota not in POSTS:
            return self._json({"erro": "nao encontrado"}, HTTPStatus.NOT_FOUND)
        try:
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
            return self._json(POSTS[rota](corpo))
        except ValueError as exc:
            return self._json({"ok": False, "erro": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return self._json({"ok": False, "erro": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    porta = int(sys.argv[sys.argv.index("--porta") + 1]) if "--porta" in sys.argv else PORTA_PADRAO
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Painel)
    print(f"Painel do Radar em http://127.0.0.1:{porta}  (Ctrl+C para parar)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
