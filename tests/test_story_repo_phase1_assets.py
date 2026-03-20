from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.build_story_repo_phase1_assets import build_flow_seeds, build_repo_record, skip_reason


def _write_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_skip_reason_blocks_sensitive_and_noise_paths():
    assert skip_reason(".env") == "sensitive_env"
    assert skip_reason("node_modules/react/index.js") == "noise_segment"
    assert skip_reason(".attachments/image-1.png") == "noise_segment"
    assert skip_reason("src/app/screens/index.ts") == ""


def test_flow_seeds_dedupe_base_shell_and_feature_frontend(tmp_path: Path):
    base_zip = tmp_path / "BCP.MSE.Base.Frontend.zip"
    payments_zip = tmp_path / "BCP.MSE.Payments.Frontend.zip"

    _write_zip(
        base_zip,
        {
            "package.json": json.dumps({"name": "mse-base", "dependencies": {"@api/mse-payments-xp": "1.0.0"}}),
            "src/app/screens/index.ts": "export * from './payments/servicePayments';\nexport * from './payments/statePayments';\nexport * from './beneficiaries';\nexport * from './_entrypoints';\n",
            ".env": "SECRET=should_not_be_read\n",
            "node_modules/react/index.js": "noise",
        },
    )
    _write_zip(
        payments_zip,
        {
            "package.json": json.dumps({"name": "mse-payments", "dependencies": {"@api/mse-payments-xp": "1.0.0"}}),
            "federation.config.json": json.dumps({"name": "payments", "exposes": {"./screens": "./src/app/screens/index.ts"}}),
            "src/app/screens/index.ts": "export * from './servicePayments';\n",
        },
    )

    base_record = build_repo_record(base_zip)
    payments_record = build_repo_record(payments_zip)
    flow_seeds = build_flow_seeds([base_record, payments_record])

    assert base_record["skipped_counts"]["sensitive_env"] == 1
    assert base_record["skipped_counts"]["noise_segment"] == 1
    assert payments_record["frontend"]["federated"] is True

    entries = flow_seeds["entries"]
    service_payments = [entry for entry in entries if entry["domain"] == "Pagamentos" and entry["flow"] == "servicePayments"]
    assert len(service_payments) == 1
    assert sorted(service_payments[0]["evidence_repos"]) == ["BCP.MSE.Base.Frontend", "BCP.MSE.Payments.Frontend"]
    assert any(entry["domain"] == "Beneficiarios" and entry["flow"] == "beneficiaries" for entry in entries)
    assert all(entry["flow"] != "_entrypoints" for entry in entries)
