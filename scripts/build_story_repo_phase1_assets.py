#!/usr/bin/env python3
"""Build Phase 1 repo-crawl artifacts from extracted Azure DevOps ZIP archives.

Phase 1 motto:
    seguranca de dados confidenciais sempre

This script does a conservative semantic crawl over repo ZIPs and produces:
1. repo_atlas.json        -> structural map by domain/module/layer
2. flow_seeds.json        -> deduped flow/screen seeds
3. knowledge_bundle.json  -> ready-to-import knowledge asset array

The crawl is intentionally safe-by-default:
- skips .env* files entirely
- skips node_modules, wiki attachments, binaries, build output and temp folders
- only reads a small allow-list of semantically useful files such as package.json,
  federation.config.json, swagger/openapi specs, screen index exports and wiki pages
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_ROOT = Path.home() / "Downloads" / "IT.DIT_FULL_ZIPS" / "IT.DIT"
DEFAULT_OUTPUT_DIR = ROOT / "tmp" / "phase1_repo_crawl"

PHASE_1_MOTTO = "seguranca de dados confidenciais sempre"
OUTPUT_VERSION = 1

LAYER_SUFFIXES: list[tuple[str, str]] = [
    (".Experience.Backend", "experience_backend"),
    (".Process.Backend", "process_backend"),
    (".Frontend", "frontend"),
    (".Backend", "backend"),
    (".API", "api"),
    (".Api", "api"),
    (".Wiki", "wiki"),
]

DOMAIN_NAME_OVERRIDES = {
    "Account": "Conta",
    "Base": "Base",
    "Beneficiaries": "Beneficiarios",
    "Cards": "Cartoes",
    "Companies": "Empresas",
    "CompProfile": "Perfil Empresa",
    "Credit": "Credito",
    "Credits": "Credito",
    "Document": "Documentos",
    "Documents": "Documentos",
    "GlobalSession": "Sessao Global",
    "Investments": "Investimentos",
    "Library": "Biblioteca Partilhada",
    "Onboarding": "Onboarding",
    "Operation": "Operacoes",
    "Payments": "Pagamentos",
    "Public": "Publico",
    "Receivables": "Recebiveis",
    "Report": "Report",
    "Transfers": "Transferencias",
    "User": "Utilizador",
    "Utilities": "Utilitarios Partilhados",
}

DOMAIN_SLUG_OVERRIDES = {
    "beneficiaries": "Beneficiarios",
    "cards": "Cartoes",
    "cdt": "CDT",
    "changecredentials": "Credenciais",
    "company": "Empresas",
    "companies": "Empresas",
    "confirming": "Confirming",
    "creditdetails": "Credito",
    "creditwallet": "Credito",
    "digitalsignature": "Operacoes",
    "documents": "Documentos",
    "europeanfunds": "Fundos Europeus",
    "home": "Base",
    "insurance": "Seguros",
    "investment": "Investimentos",
    "investments": "Investimentos",
    "login": "Autenticacao",
    "notifications": "Notificacoes",
    "onboarding": "Onboarding",
    "operations": "Operacoes",
    "payments": "Pagamentos",
    "products": "Produtos",
    "public": "Publico",
    "receivables": "Recebiveis",
    "schedule": "Agenda",
    "supplier": "Fornecedores",
    "transfers": "Transferencias",
    "userprofile": "Perfil Utilizador",
}

SENSITIVE_BASENAME_PREFIXES = (".env",)
NOISE_SEGMENTS = {
    ".attachments",
    ".git",
    "__macosx",
    "bin",
    "dist",
    "node_modules",
    "obj",
    "packages",
}
BINARY_EXTENSIONS = {
    ".7z",
    ".bmp",
    ".class",
    ".dll",
    ".doc",
    ".docx",
    ".dylib",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".otf",
    ".pdf",
    ".png",
    ".pyd",
    ".pyc",
    ".so",
    ".ttf",
    ".wav",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".zip",
}
INTERNAL_FLOW_TOKENS = {
    "debugcommunicationfee",
    "entryapp",
    "entryapploadingscreen",
    "entrypoints",
    "appredirect",
    "associateaccountsredirect",
    "entryapperrorscreen",
    "loginidpredirect",
    "obatransferredirect",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_token(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def title_case_words(value: str) -> str:
    parts = [part for part in re.split(r"\s+", str(value or "").strip()) if part]
    return " ".join(part[:1].upper() + part[1:] for part in parts)


def humanize_identifier(value: str) -> str:
    text = str(value or "").strip().replace("_", " ").replace("-", " ")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    return title_case_words(text)


def infer_business_domain(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    direct = DOMAIN_NAME_OVERRIDES.get(raw)
    if direct:
        return direct
    slug = normalize_token(raw).replace("_", "")
    slug_match = DOMAIN_SLUG_OVERRIDES.get(slug)
    if slug_match:
        return slug_match
    first = raw.split(".", 1)[0]
    direct_first = DOMAIN_NAME_OVERRIDES.get(first)
    if direct_first:
        return direct_first
    return humanize_identifier(first)


def has_explicit_domain_hint(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    if raw in DOMAIN_NAME_OVERRIDES:
        return True
    slug = normalize_token(raw).replace("_", "")
    return slug in DOMAIN_SLUG_OVERRIDES


def split_repo_name(archive_name: str) -> dict[str, str]:
    repo_name = archive_name[:-4] if archive_name.lower().endswith(".zip") else archive_name
    base_name = repo_name
    layer = "other"
    for suffix, candidate in LAYER_SUFFIXES:
        if repo_name.lower().endswith(suffix.lower()):
            base_name = repo_name[: -len(suffix)]
            layer = candidate
            break
    parts = base_name.split(".")
    family = parts[1] if len(parts) >= 2 and parts[0] == "BCP" else ""
    if len(parts) >= 3 and parts[0] == "BCP":
        module_path = ".".join(parts[2:])
    elif len(parts) == 2 and parts[0] == "BCP":
        module_path = parts[1]
    else:
        module_path = base_name
    domain_key = module_path.split(".", 1)[0] if module_path else base_name
    team_scope = "/".join(part for part in [family, module_path.replace(".", "/")] if part)
    return {
        "archive_name": archive_name,
        "repo_name": repo_name,
        "base_name": base_name,
        "family": family,
        "module_path": module_path or base_name,
        "domain_key": domain_key or base_name,
        "layer": layer,
        "team_scope": team_scope,
        "business_domain": infer_business_domain(domain_key or base_name),
    }


def skip_reason(path: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized or normalized.endswith("/"):
        return "directory"
    basename = normalized.rsplit("/", 1)[-1].lower()
    if any(basename.startswith(prefix) for prefix in SENSITIVE_BASENAME_PREFIXES):
        return "sensitive_env"
    segments = [segment.lower() for segment in normalized.split("/") if segment]
    if any(segment in NOISE_SEGMENTS for segment in segments):
        return "noise_segment"
    if Path(basename).suffix.lower() in BINARY_EXTENSIONS:
        return "binary_or_blob"
    return ""


def safe_read_text(zf: zipfile.ZipFile, member: str, limit: int = 250_000) -> str:
    data = zf.read(member)
    if len(data) > limit:
        data = data[:limit]
    return data.decode("utf-8", errors="ignore")


def safe_read_json(zf: zipfile.ZipFile, member: str) -> dict[str, Any]:
    try:
        raw = safe_read_text(zf, member)
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def extract_export_paths(index_text: str) -> list[str]:
    exports: list[str] = []
    for match in re.finditer(r"export\s+\*\s+from\s+['\"](.+?)['\"]", index_text):
        candidate = str(match.group(1) or "").strip()
        if candidate:
            exports.append(candidate)
    return exports


def flow_entry_from_export(module_domain: str, module_scope: str, export_path: str) -> dict[str, Any] | None:
    cleaned = str(export_path or "").strip().replace("\\", "/")
    if not cleaned:
        return None
    cleaned = cleaned[2:] if cleaned.startswith("./") else cleaned
    parts = [part for part in cleaned.split("/") if part and part != "index"]
    if not parts:
        return None
    flow_key = parts[-1]
    flow_norm = normalize_token(flow_key)
    if not flow_norm:
        return None
    raw_flow_norm = normalize_token(flow_key.lstrip("_"))
    if (
        flow_key.startswith("_")
        or raw_flow_norm in INTERNAL_FLOW_TOKENS
        or flow_norm in INTERNAL_FLOW_TOKENS
        or "redirect" in flow_norm
        or "redirect" in raw_flow_norm
        or flow_norm.startswith("debug")
        or raw_flow_norm.startswith("debug")
    ):
        return None
    journey_key = parts[0] if len(parts) > 1 else module_domain
    if len(parts) > 1:
        business_domain = infer_business_domain(journey_key or module_domain) or module_domain
    elif module_domain == "Base" and has_explicit_domain_hint(flow_key):
        business_domain = infer_business_domain(flow_key) or module_domain
    else:
        business_domain = module_domain
    return {
        "domain": business_domain,
        "journey_key": journey_key,
        "journey": infer_business_domain(journey_key) if len(parts) > 1 else business_domain,
        "flow_key": flow_key,
        "flow": flow_key,
        "flow_label": humanize_identifier(flow_key),
        "export_path": cleaned,
        "site_section": module_scope,
    }


def extract_frontend_details(zf: zipfile.ZipFile, repo_meta: dict[str, str], names: list[str]) -> dict[str, Any]:
    package_json = safe_read_json(zf, "package.json") if "package.json" in names else {}
    federation_json = safe_read_json(zf, "federation.config.json") if "federation.config.json" in names else {}
    exports: list[str] = []
    if "src/app/screens/index.ts" in names:
        exports = extract_export_paths(safe_read_text(zf, "src/app/screens/index.ts"))
    elif "src/app/screens/index.tsx" in names:
        exports = extract_export_paths(safe_read_text(zf, "src/app/screens/index.tsx"))

    flow_entries: list[dict[str, Any]] = []
    for export_path in exports:
        flow_entry = flow_entry_from_export(
            repo_meta["business_domain"],
            repo_meta["team_scope"],
            export_path,
        )
        if flow_entry:
            flow_entries.append(flow_entry)

    if not flow_entries:
        screen_dirs = sorted(
            {
                match.group(1)
                for name in names
                for match in [re.match(r"src/app/screens/([^/]+)/", name)]
                if match
            }
        )
        for screen in screen_dirs:
            flow_entry = flow_entry_from_export(
                repo_meta["business_domain"],
                repo_meta["team_scope"],
                f"./{screen}",
            )
            if flow_entry:
                flow_entries.append(flow_entry)

    dependencies = package_json.get("dependencies", {}) if isinstance(package_json.get("dependencies"), dict) else {}
    internal_apis = sorted(dep for dep in dependencies if dep.startswith("@api/"))[:12]
    shared_packages = sorted(
        dep
        for dep in dependencies
        if dep in {"react-router-dom", "zustand", "zod"} or dep.startswith("@bcp-nextgen")
    )[:12]

    return {
        "package_name": str(package_json.get("name", "") or ""),
        "package_version": str(package_json.get("version", "") or ""),
        "federated": bool(federation_json),
        "federation_name": str(federation_json.get("name", "") or ""),
        "federation_exposes": sorted((federation_json.get("exposes") or {}).keys())[:12]
        if isinstance(federation_json.get("exposes"), dict)
        else [],
        "internal_apis": internal_apis,
        "shared_packages": shared_packages,
        "flow_entries": flow_entries,
    }


def select_primary_spec_member(names: list[str]) -> str:
    preferred = [
        "src/swagger.json",
        "src/openapi.json",
        "swagger.json",
        "openapi.json",
    ]
    for item in preferred:
        if item in names:
            return item
    candidates = [
        name
        for name in names
        if name.lower().endswith("/swagger.json") or name.lower().endswith("/openapi.json")
    ]
    if not candidates:
        return ""
    return sorted(candidates, key=lambda item: (item.count("/"), len(item)))[0]


def extract_operation_name(path_value: str) -> str:
    text = str(path_value or "").strip().strip("/")
    if not text:
        return ""
    last = text.split("/")[-1]
    return last or text


def extract_api_details(zf: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    package_json = safe_read_json(zf, "package.json") if "package.json" in names else {}
    spec_member = select_primary_spec_member(names)
    spec = safe_read_json(zf, spec_member) if spec_member else {}
    path_keys = list((spec.get("paths") or {}).keys()) if isinstance(spec.get("paths"), dict) else []
    operations = [extract_operation_name(item) for item in path_keys]
    operations = [item for item in operations if item]
    return {
        "package_name": str(package_json.get("name", "") or ""),
        "package_version": str(package_json.get("version", "") or ""),
        "spec_member": spec_member,
        "operation_count": len(path_keys),
        "operations": operations[:20],
    }


def extract_backend_details(names: list[str]) -> dict[str, Any]:
    controllers: list[str] = []
    seen: set[str] = set()
    for name in names:
        lower_name = name.lower()
        if not lower_name.endswith("controller.cs"):
            continue
        controller = Path(name).name
        controller = controller[: -len("Controller.cs")]
        if controller and controller not in seen:
            seen.add(controller)
            controllers.append(controller)
    return {
        "controller_count": len(controllers),
        "controllers": controllers[:24],
    }


def extract_first_heading(markdown_text: str) -> str:
    for raw_line in markdown_text.splitlines()[:20]:
        line = str(raw_line or "").strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    for raw_line in markdown_text.splitlines()[:20]:
        line = str(raw_line or "").strip()
        if line:
            return line[:120]
    return ""


def extract_wiki_details(zf: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    markdown_members = sorted(name for name in names if name.lower().endswith(".md"))
    pages: list[dict[str, str]] = []
    for member in markdown_members[:18]:
        heading = extract_first_heading(safe_read_text(zf, member, limit=40_000))
        pages.append(
            {
                "path": member,
                "title": heading or humanize_identifier(Path(member).stem),
            }
        )
    return {
        "page_count": len(markdown_members),
        "pages": pages,
    }


def extract_pipeline_files(names: list[str]) -> list[str]:
    return sorted(name for name in names if name.startswith(".pipelines/") and name.lower().endswith((".yml", ".yaml")))[:12]


def build_repo_record(zip_path: Path) -> dict[str, Any]:
    repo_meta = split_repo_name(zip_path.name)
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(zf.namelist())
        skip_counts: dict[str, int] = defaultdict(int)
        safe_name_count = 0
        for name in names:
            reason = skip_reason(name)
            if reason:
                skip_counts[reason] += 1
            else:
                safe_name_count += 1

        record: dict[str, Any] = {
            **repo_meta,
            "zip_size_bytes": zip_path.stat().st_size,
            "file_count": len(names),
            "safe_name_count": safe_name_count,
            "skipped_counts": dict(sorted(skip_counts.items())),
            "pipeline_files": extract_pipeline_files(names),
        }

        if repo_meta["layer"] == "frontend":
            record["frontend"] = extract_frontend_details(zf, repo_meta, names)
        elif repo_meta["layer"] == "api":
            record["api"] = extract_api_details(zf, names)
        elif repo_meta["layer"] in {"experience_backend", "process_backend", "backend"}:
            record["backend"] = extract_backend_details(names)
        elif repo_meta["layer"] == "wiki":
            record["wiki"] = extract_wiki_details(zf, names)
        return record


def summarize_layers(repo_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in repo_records:
        key = record["base_name"]
        current = grouped.setdefault(
            key,
            {
                "key": key,
                "family": record["family"],
                "module_path": record["module_path"],
                "team_scope": record["team_scope"],
                "business_domain": record["business_domain"],
                "layers": set(),
                "repos": [],
                "federated": False,
                "screens": set(),
                "journeys": set(),
                "api_operations": set(),
                "controllers": set(),
                "wiki_pages": set(),
                "pipeline_files": set(),
            },
        )
        current["layers"].add(record["layer"])
        current["repos"].append(record["repo_name"])
        current["pipeline_files"].update(record.get("pipeline_files", []))

        frontend = record.get("frontend") or {}
        if frontend:
            current["federated"] = current["federated"] or bool(frontend.get("federated"))
            for flow_entry in frontend.get("flow_entries", []) or []:
                current["screens"].add(str(flow_entry.get("flow", "") or ""))
                current["journeys"].add(str(flow_entry.get("journey", "") or ""))

        api = record.get("api") or {}
        for operation in api.get("operations", []) or []:
            current["api_operations"].add(str(operation or ""))

        backend = record.get("backend") or {}
        for controller in backend.get("controllers", []) or []:
            current["controllers"].add(str(controller or ""))

        wiki = record.get("wiki") or {}
        for page in wiki.get("pages", []) or []:
            current["wiki_pages"].add(str(page.get("title", "") or ""))

    summaries = []
    for current in grouped.values():
        summaries.append(
            {
                "key": current["key"],
                "family": current["family"],
                "module_path": current["module_path"],
                "team_scope": current["team_scope"],
                "business_domain": current["business_domain"],
                "layers": sorted(item for item in current["layers"] if item),
                "repos": sorted(item for item in current["repos"] if item),
                "federated": bool(current["federated"]),
                "screens": sorted(item for item in current["screens"] if item),
                "journeys": sorted(item for item in current["journeys"] if item),
                "api_operations": sorted(item for item in current["api_operations"] if item)[:24],
                "controllers": sorted(item for item in current["controllers"] if item)[:24],
                "wiki_pages": sorted(item for item in current["wiki_pages"] if item)[:18],
                "pipeline_files": sorted(item for item in current["pipeline_files"] if item)[:12],
            }
        )
    return sorted(summaries, key=lambda item: (item["family"], item["module_path"]))


def build_repo_atlas(repo_records: list[dict[str, Any]]) -> dict[str, Any]:
    modules = summarize_layers(repo_records)
    family_counts: dict[str, int] = defaultdict(int)
    layer_counts: dict[str, int] = defaultdict(int)
    for record in repo_records:
        family_counts[record["family"] or "unknown"] += 1
        layer_counts[record["layer"]] += 1
    return {
        "version": OUTPUT_VERSION,
        "generated_at": utc_now_iso(),
        "motto": PHASE_1_MOTTO,
        "source_type": "repo_semantic_crawl_phase_1",
        "repo_count": len(repo_records),
        "family_counts": dict(sorted(family_counts.items())),
        "layer_counts": dict(sorted(layer_counts.items())),
        "safety_rules": [
            "skip .env files entirely",
            "skip node_modules, build output and temporary folders",
            "skip wiki attachments and binary/blob files",
            "read only semantically useful safe files",
        ],
        "repos": repo_records,
        "modules": modules,
    }


def dedupe_flow_entries(repo_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in repo_records:
        frontend = record.get("frontend") or {}
        for flow_entry in frontend.get("flow_entries", []) or []:
            key = "|".join(
                [
                    normalize_token(flow_entry.get("domain", "")),
                    normalize_token(flow_entry.get("journey", "")),
                    normalize_token(flow_entry.get("flow", "")),
                ]
            )
            if not key or key == "||":
                continue
            current = grouped.setdefault(
                key,
                {
                    "domain": flow_entry.get("domain", ""),
                    "journey": flow_entry.get("journey", ""),
                    "flow": flow_entry.get("flow", ""),
                    "flow_label": flow_entry.get("flow_label", ""),
                    "site_sections": set(),
                    "evidence_repos": set(),
                    "evidence_layers": set(),
                    "related_internal_apis": set(),
                },
            )
            current["site_sections"].add(record.get("team_scope", ""))
            current["evidence_repos"].add(record.get("repo_name", ""))
            current["evidence_layers"].add(record.get("layer", ""))
            for dep in frontend.get("internal_apis", []) or []:
                current["related_internal_apis"].add(dep)

    flow_entries = []
    for key, current in grouped.items():
        domain = str(current.get("domain", "") or "")
        journey = str(current.get("journey", "") or domain)
        flow = str(current.get("flow", "") or "")
        confidence = 0.55
        if len(current["evidence_repos"]) >= 2:
            confidence += 0.1
        if current["related_internal_apis"]:
            confidence += 0.05
        flow_entries.append(
            {
                "id": f"repo-flow:{key}",
                "dedupe_key": key,
                "source_kind": "repo_flow_seed",
                "domain": domain,
                "journey": journey,
                "flow": flow,
                "detail": "Flow inferido por crawl semantico de repos frontend.",
                "title": f"{domain} | {flow}" if domain else flow,
                "file_title": ", ".join(sorted(current["evidence_repos"])[:3]),
                "url": "",
                "site_placement": ", ".join(sorted(current["site_sections"])[:3]),
                "routing_note": "Confirmar sempre no GitHub main antes de assumir source of truth funcional.",
                "aliases": [humanize_identifier(flow), flow],
                "ui_components": [],
                "ux_terms": [flow, humanize_identifier(flow), journey][:6],
                "currentness_score": 0.45,
                "production_confidence": round(min(confidence, 0.85), 4),
                "quality_score": 0.0,
                "source_work_item_id": "",
                "evidence_repos": sorted(current["evidence_repos"]),
                "evidence_layers": sorted(current["evidence_layers"]),
                "related_internal_apis": sorted(current["related_internal_apis"])[:12],
            }
        )
    return sorted(flow_entries, key=lambda item: (item["domain"], item["journey"], item["flow"]))


def build_flow_seeds(repo_records: list[dict[str, Any]]) -> dict[str, Any]:
    entries = dedupe_flow_entries(repo_records)
    return {
        "version": OUTPUT_VERSION,
        "generated_at": utc_now_iso(),
        "motto": PHASE_1_MOTTO,
        "source": "repo_semantic_crawl_phase_1",
        "metadata": {
            "entry_count": len(entries),
            "domains": sorted({str(item.get("domain", "") or "") for item in entries if item.get("domain")}),
        },
        "entries": entries,
    }


def build_domain_summary_asset(module_summary: dict[str, Any]) -> dict[str, str]:
    domain = str(module_summary.get("business_domain", "") or "")
    module_path = str(module_summary.get("module_path", "") or "")
    layers = ", ".join(module_summary.get("layers", []) or [])
    screens = ", ".join((module_summary.get("screens", []) or [])[:10])
    operations = ", ".join((module_summary.get("api_operations", []) or [])[:10])
    controllers = ", ".join((module_summary.get("controllers", []) or [])[:10])
    wiki_pages = ", ".join((module_summary.get("wiki_pages", []) or [])[:6])
    repo_names = ", ".join((module_summary.get("repos", []) or [])[:6])
    content_parts = [
        f"Dominio {domain}.",
        f"Modulo tecnico {module_path}.",
        f"Team scope {module_summary.get('team_scope', '')}.",
        f"Layers observadas: {layers}." if layers else "",
        f"Repos observados: {repo_names}." if repo_names else "",
        f"Flows/screens observados: {screens}." if screens else "",
        f"Operacoes API observadas: {operations}." if operations else "",
        f"Controllers relevantes: {controllers}." if controllers else "",
        f"Paginas wiki relacionadas: {wiki_pages}." if wiki_pages else "",
        "Conteudo curado sem ler .env, node_modules, attachments ou binarios.",
        "Confirmar sempre detalhes finais contra GitHub main.",
    ]
    return {
        "asset_key": f"phase1-domain-{normalize_token(module_summary.get('key', ''))}",
        "title": f"Atlas | {domain} | {module_path}",
        "domain": domain,
        "journey": module_path,
        "flow": "atlas",
        "team_scope": str(module_summary.get("team_scope", "") or ""),
        "note": PHASE_1_MOTTO,
        "content": " ".join(part for part in content_parts if part).strip()[:18_000],
    }


def build_flow_asset(flow_entry: dict[str, Any], modules_by_domain: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    domain = str(flow_entry.get("domain", "") or "")
    module_candidates = modules_by_domain.get(domain, [])
    operations = []
    controllers = []
    layers = set()
    for module in module_candidates[:3]:
        operations.extend(module.get("api_operations", []) or [])
        controllers.extend(module.get("controllers", []) or [])
        layers.update(module.get("layers", []) or [])
    operations = list(dict.fromkeys(operations))[:8]
    controllers = list(dict.fromkeys(controllers))[:8]
    content_parts = [
        f"Flow {flow_entry.get('flow', '')} no dominio {domain}.",
        f"Jornada provavel: {flow_entry.get('journey', '')}.",
        f"Repos frontend de evidencia: {', '.join(flow_entry.get('evidence_repos', [])[:4])}.",
        f"Layers observadas: {', '.join(sorted(layers))}." if layers else "",
        f"Dependencias internas de API: {', '.join(flow_entry.get('related_internal_apis', [])[:8])}."
        if flow_entry.get("related_internal_apis")
        else "",
        f"Operacoes API relacionadas: {', '.join(operations)}." if operations else "",
        f"Controllers relacionados: {', '.join(controllers)}." if controllers else "",
        "Flow descoberto via crawl semantico seguro de repos; sem leitura de configuracoes sensiveis.",
        "Validar comportamento final no GitHub main.",
    ]
    return {
        "asset_key": f"phase1-flow-{normalize_token(flow_entry.get('domain', ''))}-{normalize_token(flow_entry.get('flow', ''))}",
        "title": f"{domain} | {flow_entry.get('flow', '')}",
        "domain": domain,
        "journey": str(flow_entry.get("journey", "") or ""),
        "flow": str(flow_entry.get("flow", "") or ""),
        "team_scope": str(flow_entry.get("site_placement", "") or ""),
        "note": PHASE_1_MOTTO,
        "content": " ".join(part for part in content_parts if part).strip()[:18_000],
    }


def build_wiki_assets(repo_records: list[dict[str, Any]]) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    for record in repo_records:
        wiki = record.get("wiki") or {}
        pages = wiki.get("pages", []) or []
        if not pages:
            continue
        page_titles = ", ".join(page.get("title", "") for page in pages[:8] if page.get("title"))
        content_parts = [
            f"Wiki operacional {record.get('repo_name', '')}.",
            f"Team scope {record.get('team_scope', '')}.",
            f"Paginas observadas: {page_titles}." if page_titles else "",
            "Usar estas wikis como contexto operacional secundario, nunca como source of truth final do produto.",
            "Attachments e blobs binarios foram ignorados.",
        ]
        assets.append(
            {
                "asset_key": f"phase1-wiki-{normalize_token(record.get('repo_name', ''))}",
                "title": f"Wiki | {record.get('repo_name', '')}",
                "domain": infer_business_domain(record.get("domain_key", "") or "Operacao") or "Operacao",
                "journey": "Operacao",
                "flow": "wiki",
                "team_scope": str(record.get("team_scope", "") or ""),
                "note": PHASE_1_MOTTO,
                "content": " ".join(part for part in content_parts if part).strip()[:18_000],
            }
        )
    return assets


def build_knowledge_bundle(repo_atlas: dict[str, Any], flow_seeds: dict[str, Any], repo_records: list[dict[str, Any]]) -> list[dict[str, str]]:
    modules = repo_atlas.get("modules", []) or []
    entries = flow_seeds.get("entries", []) or []
    modules_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for module in modules:
        modules_by_domain[str(module.get("business_domain", "") or "")].append(module)

    bundle: list[dict[str, str]] = []
    for module in modules:
        bundle.append(build_domain_summary_asset(module))
    for flow_entry in entries:
        bundle.append(build_flow_asset(flow_entry, modules_by_domain))
    bundle.extend(build_wiki_assets(repo_records))
    return bundle


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_phase_1(input_root: Path, output_dir: Path) -> dict[str, Any]:
    zip_paths = sorted(path for path in input_root.iterdir() if path.suffix.lower() == ".zip")
    repo_records = [build_repo_record(path) for path in zip_paths]
    repo_atlas = build_repo_atlas(repo_records)
    flow_seeds = build_flow_seeds(repo_records)
    knowledge_bundle = build_knowledge_bundle(repo_atlas, flow_seeds, repo_records)

    write_json(output_dir / "repo_atlas.json", repo_atlas)
    write_json(output_dir / "flow_seeds.json", flow_seeds)
    write_json(output_dir / "knowledge_bundle.json", knowledge_bundle)
    write_json(
        output_dir / "manifest.json",
        {
            "version": OUTPUT_VERSION,
            "generated_at": utc_now_iso(),
            "motto": PHASE_1_MOTTO,
            "input_root": str(input_root),
            "outputs": [
                "repo_atlas.json",
                "flow_seeds.json",
                "knowledge_bundle.json",
            ],
            "repo_count": len(repo_records),
            "module_count": len(repo_atlas.get("modules", []) or []),
            "flow_seed_count": len(flow_seeds.get("entries", []) or []),
            "knowledge_bundle_count": len(knowledge_bundle),
        },
    )
    return {
        "repo_count": len(repo_records),
        "module_count": len(repo_atlas.get("modules", []) or []),
        "flow_seed_count": len(flow_seeds.get("entries", []) or []),
        "knowledge_bundle_count": len(knowledge_bundle),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 1 repo-crawl artifacts from ZIP archives.")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT), help="Directory with repo ZIP archives.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory where Phase 1 artifacts will be written.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = Path(args.input_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not input_root.exists():
        raise SystemExit(f"Input root not found: {input_root}")
    result = run_phase_1(input_root, output_dir)
    print(
        json.dumps(
            {
                "status": "ok",
                "motto": PHASE_1_MOTTO,
                "input_root": str(input_root),
                "output_dir": str(output_dir),
                **result,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
