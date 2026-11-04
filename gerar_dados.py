"""
Gera a base fictícia do dashboard modelo: base_modelo.xlsx.

    python gerar_dados.py               # semente padrão (reproduz a base entregue)
    python gerar_dados.py --semente 99  # outra base, mesma estrutura

Estrutura (a mesma de uma operação real do produto, anonimizada):
  - 5 marcas, 10 lojas e 17 unidades (unidade = marca + loja);
  - 1 gerente por unidade;
  - 63 vagas de consultor. No trimestre passam 65 consultores, porque há
    saídas e contratações, como numa rede de verdade;
  - trimestre móvel de agosto a outubro de 2026;
  - Sell In (pedidos da concessionária à Suiçatech), pagamentos de verba e
    uso da verba de marketing, para alimentar a página Verbas.

Os valores ficam na faixa de uma operação real: as médias por consultor/mês
estão em REFERENCIA. O script começa na semente informada e usa a primeira
cujas médias fiquem a no máximo TOLERANCIA das referências, então a base é
sempre reprodutível e sempre na faixa certa.

Variação natural da base:
  - cada consultor tem volume (passagens) e conversão próprios: uns acima da
    média, outros abaixo;
  - dois consultores caem mês a mês no trimestre (EM_QUEDA) e um sobe (EM_ALTA);
  - contratados no meio do trimestre começam abaixo e vão subindo.

Regras de cálculo (as mesmas do app):
  faturamento    = refil_diant × preço dianteiro + refil_tras × preço traseiro
  aproveitamento = refil_diant ÷ passagens
  verba consultor = refil_diant × R$ 10 + refil_tras × R$ 5
"""

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "base_modelo.xlsx"

SEMENTE = 2026
TOLERANCIA = 0.06            # distância máxima de cada média para a referência
MESES = pd.to_datetime(["2026-08-01", "2026-09-01", "2026-10-01"])

# Preço ao consumidor final, por marca (R$ por par dianteiro / por unidade traseira).
# A Marca 5 não tem refil traseiro no catálogo: preço zero e nenhuma venda.
PRECOS = {
    "Marca 1": (197.90, 118.90),
    "Marca 2": (197.90, 98.90),
    "Marca 3": (168.90, 98.90),
    "Marca 4": (168.90, 98.90),
    "Marca 5": (168.90, 0.00),
}

# unidade, marca, loja, vagas, passagens/consultor/mês, aproveitamento, refil traseiro/passagem
UNIDADES = [
    ("Unidade 1", "Marca 1", "Loja 1", 5, 76, 0.27, 0.17),
    ("Unidade 2", "Marca 2", "Loja 1", 4, 66, 0.20, 0.10),
    ("Unidade 3", "Marca 3", "Loja 1", 4, 68, 0.47, 0.07),
    ("Unidade 4", "Marca 4", "Loja 1", 3, 64, 0.42, 0.33),
    ("Unidade 5", "Marca 5", "Loja 1", 4, 92, 0.23, 0.00),
    ("Unidade 6", "Marca 1", "Loja 2", 4, 57, 0.18, 0.13),
    ("Unidade 7", "Marca 2", "Loja 2", 4, 46, 0.10, 0.02),
    ("Unidade 8", "Marca 3", "Loja 2", 3, 72, 0.16, 0.05),
    ("Unidade 9", "Marca 1", "Loja 3", 3, 50, 0.13, 0.04),
    ("Unidade 10", "Marca 2", "Loja 3", 5, 70, 0.21, 0.11),
    ("Unidade 11", "Marca 2", "Loja 4", 3, 61, 0.13, 0.05),
    ("Unidade 12", "Marca 2", "Loja 5", 3, 80, 0.16, 0.04),
    ("Unidade 13", "Marca 3", "Loja 6", 3, 62, 0.55, 0.13),
    ("Unidade 14", "Marca 3", "Loja 7", 3, 69, 0.19, 0.03),
    ("Unidade 15", "Marca 1", "Loja 8", 4, 66, 0.21, 0.07),
    ("Unidade 16", "Marca 1", "Loja 9", 5, 63, 0.31, 0.22),
    ("Unidade 17", "Marca 1", "Loja 10", 3, 59, 0.29, 0.12),
]

