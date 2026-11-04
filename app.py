"""
Dashboard modelo Suiçatech — Refis para Palhetas · Grupo Modelo

Versão de demonstração do dashboard que a concessionária recebe ao fechar com a
Suiçatech. Mesmas telas do produto em uso:
  - Dashboard: acompanhamento trimestral móvel por consultor, unidade e marca;
  - Relatório Por Gerente / Por Consultor: rankings do mês;
  - Verbas: verba gerada, paga e saldo (verbas_pagina.py).

Os dados são fictícios e vêm de base_modelo.xlsx (dados.py); não há banco.

Como rodar, na pasta do projeto:
    streamlit run app.py
"""

import base64
import datetime as dt
import io

import pandas as pd
import plotly.express as px
import streamlit as st

import dados
from tema import (FUNDO_SECUNDARIO, GRUPO, ICONE, LINHA_GRADE, LOGO, PALETA, TEXTO,
                  TEXTO_SUAVE, TRACOS, VERMELHO, VERMELHO_CLARO, XL_BORDA, XL_CABECALHO,
                  XL_TITULO, XL_ZEBRA, aplicar_tema, cores_destaque)

st.set_page_config(page_title=f"Suiçatech — Refis para Palhetas · {GRUPO}",
                   page_icon=str(ICONE) if ICONE.exists() else "📊", layout="wide")

N_MESES = 3
MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

PAG_DASHBOARD = "Dashboard"
PAG_VERBAS = "Verbas"
PAG_GERENTE = "Relatório Por Gerente"
PAG_CONSULTOR = "Relatório Por Consultor"
PAGINAS = [PAG_DASHBOARD, PAG_GERENTE, PAG_CONSULTOR, PAG_VERBAS]

ARQ = GRUPO.replace(" ", "_")     # prefixo dos arquivos exportados


# --------------------------- Identidade visual ---------------------------
def _injetar_css():
    """Identidade Suiçatech sobre o tema escuro: fundo grafite, texto claro e o
    vermelho da logo como acento (títulos, bordas e o dado principal)."""
    st.markdown(f"""
        <style>
        /* Títulos em vermelho Suiçatech (texto grande: 4,1:1 sobre o grafite) */
        h1, h2, h3 {{ color: {VERMELHO} !important; }}
        /* Cartões de KPI: grafite um tom acima do fundo, acento vermelho à esquerda */
        div[data-testid="stMetric"] {{
            background: {FUNDO_SECUNDARIO}; border: 1px solid {LINHA_GRADE};
            border-left: 5px solid {VERMELHO};
            border-radius: 8px; padding: 14px 16px; }}
        /* Valor do KPI acompanha a largura da tela, para "R$ 247.935,70" caber
           inteiro do tablet ao monitor grande (3 cartões por linha). */
        div[data-testid="stMetricValue"] {{ color: {TEXTO};
            font-size: clamp(24px, 2.4vw, 36px); }}
        .st-key-verba_gerada div[data-testid="stMetricValue"] {{
            font-size: clamp(22px, 2.3vw, 34px); }}
        /* Relatórios: 4 cartões por linha, fonte proporcionalmente menor. */
        .st-key-kpis_relatorio div[data-testid="stMetricValue"] {{
            font-size: clamp(18px, 1.9vw, 30px); }}
        /* Barra lateral um tom acima do fundo, com borda vermelha */
        section[data-testid="stSidebar"] {{
            background: {FUNDO_SECUNDARIO}; border-right: 3px solid {VERMELHO}; }}
        hr {{ border-color: rgba(250,35,30,.45) !important; }}
        /* Item de menu selecionado em vermelho (variação clara, para texto pequeno) */
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {{
            color: {VERMELHO_CLARO}; font-weight: 700; }}
        /* Cabeçalho com a logo */
        .topo {{ display: flex; align-items: center; justify-content: space-between;
                 gap: 16px; flex-wrap: wrap; padding: 4px 0 12px;
                 border-bottom: 3px solid {VERMELHO}; margin-bottom: 8px; }}
        .topo img {{ height: 46px; max-width: 100%; }}
        .topo-cliente {{ text-align: right; line-height: 1.2; }}
        .topo-cliente small {{ display: block; color: {TEXTO_SUAVE};
                               font-size: 12px; letter-spacing: .08em;
                               text-transform: uppercase; }}
        .topo-cliente strong {{ color: {TEXTO}; font-size: 22px; }}
        .rodape-demo {{ color: {TEXTO_SUAVE}; font-size: 12px; }}
        </style>
    """, unsafe_allow_html=True)


@st.cache_resource
def _logo_base64():
    """Logo reduzida para o cabeçalho (evita reenviar o arquivo grande a cada clique)."""
    from PIL import Image
    img = Image.open(LOGO)
    img.thumbnail((700, 140))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def cabecalho():
    """Logo da Suiçatech à esquerda e o grupo cliente à direita, em todas as páginas."""
    logo = (f'<img src="data:image/png;base64,{_logo_base64()}" alt="Suiçatech">'
            if LOGO.exists() else '<strong style="color:%s;font-size:28px">SUIÇA TECH</strong>' % VERMELHO)
    st.markdown(
        f'<div class="topo">{logo}<div class="topo-cliente">'
        f'<small>Refis para palhetas · Cliente</small><strong>{GRUPO}</strong></div></div>',
        unsafe_allow_html=True)


