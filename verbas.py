"""Conciliação mensal Sell In / Sell Out das verbas, sem Streamlit nem Excel."""

import pandas as pd


CATEGORIAS = {"consultor": "consultor", "gerente": "gerente", "marketing": "reserva"}


def calcular_verbas(vendas, sell_out, pagos, marketing_pagos):
    """Calcula todo o histórico antes de qualquer filtro de ano/mês.

    Sell In provisiona; Sell Out gera direito ao pagamento de consultor/gerente.
    Flags de pagamento referem-se ao mês do Sell Out. Marketing mantém o caixa
    provisionado no Sell In e desconta os valores efetivamente usados.
    Estoque inicial = zero no início das bases.

    O Sell Out só identifica dianteiro/traseiro, não o produto. Por isso as
    tarifas precisam ser uniformes por tipo; havendo tarifas diferentes, o
    cálculo para em vez de inventar uma média.
    """
    v, s = vendas.copy(), sell_out.copy()
    v["data"] = pd.to_datetime(v["data"], errors="raise")
    s["mes"] = pd.to_datetime(s["mes"], errors="raise")
    if v["data"].isna().any() or s["mes"].isna().any():
        raise ValueError("Há registros sem data nas bases de Sell In/Sell Out.")
    if not v["tipo_refil"].isin(["diant", "tras"]).all():
        raise ValueError("Há produtos sem tipo de refil no Sell In.")
    for frame, cols in ((v, ["qtde"]), (s, ["refil_diant", "refil_tras"])):
        for col in cols:
            frame[col] = pd.to_numeric(frame[col], errors="raise")
            if frame[col].isna().any() or (frame[col] < 0).any() or (frame[col] % 1 != 0).any():
                raise ValueError(f"Quantidades inválidas em {col}; revise a base antes de calcular as verbas.")
    v["mes"] = v["data"].dt.to_period("M").dt.to_timestamp()
    s["mes"] = s["mes"].dt.to_period("M").dt.to_timestamp()
    datas = list(v["mes"]) + list(s["mes"]) + list(pagos) + list(marketing_pagos)
    if not datas:
        raise ValueError("Não há histórico para calcular as verbas.")
    meses = pd.date_range(min(datas), max(datas), freq="MS")
    mensal = pd.DataFrame(index=meses)
    mensal.index.name = "mes"
    mensal["faturamento"] = v.groupby("mes")["total_item"].sum().reindex(meses, fill_value=0)
    for cat in CATEGORIAS:
        mensal[f"gerada_{cat}"] = 0.0
        mensal[f"realizada_{cat}"] = 0.0
    for tipo in ("diant", "tras"):
        vt = v[v["tipo_refil"] == tipo]
        mensal[f"entrada_{tipo}"] = vt.groupby("mes")["qtde"].sum().reindex(meses, fill_value=0)
        mensal[f"saida_{tipo}"] = s.groupby("mes")[f"refil_{tipo}"].sum().reindex(meses, fill_value=0)
        mensal[f"estoque_{tipo}"] = (mensal[f"entrada_{tipo}"] - mensal[f"saida_{tipo}"]).cumsum()
        for cat, campo in CATEGORIAS.items():
            tarifas = pd.to_numeric(vt[f"verba_{campo}"], errors="raise")
            if tarifas.isna().any() or (tarifas < 0).any() or tarifas.nunique() > 1:
                raise ValueError(f"Tarifas de {cat} para refil {tipo} divergentes; revise a regra de tarifa.")
            if tarifas.empty and mensal[f"saida_{tipo}"].sum():
                raise ValueError(f"Sell Out de refil {tipo} sem tarifa correspondente no Sell In.")
            tarifa = float(tarifas.iloc[0]) if not tarifas.empty else 0.0
            totais = pd.to_numeric(vt[f"total_{campo}"], errors="raise")
            if totais.isna().any() or ((totais - vt["qtde"] * tarifas).abs() > 0.011).any():
                raise ValueError(f"Total de {cat} não confere com quantidade × tarifa no Sell In.")
            mensal[f"gerada_{cat}"] += vt.assign(valor=totais).groupby("mes")["valor"].sum().reindex(meses, fill_value=0)
            mensal[f"realizada_{cat}"] += mensal[f"saida_{tipo}"] * tarifa
    for cat in CATEGORIAS:
        if cat == "marketing":
            mensal[f"paga_{cat}"] = [float(marketing_pagos.get(m, 0)) for m in meses]
        else:
            mensal[f"paga_{cat}"] = mensal[f"realizada_{cat}"] * [bool(pagos.get(m, {}).get(cat)) for m in meses]
        mensal[f"estoque_{cat}"] = (mensal[f"gerada_{cat}"] - mensal[f"realizada_{cat}"]).cumsum()
        mensal[f"saldo_{cat}"] = mensal[f"gerada_{cat}"] - mensal[f"paga_{cat}"]
        mensal[f"acumulado_{cat}"] = mensal[f"saldo_{cat}"].cumsum()
        if cat != "marketing":
            mensal[f"a_pagar_{cat}"] = mensal[f"realizada_{cat}"] - mensal[f"paga_{cat}"]
            mensal[f"pendente_{cat}"] = mensal[f"a_pagar_{cat}"].cumsum()
    for prefixo in ("gerada", "realizada", "paga", "estoque", "saldo", "acumulado"):
        mensal[f"{prefixo}_total"] = mensal[[f"{prefixo}_{c}" for c in CATEGORIAS]].sum(axis=1)
    return mensal.round(2)
