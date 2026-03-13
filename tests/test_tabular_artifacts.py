from __future__ import annotations

import io

import openpyxl
import pytest

import tools
from tabular_artifacts import (
    build_tabular_artifact,
    export_tabular_artifact_as_csv_bytes,
    load_tabular_artifact_dataset,
    load_tabular_artifact_preview,
)


def _sample_xlsx_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Category", "Revenue"])
    sheet.append(["2026-01-01", "A", 10])
    sheet.append(["2026-01-02", "B", 20])
    sheet.append(["2026-01-03", "A", 30])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _large_csv_bytes(row_count: int = 6000) -> bytes:
    lines = ["Date,Category,Revenue"]
    for idx in range(1, row_count + 1):
        day = ((idx - 1) % 28) + 1
        category = "A" if idx % 2 else "B"
        lines.append(f"2026-01-{day:02d},{category},{idx}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_build_tabular_artifact_creates_parquet_dataset():
    artifact = build_tabular_artifact(_sample_xlsx_bytes(), "sample.xlsx", batch_rows=2)

    assert artifact["format"] == "parquet"
    assert artifact["row_count"] == 3
    assert artifact["columns"] == ["Date", "Category", "Revenue"]
    assert artifact["artifact_bytes"]

    dataset = load_tabular_artifact_dataset(artifact["artifact_bytes"], max_rows=10)
    assert dataset["row_count"] == 3
    assert dataset["rows_loaded"] == 3
    assert dataset["records"][0]["Revenue"] == "10"


def test_load_tabular_artifact_preview_returns_expected_shape():
    artifact = build_tabular_artifact(_sample_xlsx_bytes(), "sample.xlsx", batch_rows=2)
    preview = load_tabular_artifact_preview(artifact["artifact_bytes"], preview_rows=2, preview_char_limit=1000)

    assert preview["columns"] == ["Date", "Category", "Revenue"]
    assert preview["row_count"] == 3
    assert preview["sample_records"][0]["Category"] == "A"
    assert "2026-01-01" in preview["data_text"]


def test_export_tabular_artifact_as_csv_bytes_returns_csv():
    artifact = build_tabular_artifact(_sample_xlsx_bytes(), "sample.xlsx", batch_rows=2)
    csv_bytes = export_tabular_artifact_as_csv_bytes(artifact["artifact_bytes"])
    text = csv_bytes.decode("utf-8")

    assert "Date,Category,Revenue" in text
    assert "2026-01-01,A,10" in text


@pytest.mark.asyncio
async def test_resolve_uploaded_tabular_source_prefers_artifact(monkeypatch):
    async def _fake_table_query(*_args, **_kwargs):
        return [
            {
                "Filename": "sample.xlsx",
                "TabularArtifactBlobRef": "upload-artifacts/sample.parquet",
                "TabularArtifactFormat": "parquet",
                "RawBlobRef": "upload-raw/sample.xlsx",
                "UploadedAt": "2026-03-13T10:00:00+00:00",
            }
        ]

    downloads = []

    async def _fake_blob_download_bytes(container, blob_name):
        downloads.append(f"{container}/{blob_name}")
        artifact = build_tabular_artifact(_sample_xlsx_bytes(), "sample.xlsx")
        return artifact["artifact_bytes"]

    monkeypatch.setattr(tools, "table_query", _fake_table_query)
    monkeypatch.setattr(tools, "blob_download_bytes", _fake_blob_download_bytes)

    resolved = await tools._resolve_uploaded_tabular_source("conv-1", "pedro", "sample.xlsx")

    assert resolved["source_kind"] == "artifact"
    assert resolved["artifact_format"] == "parquet"
    assert downloads == ["upload-artifacts/sample.parquet"]


@pytest.mark.asyncio
async def test_load_uploaded_files_for_code_falls_back_to_artifact(monkeypatch):
    async def _fake_table_query(*_args, **_kwargs):
        return [
            {
                "Filename": "sample.xlsx",
                "TabularArtifactBlobRef": "upload-artifacts/sample.parquet",
                "UploadedAt": "2026-03-13T10:00:00+00:00",
            }
        ]

    async def _fake_blob_download_bytes(container, blob_name):
        assert container == "upload-artifacts"
        assert blob_name == "sample.parquet"
        artifact = build_tabular_artifact(_sample_xlsx_bytes(), "sample.xlsx")
        return artifact["artifact_bytes"]

    monkeypatch.setattr(tools, "table_query", _fake_table_query)
    monkeypatch.setattr(tools, "blob_download_bytes", _fake_blob_download_bytes)

    mounted = await tools._load_uploaded_files_for_code("conv-1", user_sub="pedro", filename="sample.xlsx")

    assert list(mounted.keys()) == ["sample.csv"]
    assert b"Date,Category,Revenue" in mounted["sample.csv"]


@pytest.mark.asyncio
async def test_load_uploaded_files_for_code_prefers_artifact_over_raw(monkeypatch):
    async def _fake_table_query(*_args, **_kwargs):
        return [
            {
                "Filename": "sample.xlsx",
                "TabularArtifactBlobRef": "upload-artifacts/sample.parquet",
                "RawBlobRef": "upload-raw/sample.xlsx",
                "UploadedAt": "2026-03-13T10:00:00+00:00",
            }
        ]

    downloads = []
    artifact = build_tabular_artifact(_sample_xlsx_bytes(), "sample.xlsx")

    async def _fake_blob_download_bytes(container, blob_name):
        downloads.append(f"{container}/{blob_name}")
        if container == "upload-artifacts":
            return artifact["artifact_bytes"]
        raise AssertionError("raw blob should not be used when artifact is available")

    monkeypatch.setattr(tools, "table_query", _fake_table_query)
    monkeypatch.setattr(tools, "blob_download_bytes", _fake_blob_download_bytes)

    mounted = await tools._load_uploaded_files_for_code("conv-1", user_sub="pedro", filename="sample.xlsx")

    assert list(mounted.keys()) == ["sample.csv"]
    assert b"Date,Category,Revenue" in mounted["sample.csv"]
    assert downloads == ["upload-artifacts/sample.parquet"]


@pytest.mark.asyncio
async def test_analyze_uploaded_table_uses_full_artifact_rows_beyond_inference_sample(monkeypatch):
    artifact = build_tabular_artifact(_large_csv_bytes(), "sample.csv")

    async def _fake_resolve_uploaded_tabular_source(_conv_id, _user_sub="", _filename=""):
        return {
            "filename": "sample.csv",
            "source_kind": "artifact",
            "artifact_bytes": artifact["artifact_bytes"],
            "artifact_format": "parquet",
        }

    monkeypatch.setattr(tools, "_resolve_uploaded_tabular_source", _fake_resolve_uploaded_tabular_source)

    result = await tools.tool_analyze_uploaded_table(
        query="qual a soma da revenue",
        conv_id="conv-1",
        user_sub="pedro",
        filename="sample.csv",
        value_column="Revenue",
        agg="sum",
    )

    assert result["row_count"] == 6000
    assert result["groups"] == [{"group": "overall", "value": 18003000.0, "count": 6000}]
    assert result["analysis_quality"]["rows_processed"] == 6000
    assert result["analysis_quality"]["rows_total"] == 6000
    assert result["analysis_quality"]["coverage"] == 1.0
    assert not result["analysis_quality"]["warnings"]
