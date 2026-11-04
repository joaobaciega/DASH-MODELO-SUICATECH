"""
Identidade visual Suiçatech: cores extraídas da logo por extrair_paleta.py.

Três cores dominantes na logo (assets/logo_suicatech.jpg):
  BRANCO   #FFFFFF  fundo da arte (74% dos pixels)
  VERMELHO #FA231E  "SUIÇA TECH" e símbolo (20%)      -> acento: dado principal
  GRAFITE  #231F20  "INTRACE Br" (2%)                 -> fundo do app (tema escuro)

Tema escuro: o fundo é o grafite da logo, e as demais cores são misturas dele
com o branco (neutros) e do vermelho com o branco (acentos). Contrastes sobre o
fundo (WCAG 2.1): texto 13,9:1; vermelho 4,1:1 (gráficos e títulos grandes,
mínimo 3:1); VERMELHO_CLARO 4,5:1 sobre o cinza da barra lateral (texto
pequeno); todas as séries dos gráficos acima de 4,3:1.
"""

from pathlib import Path

VERMELHO = "#FA231E"         # acento: série/barra principal, bordas, títulos grandes
VERMELHO_CLARO = "#FC6562"   # vermelho para texto pequeno sobre fundo escuro (4,5:1)
VERMELHO_BOTAO = "#E7231E"   # primaryColor: texto branco em botões e tags (4,5:1)
GRAFITE = "#231F20"          # fundo do app; cabeçalho dos Excel
BRANCO = "#FFFFFF"
FUNDO = GRAFITE              # fundo principal
FUNDO_SECUNDARIO = "#322F30" # barra lateral, cartões de KPI, caixas de dica
LINHA_GRADE = "#444141"      # grade dos gráficos e divisores
TEXTO = "#EDEDED"            # branco suavizado (menos ofuscante que o puro)
TEXTO_SUAVE = "#ABAAAA"      # legendas e notas
CINZA_SERIE = "#868484"      # barras não destacadas (o destaque fica em vermelho)

# Séries dos gráficos, na ordem de uso. Todas com 4,3:1 ou mais sobre o fundo;
# a ordem alterna claro e médio para que vizinhas fiquem distintas também para
# daltônicos (OKLab ΔE ≥ 18 visão normal, ≥ 12 em protan/deutan/tritan).
PALETA = ["#FA231E", "#DEDDDE", "#FC6562", "#BDBCBC",
          "#868484", "#FDA7A5", "#FB4440", "#B2B1B1"]
# Codificação secundária das linhas (não depender só da cor).
TRACOS = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]

# Excel (openpyxl usa ARGB sem "#"). As planilhas exportadas continuam claras:
# são documentos para abrir no Excel e imprimir, não telas do app.
XL_CABECALHO = "FF231F20"
XL_TITULO = "FFDA221E"
XL_ZEBRA = "FFF4F4F4"
XL_BORDA = "FFE5E4E4"

ASSETS = Path(__file__).resolve().parent / "assets"
LOGO = ASSETS / "logo_suicatech_escuro.png"  # "INTRACE Br" claro, para o fundo escuro
ICONE = ASSETS / "icone.png"

GRUPO = "Grupo Modelo"


def aplicar_tema(fig, **layout):
    """Fundo transparente (o grafite do app), texto claro e grade discreta em
    todos os gráficos Plotly."""
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font_color=TEXTO,
                      hoverlabel=dict(bgcolor=FUNDO_SECUNDARIO, bordercolor=LINHA_GRADE,
                                      font_color=TEXTO), **layout)
    fig.update_xaxes(gridcolor=LINHA_GRADE, linecolor=LINHA_GRADE, zerolinecolor=LINHA_GRADE)
    fig.update_yaxes(gridcolor=LINHA_GRADE, linecolor=LINHA_GRADE, zerolinecolor=LINHA_GRADE)
    return fig


def cores_destaque(n, destaque_ultimo=True):
    """Barras horizontais ordenadas: o líder (a última barra, que o Plotly
    desenha no topo) em vermelho; as demais em cinza."""
    cores = [CINZA_SERIE] * n
    if n:
        cores[-1 if destaque_ultimo else 0] = VERMELHO
    return cores
