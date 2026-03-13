from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

import app


def test_retention_expiry_helper():
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    assert app._is_retention_expired(past) is True
    assert app._is_retention_expired(future) is False
    assert app._is_retention_expired("") is False


def test_raw_blob_retention_for_tabular_artifact_uses_shorter_window(monkeypatch):
    monkeypatch.setattr(app, "UPLOAD_TABULAR_RAW_RETENTION_HOURS", 6)

    retention_until = app._raw_blob_retention_until_iso(
        filename="sample.xlsx",
        artifact_blob_ref="upload-artifacts/sample.parquet",
        fallback_hours=72,
    )

    delta = datetime.fromisoformat(retention_until) - datetime.now(timezone.utc)
    assert delta.total_seconds() > 5 * 3600
    assert delta.total_seconds() < 7 * 3600


@pytest.mark.asyncio
async def test_purge_expired_upload_artifacts_removes_expired_rows_and_jobs(monkeypatch):
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    queries = []
    deleted_blobs = []
    deleted_rows = []
    deleted_jobs = []

    async def fake_table_query(table_name, filter_str="", top=0):
        queries.append((table_name, filter_str, top))
        if table_name == "UploadIndex":
            return [
                {
                    "PartitionKey": "conv-1",
                    "RowKey": "job-expired",
                    "RetentionUntil": expired,
                    "RawBlobRef": "upload-raw/expired.xlsx",
                    "ExtractedBlobRef": "upload-text/expired.json",
                    "ChunksBlobRef": "",
                    "TabularArtifactBlobRef": "upload-artifacts/expired.parquet",
                },
                {
                    "PartitionKey": "conv-1",
                    "RowKey": "job-active",
                    "RetentionUntil": future,
                    "RawBlobRef": "upload-raw/active.xlsx",
                    "ExtractedBlobRef": "",
                    "ChunksBlobRef": "",
                    "TabularArtifactBlobRef": "",
                },
            ]
        if table_name == "UploadJobs":
            return [
                {
                    "PartitionKey": "upload",
                    "RowKey": "job-expired",
                    "Status": "completed",
                    "RetentionUntil": expired,
                    "RawBlobRef": "upload-raw/expired.xlsx",
                    "TabularArtifactBlobRef": "upload-artifacts/expired.parquet",
                },
                {
                    "PartitionKey": "upload",
                    "RowKey": "job-failed",
                    "Status": "failed",
                    "RetentionUntil": expired,
                    "RawBlobRef": "upload-raw/failed.xlsx",
                    "TabularArtifactBlobRef": "upload-artifacts/failed.parquet",
                },
                {
                    "PartitionKey": "upload",
                    "RowKey": "job-active",
                    "Status": "completed",
                    "RetentionUntil": future,
                    "RawBlobRef": "upload-raw/active.xlsx",
                    "TabularArtifactBlobRef": "",
                },
            ]
        return []

    async def fake_blob_delete(container, blob_name):
        deleted_blobs.append(f"{container}/{blob_name}")

    async def fake_table_delete(table_name, partition_key, row_key):
        deleted_rows.append((table_name, partition_key, row_key))

    async def fake_job_delete(job_id, partition_key=None):
        deleted_jobs.append((partition_key, job_id))
        return None

    monkeypatch.setattr(app, "table_query", fake_table_query)
    monkeypatch.setattr(app, "blob_delete", fake_blob_delete)
    monkeypatch.setattr(app, "table_delete", fake_table_delete)
    monkeypatch.setattr(app.upload_jobs_store, "delete", fake_job_delete)

    result = await app._purge_expired_upload_artifacts(limit=50)

    assert ("UploadIndex", "conv-1", "job-expired") in deleted_rows
    assert ("upload", "job-expired") in deleted_jobs
    assert ("upload", "job-failed") in deleted_jobs
    assert "upload-raw/expired.xlsx" in deleted_blobs
    assert "upload-text/expired.json" in deleted_blobs
    assert "upload-artifacts/expired.parquet" in deleted_blobs
    assert "upload-raw/failed.xlsx" in deleted_blobs
    assert "upload-artifacts/failed.parquet" in deleted_blobs
    assert result["rows_deleted"] == 1
    assert result["jobs_deleted"] == 2
    assert result["blobs_deleted"] >= 3
    assert [q[0] for q in queries] == ["UploadIndex", "UploadJobs"]