# Médias por consultor/mês de uma operação real do produto (ago–out/2026).
REFERENCIA = {
    "passagens": 65.59,
    "refil_diant": 16.79,
    "refil_tras": 6.76,
    "aproveitamento": 0.2576,
    "faturamento": 3832.71,
    "verba": 201.73,
}

VERBA_CONSULTOR = {"diant": 10.00, "tras": 5.00}
VERBA_GERENTE = {"diant": 2.50, "tras": 1.25}
VERBA_MARKETING = {"diant": 2.00, "tras": 1.00}

# Catálogo Suiçatech usado no Sell In (preço de venda à concessionária).
PRODUTOS = {
    "AT800": ("REFIL PALHETA AEROTWIN PAR 31,5 POLEGADAS", "diant", 96.70),
    "63 750": ("REFIL PALHETA CONVENCIONAL PAR 29,5 POLEGADAS", "diant", 96.70),
    "ATT400": ("REFIL PALHETA TRASEIRA SISTEMA AERODINÂMICO 15,75 POLEGADAS", "tras", 56.80),
    "63 510": ("REFIL PALHETA CONVENCIONAL TRAS. 20 POLEGADAS", "tras", 56.80),
}

# Verba de consultor e gerente paga até setembro; outubro ainda em aberto.
PAGAMENTOS = [("2026-08-01", "Sim", "Sim"), ("2026-09-01", "Sim", "Sim"),
              ("2026-10-01", "Não", "Não")]
MARKETING_PAGOS = [("2026-10-01", 4500.00)]

TENDENCIA_REDE = [0.97, 1.00, 1.03]          # leve alta da conversão no trimestre
EM_QUEDA = {"aprov": [1.00, 0.72, 0.45], "passagens": [1.00, 0.95, 0.88]}
EM_ALTA = {"aprov": [0.78, 0.97, 1.20], "passagens": [0.96, 1.00, 1.05]}
RAMPA_CONTRATADO = [{"aprov": 0.55, "passagens": 0.70}, {"aprov": 0.85, "passagens": 0.90},
                    {"aprov": 1.00, "passagens": 1.00}]


# --------------------------------------------------------------------------
# Quadro de pessoas: quem ocupa cada vaga em cada mês
# --------------------------------------------------------------------------
def montar_quadro(rng):
    """Uma linha por consultor, com a unidade e os meses em que trabalhou.

    63 vagas. Em 58 o mesmo consultor fica o trimestre todo. Nas outras:
      - 1 vaga: saída em agosto, substituído em setembro;
      - 2 vagas: saída depois de setembro, vaga aberta em outubro;
      - 1 vaga: saída depois de setembro, substituído em outubro;
      - 1 vaga: aberta em agosto, preenchida em setembro.
    """
    vagas = [(u[0], i) for u in UNIDADES for i in range(u[3])]
    ordem = rng.permutation(len(vagas))
    roteiro = (["sai_ago"] + ["sai_set"] * 2 + ["troca_out"] + ["nova_set"]
               + ["fixo"] * (len(vagas) - 5))
    pessoas = []
    for k, idx in enumerate(ordem):
        unidade, _ = vagas[idx]
        tipo = roteiro[k]
        if tipo == "fixo":
            pessoas.append((unidade, [0, 1, 2], False))
        elif tipo == "sai_ago":
            pessoas += [(unidade, [0], False), (unidade, [1, 2], True)]
        elif tipo == "sai_set":
            pessoas.append((unidade, [0, 1], False))
        elif tipo == "troca_out":
            pessoas += [(unidade, [0, 1], False), (unidade, [2], True)]
        elif tipo == "nova_set":
            pessoas.append((unidade, [1, 2], True))
    quadro = pd.DataFrame(pessoas, columns=["unidade", "meses", "contratado"])
    # Numeração: quem já estava em agosto recebe 1..N em ordem aleatória;
    # os contratados depois ficam com os números seguintes, por data de entrada.
    quadro["inicio"] = quadro["meses"].map(min)
    veteranos = quadro.index[quadro["inicio"] == 0].to_numpy()
    numeros = np.empty(len(quadro), dtype=int)
    numeros[rng.permutation(veteranos)] = np.arange(1, len(veteranos) + 1)
    novos = quadro.index[quadro["inicio"] > 0]
    novos = sorted(novos, key=lambda i: (quadro.at[i, "inicio"], rng.random()))
    numeros[novos] = np.arange(len(veteranos) + 1, len(quadro) + 1)
    quadro["consultor"] = [f"Consultor {n}" for n in numeros]
    return quadro


