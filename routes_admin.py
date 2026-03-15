"""routes_admin.py — Admin, debug, health, info, learning, feedback endpoints."""

import json
import logging
import os
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from auth import get_current_user
from config import (
    APP_TITLE,
    APP_VERSION,
    AZURE_SPEECH_ENABLED,
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    DEVOPS_INDEX,
    OMNI_INDEX,
    EXAMPLES_INDEX,
    LLM_TIER_FAST,
    LLM_TIER_STANDARD,
    LLM_TIER_PRO,
    LLM_TIER_VISION,
    VISION_ENABLED,
    SPEECH_PROMPT_PRIMARY_SPEC,
    SPEECH_PROMPT_FALLBACK_SPEC,
    PROVIDER_GOVERNANCE_MODE,
    PROVIDER_EXTERNAL_MODEL_FAMILIES,
    PROVIDER_GOVERNANCE_EXPERIMENTAL_ALLOW_EXTERNAL,
    MODEL_ROUTER_ENABLED,
    MODEL_ROUTER_SPEC,
    MODEL_ROUTER_TARGET_TIERS,
    MODEL_ROUTER_NON_PROD_ONLY,
    IS_PRODUCTION,
    RERANK_ENABLED,
    RERANK_MODEL,
    RERANK_ENDPOINT,
    RERANK_TOP_N,
    RERANK_AUTH_MODE,
    SEARCH_SERVICE,
    SEARCH_KEY,
    API_VERSION_SEARCH,
    UPLOAD_MAX_FILES_PER_CONVERSATION,
    UPLOAD_MAX_FILE_BYTES,
    UPLOAD_MAX_CONCURRENT_JOBS,
    UPLOAD_MAX_PENDING_JOBS_PER_USER,
    UPLOAD_MAX_IMAGES_PER_MESSAGE,
    UPLOAD_EMBEDDING_CONCURRENCY,
    UPLOAD_MAX_CHUNKS_PER_FILE,
    UPLOAD_JOB_STALE_SECONDS,
    UPLOAD_MAX_BATCH_TOTAL_BYTES,
    UPLOAD_BLOB_CONTAINER_RAW,
    UPLOAD_BLOB_CONTAINER_TEXT,
    UPLOAD_BLOB_CONTAINER_CHUNKS,
    UPLOAD_INLINE_WORKER_ENABLED,
    UPLOAD_INLINE_WORKER_RUNTIME_ENABLED,
    UPLOAD_DEDICATED_WORKER_ENABLED,
    UPLOAD_WORKER_POLL_SECONDS,
    UPLOAD_WORKER_BATCH_SIZE,
    UPLOAD_INDEX_TOP,
    UPLOAD_FRONTEND_ASYNC_THRESHOLD_BYTES,
    EXPORT_AUTO_ASYNC_ENABLED,
    EXPORT_ASYNC_THRESHOLD_ROWS,
    EXPORT_MAX_CONCURRENT_JOBS,
    EXPORT_JOB_STALE_SECONDS,
    EXPORT_INLINE_WORKER_ENABLED,
    EXPORT_DEDICATED_WORKER_ENABLED,
    EXPORT_WORKER_POLL_SECONDS,
    EXPORT_WORKER_BATCH_SIZE,
    CHAT_TOOLRESULT_BLOB_CONTAINER,
    STORY_LANE_ENABLED,
    UPLOAD_WORKER_PID_FILE,
    EXPORT_WORKER_PID_FILE,
)
from models import (
    FeedbackRequest,
    ClientErrorReport,
    UserStoryPromoteRequest,
    UserStoryCurationReviewRequest,
    UserStorySearchSyncRequest,
    UserStoryDevOpsSyncRequest,
    UserStoryKnowledgeSyncRequest,
    UserStoryKnowledgeAssetUploadRequest,
    UserStoryKnowledgeAssetTextRequest,
    UserStoryKnowledgeAssetBundleRequest,
    UserStoryKnowledgeAssetReviewRequest,
)
from route_deps import (
    security,
    limiter,
    _user_or_ip_rate_key,
    _login_rate_key,
    _is_admin_user,
    _conversation_belongs_to_user,
    _auth_payload_from_request,
    log_audit,
    feedback_memory,
)
from storage import table_insert, table_query, table_delete, table_merge, blob_download_bytes
from tabular_loader import get_tabular_upload_limits
from tool_registry import get_registered_tool_names
from learning import invalidate_prompt_rules_cache
from llm_provider import llm_simple
from user_story_lane import (
    build_user_story_eval_summary,
    promote_user_story_to_curated_corpus,
    review_user_story_curated_candidate,
    sync_user_story_examples_search_index,
)
from story_devops_index import sync_story_devops_index
from story_index_admin import get_story_lane_index_status
from story_knowledge_assets import (
    list_story_knowledge_assets,
    create_story_knowledge_asset_from_upload,
    create_story_knowledge_asset_from_text,
    create_story_knowledge_assets_from_bundle,
    review_story_knowledge_asset,
)
from story_knowledge_index import sync_story_knowledge_index

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected by app.py at include time via router_state
_router_state: dict = {}