@pytest.mark.asyncio
async def test_purge_expired_upload_artifacts_can_drop_only_raw_blob_when_artifact_exists(monkeypatch):
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    deleted_blobs = []
    merged_rows = []
    deleted_rows = []
    deleted_jobs = []
    cached_jobs = {
        "job-tabular": {
            "job_id": "job-tabular",
            "raw_blob_ref": "upload-raw/tabular.xlsx",
            "raw_blob_retention_until": expired,
            "artifact_blob_ref": "upload-artifacts/tabular.parquet",
        }
    }
    put_payloads = []

    async def fake_table_query(table_name, filter_str="", top=0):
        if table_name == "UploadIndex":
            return [
                {
                    "PartitionKey": "conv-1",
                    "RowKey": "job-tabular",
                    "RetentionUntil": future,
                    "RawBlobRef": "upload-raw/tabular.xlsx",
                    "RawBlobRetentionUntil": expired,
                    "ExtractedBlobRef": "upload-text/tabular.txt",
                    "ChunksBlobRef": "",
                    "TabularArtifactBlobRef": "upload-artifacts/tabular.parquet",
                    "Filename": "tabular.xlsx",
                }
            ]
        if table_name == "UploadJobs":
            return [
                {
                    "PartitionKey": "upload",
                    "RowKey": "job-tabular",
                    "Status": "completed",
                    "RetentionUntil": future,
                    "RawBlobRef": "upload-raw/tabular.xlsx",
                    "RawBlobRetentionUntil": expired,
                    "ArtifactBlobRef": "upload-artifacts/tabular.parquet",
                }
            ]
        return []

    async def fake_blob_delete(container, blob_name):
        deleted_blobs.append(f"{container}/{blob_name}")

    async def fake_table_delete(table_name, partition_key, row_key):
        deleted_rows.append((table_name, partition_key, row_key))

    async def fake_table_merge(table_name, entity):
        merged_rows.append((table_name, entity))

    async def fake_job_delete(job_id, partition_key=None):
        deleted_jobs.append((partition_key, job_id))
        return None

    async def fake_job_get(job_id):
        return cached_jobs.get(job_id)

    async def fake_job_put(job_id, payload):
        put_payloads.append((job_id, dict(payload)))
        cached_jobs[job_id] = dict(payload)

    monkeypatch.setattr(app, "table_query", fake_table_query)
    monkeypatch.setattr(app, "blob_delete", fake_blob_delete)
    monkeypatch.setattr(app, "table_delete", fake_table_delete)
    monkeypatch.setattr(app, "table_merge", fake_table_merge)
    monkeypatch.setattr(app.upload_jobs_store, "delete", fake_job_delete)
    monkeypatch.setattr(app.upload_jobs_store, "get", fake_job_get)
    monkeypatch.setattr(app.upload_jobs_store, "put", fake_job_put)

    result = await app._purge_expired_upload_artifacts(limit=50)

    assert deleted_blobs == ["upload-raw/tabular.xlsx"]
    assert deleted_rows == []
    assert deleted_jobs == []
    assert result["rows_deleted"] == 0
    assert result["jobs_deleted"] == 0
    assert result["blobs_deleted"] == 1
    assert any(
        table_name == "UploadIndex"
        and entity.get("RowKey") == "job-tabular"
        and entity.get("RawBlobRef") == ""
        and entity.get("RawBlobRetentionUntil") == ""
        for table_name, entity in merged_rows
    )
    assert any(
        table_name == "UploadJobs"
        and entity.get("RowKey") == "job-tabular"
        and entity.get("RawBlobRef") == ""
        and entity.get("RawBlobRetentionUntil") == ""
        for table_name, entity in merged_rows
    )
    assert put_payloads and put_payloads[0][1]["raw_blob_ref"] == ""
