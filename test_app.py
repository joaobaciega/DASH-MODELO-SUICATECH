"""
Teste de fumaça do dashboard modelo (streamlit.testing / AppTest).

    python -m unittest test_app -v

Abre as 4 páginas, percorre meses e filtros e confere que não há erro, que os
gráficos, tabelas e botões de download aparecem e que cada Excel exportado
abre e tem os dados.
"""

import io
import os
import unittest

# Importar app.py fora do `streamlit run` gera avisos "missing ScriptRunContext"
# (inofensivos). Silencia antes de o Streamlit ser importado.
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

PASTA = os.path.dirname(os.path.abspath(__file__))
os.chdir(PASTA)
TIMEOUT = 60


def abrir(pagina=None):
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.run()
    if pagina:
        at.sidebar.radio(key="menu_pagina").set_value(pagina).run()
    return at


def contar(at, tipo):
    return len(at.get(tipo))


class TestPaginas(unittest.TestCase):
    def assert_sem_erro(self, at):
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertEqual(len(at.error), 0, [e.value for e in at.error])

    def test_dashboard(self):
        at = abrir()
        self.assert_sem_erro(at)
        self.assertIn("Grupo Modelo", at.title[0].value)
        self.assertEqual(len(at.metric), 6)
        self.assertEqual(contar(at, "plotly_chart"), 6)       # 4 linhas + unidade + ranking
        self.assertEqual(contar(at, "download_button"), 1)
        # Mês de referência: cada um dos 3 meses
        for mes in at.main.selectbox[0].options:
            at.main.selectbox[0].set_value(mes).run()
            self.assert_sem_erro(at)
            self.assertEqual(contar(at, "plotly_chart"), 6)
        # Por consultor (cada um vira uma linha) + unidade por faturamento + ranking
        at.sidebar.multiselect[2].set_value(["Consultor 16", "Consultor 44", "Consultor 9"]).run()
        self.assert_sem_erro(at)
        at.radio(key="ord_unidade").set_value("Faturamento").run()
        for metrica in at.main.selectbox[1].options:
            at.main.selectbox[1].set_value(metrica).run()
            self.assert_sem_erro(at)
        self.assertEqual(contar(at, "plotly_chart"), 6)
        # Filtro por marca e unidade
        at.sidebar.multiselect[2].set_value([]).run()
        at.sidebar.multiselect[0].set_value(["Marca 1"]).run()
        at.sidebar.multiselect[1].set_value(["Unidade 1"]).run()
        self.assert_sem_erro(at)
        self.assertEqual(contar(at, "plotly_chart"), 6)
        self.assertEqual(len(at.dataframe), 1)                 # tabela detalhada

    def test_relatorio_gerente(self):
        at = abrir("Relatório Por Gerente")
        self.assert_sem_erro(at)
        for mes in at.main.selectbox[0].options:
            for ordem in ("Faturamento", "Aproveitamento"):
                at.main.selectbox[0].set_value(mes)
                at.main.radio[0].set_value(ordem).run()
                self.assert_sem_erro(at)
                self.assertEqual(len(at.metric), 4)
                self.assertEqual(len(at.dataframe), 1)
                self.assertEqual(contar(at, "download_button"), 1)
                self.assertEqual(len(at.dataframe[0].value), 17 + 1)   # 17 unidades + TOTAL

    def test_relatorio_consultor(self):
        at = abrir("Relatório Por Consultor")
        self.assert_sem_erro(at)
        for mes in at.main.selectbox[0].options:
            at.main.selectbox[0].set_value(mes).run()
            self.assert_sem_erro(at)
            self.assertGreaterEqual(len(at.dataframe[0].value), 61)
        at.main.selectbox[1].set_value("Unidade 3").run()
        at.main.radio[0].set_value("Aproveitamento").run()
        self.assert_sem_erro(at)
        self.assertEqual(len(at.metric), 4)
        self.assertEqual(contar(at, "download_button"), 1)

    def test_verbas(self):
        at = abrir("Verbas")
        self.assert_sem_erro(at)
        for mes in at.main.selectbox[1].options:
            at.main.selectbox[1].set_value(mes).run()
            self.assert_sem_erro(at)
            self.assertEqual(len(at.metric), 3)
            self.assertEqual(len(at.dataframe), 2)
            self.assertEqual(contar(at, "plotly_chart"), 1)
            self.assertEqual(contar(at, "download_button"), 1)


class TestExportacoes(unittest.TestCase):
    """Os bytes que os botões entregam: abrem no Excel e trazem os dados."""

    @classmethod
    def setUpClass(cls):
        import logging
        logging.disable(logging.WARNING)   # avisos de "bare mode" ao importar o app
        cls.addClassCleanup(logging.disable, logging.NOTSET)
        import app
        import dados
        import verbas_pagina
        cls.app, cls.dados, cls.vp = app, dados, verbas_pagina
        cls.df = dados.ler_base_tidy()

    def abrir_xlsx(self, b):
        self.assertEqual(b[:2], b"PK")
        return load_workbook(io.BytesIO(b))

    def test_ranking(self):
        wb = self.abrir_xlsx(self.app.gerar_excel_ranking(self.df, "Ago · Set · Out", "Todos"))
        self.assertEqual(wb.sheetnames, ["Ranking Trimestre", "Resumo Mensal"])
        self.assertIn("Grupo Modelo", wb["Ranking Trimestre"]["A1"].value)
        self.assertEqual(wb["Ranking Trimestre"].max_row, 6 + self.df["consultor"].nunique() + 1)
        self.assertEqual(wb["Resumo Mensal"].max_row, 1 + 3)

    def test_gerente_e_consultor(self):
        mes = self.df["mes"].max()
        g, ov = self.app._relatorio_gerente(self.df, mes)
        ws = self.abrir_xlsx(self.app.gerar_excel_gerente(g, ov, "Outubro/2026", "Faturamento")).active
        self.assertEqual(ws.max_row, 4 + 17 + 1)
        self.assertAlmostEqual(ws.cell(ws.max_row, 12).value, ov["total_geral"], places=2)
        g, ov = self.app._relatorio_consultor(self.df, mes)
        ws = self.abrir_xlsx(self.app.gerar_excel_consultor(g, ov, "Outubro/2026", "Faturamento")).active
        self.assertEqual(ws.max_row, 4 + len(g) + 1)
        self.assertEqual(ws.cell(ws.max_row, 13).value, ov["verba"])

    def test_verbas(self):
        from verbas import calcular_verbas
        d = self.dados
        mensal = calcular_verbas(d.ler_vendas_verbas(), self.df, d.ler_pagamentos_verba(),
                                 d.ler_pagamentos_marketing())
        tabela = self.vp.tabela_cliente(mensal, 2026)
        ws = self.abrir_xlsx(self.vp.exportar_excel_cliente(tabela))["Verbas mensais"]
        self.assertEqual(ws.max_row, 1 + 3 + 1)               # cabeçalho + 3 meses + total
        # Verba do consultor gerada pelo Sell Out = refis × tarifa (10 / 5)
        devido = self.df["refil_diant"].sum() * 10 + self.df["refil_tras"].sum() * 5
        self.assertAlmostEqual(mensal["realizada_consultor"].sum(), devido, places=2)


if __name__ == "__main__":
    unittest.main()