def mostrar_logo():
    """Logo no topo da barra lateral, presente em todas as páginas."""
    if LOGO.exists():
        st.sidebar.image(str(LOGO), width="stretch")
    else:
        st.sidebar.markdown(f"**SUIÇA TECH**")


# --------------------------- Formatação BR ---------------------------
def fmt_money(v):
    if v is None or pd.isna(v):
        return "—"
    return ("R$ {:,.2f}".format(v)).replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(v):
    if v is None or pd.isna(v):
        return "—"
    return "{:,.0f}".format(v).replace(",", ".")


def fmt_pct(v):
    if v is None or pd.isna(v):
        return "—"
    return ("{:.1f}%".format(v * 100)).replace(".", ",")


def delta_str(v, kind):
    if v is None or pd.isna(v):
        return None
    sign = "+" if v >= 0 else "-"
    a = abs(v)
    if kind == "money":
        body = fmt_money(a)
    elif kind == "int":
        body = fmt_int(a)
    else:  # pp (pontos percentuais)
        body = "{:.1f}".format(a * 100).replace(".", ",") + " p.p."
    return f"{sign}{body}"


def mlabel(d):
    d = pd.Timestamp(d)
    return f"{MESES_PT[d.month][:3]}/{d.year}"


def label_mes(d):
    """Rótulo do mês (ex.: 'Outubro/2026')."""
    return f"{MESES_PT[d.month]}/{d.year}"


# --------------------------- Helpers de dados ---------------------------
def last_n_months(df, n=N_MESES, mes_fim=None):
    """Janela dos n meses que TERMINAM em `mes_fim` (trimestre móvel). Sem
    `mes_fim`, usa o mês mais recente da base."""
    meses = sorted(df["mes"].unique())
    if mes_fim is not None and mes_fim in meses:
        idx = meses.index(mes_fim)
        keep = meses[max(0, idx - n + 1): idx + 1]
    else:
        keep = meses[-n:]
    return df[df["mes"].isin(keep)].copy(), keep


def agg_by(df, group):
    """Agrega os KPIs. O aproveitamento é SEMPRE recalculado como
    soma(refil_diant) / soma(passagens), nunca média de percentuais. Para a
    conversão, conta apenas refis de linhas que também têm passagens
    informadas. O aproveitamento traseiro (refil_tras / passagens) segue o
    mesmo critério."""
    df = df.copy()
    df["_refil_conv"] = df["refil_diant"].where(df["passagens"].notna())
    df["_refil_conv_t"] = df["refil_tras"].where(df["passagens"].notna())
    g = df.groupby(group, as_index=False).agg(
        passagens=("passagens", "sum"),
        refil_diant=("refil_diant", "sum"),
        refil_tras=("refil_tras", "sum"),
        total_diant=("total_diant", "sum"),
        total_tras=("total_tras", "sum"),
        total_geral=("total_geral", "sum"),
        _refil_conv=("_refil_conv", "sum"),
        _refil_conv_t=("_refil_conv_t", "sum"),
    )
    g["aproveitamento"] = (g["_refil_conv"] / g["passagens"]).where(g["passagens"] > 0)
    g["aproveitamento_tras"] = (g["_refil_conv_t"] / g["passagens"]).where(g["passagens"] > 0)
    return g.drop(columns=["_refil_conv", "_refil_conv_t"])


# --------------------------- Excel ---------------------------
def _estilos_excel():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    thin = Side(style="thin", color=XL_BORDA)
    return {
        "BD": Border(left=thin, right=thin, top=thin, bottom=thin),
        "cab_font": Font(name="Arial", bold=True, color="FFFFFFFF", size=10),
        "cab_fill": PatternFill("solid", fgColor=XL_CABECALHO),
        "zebra": PatternFill("solid", fgColor=XL_ZEBRA),
        "titulo": lambda size: Font(name="Arial", bold=True, size=size, color=XL_TITULO),
        "nota": Font(name="Arial", size=9, color="FF656263"),
        "centro": Alignment(horizontal="center"),
        "cab_alin": Alignment(horizontal="center", vertical="center", wrap_text=True),
    }


def _v(x):  # NaN -> None (célula vazia em vez de "nan")
    return None if (isinstance(x, float) and pd.isna(x)) else x


def _cabecalho_excel(ws, headers, row, E):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row, j, h)
        c.font, c.fill, c.alignment, c.border = E["cab_font"], E["cab_fill"], E["cab_alin"], E["BD"]


