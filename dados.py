"""
Camada de dados do dashboard modelo: lê base_modelo.xlsx (sem banco de dados).

O app nunca lê o Excel direto: chama estas funções, que devolvem os dados no
mesmo formato que o produto usa em produção. Aproveitamento e faturamento são
calculados aqui, na leitura, a partir das quantidades e do preço da marca:

    aproveitamento = refil_diant / passagens        (vazio sem passagens)
    total_diant    = refil_diant × preco_diant
    total_tras     = refil_tras  × preco_tras
    total_geral    = total_diant + total_tras

Para trocar os dados, edite o Excel (ou rode gerar_dados.py) e recarregue a
página; o cache de leitura expira em 60 s.
"""

import re
from pathlib import Path

import pandas as pd
import streamlit as st

ARQUIVO = Path(__file__).resolve().parent / "base_modelo.xlsx"


def ordem_natural(valor):
    """Chave de ordenação que põe 'Consultor 2' antes de 'Consultor 10'."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", str(valor))]


def ordenar(valores):
    return sorted(valores, key=ordem_natural)


def _ler(aba):
    return pd.read_excel(ARQUIVO, sheet_name=aba)


@st.cache_data(ttl=60)
def ler_base_tidy():
    """Base completa já calculada, uma linha por consultor/mês/unidade."""
    lanc = _ler("lancamentos")
    unidades = _ler("unidades")
    precos = _ler("precos_marca")
    df = (lanc.merge(unidades, on="unidade", how="inner", validate="many_to_one")
              .merge(precos, on="marca", how="inner", validate="many_to_one"))
    df["mes"] = pd.to_datetime(df["mes"]).dt.to_period("M").dt.to_timestamp()
    df["mes_label"] = df["mes"].dt.strftime("%m/%Y")
    for c in ("passagens", "refil_diant", "refil_tras"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["refil_diant"] = df["refil_diant"].fillna(0).astype(int)
    df["refil_tras"] = df["refil_tras"].fillna(0).astype(int)
    df["aproveitamento"] = (df["refil_diant"] / df["passagens"]).where(df["passagens"] > 0).round(4)
    df["total_diant"] = (df["refil_diant"] * df["preco_diant"]).round(2)
    df["total_tras"] = (df["refil_tras"] * df["preco_tras"]).round(2)
    df["total_geral"] = (df["total_diant"] + df["total_tras"]).round(2)
    return df[["consultor", "unidade", "loja", "marca", "gerente", "mes", "mes_label",
               "passagens", "refil_diant", "refil_tras", "aproveitamento",
               "total_diant", "total_tras", "total_geral"]]


@st.cache_data(ttl=60)
def ler_vendas_verbas():
    """Sell In: pedidos das unidades à Suiçatech, com as três verbas por item."""
    df = _ler("sell_in")
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"])
    for c in ("preco_unit", "total_item", "verba_consultor", "total_consultor",
              "verba_gerente", "total_gerente", "verba_reserva", "total_reserva"):
        df[c] = df[c].astype(float)
    df["qtde"] = df["qtde"].astype(int)
    return df


def _sim(valor):
    return str(valor).strip().lower() in {"sim", "s", "1", "true", "pago"}


@st.cache_data(ttl=60)
def ler_pagamentos_verba():
    """Meses cuja verba já foi paga: {Timestamp(1º dia do mês): {consultor, gerente}}."""
    df = _ler("pagamentos")
    meses = pd.to_datetime(df["mes"]).dt.to_period("M").dt.to_timestamp()
    return {m: {"consultor": _sim(c), "gerente": _sim(g)}
            for m, c, g in zip(meses, df["consultor_pago"], df["gerente_pago"])}


@st.cache_data(ttl=60)
def ler_pagamentos_marketing():
    """Verba de marketing usada por mês: {Timestamp(1º dia do mês): valor}.
    Vários pagamentos no mesmo mês são somados."""
    df = _ler("marketing_pagos")
    if df.empty:
        return {}
    df["mes"] = pd.to_datetime(df["mes"]).dt.to_period("M").dt.to_timestamp()
    return {m: float(v) for m, v in df.groupby("mes")["valor"].sum().items()}