BASE_DIR = Path(__file__).resolve().parent


def _get_conversations():
    return _router_state["conversations"]


def _get_conversation_meta():
    return _router_state["conversation_meta"]


def _get_uploaded_files_store():
    return _router_state["uploaded_files_store"]


def _get_upload_jobs_store():
    return _router_state["upload_jobs_store"]


def _get_export_jobs_store():
    return _router_state["export_jobs_store"]


def _get_tool_metrics():
    return _router_state["tool_metrics"]


def _get_tq_module():
    return _router_state["tq_module"]


def _get_inline_worker_task():
    return _router_state.get("inline_worker_task")


def _get_index_example():
    return _router_state["index_example"]


def _get_job_public_view():
    return _router_state["job_public_view"]


def _get_load_upload_job_from_storage():
    return _router_state["load_upload_job_from_storage"]


# =========================================================================
# SHARED HELPERS
# =========================================================================


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_pid_from_file(path: str) -> Optional[int]:
    try:
        txt = Path(path).read_text(encoding="utf-8").strip()
        if not txt:
            return None
        pid = int(txt)
        return pid if pid > 0 else None
    except Exception:
        return None


def _is_process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


# =========================================================================
# FEEDBACK
# =========================================================================


@router.post("/feedback")
@limiter.limit("30/minute", key_func=_user_or_ip_rate_key)
async def submit_feedback(
    request: Request,
    payload: FeedbackRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    question, answer = "", ""
    cid = payload.conversation_id
    conversations = _get_conversations()
    if not await _conversation_belongs_to_user(cid, str(user.get("sub", "") or "")):
        raise HTTPException(403, "Sem permissão para esta conversa")
    if cid in conversations:
        um = [m for m in conversations[cid] if m.get("role") == "user"]
        am = [m for m in conversations[cid] if m.get("role") == "assistant"]
        if um:
            question = um[-1].get("content", "") if isinstance(um[-1].get("content"), str) else str(um[-1].get("content", ""))
        if am:
            answer = am[-1].get("content", "")

    ts = datetime.now(timezone.utc).isoformat()
    safe_conv = cid.replace("-", "")[:32]
    entity = {
        "PartitionKey": safe_conv,
        "RowKey": f"{payload.message_index}_{ts.replace(':', '').replace('-', '').replace('.', '')}",
        "Rating": payload.rating,
        "Note": payload.note or "",
        "Question": question[:2000],
        "Answer": answer[:4000],
        "Timestamp_str": ts,
        "UserSub": str(user.get("sub", "") or ""),
    }
    stored = await table_insert("feedback", entity)
    if not stored:
        feedback_memory.append(entity)

    if question and answer and (payload.rating >= 7 or payload.rating <= 3):
        etype = "positive" if payload.rating >= 7 else "negative"
        eid = f"{safe_conv}_{payload.message_index}"
        await table_insert(
            "examples",
            {
                "PartitionKey": etype,
                "RowKey": eid,
                "Question": question[:2000],
                "Answer": answer[:4000],
                "Rating": payload.rating,
                "Note": payload.note or "",
                "Timestamp_str": ts,
                "UserSub": str(user.get("sub", "") or ""),
            },
        )
        try:
            _index_example = _get_index_example()
            await _index_example(eid, question, answer, payload.rating, example_type=etype, feedback_note=payload.note or "")
        except Exception as e:
            logger.error("[App] _index_example in feedback failed: %s", e)

    return {
        "status": "ok",
        "message": f"Feedback: {payload.rating}/10",
        "persisted": "table_storage" if stored else "memory",
    }


@router.get("/feedback/stats")
@limiter.limit("30/minute", key_func=_user_or_ip_rate_key)
async def feedback_stats(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if not _is_admin_user(user):
        raise HTTPException(403, "Apenas admins")
    fbs = await table_query("feedback", top=1000)
    all_fb = fbs + list(feedback_memory)
    if not all_fb:
        return {"total": 0, "average_rating": 0}
    ratings = [f.get("Rating", 0) for f in all_fb if f.get("Rating", 0) > 0]
    if not ratings:
        return {"total": 0, "average_rating": 0}
    return {
        "total": len(ratings),
        "average_rating": round(sum(ratings) / len(ratings), 1),
        "distribution": {str(r): ratings.count(r) for r in range(1, 11)},
    }


# =========================================================================
# LEARNING ENDPOINTS
# =========================================================================


@router.post("/api/learning/rules")
@limiter.limit("20/minute", key_func=_user_or_ip_rate_key)
async def add_rule(
    request: Request,
    rule_text: str,
    category: str = "general",
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    rid = f"rule_{uuid.uuid4().hex[:8]}"
    await table_insert(
        "PromptRules",
        {
            "PartitionKey": "active",
            "RowKey": rid,
            "RuleText": rule_text,
            "Category": category,
            "CreatedBy": user.get("sub"),
            "CreatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    invalidate_prompt_rules_cache()
    return {"status": "ok", "rule_id": rid}


@router.get("/api/learning/rules")
@limiter.limit("60/minute", key_func=_user_or_ip_rate_key)
async def list_rules(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if not _is_admin_user(user):
        raise HTTPException(403, "Admin only")
    rules = await table_query("PromptRules", "PartitionKey eq 'active'", top=50)
    return {
        "rules": [
            {
                "id": r.get("RowKey"),
                "text": r.get("RuleText"),
                "category": r.get("Category"),
                "created_by": r.get("CreatedBy"),
            }
            for r in rules
        ]
    }


@router.delete("/api/learning/rules/{rule_id}")
@limiter.limit("20/minute", key_func=_user_or_ip_rate_key)
async def delete_rule(
    request: Request,
    rule_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    await table_delete("PromptRules", "active", rule_id)
    invalidate_prompt_rules_cache()
    return {"status": "ok"}


@router.post("/api/learning/analyze")
@limiter.limit("10/minute", key_func=_user_or_ip_rate_key)
async def analyze_feedback(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    fbs = await table_query("feedback", top=500)
    if not fbs:
        return {"analysis": "Sem feedback suficiente.", "suggestions": []}

    neg = [f for f in fbs if f.get("Rating", 10) <= 3]
    pos = [f for f in fbs if f.get("Rating", 0) >= 8]
    summary = f"Total: {len(fbs)} feedbacks. Positivos(8+): {len(pos)}. Negativos(3-): {len(neg)}.\n\n"
    if neg:
        summary += "FEEDBACK NEGATIVO:\n"
        for f in neg[:10]:
            summary += f"- Q: {f.get('Question', '')[:80]}... Rating: {f.get('Rating')}, Nota: {f.get('Note', '')}\n"

    try:
        analysis = await llm_simple(
            f"Analisa feedback de agente AI e sugere melhorias:\n\n{summary}",
            tier="standard",
            max_tokens=1500,
        )
    except Exception as e:
        logger.warning("[App] analyze_feedback LLM failed, using summary fallback: %s", e)
        analysis = summary

    return {"analysis": analysis, "total": len(fbs), "positive": len(pos), "negative": len(neg)}


# =========================================================================
# INFO / HEALTH / DEBUG
# =========================================================================


def _build_admin_info_payload() -> dict:
    upload_jobs_store = _get_upload_jobs_store()
    return {
        "service": APP_TITLE,
        "version": APP_VERSION,
        "status": "running",
        "models": {"fast": LLM_TIER_FAST, "standard": LLM_TIER_STANDARD, "pro": LLM_TIER_PRO, "vision": LLM_TIER_VISION},
        "routing": {
            "model_router_enabled": MODEL_ROUTER_ENABLED,
            "model_router_effective": bool(MODEL_ROUTER_ENABLED and (not MODEL_ROUTER_NON_PROD_ONLY or not IS_PRODUCTION)),
            "model_router_spec": MODEL_ROUTER_SPEC,
            "model_router_target_tiers": list(MODEL_ROUTER_TARGET_TIERS),
            "model_router_non_prod_only": MODEL_ROUTER_NON_PROD_ONLY,
        },
        "rerank": {
            "enabled": RERANK_ENABLED,
            "model": RERANK_MODEL,
            "endpoint_configured": bool(str(RERANK_ENDPOINT or "").strip()),
            "top_n": RERANK_TOP_N,
            "auth_mode": RERANK_AUTH_MODE,
        },
        "indexes": {"devops": DEVOPS_INDEX, "omni": OMNI_INDEX, "examples": EXAMPLES_INDEX},
        "active_tools": get_registered_tool_names(),
        "capabilities": [
            "multi_model",
            "streaming_sse",
            "jwt_cookie_auth",
            "agent_routing",
            "parallel_tools",
            "export_csv_xlsx_pdf_svg_html_zip",
            "feedback",
            "file_upload",
            "chat_persistence",
            "adaptive_learning",
        ],
        "upload_limits": {
            "max_files_per_conversation": UPLOAD_MAX_FILES_PER_CONVERSATION,
            "max_images_per_message": UPLOAD_MAX_IMAGES_PER_MESSAGE,
            "max_file_bytes": UPLOAD_MAX_FILE_BYTES,
            "max_file_bytes_by_extension": get_tabular_upload_limits(),
            "max_batch_total_bytes": UPLOAD_MAX_BATCH_TOTAL_BYTES,
            "frontend_async_threshold_bytes": UPLOAD_FRONTEND_ASYNC_THRESHOLD_BYTES,
            "max_concurrent_jobs": UPLOAD_MAX_CONCURRENT_JOBS,
            "max_pending_jobs_per_user": UPLOAD_MAX_PENDING_JOBS_PER_USER,
            "embedding_concurrency": UPLOAD_EMBEDDING_CONCURRENCY,
            "max_chunks_per_file": UPLOAD_MAX_CHUNKS_PER_FILE,
            "job_stale_seconds": UPLOAD_JOB_STALE_SECONDS,
            "index_top": UPLOAD_INDEX_TOP,
        },
        "upload_storage": {
            "raw_container": UPLOAD_BLOB_CONTAINER_RAW,
            "text_container": UPLOAD_BLOB_CONTAINER_TEXT,
            "chunks_container": UPLOAD_BLOB_CONTAINER_CHUNKS,
            "inline_worker_enabled": bool(UPLOAD_INLINE_WORKER_ENABLED and UPLOAD_INLINE_WORKER_RUNTIME_ENABLED),
            "inline_worker_configured": UPLOAD_INLINE_WORKER_ENABLED,
            "inline_worker_runtime_guard": UPLOAD_INLINE_WORKER_RUNTIME_ENABLED,
            "dedicated_worker_sidecar": UPLOAD_DEDICATED_WORKER_ENABLED,
            "worker_poll_seconds": UPLOAD_WORKER_POLL_SECONDS,
            "worker_batch_size": UPLOAD_WORKER_BATCH_SIZE,
        },
        "export_storage": {
            "jobs_table": "ExportJobs",
            "payload_container": CHAT_TOOLRESULT_BLOB_CONTAINER,
            "auto_async_enabled": EXPORT_AUTO_ASYNC_ENABLED,
            "async_threshold_rows": EXPORT_ASYNC_THRESHOLD_ROWS,
            "max_concurrent_jobs": EXPORT_MAX_CONCURRENT_JOBS,
            "job_stale_seconds": EXPORT_JOB_STALE_SECONDS,
            "inline_worker_enabled": bool(EXPORT_INLINE_WORKER_ENABLED and UPLOAD_INLINE_WORKER_RUNTIME_ENABLED),
            "inline_worker_configured": EXPORT_INLINE_WORKER_ENABLED,
            "dedicated_worker_sidecar": EXPORT_DEDICATED_WORKER_ENABLED,
            "worker_poll_seconds": EXPORT_WORKER_POLL_SECONDS,
            "worker_batch_size": EXPORT_WORKER_BATCH_SIZE,
        },
        "pptx_status": "ok",  # Simplified — actual check in app.py
    }


@router.get("/api/info")
@limiter.limit("120/minute", key_func=_login_rate_key)
async def api_info(request: Request):
    return {
        "service": APP_TITLE,
        "version": APP_VERSION,
        "status": "running",
        "mode": "public",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "upload_limits": {
            "max_files_per_conversation": UPLOAD_MAX_FILES_PER_CONVERSATION,
            "max_images_per_message": UPLOAD_MAX_IMAGES_PER_MESSAGE,
            "max_file_bytes": UPLOAD_MAX_FILE_BYTES,
            "max_file_bytes_by_extension": get_tabular_upload_limits(),
            "max_batch_total_bytes": UPLOAD_MAX_BATCH_TOTAL_BYTES,
            "frontend_async_threshold_bytes": UPLOAD_FRONTEND_ASYNC_THRESHOLD_BYTES,
        },
        "features": {
            "user_story_lane": STORY_LANE_ENABLED,
            "speech_prompt": True,
            "speech_provider": "azure_speech" if (AZURE_SPEECH_ENABLED and AZURE_SPEECH_KEY and AZURE_SPEECH_REGION) else "browser_fallback",
            "speech_prompt_primary": SPEECH_PROMPT_PRIMARY_SPEC,
            "speech_prompt_fallback": SPEECH_PROMPT_FALLBACK_SPEC,
            "speech_submit_modes": ["auto", "text"],
            "provider_governance_mode": PROVIDER_GOVERNANCE_MODE,
            "provider_external_model_families": list(PROVIDER_EXTERNAL_MODEL_FAMILIES),
            "provider_external_models_experimental_allowed": PROVIDER_GOVERNANCE_EXPERIMENTAL_ALLOW_EXTERNAL,
        },
    }


@router.get("/api/admin/info")
@limiter.limit("60/minute", key_func=_user_or_ip_rate_key)
async def api_admin_info(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    payload = _build_admin_info_payload()
    payload["mode"] = "admin"
    return payload


@router.get("/api/admin/tool-metrics")
async def api_admin_tool_metrics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    return _get_tool_metrics().snapshot()


@router.get("/api/admin/token-quotas")
async def api_admin_token_quotas(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    mgr = _get_tq_module().token_quota_manager
    if not mgr:
        return {"error": "Token quota manager not initialised"}
    return await mgr.snapshot()


# =========================================================================
# USER STORY ADMIN
# =========================================================================


@router.get("/api/admin/user-stories/eval-summary")
async def api_admin_user_story_eval_summary(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    top: int = 250,
    user_sub: Optional[str] = None,
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    return await build_user_story_eval_summary(user_sub=str(user_sub or "").strip(), top=top)


@router.post("/api/admin/user-stories/promote-candidate")
async def api_admin_user_story_promote_candidate(
    payload: UserStoryPromoteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await promote_user_story_to_curated_corpus(
            draft_id=payload.draft_id,
            source_user_sub=payload.user_sub,
            promoted_by=str(user.get("sub", "") or user.get("username", "") or "admin"),
            note=str(payload.note or "").strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/admin/user-stories/review-candidate")
async def api_admin_user_story_review_candidate(
    payload: UserStoryCurationReviewRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await review_user_story_curated_candidate(
            draft_id=payload.draft_id,
            action=payload.action,
            reviewed_by=str(user.get("sub", "") or user.get("username", "") or "admin"),
            note=str(payload.note or "").strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/admin/user-stories/sync-search-index")
async def api_admin_user_story_sync_search_index(
    payload: UserStorySearchSyncRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await sync_user_story_examples_search_index(
            draft_id=str(payload.draft_id or "").strip(),
            top=int(payload.top or 200),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/admin/user-stories/sync-devops-index")
async def api_admin_user_story_sync_devops_index(
    payload: UserStoryDevOpsSyncRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await sync_story_devops_index(
            since_iso=str(payload.since_iso or "").strip(),
            since_days=int(payload.since_days or 30),
            top=int(payload.top or 1200),
            update_cursor=bool(payload.update_cursor),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/admin/user-stories/sync-knowledge-index")
async def api_admin_user_story_sync_knowledge_index(
    payload: UserStoryKnowledgeSyncRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await sync_story_knowledge_index(
            max_docs=int(payload.max_docs or 1500),
            batch_size=int(payload.batch_size or 150),
            update_state=bool(payload.update_state),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/admin/user-stories/index-status")
async def api_admin_user_story_index_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    return await get_story_lane_index_status()


@router.get("/api/admin/user-stories/knowledge-assets")
async def api_admin_user_story_list_knowledge_assets(
    top: int = 100,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    return await list_story_knowledge_assets(top=max(1, min(int(top or 100), 500)))


@router.post("/api/admin/user-stories/knowledge-assets/import-upload")
async def api_admin_user_story_import_knowledge_asset_upload(
    payload: UserStoryKnowledgeAssetUploadRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await create_story_knowledge_asset_from_upload(
            conversation_id=payload.conversation_id,
            file_id=payload.file_id,
            imported_by=str(user.get("sub", "") or user.get("username", "") or "admin"),
            title=str(payload.title or "").strip(),
            domain=str(payload.domain or "").strip(),
            journey=str(payload.journey or "").strip(),
            flow=str(payload.flow or "").strip(),
            team_scope=str(payload.team_scope or "").strip(),
            note=str(payload.note or "").strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/admin/user-stories/knowledge-assets/import-text")
async def api_admin_user_story_import_knowledge_asset_text(
    payload: UserStoryKnowledgeAssetTextRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await create_story_knowledge_asset_from_text(
            title=payload.title,
            content=payload.content,
            imported_by=str(user.get("sub", "") or user.get("username", "") or "admin"),
            asset_key=str(payload.asset_key or "").strip(),
            domain=str(payload.domain or "").strip(),
            journey=str(payload.journey or "").strip(),
            flow=str(payload.flow or "").strip(),
            team_scope=str(payload.team_scope or "").strip(),
            note=str(payload.note or "").strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/admin/user-stories/knowledge-assets/import-bundle")
async def api_admin_user_story_import_knowledge_asset_bundle(
    payload: UserStoryKnowledgeAssetBundleRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await create_story_knowledge_assets_from_bundle(
            entries=[item.model_dump() for item in payload.items],
            imported_by=str(user.get("sub", "") or user.get("username", "") or "admin"),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/admin/user-stories/knowledge-assets/review")
async def api_admin_user_story_review_knowledge_asset(
    payload: UserStoryKnowledgeAssetReviewRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")
    try:
        return await review_story_knowledge_asset(
            asset_id=payload.asset_id,
            action=payload.action,
            reviewed_by=str(user.get("sub", "") or user.get("username", "") or "admin"),
            note=str(payload.note or "").strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


# =========================================================================
# CLIENT ERROR REPORTING
# =========================================================================


@router.post("/api/client-error")
@limiter.limit("10/minute", key_func=_user_or_ip_rate_key)
async def report_client_error(request: Request, report: ClientErrorReport):
    user = None
    try:
        user = _auth_payload_from_request(request)
    except Exception:
        user = None
    user_id = str((user or {}).get("sub", "") or "anonymous")

    logger.warning(
        json.dumps(
            {
                "event": "client_error",
                "user_id": user_id,
                "error_type": report.error_type,
                "message": report.message[:500],
                "component": report.component or "",
                "url": report.url or "",
                "timestamp": report.timestamp or "",
                "has_stack": bool(report.stack),
            },
            ensure_ascii=False,
        )
    )
    return {"status": "logged"}


# =========================================================================
# RUNTIME CHECK
# =========================================================================


@router.get("/api/runtime/check")
async def runtime_check(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admins")

    targets = [
        BASE_DIR / "app.py",
        BASE_DIR / "agent.py",
        BASE_DIR / "tools.py",
        BASE_DIR / "config.py",
        BASE_DIR / "static" / "index.html",
    ]
    files = {}
    for p in targets:
        key = str(p.relative_to(BASE_DIR))
        try:
            full_sha = _file_sha256(p) if p.exists() else ""
            files[key] = {
                "exists": p.exists(),
                "sha256": full_sha[:24],
                "sha256_full": full_sha,
                "size_bytes": p.stat().st_size if p.exists() else 0,
            }
        except Exception as e:
            files[key] = {"exists": False, "error": str(e)}

    markers = {}
    try:
        index_txt = (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8", errors="replace")
        markers = {
            "max_files_10": "MAX_FILES_PER_CONVERSATION = 10" in index_txt,
            "upload_async_frontend": "/upload/async" in index_txt,
            "upload_status_frontend": "/api/upload/status/" in index_txt,
        }
    except Exception as e:
        markers = {"error": str(e)}

    manifest_result = {}
    manifest_path = BASE_DIR / "deploy" / "runtime-manifest.json"
    if manifest_path.exists():
        try:
            expected = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected_files = expected.get("files", {}) if isinstance(expected, dict) else {}
            drift = {}
            for rel_path, exp_hash in expected_files.items():
                actual = (files.get(rel_path) or {}).get("sha256_full", "")
                drift[rel_path] = {
                    "expected": str(exp_hash or ""),
                    "actual": str(actual or ""),
                    "match": bool(actual) and str(actual) == str(exp_hash),
                }
            manifest_result = {
                "path": str(manifest_path.relative_to(BASE_DIR)),
                "has_manifest": True,
                "all_match": all(v.get("match") for v in drift.values()) if drift else False,
                "files": drift,
            }
        except Exception as e:
            manifest_result = {"path": str(manifest_path.relative_to(BASE_DIR)), "has_manifest": True, "error": str(e)}
    else:
        manifest_result = {"path": str(manifest_path.relative_to(BASE_DIR)), "has_manifest": False}

    return {
        "service": APP_TITLE,
        "version": APP_VERSION,
        "runtime_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "markers": markers,
        "manifest_check": manifest_result,
    }


# =========================================================================
# DEBUG ENDPOINTS
# =========================================================================


@router.get("/api/debug/upload-jobs")
async def debug_upload_jobs(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials, request=request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    now = datetime.now(timezone.utc)
    upload_jobs_store = _get_upload_jobs_store()
    _job_public_view = _get_job_public_view()
    jobs_local = []
    for job_id, job in upload_jobs_store.items():
        jobs_local.append(
            {
                "job_id": str(job_id)[:12],
                "status": str(job.get("status", "")),
                "filename": str(job.get("filename", ""))[:40],
                "size_mb": round(int(job.get("size_bytes", 0) or 0) / 1024 / 1024, 1),
                "worker_id": str(job.get("worker_id", ""))[:16],
                "created_at": str(job.get("created_at", ""))[:25],
                "updated_at": str(job.get("updated_at", ""))[:25],
                "error": str(job.get("error", ""))[:100],
            }
        )
    storage_jobs = []
    try:
        rows = await table_query("UploadJobs", "PartitionKey eq 'upload'", top=20)
        for row in rows:
            status = str(row.get("Status", ""))
            if status.lower() in ("completed", "failed"):
                age = ""
                try:
                    updated = datetime.fromisoformat(str(row.get("UpdatedAt", "")))
                    age = f"{int((now - updated).total_seconds())}s ago"
                except (ValueError, TypeError):
                    pass
                if age and int((now - updated).total_seconds()) > 300:
                    continue
            storage_jobs.append(
                {
                    "job_id": str(row.get("RowKey", ""))[:12],
                    "status": status,
                    "filename": str(row.get("Filename", ""))[:40],
                    "size_mb": round(int(row.get("SizeBytes", 0) or 0) / 1024 / 1024, 1),
                    "worker_id": str(row.get("WorkerId", ""))[:16],
                    "created_at": str(row.get("CreatedAt", ""))[:25],
                    "updated_at": str(row.get("UpdatedAt", ""))[:25],
                }
            )
    except Exception as e:
        storage_jobs = [{"error": str(e)[:200]}]

    worker_instance_id = _router_state.get("worker_instance_id", "")
    inline_worker_enabled = _router_state.get("inline_worker_enabled", False)
    _inline_worker_task = _get_inline_worker_task()

    return {
        "now_utc": now.isoformat(),
        "worker_instance": str(worker_instance_id)[:16],
        "inline_worker_enabled": inline_worker_enabled,
        "worker_task_alive": _inline_worker_task is not None and not _inline_worker_task.done() if _inline_worker_task else False,
        "local_jobs": jobs_local,
        "storage_jobs": storage_jobs,
    }


@router.get("/health")
@limiter.limit("120/minute", key_func=_login_rate_key)
async def health(
    request: Request,
    deep: bool = False,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    result = {"status": "healthy", "mode": "basic", "checks": {"app": "ok"}}
    if not deep:
        return result

    try:
        user = get_current_user(credentials)
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token inválido para deep health check"},
        )
    if not _is_admin_user(user):
        raise HTTPException(403, "Apenas admins")

    result["mode"] = "deep"
    checks = {}

    try:
        await table_query("feedback", top=1)
        checks["table_storage"] = "ok"
    except Exception as e:
        checks["table_storage"] = f"error: {str(e)[:100]}"

    try:
        probe_blob = "__health_probe__.txt"
        _ = await blob_download_bytes(UPLOAD_BLOB_CONTAINER_RAW, probe_blob)
        checks["blob_storage"] = "ok"
    except Exception as e:
        checks["blob_storage"] = f"error: {str(e)[:100]}"

    try:
        _ = await llm_simple("ping", tier="fast", max_tokens=5)
        checks["llm_fast"] = "ok"
    except Exception as e:
        checks["llm_fast"] = f"error: {str(e)[:100]}"

    try:
        if VISION_ENABLED:
            _ = await llm_simple("ping", tier="vision", max_tokens=5)
            checks["llm_vision"] = "ok"
        else:
            checks["llm_vision"] = "disabled"
    except Exception as e:
        checks["llm_vision"] = f"error: {str(e)[:100]}"

    try:
        from http_helpers import search_request_with_retry

        url = f"https://{SEARCH_SERVICE}.search.windows.net/indexes/{DEVOPS_INDEX}/docs/search?api-version={API_VERSION_SEARCH}"
        headers = {"Content-Type": "application/json", "api-key": SEARCH_KEY}
        search_payload = {"search": "*", "top": 1}
        search_resp = await search_request_with_retry(url=url, headers=headers, json_body=search_payload, max_retries=2)
        checks["ai_search"] = "ok" if "error" not in search_resp else f"error: {str(search_resp.get('error', 'unknown'))[:100]}"
    except Exception as e:
        checks["ai_search"] = f"error: {str(e)[:100]}"

    try:
        if RERANK_ENABLED:
            endpoint_configured = bool(str(RERANK_ENDPOINT or "").strip())
            checks["rerank"] = "configured" if endpoint_configured else "error: missing endpoint"
        else:
            checks["rerank"] = "disabled"
    except Exception as e:
        checks["rerank"] = f"error: {str(e)[:100]}"

    try:
        upload_worker_enabled = UPLOAD_DEDICATED_WORKER_ENABLED
        if upload_worker_enabled:
            pid = _load_pid_from_file(UPLOAD_WORKER_PID_FILE)
            checks["upload_worker"] = "ok" if _is_process_alive(pid) else "error: worker_not_running"
        else:
            checks["upload_worker"] = "disabled"
    except Exception as e:
        checks["upload_worker"] = f"error: {str(e)[:100]}"

    try:
        export_worker_enabled = EXPORT_DEDICATED_WORKER_ENABLED
        if export_worker_enabled:
            pid = _load_pid_from_file(EXPORT_WORKER_PID_FILE)
            checks["export_worker"] = "ok" if _is_process_alive(pid) else "error: worker_not_running"
        else:
            checks["export_worker"] = "disabled"
    except Exception as e:
        checks["export_worker"] = f"error: {str(e)[:100]}"

    result["checks"] = checks
    all_ok = all(v == "ok" or v in ("configured", "disabled") for v in checks.values())
    result["status"] = "healthy" if all_ok else "degraded"
    return JSONResponse(status_code=200 if all_ok else 503, content=result)


@router.get("/debug/conversations")
async def debug_conversations(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(403)
    conversations = _get_conversations()
    conversation_meta = _get_conversation_meta()
    uploaded_files_store = _get_uploaded_files_store()
    return {
        cid: {
            "mode": conversation_meta.get(cid, {}).get("mode"),
            "msgs": len(msgs),
            "has_file": cid in uploaded_files_store,
        }
        for cid, msgs in conversations.items()
    }