def gerar_excel_ranking(f, periodo, filtros_txt):
    """Relatório Excel do Ranking da seleção atual.
    Aba 1: ranking por consultor no trimestre. Aba 2: resumo mensal."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    E = _estilos_excel()

    def _i(x):
        return int(x) if pd.notna(x) else 0

    wb = Workbook()
    ws = wb.active
    ws.title = "Ranking Trimestre"
    ws.cell(1, 1, f"Ranking Vendas Refis para Palhetas — {GRUPO}").font = E["titulo"](14)
    for r, txt in ((2, f"Período: {periodo}"), (3, f"Filtros: {filtros_txt}"),
                   (4, f"Gerado em: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}")):
        ws.cell(r, 1, txt).font = E["nota"]

    rk = agg_by(f, ["consultor", "unidade", "marca"]).sort_values("total_geral", ascending=False)
    overall = agg_by(f.assign(_g=1), "_g").iloc[0]
    head = ["#", "Consultor", "Unidade", "Marca", "Passagens", "Refil Diant.",
            "Aprov. Diant.", "Refil Tras.", "Aprov. Tras.", "Faturamento (R$)"]
    H = 6
    _cabecalho_excel(ws, head, H, E)
    for i, (_, row) in enumerate(rk.iterrows()):
        r = H + 1 + i
        vals = [i + 1, row["consultor"], row["unidade"], row["marca"],
                row["passagens"], row["refil_diant"], row["aproveitamento"],
                row["refil_tras"], row["aproveitamento_tras"], row["total_geral"]]
        for j, v in enumerate(vals, 1):
            c = ws.cell(r, j, _v(v)); c.font = Font(name="Arial", size=10); c.border = E["BD"]
            if j in (1, 5, 6, 7, 8, 9):
                c.alignment = E["centro"]
            if j in (5, 6, 8):
                c.number_format = "#,##0"
            elif j in (7, 9):
                c.number_format = "0.0%"
            elif j == 10:
                c.number_format = "R$ #,##0.00"
        if i % 2 == 1:
            for j in range(1, len(head) + 1):
                ws.cell(r, j).fill = E["zebra"]
    tr = H + 1 + len(rk)
    ws.cell(tr, 4, "TOTAL").font = Font(name="Arial", bold=True, size=10)
    for j, v, fmt in ((5, _i(overall["passagens"]), "#,##0"),
                      (6, _i(overall["refil_diant"]), "#,##0"),
                      (7, _v(overall["aproveitamento"]), "0.0%"),
                      (8, _i(overall["refil_tras"]), "#,##0"),
                      (9, _v(overall["aproveitamento_tras"]), "0.0%"),
                      (10, _v(overall["total_geral"]), "R$ #,##0.00")):
        c = ws.cell(tr, j, v); c.font = Font(name="Arial", bold=True, size=10)
        c.border = E["BD"]; c.number_format = fmt
        if j in (5, 6, 7, 8, 9):
            c.alignment = E["centro"]
    for j, w in enumerate([5, 18, 14, 10, 11, 12, 12, 11, 12, 15], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = f"A{H + 1}"

    ws2 = wb.create_sheet("Resumo Mensal")
    mensal = agg_by(f, "mes").sort_values("mes")
    mensal["lbl"] = mensal["mes"].apply(mlabel)
    head2 = ["Mês", "Passagens", "Refil Diant.", "Aprov. Diant.", "Refil Tras.",
             "Aprov. Tras.", "Fat. Diant. (R$)", "Fat. Tras. (R$)", "Fat. Total (R$)"]
    _cabecalho_excel(ws2, head2, 1, E)
    for i, (_, row) in enumerate(mensal.iterrows()):
        r = 2 + i
        vals = [row["lbl"], row["passagens"], row["refil_diant"], row["aproveitamento"],
                row["refil_tras"], row["aproveitamento_tras"], row["total_diant"],
                row["total_tras"], row["total_geral"]]
        for j, v in enumerate(vals, 1):
            c = ws2.cell(r, j, _v(v)); c.font = Font(name="Arial", size=10); c.border = E["BD"]
            if j in (2, 3, 5):
                c.number_format = "#,##0"; c.alignment = E["centro"]
            elif j in (4, 6):
                c.number_format = "0.0%"; c.alignment = E["centro"]
            elif j in (7, 8, 9):
                c.number_format = "R$ #,##0.00"
    for j, w in enumerate([12, 11, 12, 12, 11, 12, 14, 14, 14], 1):
        ws2.column_dimensions[get_column_letter(j)].width = w
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _gerar_excel_relatorio(g, ov, titulo, ordenar, nome_aba, colunas, larguras):
    """Excel dos relatórios mensais (por gerente e por consultor).

    `colunas`: lista de (rótulo, campo, tipo), com tipo em int/pct/money/texto.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    E = _estilos_excel()
    FMT = {"int": "#,##0", "pct": "0.0%", "money": "R$ #,##0.00"}
    wb = Workbook(); ws = wb.active; ws.title = nome_aba
    ws.cell(1, 1, titulo).font = E["titulo"](13)
    ws.cell(2, 1, f"Ordenado por {ordenar} · Gerado em "
                  f"{dt.datetime.now().strftime('%d/%m/%Y %H:%M')}").font = E["nota"]
    H = 4
    _cabecalho_excel(ws, ["Seq"] + [c[0] for c in colunas], H, E)
    for i, (_, r) in enumerate(g.iterrows()):
        rr = H + 1 + i
        vals = [(i + 1, "seq")] + [(r[campo], tipo) for _, campo, tipo in colunas]
        for j, (v, tipo) in enumerate(vals, 1):
            c = ws.cell(rr, j, _v(v)); c.font = Font(name="Arial", size=10); c.border = E["BD"]
            if tipo in ("seq", "int", "pct"):
                c.alignment = E["centro"]
            if tipo in FMT:
                c.number_format = FMT[tipo]
        if i % 2 == 1:
            for j in range(1, len(colunas) + 2):
                ws.cell(rr, j).fill = E["zebra"]
    tr = H + 1 + len(g)
    ws.cell(tr, 2, "TOTAL").font = Font(name="Arial", bold=True, size=10)
    for j, (_, campo, tipo) in enumerate(colunas, 2):
        if tipo == "texto":
            continue
        v = 1.0 if campo == "part" else _v(ov[campo])
        c = ws.cell(tr, j, v); c.font = Font(name="Arial", bold=True, size=10); c.border = E["BD"]
        c.number_format = FMT[tipo]
        if tipo in ("int", "pct"):
            c.alignment = E["centro"]
    for j, w in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = f"A{H + 1}"
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


