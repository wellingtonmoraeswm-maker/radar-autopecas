"""Base comum dos conectores do Radar.

Contrato de um conector (modulo em coleta/conectores/<nome>.py):

    def coletar(fonte: dict, ctx: Contexto) -> Resultado

- `fonte` e a linha de config/fontes.csv (dict com as colunas do catalogo).
- O conector baixa SEMPRE por `ctx.baixar()`, que respeita o robots.txt e se identifica.
- Antes de interpretar, guarda o original com `ctx.guardar_bruto()` (regra 4).
- Devolve itens `Noticia` e/ou `Ponto` (serie) no `Resultado`. Quem grava e o executor.

Tres datas (regra 5): `ocorrido_em` (fato ou mes de referencia), `publicado_em` (fonte),
`coletado_em` (preenchido pelo executor). Data desconhecida fica None, nunca inventada.
So usa a biblioteca padrao.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BRUTOS = RAIZ / "dados_brutos"
PROCESSADOS = RAIZ / "dados_processados"
AGENTE = "RadarAutopecas/0.1 (monitoramento de mercado; contato pelo administrador da instancia)"
TIMEOUT = 60
LIMITE_TRECHO = 300
PARAMETROS_RASTREIO = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")


class ColetaBloqueada(Exception):
    """O robots.txt proibe o caminho. Nao contornar."""


@dataclass
class Noticia:
    url: str
    titulo: str
    publicado_em: str | None = None
    ocorrido_em: str | None = None
    # Usado so para classificar. Nunca exibido no painel (regra 6: so titulo, link e resumo proprio).
    trecho_interno: str = ""

    @property
    def id(self) -> str:
        return "N" + hashlib.sha1(normalizar_url(self.url).encode()).hexdigest()[:16]


@dataclass
class Ponto:
    serie_id: str
    ocorrido_em: str  # periodo de referencia: AAAA-MM ou AAAA-MM-DD
    valor: float
    unidade: str = ""
    publicado_em: str | None = None

    @property
    def id(self) -> str:
        return f"{self.serie_id}@{self.ocorrido_em}"


@dataclass
class Resultado:
    noticias: list[Noticia] = field(default_factory=list)
    pontos: list[Ponto] = field(default_factory=list)
    brutos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def agora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalizar_url(url: str) -> str:
    partes = urllib.parse.urlsplit(url.strip())
    consulta = [(k, v) for k, v in urllib.parse.parse_qsl(partes.query)
                if not k.lower().startswith(PARAMETROS_RASTREIO)]
    caminho = partes.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((partes.scheme.lower(), partes.netloc.lower(), caminho,
                                    urllib.parse.urlencode(consulta), ""))


def _ler_jsonl(nome: str) -> list[dict]:
    import json
    caminho = PROCESSADOS / nome
    if not caminho.exists():
        return []
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def ler_series_existentes() -> list[dict]:
    """Pontos ja gravados (para o conector nao baixar de novo o que ja leu)."""
    return _ler_jsonl("series.jsonl")


def urls_coletadas(fonte_id: str) -> set[str]:
    """URLs normalizadas das noticias ja gravadas desta fonte."""
    return {normalizar_url(n["url"]) for n in _ler_jsonl("noticias.jsonl") if n.get("fonte_id") == fonte_id}


def url_codificada(url: str) -> str:
    """Codifica acentos e espacos (ex.: 'INFOGRÁFICO.pdf'), sem mexer no que ja esta codificado."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path, safe="/%:@!$&'()*+,;="),
                                    urllib.parse.quote(p.query, safe="=&%+/:,;@!$'()*"), p.fragment))


def cortar(texto: str, limite: int = LIMITE_TRECHO) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[:limite].rsplit(" ", 1)[0] + "..."


def _relativo(caminho: Path) -> str:
    return caminho.relative_to(RAIZ).as_posix() if caminho.is_relative_to(RAIZ) else caminho.as_posix()


class Contexto:
    def __init__(self, fonte_id: str, ensaio: bool = False, historico_dias: int = 0):
        self.fonte_id = fonte_id
        self.ensaio = ensaio
        self.historico_dias = historico_dias  # >0: o conector busca tambem o passado (se souber)
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _permitido(self, url: str) -> bool:
        partes = urllib.parse.urlsplit(url)
        host = f"{partes.scheme}://{partes.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(self._get(f"{host}/robots.txt").decode("utf-8", "ignore").splitlines())
                self._robots[host] = rp
            except urllib.error.HTTPError as exc:
                if exc.code not in (404, 410):
                    raise ColetaBloqueada(f"robots.txt inacessivel (HTTP {exc.code}) em {host}")
                self._robots[host] = None  # sem robots.txt: permitido
        rp = self._robots[host]
        return rp is None or rp.can_fetch(AGENTE, url)

    def _get(self, url: str, dados: bytes | None = None, cabecalhos: dict | None = None) -> bytes:
        pedido = urllib.request.Request(url_codificada(url), data=dados,
                                        headers={"User-Agent": AGENTE, **(cabecalhos or {})})
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
            return r.read()

    def baixar(self, url: str, dados: bytes | None = None, cabecalhos: dict | None = None) -> bytes:
        if not self._permitido(url_codificada(url)):
            raise ColetaBloqueada(f"robots.txt proibe {url}")
        return self._get(url, dados, cabecalhos)

    def pausar(self, segundos: float) -> None:
        import time
        time.sleep(segundos)

    def guardar_bruto(self, conteudo: bytes, extensao: str) -> str:
        """Guarda o original antes de qualquer processamento. Devolve o caminho relativo."""
        resumo = hashlib.sha1(conteudo).hexdigest()[:8]
        extensao = extensao.lstrip(".")
        pasta = BRUTOS / self.fonte_id
        igual = next(pasta.glob(f"*_{resumo}.{extensao}"), None) if pasta.exists() else None
        if igual is not None:  # conteudo identico ja guardado: nao duplica
            return _relativo(igual)
        destino = pasta / f"{datetime.now().strftime('%Y-%m-%dT%H%M%S')}_{resumo}.{extensao}"
        if not self.ensaio:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
        return _relativo(destino)