# --------------------------------------------------------------------------
# Lançamentos mensais (o que o gerente informa: passagens e refis)
# --------------------------------------------------------------------------
def gerar_lancamentos(rng, quadro):
    uni = {u[0]: u for u in UNIDADES}
    n = len(quadro)
    # Perfil de cada consultor: volume e conversão próprios (média ≈ 1). Os
    # limites cortam caudas que não existem na operação real (ninguém atende o
    # triplo da média da loja).
    volume = np.clip(rng.lognormal(-0.25 ** 2 / 2, 0.25, n), 0.5, 1.5)
    habilidade = np.clip(rng.lognormal(-0.45 ** 2 / 2, 0.45, n), 0.3, 2.2)
    # Traseiro: acompanha a habilidade, mas tem quem quase não oferece.
    fator_tras = habilidade ** 0.6 * rng.lognormal(-0.6 ** 2 / 2, 0.6, n)
    fator_tras[rng.random(n) < 0.12] *= 0.1
    # Clima de cada unidade em cada mês (campanha, fluxo de oficina).
    clima = {(u[0], m): rng.lognormal(0, 0.06) for u in UNIDADES for m in range(3)}

    # Tendências individuais entre quem ficou o trimestre todo.
    fixos = quadro.index[quadro["meses"].map(len) == 3]
    potencial = pd.Series(
        [volume[i] * habilidade[i] * uni[quadro.at[i, "unidade"]][4]
         * uni[quadro.at[i, "unidade"]][5] for i in fixos], index=fixos
    ).sort_values(ascending=False)
    em_queda, unidades_queda = [], set()
    for i in potencial.index[2:]:            # bons vendedores (fora do top 2)
        if quadro.at[i, "unidade"] not in unidades_queda:
            em_queda.append(i)
            unidades_queda.add(quadro.at[i, "unidade"])
        if len(em_queda) == 2:
            break
    meio = [i for i in potencial.index[len(potencial) // 3:]
            if i not in em_queda and quadro.at[i, "unidade"] not in unidades_queda]
    em_alta = meio[0]

    linhas = []
    for i, p in quadro.iterrows():
        _, marca, _, _, pas_base, aprov_base, tras_base = uni[p["unidade"]]
        # Quem tem tendência definida oscila menos no mês, para a queda (ou a
        # alta) aparecer limpa no gráfico em vez de se perder no ruído.
        ruido_pas, ruido_ap = (0.05, 0.06) if (i in em_queda or i == em_alta) else (0.17, 0.22)
        for k, m in enumerate(p["meses"]):
            f_pas, f_ap = 1.0, TENDENCIA_REDE[m]
            if i in em_queda:
                f_pas *= EM_QUEDA["passagens"][m]
                f_ap *= EM_QUEDA["aprov"][m]
            elif i == em_alta:
                f_pas *= EM_ALTA["passagens"][m]
                f_ap *= EM_ALTA["aprov"][m]
            if p["contratado"]:
                f_pas *= RAMPA_CONTRATADO[k]["passagens"]
                f_ap *= RAMPA_CONTRATADO[k]["aprov"]
            media_pas = pas_base * volume[i] * clima[(p["unidade"], m)] * f_pas
            ruido = np.clip(rng.lognormal(-ruido_pas ** 2 / 2, ruido_pas), 0.72, 1.30)
            passagens = max(1, int(round(media_pas * ruido)))
            ap = aprov_base * habilidade[i] * f_ap * rng.lognormal(-ruido_ap ** 2 / 2, ruido_ap)
            ap = float(np.clip(ap, 0.005, 0.85))
            refil_d = int(rng.binomial(passagens, ap))
            tx_t = float(np.clip(tras_base * fator_tras[i] * f_ap, 0, 0.6))
            refil_t = int(rng.binomial(passagens, tx_t)) if PRECOS[marca][1] > 0 else 0
            linhas.append({"mes": MESES[m], "unidade": p["unidade"],
                           "consultor": p["consultor"], "passagens": passagens,
                           "refil_diant": refil_d, "refil_tras": refil_t})
    lanc = pd.DataFrame(linhas).sort_values(["mes", "unidade", "consultor"],
                                            key=chave_natural).reset_index(drop=True)
    destaques = {"em_queda": list(quadro.loc[em_queda, "consultor"]),
                 "em_alta": quadro.at[em_alta, "consultor"]}
    return lanc, destaques


def chave_natural(serie):
    """Ordena 'Unidade 2' antes de 'Unidade 10'."""
    if serie.dtype.kind == "M":
        return serie
    return serie.map(lambda s: (str(s).rsplit(" ", 1)[0], int(str(s).rsplit(" ", 1)[1]))
                     if str(s).rsplit(" ", 1)[-1].isdigit() else (str(s), 0))


# --------------------------------------------------------------------------
# Sell In: pedidos das unidades à Suiçatech
# --------------------------------------------------------------------------
def dias_uteis(mes):
    fim = mes + pd.offsets.MonthEnd(0)
    return pd.bdate_range(mes, fim)


def gerar_sell_in(rng, lanc):
    """Agosto traz o estoque inicial (≈1,45× a venda do mês). Depois, cada mês
    repõe a venda do mês anterior com 10% de folga; se a unidade vender mais do
    que tem, entra um pedido extra no mês para o estoque não ficar negativo.
    Quantidades sempre em múltiplos de 10 (caixas)."""
    venda = lanc.groupby(["unidade", "mes"])[["refil_diant", "refil_tras"]].sum()
    preferencia = {u[0]: ("AT800" if rng.random() < 0.7 else "63 750",
                          "ATT400" if rng.random() < 0.65 else "63 510")
                   for u in UNIDADES}
    caixa = lambda q: int(math.ceil(max(q, 0) / 10) * 10)
    pedidos = []
    for u in UNIDADES:
        unidade = u[0]
        estoque = {"refil_diant": 0, "refil_tras": 0}
        for k, mes in enumerate(MESES):
            q = {}
            for c in estoque:
                atual = venda.loc[(unidade, mes), c]
                base = atual * 1.45 if k == 0 else venda.loc[(unidade, MESES[k - 1]), c] * 1.10
                q[c] = max(caixa(base), caixa(atual - estoque[c]))
                estoque[c] += q[c] - atual
            q_d, q_t = q["refil_diant"], q["refil_tras"]
            if q_d + q_t == 0:
                continue
            dias = dias_uteis(mes)
            if q_d + q_t > 150:              # unidades grandes pedem duas vezes no mês
                partes = [(int(round(q_d * 0.55 / 10) * 10), int(round(q_t * 0.55 / 10) * 10))]
                partes.append((q_d - partes[0][0], q_t - partes[0][1]))
                datas = [rng.choice(dias[:len(dias) // 2]), rng.choice(dias[len(dias) // 2:])]
            else:
                partes, datas = [(q_d, q_t)], [rng.choice(dias)]
            for (pd_, pt_), data in zip(partes, datas):
                itens = []
                if pd_ > 0:
                    itens.append((preferencia[unidade][0], pd_))
                if pt_ > 0:
                    itens.append((preferencia[unidade][1], pt_))
                if itens:
                    pedidos.append((pd.Timestamp(data), unidade, itens))
    pedidos.sort(key=lambda p: (p[0], chave_natural(pd.Series([p[1]])).iloc[0]))
    linhas = []
    for n, (data, unidade, itens) in enumerate(pedidos):
        for codigo, qtde in itens:
            produto, tipo, preco = PRODUTOS[codigo]
            vc, vg, vm = VERBA_CONSULTOR[tipo], VERBA_GERENTE[tipo], VERBA_MARKETING[tipo]
            linhas.append({
                "data": data, "pedido": str(20431 + n), "cliente": unidade,
                "codigo": codigo, "produto": produto, "tipo_refil": tipo,
                "preco_unit": preco, "qtde": qtde, "total_item": round(preco * qtde, 2),
                "verba_consultor": vc, "total_consultor": round(vc * qtde, 2),
                "verba_gerente": vg, "total_gerente": round(vg * qtde, 2),
                "verba_reserva": vm, "total_reserva": round(vm * qtde, 2),
            })
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------
# Conferência das médias
# --------------------------------------------------------------------------
def medias(lanc):
    """Médias por consultor/mês, com as mesmas regras do app."""
    marca = {u[0]: u[1] for u in UNIDADES}
    d = lanc.copy()
    pd_, pt_ = zip(*d["unidade"].map(lambda u: PRECOS[marca[u]]))
    d["faturamento"] = d["refil_diant"] * np.array(pd_) + d["refil_tras"] * np.array(pt_)
    d["aproveitamento"] = d["refil_diant"] / d["passagens"]
    d["verba"] = d["refil_diant"] * VERBA_CONSULTOR["diant"] + d["refil_tras"] * VERBA_CONSULTOR["tras"]
    return {k: float(d[k].mean()) for k in REFERENCIA}


def gerar(semente):
    rng = np.random.default_rng(semente)
    quadro = montar_quadro(rng)
    lanc, destaques = gerar_lancamentos(rng, quadro)
    return rng, quadro, lanc, destaques


def tendencias_ok(lanc, destaques):
    """Os consultores em queda caem todo mês em refis dianteiros; o em alta sobe.

    A rede como um todo fica estável ou em leve alta (outubro entre 100% e 112%
    de agosto em refis dianteiros): a queda é individual, não do grupo.
    """
    total = lanc.groupby("mes")["refil_diant"].sum().sort_index().to_list()
    if not (1.00 <= total[-1] / total[0] <= 1.12):
        return False
    serie = lanc.set_index("consultor")
    for nome in destaques["em_queda"]:
        rd = serie.loc[nome].sort_values("mes")["refil_diant"].to_list()
        if not (rd[0] > rd[1] > rd[2]):
            return False
    rd = serie.loc[destaques["em_alta"]].sort_values("mes")["refil_diant"].to_list()
    return rd[0] < rd[1] < rd[2]


def escolher_semente(inicial, tentativas=500):
    for semente in range(inicial, inicial + tentativas):
        rng, quadro, lanc, destaques = gerar(semente)
        med = medias(lanc)
        if (all(abs(med[k] / REFERENCIA[k] - 1) <= TOLERANCIA for k in REFERENCIA)
                and tendencias_ok(lanc, destaques)):
            return semente, rng, quadro, lanc, destaques, med
    raise RuntimeError("Nenhuma semente dentro da tolerância; revise os parâmetros.")


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------
LEIA_ME = [
    "BASE DO DASHBOARD MODELO — GRUPO MODELO",
    "",
    "Dados fictícios para demonstração. Gerados por gerar_dados.py; rode o script de novo para recriar.",
    "O app lê este arquivo direto (não usa banco de dados). Período: trimestre móvel ago–out/2026.",
    "",
    "ABAS",
    "lancamentos: o que o gerente informa por consultor e mês (passagens, refil dianteiro, refil traseiro).",
    "unidades: cadastro da unidade (marca + loja) e do gerente responsável.",
    "precos_marca: preço do refil ao consumidor final, por marca. Base do faturamento.",
    "sell_in: pedidos das unidades à Suiçatech, com as três verbas por item (página Verbas).",
    "pagamentos: meses cuja verba de consultor e gerente já foi paga (Sim/Não).",
    "marketing_pagos: valores usados da verba de marketing, por mês.",
    "",
    "REGRAS (calculadas no app, não digitadas)",
    "Faturamento = refil dianteiro × preço dianteiro + refil traseiro × preço traseiro.",
    "Aproveitamento = refil dianteiro ÷ passagens.",
    "Verba consultor = refil dianteiro × R$ 10,00 + refil traseiro × R$ 5,00.",
    "Verba gerente = refil dianteiro × R$ 2,50 + refil traseiro × R$ 1,25.",
    "Verba marketing (reserva) = par dianteiro × R$ 2,00 + traseiro × R$ 1,00, provisionada no Sell In.",
]


def salvar_excel(lanc, sell_in, caminho=ARQUIVO):
    from openpyxl.styles import Alignment, Font, PatternFill

    unidades = pd.DataFrame(
        [(u[0], u[1], u[2]) for u in UNIDADES], columns=["unidade", "marca", "loja"])
    unidades["gerente"] = GERENTES
    precos = pd.DataFrame([(m, p[0], p[1]) for m, p in PRECOS.items()],
                          columns=["marca", "preco_diant", "preco_tras"])
    pagos = pd.DataFrame(PAGAMENTOS, columns=["mes", "consultor_pago", "gerente_pago"])
    pagos["mes"] = pd.to_datetime(pagos["mes"])
    mkt = pd.DataFrame(MARKETING_PAGOS, columns=["mes", "valor"])
    mkt["mes"] = pd.to_datetime(mkt["mes"])

    abas = {"leia-me": pd.DataFrame({"COMO ESTA BASE FUNCIONA": LEIA_ME}),
            "lancamentos": lanc, "unidades": unidades, "precos_marca": precos,
            "sell_in": sell_in, "pagamentos": pagos, "marketing_pagos": mkt}
    formatos = {"mes": "mm/yyyy", "data": "dd/mm/yyyy", "valor": "#,##0.00",
                "preco_diant": "#,##0.00", "preco_tras": "#,##0.00"}
    with pd.ExcelWriter(caminho, engine="openpyxl") as w:
        for nome, df in abas.items():
            df.to_excel(w, sheet_name=nome, index=False)
            ws = w.book[nome]
            for cel in ws[1]:
                cel.font = Font(bold=True, color="FFFFFF")
                cel.fill = PatternFill("solid", fgColor="231F20")
                cel.alignment = Alignment(horizontal="center")
            for j, col in enumerate(df.columns, 1):
                letra = ws.cell(1, j).column_letter
                largura = 110 if nome == "leia-me" else max(12, min(48, int(
                    df[col].astype(str).str.len().max() if len(df) else 10) + 2, len(col) + 4))
                ws.column_dimensions[letra].width = largura
                fmt = formatos.get(col)
                if fmt is None and col.startswith(("total_", "verba_", "preco_unit")):
                    fmt = "#,##0.00"
                if fmt:
                    for cel in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                        cel[0].number_format = fmt
            if nome != "leia-me":
                ws.freeze_panes = "A2"
                ws.auto_filter.ref = ws.dimensions


GERENTES = []   # preenchido em main(): numeração aleatória, um por unidade


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--semente", type=int, default=SEMENTE)
    args = ap.parse_args()

    semente, rng, quadro, lanc, destaques, med = escolher_semente(args.semente)
    GERENTES[:] = [f"Gerente {n}" for n in rng.permutation(len(UNIDADES)) + 1]
    sell_in = gerar_sell_in(rng, lanc)
    salvar_excel(lanc, sell_in)

    print(f"Base gerada: {ARQUIVO.name}  (semente {semente})")
    print(f"  {lanc['unidade'].nunique()} unidades · {len(GERENTES)} gerentes · "
          f"{lanc['consultor'].nunique()} consultores · {len(PRECOS)} marcas · "
          f"{len({u[2] for u in UNIDADES})} lojas")
    print("  lançamentos por mês:",
          {m.strftime('%m/%Y'): n for m, n in lanc.groupby('mes').size().items()})
    print(f"  Sell In: {sell_in['pedido'].nunique()} pedidos, {len(sell_in)} itens")
    print(f"  em queda: {', '.join(destaques['em_queda'])} · em alta: {destaques['em_alta']}")
    print("\n  Média por consultor/mês     modelo    referência   diferença")
    for k, ref in REFERENCIA.items():
        print(f"  {k:24} {med[k]:10.2f} {ref:12.2f} {med[k] / ref - 1:+10.1%}")


if __name__ == "__main__":
    main()