# ============================ PÁGINA: DASHBOARD ============================
def pagina_dashboard():
    st.title(f"📊 Análise de Vendas — {GRUPO}")
    try:
        df = dados.ler_base_tidy()
    except Exception:
        st.error("Não foi possível ler a base de dados no momento. Tente novamente.")
        return

    if df.empty:
        st.info("Ainda não há lançamentos na base.")
        return

    # ---- Seleção do mês de referência ----
    meses_disp = sorted(df["mes"].dropna().unique())
    lbl_to_mes = {mlabel(m): m for m in meses_disp}
    labels_mes = [mlabel(m) for m in reversed(meses_disp)]  # mais recente primeiro
    csel, _ = st.columns([2, 3])
    mes_sel_lbl = csel.selectbox(
        "📅 Mês de referência", labels_mes, index=0,
        help="Escolha o mês para ver os KPIs. Os gráficos mostram o trimestre "
             "móvel encerrado no mês selecionado.")
    mes_sel = lbl_to_mes[mes_sel_lbl]

    win, keep = last_n_months(df, mes_fim=mes_sel)
    ordem_meses = [mlabel(m) for m in sorted(keep)]
    periodo = " · ".join(ordem_meses)
    st.caption(f"Acompanhamento trimestral móvel · {periodo}")

    # ---- Filtros (sidebar) ----
    st.sidebar.header("Filtros")
    st.sidebar.caption(f"Trimestre vigente: **{periodo}**")
    marcas = dados.ordenar(win["marca"].dropna().unique())
    sel_marcas = st.sidebar.multiselect("Marca", marcas, default=[], placeholder="Todas")

    base_uni = win[win["marca"].isin(sel_marcas)] if sel_marcas else win
    unidades = dados.ordenar(base_uni["unidade"].dropna().unique())
    sel_unidades = st.sidebar.multiselect("Unidade", unidades, default=[], placeholder="Todas")

    base_cons = win.copy()
    if sel_marcas:
        base_cons = base_cons[base_cons["marca"].isin(sel_marcas)]
    if sel_unidades:
        base_cons = base_cons[base_cons["unidade"].isin(sel_unidades)]
    consultores = dados.ordenar(base_cons["consultor"].dropna().unique())
    sel_cons = st.sidebar.multiselect("Consultor", consultores, default=[], placeholder="Todos")
    st.sidebar.divider()
    st.sidebar.caption("Sem consultor selecionado, mostra o agregado do filtro. "
                       "Selecionando consultores, cada um vira uma linha.")

    f = win.copy()
    if sel_marcas:
        f = f[f["marca"].isin(sel_marcas)]
    if sel_unidades:
        f = f[f["unidade"].isin(sel_unidades)]
    if sel_cons:
        f = f[f["consultor"].isin(sel_cons)]

    if f.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    # ---- Exportar relatório (reflete os filtros atuais) ----
    partes = []
    if sel_marcas:
        partes.append("Marcas: " + ", ".join(sel_marcas))
    if sel_unidades:
        partes.append("Unidades: " + ", ".join(sel_unidades))
    if sel_cons:
        partes.append("Consultores: " + ", ".join(sel_cons))
    filtros_txt = " · ".join(partes) if partes else "Todos"
    _, colexp = st.columns([3, 1])
    colexp.download_button(
        "📥 Exportar relatório (Excel)",
        data=gerar_excel_ranking(f, periodo, filtros_txt),
        file_name=f"Ranking_{ARQ}_{dt.date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    # ---- KPI cards ----
    mensal = agg_by(f, "mes").sort_values("mes")
    mensal["mes_lbl"] = mensal["mes"].apply(mlabel)
    atual = mensal.iloc[-1]
    ant = mensal.iloc[-2] if len(mensal) > 1 else None

    def d(col, kind):
        return delta_str(atual[col] - ant[col], kind) if ant is not None else None

    r1 = st.columns(3)
    r1[0].metric(f"Passagens ({mes_sel_lbl})", fmt_int(atual["passagens"]), d("passagens", "int"))
    r1[1].metric(f"Nº Refil Diant. ({mes_sel_lbl})", fmt_int(atual["refil_diant"]),
                 d("refil_diant", "int"))
    r1[2].metric(f"Aproveitamento Diant. ({mes_sel_lbl})", fmt_pct(atual["aproveitamento"]),
                 d("aproveitamento", "pp"))
    r2 = st.columns(3)
    r2[0].metric(f"Faturamento total ({mes_sel_lbl})", fmt_money(atual["total_geral"]),
                 d("total_geral", "money"))
    r2[1].metric(f"Nº Refil Tras. ({mes_sel_lbl})", fmt_int(atual["refil_tras"]),
                 d("refil_tras", "int"))
    r2[2].metric(f"Aproveitamento Tras. ({mes_sel_lbl})", fmt_pct(atual["aproveitamento_tras"]),
                 d("aproveitamento_tras", "pp"))
    st.caption("Variação comparada ao mês imediatamente anterior dentro da janela.")
    st.divider()

    # ---- Evolução ----
    st.subheader("Evolução no trimestre")
    by_cons = bool(sel_cons)
    if by_cons:
        evo = agg_by(f, ["mes", "consultor"]).sort_values("mes")
        evo["mes_lbl"] = evo["mes"].apply(mlabel)
        color = "consultor"
    else:
        evo = mensal.copy()
        evo["consultor"] = "Agregado"
        color = None
    ordem_cons = dados.ordenar(evo["consultor"].unique())

    def line_fig(dfp, ycol, titulo, fmt):
        # Agregado: uma linha só, no vermelho de acento. Por consultor: cada um
        # com cor e traço próprios (identidade não depende só da cor).
        fig = px.line(dfp, x="mes_lbl", y=ycol, color=color, line_dash=color, markers=True,
                      color_discrete_sequence=PALETA, line_dash_sequence=TRACOS,
                      category_orders={"mes_lbl": ordem_meses, "consultor": ordem_cons})
        fig.update_traces(hovertemplate="%{x}<br>" + fmt + "<extra>%{fullData.name}</extra>",
                          line_width=2.5, marker_size=8)
        aplicar_tema(fig, title=titulo, height=300, margin=dict(l=10, r=10, t=50, b=10),
                     xaxis_title=None, yaxis_title=None,
                     legend=dict(orientation="h", y=-0.2, title=None))
        # Piso do eixo Y por métrica (em vez de começar no zero): dá zoom o
        # suficiente para ver a variação, sem exagerar as quedas. No modo por
        # consultor, com valores menores, o eixo volta a se ajustar sozinho.
        pisos = {"passagens": 1500, "refil_diant": 350,
                 "aproveitamento": 0.10, "total_geral": 80000}
        piso = pisos.get(ycol)
        ymax = dfp[ycol].max()
        if piso is not None and pd.notna(ymax) and ymax > piso:
            fig.update_yaxes(range=[piso, ymax * 1.05])
        else:
            fig.update_yaxes(rangemode="tozero")
        if ycol == "aproveitamento":
            fig.update_yaxes(tickformat=".0%")
        return fig

    r1c1, r1c2 = st.columns(2)
    r1c1.plotly_chart(line_fig(evo, "passagens", "Passagens", "%{y:,.0f}"), width="stretch")
    r1c2.plotly_chart(line_fig(evo, "refil_diant", "Nº Refil Dianteiro", "%{y:,.0f}"),
                      width="stretch")
    r2c1, r2c2 = st.columns(2)
    r2c1.plotly_chart(line_fig(evo, "aproveitamento", "Aproveitamento", "%{y:.1%}"),
                      width="stretch")
    r2c2.plotly_chart(line_fig(evo, "total_geral", "Faturamento (R$)", "R$ %{y:,.2f}"),
                      width="stretch")
    st.divider()

    # ---- Por unidade (aproveitamento ou faturamento) ----
    ctit, cord = st.columns([3, 1])
    ord_uni = cord.radio("Ordenar por", ["Aproveitamento", "Faturamento"], key="ord_unidade")
    por_fat = ord_uni == "Faturamento"
    ctit.subheader("Faturamento por unidade" if por_fat else "Aproveitamento por unidade")
    ctit.caption("Faturamento total por unidade, somado no trimestre. Em vermelho, a líder."
                 if por_fat else
                 "Taxa de conversão (refil dianteiro ÷ passagens) por unidade, "
                 "somada no trimestre. Em vermelho, a líder.")
    apu = agg_by(f, "unidade")
    if por_fat:
        apu = apu.sort_values("total_geral")
        xcol = "total_geral"
        txt = apu["total_geral"].map(fmt_money)
        htmpl, xfmt = "%{y}<br>R$ %{x:,.2f}<extra></extra>", None
    else:
        apu = apu[apu["passagens"] > 0].sort_values("aproveitamento")
        xcol = "aproveitamento"
        txt = apu["aproveitamento"].map(fmt_pct)
        htmpl, xfmt = "%{y}<br>%{x:.1%}<extra></extra>", ".0%"
    if apu.empty:
        st.caption("Sem dados suficientes no período para montar este gráfico.")
    else:
        figu = px.bar(apu, x=xcol, y="unidade", orientation="h", text=txt)
        figu.update_traces(hovertemplate=htmpl, textposition="outside", cliponaxis=False,
                           marker_color=cores_destaque(len(apu)),
                           textfont_color=TEXTO)
        aplicar_tema(figu, height=max(320, 28 * len(apu)),
                     margin=dict(l=10, r=60, t=20, b=10),
                     xaxis_title=ord_uni, yaxis_title=None)
        if xfmt:
            figu.update_xaxes(tickformat=xfmt)
        st.plotly_chart(figu, width="stretch")
    st.divider()

    # ---- Ranking ----
    st.subheader("Ranking no trimestre")
    rk = {"Faturamento (R$)": ("total_geral", "money"),
          "Passagens": ("passagens", "int"),
          "Nº Refil Dianteiro": ("refil_diant", "int"),
          "Aproveitamento": ("aproveitamento", "pct")}
    colr1, colr2 = st.columns([2, 1])
    metrica = colr1.selectbox("Ordenar por", list(rk.keys()))
    topn = colr2.slider("Quantos exibir", 5, 65, 15)
    ycol, kind = rk[metrica]
    rank = agg_by(f, "consultor").sort_values(ycol, ascending=False).head(topn).sort_values(ycol)
    if kind == "money":
        txt = rank[ycol].map(fmt_money); htmpl = "R$ %{x:,.2f}<extra></extra>"; xfmt = None
    elif kind == "pct":
        txt = rank[ycol].map(fmt_pct); htmpl = "%{x:.1%}<extra></extra>"; xfmt = ".0%"
    else:
        txt = rank[ycol].map(fmt_int); htmpl = "%{x:,.0f}<extra></extra>"; xfmt = None
    figr = px.bar(rank, x=ycol, y="consultor", orientation="h", text=txt)
    figr.update_traces(hovertemplate=htmpl, textposition="outside", cliponaxis=False,
                       marker_color=cores_destaque(len(rank)), textfont_color=TEXTO)
    aplicar_tema(figr, height=max(340, 26 * len(rank)),
                 margin=dict(l=10, r=40, t=20, b=10),
                 xaxis_title=metrica, yaxis_title=None)
    if xfmt:
        figr.update_xaxes(tickformat=xfmt)
    st.plotly_chart(figr, width="stretch")
    st.divider()

    # ---- Tabela detalhada ----
    with st.expander("Ver dados detalhados (filtro aplicado)"):
        show = f[["consultor", "unidade", "mes_label", "passagens", "refil_diant",
                  "refil_tras", "aproveitamento", "total_diant", "total_tras",
                  "total_geral"]].copy()
        show["aproveitamento"] = show["aproveitamento"] * 100
        show = show.rename(columns={
            "consultor": "Consultor", "unidade": "Unidade", "mes_label": "Mês",
            "passagens": "Passagens", "refil_diant": "Refil Diant.",
            "refil_tras": "Refil Tras.", "aproveitamento": "Aproveitamento",
            "total_diant": "Total Diant.", "total_tras": "Total Tras.",
            "total_geral": "Total Geral"})
        st.dataframe(show, width="stretch", hide_index=True,
                     column_config={
                         "Aproveitamento": st.column_config.NumberColumn(format="%.1f%%"),
                         "Total Diant.": st.column_config.NumberColumn(format="R$ %.2f"),
                         "Total Tras.": st.column_config.NumberColumn(format="R$ %.2f"),
                         "Total Geral": st.column_config.NumberColumn(format="R$ %.2f")})


# ======================= PÁGINA: RELATÓRIO POR GERENTE =======================
# Verba paga ao gerente da unidade por refil vendido (R$ por unidade).
VERBA_GER_DIANT, VERBA_GER_TRAS = 2.50, 1.25


def _relatorio_gerente(df, mes_sel):
    """Monta o ranking por gerente/unidade de um mês + a linha de totais."""
    sem = df[df["mes"] == mes_sel].copy()
    sem["gerente"] = sem["gerente"].fillna("(sem gerente)")
    g = agg_by(sem, ["unidade", "gerente", "loja", "marca"])
    g["aprov_d"] = (g["refil_diant"] / g["passagens"]).where(g["passagens"] > 0)
    g["aprov_t"] = (g["refil_tras"] / g["passagens"]).where(g["passagens"] > 0)
    tot_fat = g["total_geral"].sum()
    g["part"] = (g["total_geral"] / tot_fat) if tot_fat else 0.0
    g["verba"] = g["refil_diant"] * VERBA_GER_DIANT + g["refil_tras"] * VERBA_GER_TRAS
    ov = agg_by(sem.assign(_g=1), "_g").iloc[0].to_dict()
    p = ov["passagens"]
    ov["aprov_d"] = (ov["refil_diant"] / p) if (p and p > 0) else None
    ov["aprov_t"] = (ov["refil_tras"] / p) if (p and p > 0) else None
    ov["verba"] = ov["refil_diant"] * VERBA_GER_DIANT + ov["refil_tras"] * VERBA_GER_TRAS
    return g, ov


COLS_XL_GERENTE = [("Gerente", "gerente", "texto"), ("Marca", "marca", "texto"),
                   ("Loja", "loja", "texto"), ("Passagens", "passagens", "int"),
                   ("Refil Diant.", "refil_diant", "int"), ("% Aprov", "aprov_d", "pct"),
                   ("Total Diant.", "total_diant", "money"), ("Refil Tras.", "refil_tras", "int"),
                   ("% Aprov", "aprov_t", "pct"), ("Total Tras.", "total_tras", "money"),
                   ("Total Geral", "total_geral", "money"), ("Part %", "part", "pct"),
                   ("Verba", "verba", "money")]


def gerar_excel_gerente(g, ov, mes_lbl, ordenar):
    return _gerar_excel_relatorio(
        g, ov, f"Resultado {GRUPO} {mes_lbl}", ordenar, "Relatório Gerente",
        COLS_XL_GERENTE, [5, 14, 10, 10, 11, 12, 9, 13, 11, 9, 13, 14, 8, 12])


def pagina_relatorio_gerente():
    st.title("📅 Relatório por Gerente")
    st.caption("Ranking das unidades no mês, no formato do relatório da diretoria.")
    try:
        df = dados.ler_base_tidy()
    except Exception:
        st.error("Não foi possível ler a base de dados no momento. Tente novamente.")
        return
    if df.empty or df["mes"].dropna().empty:
        st.info("Ainda não há lançamentos na base.")
        return

    meses = sorted(df["mes"].dropna().unique(), reverse=True)
    mes_por_label = {label_mes(pd.Timestamp(s)): s for s in meses}
    c1, c2 = st.columns([2, 1])
    label_sel = c1.selectbox("Mês", list(mes_por_label.keys()))
    ordenar = c2.radio("Ordenar por", ["Faturamento", "Aproveitamento"], horizontal=True)
    mes_sel = mes_por_label[label_sel]

    g, ov = _relatorio_gerente(df, mes_sel)
    if g.empty:
        st.warning("Sem dados neste mês.")
        return
    ordcol = "total_geral" if ordenar == "Faturamento" else "aprov_d"
    g = g.sort_values(ordcol, ascending=False).reset_index(drop=True)

    k1, k2, k3, k4 = st.container(key="kpis_relatorio").columns(4)
    k1.metric("Passagens", fmt_int(ov["passagens"]))
    k2.metric("Refil Diant.", fmt_int(ov["refil_diant"]))
    k3.metric("Aproveitamento", fmt_pct(ov["aprov_d"]))
    k4.metric("Faturamento total", fmt_money(ov["total_geral"]))

    _, cexp = st.columns([3, 1])
    cexp.download_button(
        "📥 Exportar relatório (Excel)",
        data=gerar_excel_gerente(g, ov, label_sel, ordenar),
        file_name=f"Relatorio_Gerente_{ARQ}_{pd.Timestamp(mes_sel).date().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    linhas = []
    for i, (_, r) in enumerate(g.iterrows(), 1):
        linhas.append({
            "Seq": str(i), "Gerente": r["gerente"], "Marca": r["marca"], "Loja": r["loja"],
            "Passagens": fmt_int(r["passagens"]), "Refil Diant.": fmt_int(r["refil_diant"]),
            "% Aprov (D)": fmt_pct(r["aprov_d"]), "Total Diant.": fmt_money(r["total_diant"]),
            "Refil Tras.": fmt_int(r["refil_tras"]), "% Aprov (T)": fmt_pct(r["aprov_t"]),
            "Total Tras.": fmt_money(r["total_tras"]), "Total Geral": fmt_money(r["total_geral"]),
            "Part %": fmt_pct(r["part"]), "Verba": fmt_money(r["verba"]),
        })
    linhas.append({
        "Seq": "", "Gerente": "TOTAL", "Marca": "", "Loja": "",
        "Passagens": fmt_int(ov["passagens"]), "Refil Diant.": fmt_int(ov["refil_diant"]),
        "% Aprov (D)": fmt_pct(ov["aprov_d"]), "Total Diant.": fmt_money(ov["total_diant"]),
        "Refil Tras.": fmt_int(ov["refil_tras"]), "% Aprov (T)": fmt_pct(ov["aprov_t"]),
        "Total Tras.": fmt_money(ov["total_tras"]), "Total Geral": fmt_money(ov["total_geral"]),
        "Part %": "100,0%", "Verba": fmt_money(ov["verba"]),
    })
    st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    # "R\$": sem o escape, o Markdown lê o trecho entre dois "$" como fórmula.
    st.caption(f"Verba = (Refil Diant. × R\\$ {fmt_money(VERBA_GER_DIANT)[3:]}) + "
               f"(Refil Tras. × R\\$ {fmt_money(VERBA_GER_TRAS)[3:]}). "
               "Part % = participação da unidade no faturamento total do mês.")


# ===================== PÁGINA: RELATÓRIO POR CONSULTOR =====================
# Verba paga ao consultor por refil vendido (R$ por unidade).
VERBA_DIANT, VERBA_TRAS = 10, 5


def _relatorio_consultor(df, mes_sel):
    """Monta o ranking por consultor/unidade de um mês + a linha de totais."""
    sem = df[df["mes"] == mes_sel].copy()
    g = agg_by(sem, ["consultor", "unidade"])
    g["aprov_d"] = (g["refil_diant"] / g["passagens"]).where(g["passagens"] > 0)
    g["aprov_t"] = (g["refil_tras"] / g["passagens"]).where(g["passagens"] > 0)
    tot_fat = g["total_geral"].sum()
    g["part"] = (g["total_geral"] / tot_fat) if tot_fat else 0.0
    g["verba"] = g["refil_diant"] * VERBA_DIANT + g["refil_tras"] * VERBA_TRAS
    ov = agg_by(sem.assign(_g=1), "_g").iloc[0].to_dict()
    p = ov["passagens"]
    ov["aprov_d"] = (ov["refil_diant"] / p) if (p and p > 0) else None
    ov["aprov_t"] = (ov["refil_tras"] / p) if (p and p > 0) else None
    ov["verba"] = ov["refil_diant"] * VERBA_DIANT + ov["refil_tras"] * VERBA_TRAS
    return g, ov


COLS_XL_CONSULTOR = [("Consultor", "consultor", "texto"), ("Unidade", "unidade", "texto"),
                     ("Passagens", "passagens", "int"), ("Refil Diant.", "refil_diant", "int"),
                     ("% Aprov", "aprov_d", "pct"), ("Total Diant.", "total_diant", "money"),
                     ("Refil Tras.", "refil_tras", "int"), ("% Aprov", "aprov_t", "pct"),
                     ("Total Tras.", "total_tras", "money"), ("Total Geral", "total_geral", "money"),
                     ("Part %", "part", "pct"), ("Verba", "verba", "money")]


def gerar_excel_consultor(g, ov, mes_lbl, ordenar):
    return _gerar_excel_relatorio(
        g, ov, f"Resultado por Consultor {GRUPO} {mes_lbl}", ordenar, "Relatório Consultor",
        COLS_XL_CONSULTOR, [5, 16, 14, 11, 12, 9, 13, 11, 9, 13, 14, 8, 12])


def pagina_relatorio_consultor():
    st.title("🧑‍💼 Relatório por Consultor")
    st.caption("Ranking dos consultores no mês, com a verba de cada um.")
    try:
        df = dados.ler_base_tidy()
    except Exception:
        st.error("Não foi possível ler a base de dados no momento. Tente novamente.")
        return
    if df.empty or df["mes"].dropna().empty:
        st.info("Ainda não há lançamentos na base.")
        return

    meses = sorted(df["mes"].dropna().unique(), reverse=True)
    mes_por_label = {label_mes(pd.Timestamp(s)): s for s in meses}
    TODAS = "Todas as unidades"
    unidades = [TODAS] + dados.ordenar(df["unidade"].dropna().unique())
    c1, c2, c3 = st.columns([2, 2, 1])
    label_sel = c1.selectbox("Mês", list(mes_por_label.keys()))
    unidade_sel = c2.selectbox("Unidade", unidades)
    ordenar = c3.radio("Ordenar por", ["Faturamento", "Aproveitamento"], horizontal=True)
    mes_sel = mes_por_label[label_sel]

    if unidade_sel != TODAS:
        df = df[df["unidade"] == unidade_sel]
    if df[df["mes"] == mes_sel].empty:
        st.warning("Sem dados para esta unidade neste mês.")
        return
    g, ov = _relatorio_consultor(df, mes_sel)
    if g.empty:
        st.warning("Sem dados neste mês.")
        return
    ordcol = "total_geral" if ordenar == "Faturamento" else "aprov_d"
    g = g.sort_values(ordcol, ascending=False).reset_index(drop=True)

    k1, k2, k3, k4 = st.container(key="kpis_relatorio").columns(4)
    k1.metric("Passagens", fmt_int(ov["passagens"]))
    k2.metric("Refil Diant.", fmt_int(ov["refil_diant"]))
    k3.metric("Aproveitamento", fmt_pct(ov["aprov_d"]))
    k4.metric("Faturamento total", fmt_money(ov["total_geral"]))

    _, cexp = st.columns([3, 1])
    cexp.download_button(
        "📥 Exportar relatório (Excel)",
        data=gerar_excel_consultor(g, ov, label_sel, ordenar),
        file_name=f"Relatorio_Consultor_{ARQ}_{pd.Timestamp(mes_sel).date().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    linhas = []
    for i, (_, r) in enumerate(g.iterrows(), 1):
        linhas.append({
            "Seq": str(i), "Consultor": r["consultor"], "Unidade": r["unidade"],
            "Passagens": fmt_int(r["passagens"]), "Refil Diant.": fmt_int(r["refil_diant"]),
            "% Aprov (D)": fmt_pct(r["aprov_d"]), "Total Diant.": fmt_money(r["total_diant"]),
            "Refil Tras.": fmt_int(r["refil_tras"]), "% Aprov (T)": fmt_pct(r["aprov_t"]),
            "Total Tras.": fmt_money(r["total_tras"]), "Total Geral": fmt_money(r["total_geral"]),
            "Part %": fmt_pct(r["part"]), "Verba": fmt_money(r["verba"]),
        })
    linhas.append({
        "Seq": "", "Consultor": "TOTAL", "Unidade": "",
        "Passagens": fmt_int(ov["passagens"]), "Refil Diant.": fmt_int(ov["refil_diant"]),
        "% Aprov (D)": fmt_pct(ov["aprov_d"]), "Total Diant.": fmt_money(ov["total_diant"]),
        "Refil Tras.": fmt_int(ov["refil_tras"]), "% Aprov (T)": fmt_pct(ov["aprov_t"]),
        "Total Tras.": fmt_money(ov["total_tras"]), "Total Geral": fmt_money(ov["total_geral"]),
        "Part %": "100,0%", "Verba": fmt_money(ov["verba"]),
    })
    st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    st.caption(f"Verba = (Refil Diant. × R\\$ {VERBA_DIANT}) + (Refil Tras. × R\\$ {VERBA_TRAS}). "
               "Part % = participação do consultor no faturamento total do mês.")


# Página Verbas fica em módulo próprio, como no produto.
from verbas_pagina import pagina_verbas  # noqa: E402


# ============================ NAVEGAÇÃO ============================
_injetar_css()
mostrar_logo()
st.sidebar.title(GRUPO)
pagina = st.sidebar.radio("Menu", PAGINAS, key="menu_pagina")
st.sidebar.divider()

DESTINOS = {
    PAG_DASHBOARD: pagina_dashboard,
    PAG_VERBAS: pagina_verbas,
    PAG_GERENTE: pagina_relatorio_gerente,
    PAG_CONSULTOR: pagina_relatorio_consultor,
}
cabecalho()
DESTINOS.get(pagina, pagina_dashboard)()

st.sidebar.divider()
st.sidebar.markdown('<span class="rodape-demo">Suiçatech · Intrace Br<br>'
                    'Versão de demonstração · dados fictícios</span>',
                    unsafe_allow_html=True)
