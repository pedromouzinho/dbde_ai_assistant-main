from __future__ import annotations

import io

import openpyxl
import pytest

import tools
from tabular_artifacts import (
    build_tabular_artifact,
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
