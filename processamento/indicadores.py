"""Indicadores do Radar calculados em codigo (regra 1: a IA nunca calcula numeros).

Le dados_processados/series.jsonl (ultima versao de cada periodo, respeitando revisoes) e
config/indicadores.csv (nome, unidade, formato e tipo de variacao de cada serie).

Uso: python -m processamento.indicadores   (mostra a tabela calculada)

Variacao:
- pct: variacao percentual (ex.: cambio, atividade, credito)
- pp:  diferenca em pontos percentuais, para series que ja sao taxas (Selic, inadimplencia)
- nenhuma: a serie ja e uma variacao publicada pela fonte; mostrada como esta, com sinal.
Comparacao: ambos (mes anterior e 12 meses) ou ano (so 12 meses, para series sem ajuste sazonal).
"""

from __future__ import annotations

import sys

from processamento.classificar import CONFIG, ler_csv, ler_jsonl

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def fmt_numero(valor: float, casas: int) -> str:
    texto = f"{valor:,.{casas}f}"  # 1,234.56
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,56


def fmt_mes(ref: str) -> str:
    ano, mes = ref[:4], int(ref[5:7])
    return f"{MESES[mes - 1]}/{ano}"


def fmt_variacao(valor: float | None, tipo: str) -> str | None:
    if valor is None:
        return None
    sinal = "+" if valor > 0 else ("-" if valor < 0 else "")
    corpo = fmt_numero(abs(valor), 1 if tipo == "pct" else 2)
    return f"{sinal}{corpo}{'%' if tipo == 'pct' else ' p.p.'}"


def mes_anterior(ref: str, meses: int) -> str:
    ano, mes = int(ref[:4]), int(ref[5:7])
    total = ano * 12 + (mes - 1) - meses
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def series_atuais() -> dict[str, dict[str, float]]:
    """{serie_id: {AAAA-MM: valor}} com a versao mais recente de cada ponto."""
    series: dict[str, dict[str, float]] = {}
    for p in ler_jsonl("series.jsonl"):  # ordem de gravacao: a ultima versao vence
        series.setdefault(p["serie_id"], {})[p["ocorrido_em"][:7]] = p["valor"]
    return series


def variacao(atual: float, antes: float | None, tipo: str) -> float | None:
    if antes is None:
        return None
    if tipo == "pp":
        return atual - antes
    return (atual / antes - 1) * 100 if antes else None


def calcular() -> list[dict]:
    series = series_atuais()
    resultado = []
    for cfg in ler_csv(CONFIG / "indicadores.csv"):
        pontos = series.get(cfg["serie_id"])
        if not pontos:
            continue
        ref = max(pontos)
        valor, casas, tipo = pontos[ref], int(cfg["casas"]), cfg["variacao"]
        if tipo == "nenhuma":  # a serie ja e uma variacao publicada pela fonte (ex.: acumulado do ano da ANIP)
            valor_fmt = fmt_variacao(valor, "pct")
            resultado.append({
                "id": "I_" + cfg["serie_id"], "serie_id": cfg["serie_id"], "nome": cfg["nome"], "unidade": cfg["unidade"],
                "fonte_id": cfg["fonte_id"], "observacao": cfg["observacao"], "referencia": ref,
                "referencia_fmt": fmt_mes(ref), "valor": valor, "valor_fmt": valor_fmt, "var_mes": None,
                "var_mes_fmt": None, "var_ano": None, "var_ano_fmt": None, "tipo_variacao": tipo,
                "frase": f"{cfg['nome']}: {valor_fmt} no acumulado até {fmt_mes(ref)}, contra o mesmo período do ano anterior"})
            continue
        ant_mes, ant_ano = mes_anterior(ref, 1), mes_anterior(ref, 12)
        var_mes = variacao(valor, pontos.get(ant_mes), tipo)
        var_ano = variacao(valor, pontos.get(ant_ano), tipo)
        prefixo = f"{cfg['prefixo']} " if cfg["prefixo"] else ""
        sufixo = cfg["sufixo"] if cfg["sufixo"].startswith("%") else (f" {cfg['sufixo']}" if cfg["sufixo"] else "")
        valor_fmt = f"{prefixo}{fmt_numero(valor, casas)}{sufixo}"
        if cfg["comparacao"] == "ano":  # serie sem ajuste sazonal: mes contra mes anterior engana
            var_mes = None
        partes = [f"{cfg['nome']}: {valor_fmt} em {fmt_mes(ref)}"]
        if var_mes is not None:
            partes.append(f"{fmt_variacao(var_mes, tipo)} sobre {fmt_mes(ant_mes)}")
        if var_ano is not None:
            partes.append(f"{fmt_variacao(var_ano, tipo)} sobre {fmt_mes(ant_ano)}")
        resultado.append({
            "id": "I_" + cfg["serie_id"], "serie_id": cfg["serie_id"], "nome": cfg["nome"], "unidade": cfg["unidade"],
            "fonte_id": cfg["fonte_id"], "observacao": cfg["observacao"], "referencia": ref,
            "referencia_fmt": fmt_mes(ref), "valor": valor, "valor_fmt": valor_fmt,
            "var_mes": var_mes, "var_mes_fmt": fmt_variacao(var_mes, tipo),
            "var_ano": var_ano, "var_ano_fmt": fmt_variacao(var_ano, tipo),
            "tipo_variacao": tipo, "frase": "; ".join(partes),
        })
    return resultado


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for i in calcular():
        print(i["frase"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
