"""Tests for upload auto-summary (A4)."""

import app


class TestBuildUploadAutoSummary:
    def test_tabular_file_with_stats(self):
        entry = {
            "row_count": 1500,
            "col_names": ["Nome", "Idade", "Salário", "Departamento"],
            "full_col_stats": [
                {"name": "Idade", "type": "numeric", "min": 22, "max": 65, "mean": 38.5},
                {"name": "Salário", "type": "numeric", "min": 800, "max": 5000, "mean": 2100},
                {"name": "Nome", "type": "text", "unique_approx": 1490, "sample": ["Ana", "João"]},
            ],
        }
        result = app._build_upload_auto_summary(entry, "equipa.xlsx")
        assert "equipa.xlsx" in result
        assert "1,500" in result or "1500" in result
        assert "4 colunas" in result
        assert "Idade" in result
        assert "Salário" in result
        assert "gráficos" in result  # CTA for tabular

    def test_tabular_many_columns(self):
        entry = {
            "row_count": 100,
            "col_names": [f"Col{i}" for i in range(20)],
        }
        result = app._build_upload_auto_summary(entry, "dados.csv")
        assert "20" in result  # column count shown
        assert "…" in result  # truncated indicator

    def test_pdf_file(self):
        entry = {
            "row_count": 0,
            "col_names": [],
            "has_chunks": True,
        }
        result = app._build_upload_auto_summary(entry, "relatorio.pdf")
        assert "📄" in result
        assert "relatorio.pdf" in result
        assert "semântica" in result  # semantic search available

    def test_pptx_file(self):
        entry = {"row_count": 0, "col_names": []}
        result = app._build_upload_auto_summary(entry, "apresentacao.pptx")
        assert "📑" in result
        assert "apresentacao.pptx" in result

    def test_unknown_file(self):
        entry = {"row_count": 0, "col_names": []}
        result = app._build_upload_auto_summary(entry, "dados.json")
        assert "📎" in result

    def test_polymorphic_dataset(self):
        entry = {
            "row_count": 5000,
            "col_names": ["Tipo", "Campo1", "Campo2"],
            "polymorphic_schema": {
                "is_polymorphic": True,
                "pivot_column": "Tipo",
                "pivot_values_count": 3,
            },
        }
        result = app._build_upload_auto_summary(entry, "multi.xlsx")
        assert "polimórfico" in result
        assert "Tipo" in result
        assert "3 perfis" in result

    def test_date_period_detection(self):
        entry = {
            "row_count": 200,
            "col_names": ["DataCriacao", "Valor"],
            "full_col_stats": [
                {"name": "DataCriacao", "type": "text", "first": "2024-01-01", "last": "2024-12-31", "unique_approx": 200},
                {"name": "Valor", "type": "numeric", "min": 10, "max": 99, "mean": 55},
            ],
        }
        result = app._build_upload_auto_summary(entry, "vendas.csv")
        assert "Período" in result
        assert "2024-01-01" in result
        assert "2024-12-31" in result

    def test_empty_entry(self):
        """Should not crash on minimal entry."""
        result = app._build_upload_auto_summary({}, "vazio.txt")
        assert "vazio.txt" in result

    def test_no_col_names_returns_gracefully(self):
        entry = {"row_count": 50, "col_names": None}
        result = app._build_upload_auto_summary(entry, "test.csv")
        assert "test.csv" in result
