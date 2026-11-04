"""Página Verbas: verba gerada, verba paga e saldo (consultor / gerente / marketing)."""

import io

import pandas as pd
import plotly.express as px
import streamlit as st

import dados
from tema import PALETA, VERMELHO, XL_CABECALHO, aplicar_tema
from verbas import CATEGORIAS, calcular_verbas


MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def dinheiro(valor):
    return (f"R$ {valor:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")


# Lista explícita: o relatório ao cliente traz só o que é dele (gerado, pago, saldo).
COLUNAS_CLIENTE = {
    "gerada_consultor": "Gerado — Consultor",
    "gerada_gerente": "Gerado — Gerente",
    "gerada_marketing": "Gerado — Marketing",
    "gerada_total": "Total gerado",
    "paga_consultor": "Pago — Consultor",
    "paga_gerente": "Pago — Gerente",
    "paga_marketing": "Pago — Marketing",
    "paga_total": "Total pago",
    "acumulado_total": "Saldo de verbas",
}


def tabela_cliente(mensal, ano):
    rec = mensal.loc[mensal.index.year == ano, list(COLUNAS_CLIENTE)].copy()
    tabela = rec.copy()
    tabela.index = [MESES[m.month] for m in rec.index]
    if not rec.empty:
        tabela.loc["TOTAL DO ANO / SALDO FINAL"] = {
            c: rec[c].iloc[-1] if c == "acumulado_total" else rec[c].sum()
            for c in COLUNAS_CLIENTE
        }
    return tabela.rename(columns=COLUNAS_CLIENTE).rename_axis("Mês")


def exportar_excel_cliente(tabela):
    """Exporta exclusivamente os mesmos dados da tabela mensal."""
    from openpyxl.styles import Font, PatternFill

    tabela = tabela[list(COLUNAS_CLIENTE.values())]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        tabela.to_excel(writer, sheet_name="Verbas mensais")
        ws = writer.book["Verbas mensais"]
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
        for cel in ws[1]:
            cel.font = Font(bold=True, color="FFFFFF")
            cel.fill = PatternFill("solid", fgColor=XL_CABECALHO)
        ws.column_dimensions["A"].width = 34
        for col in ws.iter_cols(min_col=2):
            ws.column_dimensions[col[0].column_letter].width = 23
            for cel in col[1:]:
                cel.number_format = 'R$ #,##0.00'
    return buf.getvalue()


def pagina_verbas():
    st.title("💰 Verbas")
    try:
        vendas = dados.ler_vendas_verbas()
        sell_out = dados.ler_base_tidy()
        pagos = dados.ler_pagamentos_verba()
        mkt_pagos = dados.ler_pagamentos_marketing()
        if vendas.empty or sell_out.empty:
            st.info("As informações de verbas ainda não estão disponíveis.")
            return
        mensal = calcular_verbas(vendas, sell_out, pagos, mkt_pagos)
    except Exception:
        st.error("As informações de verbas estão temporariamente indisponíveis. Tente novamente mais tarde.")
        return

    ca, cm, _ = st.columns([1, 2, 3])
    ano = ca.selectbox("Ano", sorted(set(mensal.index.year), reverse=True))
    do_ano = mensal[mensal.index.year == ano]
    escolha = cm.selectbox("📅 Mês", ["Ano todo"] + [MESES[m.month] for m in reversed(do_ano.index)])
    rec = do_ano if escolha == "Ano todo" else do_ano[do_ano.index.month == MESES.index(escolha)]
    fim = rec.index[-1]
    periodo = str(ano) if escolha == "Ano todo" else f"{escolha}/{ano}"
    fechamento = f"{MESES[fim.month]}/{fim.year}"
    soma, posicao = rec.sum(numeric_only=True), rec.iloc[-1]
    st.caption(f"Período: {periodo} · Valores em reais. O mês mais recente pode estar em andamento.")

    with st.container(key="verba_gerada"):
        cards = st.columns(3)
        cards[0].metric("Verba gerada", dinheiro(soma.gerada_total),
                        help="Verba gerada pelas compras no período selecionado.")
        cards[1].metric("Verba paga", dinheiro(soma.paga_total),
                        help="Pagamentos de consultores, gerentes e marketing no período selecionado.")
        cards[2].metric("Saldo de verbas", dinheiro(posicao.acumulado_total),
                        help=f"Total gerado menos pagamentos até {fechamento}, incluindo os períodos anteriores. Não representa apenas valores já devidos para pagamento.")
    st.caption(f"Gerado e pago referem-se ao período selecionado. O saldo considera todo o histórico até {fechamento}.")

    resumo = pd.DataFrame([
        {"Categoria": cat.title(), "Gerado no período": soma[f"gerada_{cat}"],
         "Pago no período": soma[f"paga_{cat}"], "Saldo de verbas": posicao[f"acumulado_{cat}"]}
        for cat in CATEGORIAS
    ])
    st.dataframe(resumo.style.format({c: dinheiro for c in resumo.columns if c != "Categoria"}),
                 width="stretch", hide_index=True)
    st.caption("Os pagamentos a consultores e gerentes consideram as vendas ao consumidor. Marketing considera os valores utilizados nas ações realizadas.")

    st.subheader(f"Verbas mês a mês — {ano}")
    tabela = tabela_cliente(mensal, ano)
    st.dataframe(tabela.style.format(dinheiro), width="stretch")
    st.caption("O saldo de cada mês inclui os períodos anteriores. Na última linha, gerado e pago são os totais do ano; o saldo é a posição ao final do período.")
    st.download_button("Exportar relatório (.xlsx)", exportar_excel_cliente(tabela),
                       file_name=f"verbas_{ano}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.subheader("Verba gerada e paga")
    grafico = do_ano[["gerada_total", "paga_total"]].rename(columns={
        "gerada_total": "Gerada", "paga_total": "Paga"})
    grafico.index = [MESES[m.month][:3] for m in grafico.index]
    # Gerada é o dado principal (acento vermelho); paga fica no cinza claro
    # (2ª cor da paleta), que se lê bem sobre o fundo escuro.
    fig = px.bar(grafico, barmode="group", color_discrete_sequence=[VERMELHO, PALETA[1]])
    fig.update_traces(hovertemplate="%{x}<br>R$ %{y:,.2f}<extra>%{fullData.name}</extra>")
    aplicar_tema(fig, xaxis_title=None, yaxis_title=None, legend_title=None, bargap=0.35)
    fig.update_yaxes(tickprefix="R$ ")
    st.plotly_chart(fig, width="stretch")
