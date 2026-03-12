# =============================================================================
# tools_export.py — File/chart generation and temporary file store
# =============================================================================

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from config import (
    AGENT_TOOL_RESULT_MAX_SIZE,
    AGENT_TOOL_RESULT_KEEP_ITEMS,
    EXPORT_ASYNC_THRESHOLD_ROWS,
    EXPORT_FILE_ROW_CAP,
    EXPORT_FILE_ROW_CAP_MAX,
)
from export_engine import to_csv, to_xlsx, to_pdf, to_docx, to_html
from generated_files import (
    cleanup_generated_files as _shared_cleanup_generated_files,
    generated_file_ttl_seconds,
    get_generated_file as _shared_get_generated_file,
    store_generated_file as _shared_store_generated_file,
)

_GENERATED_FILE_TTL_SECONDS = generated_file_ttl_seconds()
_AUTO_EXPORT_MIN_ROWS = 25
SUPPORTED_FILE_FORMATS = ("csv", "xlsx", "pdf", "docx", "html")

def _as_dt(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    txt = str(value or "").strip()
    if not txt:
        return None
    try:
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _generated_blob_paths(download_id: str, fmt: str = "") -> tuple[str, str]:
    safe_id = "".join(c if c.isalnum() else "_" for c in str(download_id or "").strip())[:80] or "file"
    ext = "".join(c if c.isalnum() else "" for c in str(fmt or "").lower())[:10]
    ext = ext or "bin"
    base = f"generated/{safe_id}"
    return f"{base}/content.{ext}", f"{base}/meta.json"

async def _cleanup_generated_files() -> None:
    await _shared_cleanup_generated_files()


async def _store_generated_file(
    content: bytes,
    mime_type: str,
    filename: str,
    fmt: str,
    *,
    user_sub: str = "",
    conversation_id: str = "",
    scope: str = "",
) -> str:
    return await _shared_store_generated_file(
        content,
        mime_type,
        filename,
        fmt,
        user_sub=user_sub,
        conversation_id=conversation_id,
        scope=scope or "export_tool",
    )

async def _attach_auto_csv_export(
    result: dict,
    title_hint: str,
    min_rows: int = _AUTO_EXPORT_MIN_ROWS,
    *,
    user_sub: str = "",
    conversation_id: str = "",
) -> None:
    """Para resultados pesados, gera CSV completo automaticamente."""
    if not isinstance(result, dict):
        return
    items = result.get("items")
    if not isinstance(items, list):
        return
    total = int(result.get("total_count", len(items)) or 0)
    if total < min_rows or len(items) < min_rows:
        return
    if total >= max(100, EXPORT_ASYNC_THRESHOLD_ROWS):
        # Evita trabalho pesado inline; export pesado deve ir para worker assíncrono.
        result["_auto_export_deferred"] = True
        result["_auto_export_reason"] = "heavy_result_async_recommended"
        return
    if result.get("_auto_file_downloads"):
        return

    try:
        payload = {"items": items, "total_count": total}
        buf = to_csv(payload)
        content = buf.getvalue()
        if not content:
            return
        base_name = "".join(ch if ch.isalnum() or ch in " _-" else "_" for ch in str(title_hint or "export_completo")).strip()
        base_name = (base_name or "export_completo")[:50]
        filename = f"{base_name}.csv"
        download_id = await _store_generated_file(
            content,
            "text/csv",
            filename,
            "csv",
            user_sub=user_sub,
            conversation_id=conversation_id,
            scope="auto_csv_export",
        )
        if not download_id:
            return
        result["_auto_file_downloads"] = [
            {
                "download_id": download_id,
                "endpoint": f"/api/download/{download_id}",
                "filename": filename,
                "format": "csv",
                "mime_type": "text/csv",
                "size_bytes": len(content),
                "expires_in_seconds": _GENERATED_FILE_TTL_SECONDS,
                "auto_generated": True,
                "scope": "full_result",
            }
        ]
    except Exception as e:
        logging.warning("[Tools] auto csv export skipped: %s", e)

async def get_generated_file(download_id: str):
    return await _shared_get_generated_file(download_id)

async def tool_generate_chart(
    chart_type: str = "bar",
    title: str = "Chart",
    x_values: list = None,
    y_values: list = None,
    labels: list = None,
    values: list = None,
    series: list = None,
    x_label: str = "",
    y_label: str = "",
):
    """Gera um chart spec para Plotly.js. Retorna _chart no resultado."""
    chart_type = (chart_type or "bar").lower().strip()
    supported = ["bar", "pie", "line", "scatter", "histogram", "hbar"]
    if chart_type not in supported:
        chart_type = "bar"

    def _normalize_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return []

    def _is_non_empty_list(value):
        return isinstance(value, list) and len(value) > 0

    data = []
    layout = {
        "title": {"text": title, "font": {"size": 16}},
        "font": {"family": "Montserrat, sans-serif"},
    }

    # Multi-series via 'series' param
    if series and isinstance(series, list):
        valid_series = []
        for s in series:
            if not isinstance(s, dict):
                continue
            trace = {"type": s.get("type", chart_type), "name": s.get("name", "")}
            sx = _normalize_list(s.get("x"))
            sy = _normalize_list(s.get("y"))
            sl = _normalize_list(s.get("labels"))
            sv = _normalize_list(s.get("values"))
            stype = (trace.get("type") or chart_type).lower().strip()
            if stype == "pie":
                if not _is_non_empty_list(sl) or not _is_non_empty_list(sv) or len(sl) != len(sv):
                    continue
                trace["type"] = "pie"
                trace["labels"] = sl
                trace["values"] = sv
            elif stype == "histogram":
                src = sx or sy
                if not _is_non_empty_list(src):
                    continue
                trace["type"] = "histogram"
                trace["x"] = src
            else:
                if not _is_non_empty_list(sx) or not _is_non_empty_list(sy) or len(sx) != len(sy):
                    continue
                trace["type"] = stype if stype in supported else chart_type
                trace["x"] = sx
                trace["y"] = sy
            valid_series.append(trace)
        data.extend(valid_series)
        if not data:
            return {
                "error": "generate_chart: input inválido. Fornece séries com dados válidos (x/y ou labels/values).",
                "chart_generated": False,
            }
    elif chart_type == "pie":
        pie_labels = _normalize_list(labels or x_values)
        pie_values = _normalize_list(values or y_values)
        if not _is_non_empty_list(pie_labels) or not _is_non_empty_list(pie_values) or len(pie_labels) != len(pie_values):
            return {
                "error": "generate_chart: pie requer labels e values não vazios e com o mesmo tamanho.",
                "chart_generated": False,
            }
        data.append({
            "type": "pie",
            "labels": pie_labels,
            "values": pie_values,
            "textinfo": "label+percent",
            "hole": 0.3,
        })
    elif chart_type == "hbar":
        hx = _normalize_list(x_values)
        hy = _normalize_list(y_values)
        if not _is_non_empty_list(hx) or not _is_non_empty_list(hy) or len(hx) != len(hy):
            return {
                "error": "generate_chart: hbar requer x_values e y_values não vazios e com o mesmo tamanho.",
                "chart_generated": False,
            }
        data.append({
            "type": "bar",
            "y": hx,
            "x": hy,
            "orientation": "h",
            "name": title,
        })
        layout["yaxis"] = {"title": x_label, "automargin": True}
        layout["xaxis"] = {"title": y_label}
    elif chart_type == "histogram":
        hist_values = _normalize_list(x_values or y_values)
        if not _is_non_empty_list(hist_values):
            return {
                "error": "generate_chart: histogram requer x_values (ou y_values) com dados.",
                "chart_generated": False,
            }
        data.append({
            "type": "histogram",
            "x": hist_values,
            "name": title,
        })
        layout["xaxis"] = {"title": x_label}
        layout["yaxis"] = {"title": y_label or "Frequência"}
    else:
        # bar, line, scatter
        x_clean = _normalize_list(x_values)
        y_clean = _normalize_list(y_values)
        if not _is_non_empty_list(x_clean) or not _is_non_empty_list(y_clean) or len(x_clean) != len(y_clean):
            return {
                "error": "generate_chart: chart requer x_values e y_values não vazios e com o mesmo tamanho.",
                "chart_generated": False,
            }
        data.append({
            "type": chart_type if chart_type != "bar" else "bar",
            "x": x_clean,
            "y": y_clean,
            "name": title,
        })
        if x_label: layout["xaxis"] = {"title": x_label}
        if y_label: layout["yaxis"] = {"title": y_label}

    chart_spec = {"data": data, "layout": layout, "config": {"responsive": True}}

    return {
        "chart_generated": True,
        "chart_type": chart_type,
        "title": title,
        "data_points": len((x_values or labels or values or [])),
        "_chart": chart_spec,
    }

async def tool_generate_file(
    format: str = "csv",
    title: str = "Export",
    data: list = None,
    columns: list = None,
    conv_id: str = "",
    user_sub: str = "",
):
    """Gera ficheiro em memória (CSV/XLSX/PDF/DOCX/HTML) e devolve metadados de download."""
    fmt = (format or "csv").strip().lower()
    if fmt not in SUPPORTED_FILE_FORMATS:
        return {"error": f"Formato inválido. Suportados: {', '.join(SUPPORTED_FILE_FORMATS)}"}

    if not isinstance(data, list):
        return {"error": "Campo 'data' deve ser array com pelo menos uma linha"}
    total_rows = len(data)
    if total_rows == 0:
        return {"error": "Dados vazios — nada para exportar.", "format": fmt}

    if columns is None:
        first = data[0]
        if isinstance(first, dict):
            columns = list(first.keys())
        elif isinstance(first, (list, tuple)):
            columns = [f"col_{i+1}" for i in range(len(first))]
        else:
            return {"error": "Não foi possível inferir colunas. Envia 'columns' explicitamente."}

    if not isinstance(columns, list) or len(columns) == 0:
        return {"error": "Campo 'columns' deve ser array de strings"}

    clean_columns = [str(c).strip() for c in columns if str(c).strip()]
    if not clean_columns:
        return {"error": "Sem colunas válidas para gerar ficheiro"}

    row_cap = max(1, min(int(EXPORT_FILE_ROW_CAP or 5000), int(EXPORT_FILE_ROW_CAP_MAX or 100000)))
    effective_data = data[:row_cap]
    was_capped = total_rows > row_cap

    items = []
    for row in effective_data:
        if isinstance(row, dict):
            item = {c: row.get(c, "") for c in clean_columns}
        elif isinstance(row, (list, tuple)):
            item = {c: (row[idx] if idx < len(row) else "") for idx, c in enumerate(clean_columns)}
        else:
            continue
        items.append(item)

    if not items:
        return {"error": "Sem linhas válidas para gerar ficheiro"}

    payload = {"items": items, "total_count": len(items)}
    safe_title = "".join(ch if ch.isalnum() or ch in " _-" else "_" for ch in (title or "Export")).strip()[:40] or "Export"

    try:
        if fmt == "csv":
            mime_type = "text/csv"
            buf = to_csv(payload)
        elif fmt == "xlsx":
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            buf = to_xlsx(payload, safe_title)
        elif fmt == "pdf":
            mime_type = "application/pdf"
            buf = to_pdf(payload, safe_title)
        elif fmt == "docx":
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            buf = to_docx(payload, safe_title)
        else:
            mime_type = "text/html"
            buf = to_html(payload, safe_title)
    except Exception as e:
        logging.error("[Tools] tool_generate_file failed (%s): %s", fmt, e)
        return {"error": f"Erro ao gerar ficheiro {fmt}: {str(e)}"}

    content = buf.getvalue()
    if not content:
        return {"error": "Ficheiro gerado está vazio"}

    filename = f"{safe_title}.{fmt}"
    download_id = await _store_generated_file(
        content,
        mime_type,
        filename,
        fmt,
        user_sub=str(user_sub or "").strip(),
        conversation_id=str(conv_id or "").strip(),
        scope="generate_file",
    )
    if not download_id:
        return {"error": "Ficheiro demasiado grande para armazenamento temporário no servidor"}

    result = {
        "file_generated": True,
        "format": fmt,
        "title": safe_title,
        "rows": len(items),
        "rows_total": total_rows,
        "rows_capped": was_capped,
        "columns": clean_columns,
        "_file_download": {
            "download_id": download_id,
            "endpoint": f"/api/download/{download_id}",
            "filename": filename,
            "format": fmt,
            "mime_type": mime_type,
            "size_bytes": len(content),
            "expires_in_seconds": _GENERATED_FILE_TTL_SECONDS,
        },
    }
    if was_capped:
        result["cap_warning"] = (
            f"Dados truncados a {row_cap} de {total_rows} linhas. "
            "Para ficheiro completo, usar /api/export."
        )
    return result

def truncate_tool_result(result_str):
    if len(result_str) <= AGENT_TOOL_RESULT_MAX_SIZE: return result_str
    try:
        data = json.loads(result_str)
        if isinstance(data, dict) and "items" in data:
            original_items = len(data.get("items", []) or [])
            data["items"] = (data.get("items") or [])[:AGENT_TOOL_RESULT_KEEP_ITEMS]
            data["_truncated"] = True
            data["_original_items"] = original_items
            data["items_returned"] = len(data.get("items", []))
            return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        logging.warning("[Tools] truncate_tool_result fallback: %s", e)
    return result_str[:AGENT_TOOL_RESULT_MAX_SIZE] + "\n...(truncado)"
