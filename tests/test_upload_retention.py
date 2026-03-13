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
                },
                {
                    "PartitionKey": "conv-1",
                    "RowKey": "job-active",
                    "RetentionUntil": future,
                    "RawBlobRef": "upload-raw/active.xlsx",
                    "ExtractedBlobRef": "",
                    "ChunksBlobRef": "",
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
                },
                {
                    "PartitionKey": "upload",
                    "RowKey": "job-failed",
                    "Status": "failed",
                    "RetentionUntil": expired,
                    "RawBlobRef": "upload-raw/failed.xlsx",
                },
                {
                    "PartitionKey": "upload",
                    "RowKey": "job-active",
                    "Status": "completed",
                    "RetentionUntil": future,
                    "RawBlobRef": "upload-raw/active.xlsx",
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
    assert "upload-raw/failed.xlsx" in deleted_blobs
    assert result["rows_deleted"] == 1
    assert result["jobs_deleted"] == 2
    assert result["blobs_deleted"] >= 3
    assert [q[0] for q in queries] == ["UploadIndex", "UploadJobs"]
