# =============================================================================
# tools_knowledge.py — Search, embeddings and rerank utilities
# =============================================================================

import json
import math
import logging
import re
import unicodedata
from typing import Optional

import httpx

from azure_auth import build_search_auth_headers
from config import (
    SEARCH_SERVICE,
    SEARCH_KEY,
    API_VERSION_SEARCH,
    DEVOPS_INDEX,
    OMNI_INDEX,
    RERANK_ENABLED,
    RERANK_ENDPOINT,
    RERANK_API_KEY,
    RERANK_MODEL,
    RERANK_TOP_N,
    RERANK_TIMEOUT_SECONDS,
    RERANK_AUTH_MODE,
    WEB_SEARCH_ENABLED,
    WEB_SEARCH_API_KEY,
    WEB_SEARCH_ENDPOINT,
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_MARKET,
    WEB_ANSWERS_ENABLED,
    WEB_ANSWERS_API_KEY,
    WEB_ANSWERS_ENDPOINT,
    WEB_ANSWERS_MODEL,
    WEB_ANSWERS_TIMEOUT_SECONDS,
)
from llm_provider import get_embedding_provider
from http_helpers import _sanitize_error_response, search_request_with_retry
from pii_shield import PIIMaskingContext, _regex_pre_mask

logger = logging.getLogger(__name__)

_http_client: Optional[httpx.AsyncClient] = None
_LEGACY_INDEX_AVAILABILITY = {"devops": None, "omni": None}

if RERANK_ENABLED:
    logger.info("[RAG] Reranking enabled: model=%s, top_n=%s", RERANK_MODEL, RERANK_TOP_N)


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=max(25, int(RERANK_TIMEOUT_SECONDS or 25)))
    return _http_client


async def _close_http_client() -> None:
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
    _http_client = None


def _build_rerank_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = str(RERANK_API_KEY or "").strip()
    mode = str(RERANK_AUTH_MODE or "").strip().lower()
    if token:
        if mode == "bearer":
            headers["Authorization"] = f"Bearer {token}"
        elif mode == "api-key":
            headers["api-key"] = token
    return headers


async def _search_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    headers.update(await build_search_auth_headers(api_key=SEARCH_KEY, service_name=SEARCH_SERVICE))
    return headers


def _mark_legacy_index_availability(index_key: str, *, available: bool) -> None:
    if index_key in _LEGACY_INDEX_AVAILABILITY:
        _LEGACY_INDEX_AVAILABILITY[index_key] = bool(available)


def _legacy_index_known_unavailable(index_key: str) -> bool:
    return _LEGACY_INDEX_AVAILABILITY.get(index_key) is False


def _looks_like_missing_index(error_message: str) -> bool:
    text = str(error_message or "").strip().lower()
    if not text:
        return False
    return "404" in text or "not found" in text or "no such index" in text


def _normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", folded).strip()


def _tokenize(value: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", _normalize_text(value))
    return {token for token in normalized.split() if len(token) >= 3}


def _website_item_signature(item: dict) -> str:
    parts = [
        str(item.get("origin", "") or ""),
        str(item.get("id", "") or ""),
        str(item.get("url", "") or ""),
        str(item.get("title", "") or ""),
        str(item.get("tag", "") or ""),
        str(item.get("domain", "") or ""),
        str(item.get("journey", "") or ""),
        str(item.get("flow", "") or ""),
    ]
    raw = "|".join(part.strip() for part in parts if str(part or "").strip())
    return _normalize_text(raw)


def _website_item_search_text(item: dict) -> str:
    return " ".join(
        part
        for part in [
            str(item.get("title", "") or ""),
            str(item.get("content", "") or ""),
            str(item.get("tag", "") or ""),
            str(item.get("domain", "") or ""),
            str(item.get("journey", "") or ""),
            str(item.get("flow", "") or ""),
        ]
        if part
    )


def _rank_website_items(query: str, items: list[dict]) -> list[dict]:
    query_tokens = _tokenize(query)
    ranked: list[dict] = []
    for item in items:
        base_score = float(item.get("score", 0.0) or 0.0)
        search_tokens = _tokenize(_website_item_search_text(item))
        overlap = (len(query_tokens & search_tokens) / max(1, len(query_tokens))) if query_tokens and search_tokens else 0.0
        origin = str(item.get("origin", "") or "")
        source_bias = 0.0
        if origin == "local_story_context":
            source_bias += 0.08
        elif origin == "azure_ai_search_story_knowledge":
            source_bias += 0.04
        if str(item.get("flow", "") or "").strip():
            source_bias += 0.04
        elif str(item.get("journey", "") or "").strip():
            source_bias += 0.02
        hybrid_score = round(base_score + (overlap * 0.45) + source_bias, 4)
        ranked.append({**item, "hybrid_score": hybrid_score, "query_overlap": round(overlap, 4)})
    ranked.sort(
        key=lambda item: (
            float(item.get("hybrid_score", 0.0) or 0.0),
            float(item.get("score", 0.0) or 0.0),
        ),
        reverse=True,
    )
    return ranked


def _dedupe_website_items(items: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for item in items:
        signature = _website_item_signature(item)
        if not signature:
            continue
        current = deduped.get(signature)
        current_score = float(current.get("hybrid_score", current.get("score", 0.0)) or 0.0) if current else -1.0
        candidate_score = float(item.get("hybrid_score", item.get("score", 0.0)) or 0.0)
        if current is None or candidate_score > current_score:
            deduped[signature] = item
    return list(deduped.values())


def _profile_to_website_item(profile: dict) -> dict:
    domain = str(profile.get("domain", "") or "").strip()
    journeys = [str(item) for item in profile.get("top_journeys", []) if item]
    flows = [str(item) for item in profile.get("top_flows", []) if item]
    content = " ".join(
        part
        for part in [
            f"Domínio {domain}." if domain else "",
            f"Journeys: {', '.join(journeys[:4])}." if journeys else "",
            f"Flows: {', '.join(flows[:6])}." if flows else "",
            " ".join(str(item) for item in profile.get("routing_notes", [])[:3] if item),
        ]
        if part
    ).strip()
    base_score = max(
        float(profile.get("score", 0.0) or 0.0),
        0.45 + min(0.2, float(profile.get("production_confidence", 0.0) or 0.0) * 0.2) + min(0.15, float(profile.get("coverage_score", 0.0) or 0.0) * 0.15),
    )
    return {
        "id": f"profile:{_normalize_text(domain).replace(' ', '_')}",
        "title": f"Domain Profile | {domain}" if domain else "Domain Profile",
        "content": content[:500],
        "url": str(profile.get("design_file_url", "") or ""),
        "tag": "Story domain profile",
        "score": round(base_score, 4),
        "origin": "local_story_context",
        "domain": domain,
        "journey": journeys[0] if journeys else "",
        "flow": flows[0] if flows else "",
    }


def _serialize_local_story_context(query: str, top: int) -> dict:
    try:
        from figma_story_map import search_story_design_map, serialize_design_match
        from story_domain_profiles import select_story_domain_profile
        from story_flow_map import search_story_flow_map, serialize_story_flow_match
        from story_policy_packs import select_story_policy_pack
    except Exception as exc:
        logger.warning("[Tools] local story context unavailable: %s", exc)
        return {"items": [], "dominant_domain": "", "sources": []}

    expanded_query = _expanded_story_query_context(query)

    flow_result = search_story_flow_map(
        objective=query,
        context=expanded_query,
        dominant_domain="",
        top=max(1, min(int(top or 3), 4)),
    )
    dominant_domain = str(flow_result.get("dominant_domain", "") or "").strip()

    profile = select_story_domain_profile(
        objective=query,
        context=expanded_query,
        dominant_domain=dominant_domain,
    )
    if not dominant_domain:
        dominant_domain = str(profile.get("domain", "") or "").strip()

    pack = select_story_policy_pack(
        objective=query,
        context=expanded_query,
        dominant_domain=dominant_domain,
    )
    if not dominant_domain:
        dominant_domain = str(pack.get("domain", "") or "").strip()

    design_result = search_story_design_map(
        objective=query,
        context=expanded_query,
        top=min(2, max(1, int(top or 3))),
    )
    if not dominant_domain:
        dominant_domain = str(design_result.get("dominant_domain", "") or "").strip()

    items: list[dict] = []
    for entry in flow_result.get("matches", [])[: max(1, min(int(top or 3), 4))]:
        serialized = serialize_story_flow_match(entry)
        items.append(
            {
                "id": str(serialized.get("key", "") or entry.get("id", "") or ""),
                "title": str(serialized.get("title", "") or entry.get("title", "") or ""),
                "content": str(serialized.get("snippet", "") or entry.get("detail", "") or "")[:500],
                "url": str(serialized.get("url", "") or entry.get("url", "") or ""),
                "tag": "Story flow map",
                "score": round(float(serialized.get("score", entry.get("score", 0.0)) or 0.0), 4),
                "origin": "local_story_context",
                "domain": str(serialized.get("domain", "") or entry.get("domain", "") or ""),
                "journey": str(serialized.get("page_name", "") or entry.get("journey", "") or ""),
                "flow": str(serialized.get("frame_name", "") or entry.get("flow", "") or ""),
            }
        )

    for entry in design_result.get("matches", [])[:2]:
        serialized = serialize_design_match(entry)
        items.append(
            {
                "id": str(serialized.get("key", "") or entry.get("file_key", "") or ""),
                "title": str(serialized.get("title", "") or entry.get("title", "") or ""),
                "content": str(serialized.get("snippet", "") or entry.get("routing_note", "") or "")[:500],
                "url": str(serialized.get("url", "") or entry.get("url", "") or ""),
                "tag": "Figma handoff",
                "score": round(float(serialized.get("score", entry.get("score", 0.0)) or 0.0), 4),
                "origin": "local_story_context",
                "domain": str(serialized.get("domain", "") or entry.get("domain", "") or ""),
                "journey": str((entry.get("journeys", []) or [""])[0] or ""),
                "flow": str((entry.get("journeys", []) or [""])[-1] or ""),
            }
        )

    if profile:
        items.append(_profile_to_website_item(profile))

    deduped = _dedupe_website_items(_rank_website_items(query, items))
    deduped.sort(
        key=lambda item: (
            float(item.get("hybrid_score", item.get("score", 0.0)) or 0.0),
            float(item.get("score", 0.0) or 0.0),
        ),
        reverse=True,
    )
    return {
        "items": deduped[: max(1, min(int(top or 3), 4))],
        "dominant_domain": dominant_domain,
        "sources": merge_sources(["design_map" if design_result.get("matches") else "", "flow_map" if flow_result.get("matches") else "", "domain_profile" if profile else "", "policy_pack" if pack else ""]),
    }


def merge_sources(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _expanded_story_query_context(query: str) -> str:
    normalized = _normalize_text(query)
    hints: list[str] = []
    if "assinatura digital" in normalized or ("operacao" in normalized and "pendente" in normalized):
        hints.append("Fluxo de operações pendentes e assinatura digital.")
    if any(token in normalized for token in ("credenciais", "login", "acesso", "autenticacao")):
        hints.append("Fluxo de autenticação, login e gestão de credenciais.")
    if any(token in normalized for token in ("documento", "documentos", "upload", "ficheiro", "ficheiros")):
        hints.append("Fluxo documental e documentos digitais com upload e consulta.")
    if any(token in normalized for token in ("recebiveis", "recebíveis", "spin", "cobrancas", "cobranças")):
        hints.append("Fluxo de recebíveis, gestão SPIN, subscrição e cancelamento.")
    if any(token in normalized for token in ("onboarding", "fundos europeus", "contas", "posicao global", "posição global")):
        hints.append("Fluxo de onboarding com contas, dia a dia, posição global e fundos europeus.")
    if any(token in normalized for token in ("beneficiario", "beneficiários", "beneficiarios")):
        hints.append("Fluxo de beneficiários com criação, edição e importação.")
    if not hints:
        return query
    return " | ".join([str(query or "").strip()] + hints)


async def _fallback_story_devops_search(query: str, top: int, *, reason: str, filter_expr: str | None = None) -> Optional[dict]:
    try:
        from story_devops_index import search_story_devops_index

        result = await search_story_devops_index(query_text=query, top=top)
    except Exception as exc:
        logger.warning("[Tools] story devops fallback failed: %s", exc)
        return None

    items = []
    for item in list(result.get("items", []) or [])[: max(1, int(top or 30))]:
        items.append(
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "content": item.get("content", "")[:500],
                "status": item.get("state", ""),
                "url": item.get("url", ""),
                "score": round(float(item.get("score", 0.0) or 0.0), 4),
                "type": item.get("type", ""),
                "area": item.get("area", ""),
                "origin": item.get("origin", "azure_ai_search_story_devops"),
            }
        )

    if not items:
        return None

    fallback_meta = {
        "reason": reason,
        "source": result.get("source", "azure_ai_search_story_devops"),
    }
    if filter_expr:
        fallback_meta["filter_expr_ignored"] = True

    return {
        "total_results": int(result.get("total_results", len(items)) or len(items)),
        "items": items,
        "_fallback": fallback_meta,
    }


async def _fallback_story_knowledge_search(query: str, top: int, *, reason: str, dominant_domain: str = "") -> Optional[dict]:
    return await _fallback_story_knowledge_search_with_local(
        query,
        top,
        reason=reason,
        dominant_domain=dominant_domain,
        local_story=None,
    )


def _story_knowledge_item_to_website_item(item: dict) -> dict:
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "content": str(item.get("content", "") or "")[:500],
        "url": item.get("url", ""),
        "tag": item.get("tag", ""),
        "score": round(float(item.get("score", 0.0) or 0.0), 4),
        "origin": item.get("origin", "azure_ai_search_story_knowledge"),
        "domain": item.get("domain", ""),
        "journey": item.get("journey", ""),
        "flow": item.get("flow", ""),
    }


async def _fallback_story_knowledge_search_with_local(
    query: str,
    top: int,
    *,
    reason: str,
    dominant_domain: str = "",
    local_story: Optional[dict] = None,
) -> Optional[dict]:
    try:
        from story_knowledge_index import search_story_knowledge_index

        result = await search_story_knowledge_index(query_text=query, dominant_domain=dominant_domain, top=top)
    except Exception as exc:
        logger.warning("[Tools] story knowledge fallback failed: %s", exc)
        return None

    story_items = [
        _story_knowledge_item_to_website_item(item)
        for item in list(result.get("items", []) or [])[: max(1, int(top or 10))]
    ]
    local_items = list((local_story or {}).get("items", []) or [])[: max(1, int(top or 10))]
    merged = _dedupe_website_items(_rank_website_items(query, story_items + local_items))
    merged.sort(
        key=lambda item: (
            float(item.get("hybrid_score", item.get("score", 0.0)) or 0.0),
            float(item.get("score", 0.0) or 0.0),
        ),
        reverse=True,
    )
    if not merged:
        return None

    fallback_source = result.get("source", "azure_ai_search_story_knowledge") if story_items else "local_story_context"

    response = {
        "total_results": max(int(result.get("total_results", len(story_items)) or len(story_items)), len(merged)),
        "items": merged[: max(1, int(top or 10))],
        "_fallback": {
            "reason": reason,
            "source": fallback_source,
            "dominant_domain": dominant_domain,
        },
    }
    if story_items and local_items:
        response["_hybrid"] = {
            "story_knowledge_items": len(story_items),
            "local_story_items": len(local_items),
            "dominant_domain": dominant_domain,
            "local_sources": list((local_story or {}).get("sources", []) or []),
        }
    return response

def _rerank_document_from_item(item: dict) -> str:
    parts = []
    for key in ("title", "content", "tag", "status", "type", "state", "area"):
        val = str((item or {}).get(key, "") or "").strip()
        if val:
            parts.append(val)
    return "\n".join(parts)[:8000]

async def _rerank_items_post_retrieval(query: str, items: list) -> tuple[list, dict]:
    if not isinstance(items, list):
        return items, {"applied": False, "reason": "invalid_items"}
    if len(items) < 2:
        return items, {"applied": False, "reason": "too_few_items"}
    if not RERANK_ENABLED:
        return items, {"applied": False, "reason": "disabled"}
    if not RERANK_ENDPOINT:
        return items, {"applied": False, "reason": "missing_endpoint"}
    if str(RERANK_AUTH_MODE or "").strip().lower() in ("api-key", "bearer") and not RERANK_API_KEY:
        return items, {"applied": False, "reason": "missing_api_key"}

    top_n = max(1, min(int(RERANK_TOP_N or len(items)), len(items)))
    documents = [_rerank_document_from_item(item) for item in items]
    payload = {
        "model": RERANK_MODEL,
        "query": str(query or "")[:2000],
        "documents": documents,
        "top_n": top_n,
    }
    headers = _build_rerank_headers()

    try:
        client = _get_http_client()
        resp = await client.post(RERANK_ENDPOINT, headers=headers, json=payload)
        if resp.status_code >= 400:
            logging.warning(
                "[Tools] rerank HTTP %s: %s",
                resp.status_code,
                _sanitize_error_response(resp.text, 300),
            )
            return items, {"applied": False, "reason": f"http_{resp.status_code}"}

        data = resp.json()
    except Exception as e:
        logging.warning("[Tools] rerank request failed: %s", e)
        return items, {"applied": False, "reason": "request_failed"}

    ranked_rows = data.get("results")
    if not isinstance(ranked_rows, list):
        ranked_rows = data.get("data")
    if not isinstance(ranked_rows, list):
        return items, {"applied": False, "reason": "invalid_response"}

    ranked_items = []
    used_indexes = set()
    for row in ranked_rows:
        if not isinstance(row, dict):
            continue
        idx = row.get("index")
        if not isinstance(idx, int):
            continue
        if idx < 0 or idx >= len(items):
            continue
        if idx in used_indexes:
            continue
        cloned = dict(items[idx])
        score = row.get("relevance_score", row.get("score"))
        try:
            if score is not None:
                cloned["rerank_score"] = round(float(score), 6)
        except Exception:
            pass
        ranked_items.append(cloned)
        used_indexes.add(idx)

    if not ranked_items:
        return items, {"applied": False, "reason": "empty_results"}

    for idx, item in enumerate(items):
        if idx not in used_indexes:
            ranked_items.append(item)

    return ranked_items, {
        "applied": True,
        "model": RERANK_MODEL,
        "input_count": len(items),
        "ranked_count": len(ranked_rows),
        "top_n": top_n,
    }

async def get_embedding(text):
    try:
        return await get_embedding_provider().embed(text[:8000].strip() or " ")
    except Exception as e:
        logging.error("[Tools] get_embedding failed: %s", e)
        return None

def _cosine_similarity(vec_a, vec_b):
    if not isinstance(vec_a, list) or not isinstance(vec_b, list):
        return -1.0
    if not vec_a or not vec_b:
        return -1.0
    size = min(len(vec_a), len(vec_b))
    if size <= 0:
        return -1.0
    a = vec_a[:size]
    b = vec_b[:size]
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return -1.0
    return dot / (norm_a * norm_b)

async def tool_search_workitems(query, top=30, filter_expr=None):
    emb = await get_embedding(query)
    if not emb: return {"error": "Falha embedding"}
    if _legacy_index_known_unavailable("devops"):
        fallback = await _fallback_story_devops_search(
            query,
            top,
            reason=f"legacy_index_unavailable:{DEVOPS_INDEX}",
            filter_expr=filter_expr,
        )
        if fallback:
            return fallback
    body = {
        "vectorQueries": [{"kind": "vector", "vector": emb, "fields": "content_vector", "k": top}],
        "select": "id,title,content,url,work_item_type,state,area_path,tags",
        "top": top,
    }
    if filter_expr: body["filter"] = filter_expr
    url = f"https://{SEARCH_SERVICE}.search.windows.net/indexes/{DEVOPS_INDEX}/docs/search?api-version={API_VERSION_SEARCH}"
    data = await search_request_with_retry(
        url=url,
        headers=await _search_headers(),
        json_body=body,
        max_retries=3,
    )
    if "error" in data:
        if _looks_like_missing_index(data.get("error")):
            _mark_legacy_index_availability("devops", available=False)
            fallback = await _fallback_story_devops_search(
                query,
                top,
                reason=f"missing_legacy_index:{DEVOPS_INDEX}",
                filter_expr=filter_expr,
            )
            if fallback:
                return fallback
        return {"error": data["error"]}
    _mark_legacy_index_availability("devops", available=True)
    items = []
    for d in data.get("value",[]):
        ct = str(d.get("content", "") or "")
        title = str(d.get("title", "") or "")
        if not title:
            title = ct.split("]")[0].replace("[", "") if "]" in ct else ct[:100]
        state = str(d.get("state", "") or d.get("status", "") or "")
        work_item_type = str(d.get("work_item_type", "") or d.get("type", "") or d.get("tag", "") or "")
        area_path = str(d.get("area_path", "") or d.get("area", "") or "")
        raw_tags = d.get("tags", [])
        if not isinstance(raw_tags, list):
            raw_tags = [raw_tags] if raw_tags else []
        tags = [str(tag).strip() for tag in raw_tags if str(tag or "").strip()]
        items.append(
            {
                "id": d.get("id", ""),
                "title": title,
                "content": ct[:500],
                "status": state,
                "state": state,
                "type": work_item_type,
                "area": area_path,
                "tags": tags,
                "url": d.get("url", ""),
                "score": round(d.get("@search.score", 0), 4),
            }
        )
    items, rerank_meta = await _rerank_items_post_retrieval(query, items)
    result = {"total_results": len(items), "items": items}
    if rerank_meta.get("applied"):
        result["_rerank"] = rerank_meta
    return result

async def tool_search_website(query, top=10):
    local_story = _serialize_local_story_context(query, top=max(1, min(int(top or 10), 4)))
    dominant_domain = str(local_story.get("dominant_domain", "") or "").strip()
    emb = await get_embedding(query)
    if _legacy_index_known_unavailable("omni"):
        fallback = await _fallback_story_knowledge_search_with_local(
            query,
            top,
            reason=f"legacy_index_unavailable:{OMNI_INDEX}",
            dominant_domain=dominant_domain,
            local_story=local_story,
        )
        if fallback:
            return fallback
        local_items = list(local_story.get("items", []) or [])[: max(1, int(top or 10))]
        if local_items:
            return {
                "total_results": len(local_items),
                "items": local_items,
                "_fallback": {
                    "reason": f"legacy_index_unavailable:{OMNI_INDEX}",
                    "source": "local_story_context",
                    "dominant_domain": dominant_domain,
                },
            }
    body = {"select":"id,content,url,tag","top":top, "search": str(query or "").strip() or "*"}
    if emb:
        body["vectorQueries"] = [{"kind":"vector","vector":emb,"fields":"content_vector","k":top}]
    url = f"https://{SEARCH_SERVICE}.search.windows.net/indexes/{OMNI_INDEX}/docs/search?api-version={API_VERSION_SEARCH}"
    data = await search_request_with_retry(
        url=url,
        headers=await _search_headers(),
        json_body=body,
        max_retries=3,
    )
    if "error" in data:
        if _looks_like_missing_index(data.get("error")):
            _mark_legacy_index_availability("omni", available=False)
            fallback = await _fallback_story_knowledge_search_with_local(
                query,
                top,
                reason=f"missing_legacy_index:{OMNI_INDEX}",
                dominant_domain=dominant_domain,
                local_story=local_story,
            )
            if fallback:
                return fallback
            local_items = list(local_story.get("items", []) or [])[: max(1, int(top or 10))]
            if local_items:
                return {
                    "total_results": len(local_items),
                    "items": local_items,
                    "_fallback": {
                        "reason": f"missing_legacy_index:{OMNI_INDEX}",
                        "source": "local_story_context",
                    "dominant_domain": dominant_domain,
                    },
                }
        fallback = await _fallback_story_knowledge_search_with_local(
            query,
            top,
            reason="legacy_search_error",
            dominant_domain=dominant_domain,
            local_story=local_story,
        )
        if fallback:
            fallback.setdefault("_fallback", {})
            fallback["_fallback"]["legacy_error"] = data["error"]
            return fallback
        local_items = list(local_story.get("items", []) or [])[: max(1, int(top or 10))]
        if local_items:
            return {
                "total_results": len(local_items),
                "items": local_items,
                "_fallback": {
                    "reason": "legacy_search_error",
                    "source": "local_story_context",
                    "dominant_domain": dominant_domain,
                    "legacy_error": data["error"],
                },
            }
        return {"error": data["error"]}
    _mark_legacy_index_availability("omni", available=True)
    legacy_items = [
        {
            "id": d.get("id", ""),
            "title": d.get("tag", "") or d.get("content", "")[:120],
            "content": d.get("content", "")[:500],
            "url": d.get("url", ""),
            "tag": d.get("tag", ""),
            "score": round(d.get("@search.score", 0), 4),
            "origin": "azure_ai_search_omni",
        }
        for d in data.get("value", [])
    ]
    merged_items = _dedupe_website_items(
        _rank_website_items(
            query,
            legacy_items + list(local_story.get("items", []) or []),
        )
    )
    merged_items.sort(
        key=lambda item: (
            float(item.get("hybrid_score", item.get("score", 0.0)) or 0.0),
            float(item.get("score", 0.0) or 0.0),
        ),
        reverse=True,
    )
    items, rerank_meta = await _rerank_items_post_retrieval(query, merged_items[: max(1, int(top or 10) * 2)])
    items = items[: max(1, int(top or 10))]
    result = {
        "total_results": len(items),
        "items": items,
    }
    if local_story.get("items"):
        result["_hybrid"] = {
            "legacy_items": len(legacy_items),
            "local_story_items": len(list(local_story.get("items", []) or [])),
            "dominant_domain": dominant_domain,
            "local_sources": list(local_story.get("sources", []) or []),
        }
    if rerank_meta.get("applied"):
        result["_rerank"] = rerank_meta
    if not emb and local_story.get("items"):
        result.setdefault("_fallback", {})
        result["_fallback"].update(
            {
                "reason": "embedding_unavailable",
                "source": "local_story_context",
                "dominant_domain": dominant_domain,
            }
        )
    return result


async def tool_search_web(query: str, top: int = 5) -> dict:
    """Pesquisa web via Brave Search API. Retorna snippets relevantes."""
    if not WEB_SEARCH_ENABLED or not WEB_SEARCH_API_KEY:
        return {"error": "Pesquisa web não está configurada. Contactar administrador."}

    query = str(query or "").strip()[:200]
    if not query:
        return {"error": "Query de pesquisa vazia."}

    original_query = query
    pii_ctx = PIIMaskingContext()
    query = _regex_pre_mask(query, pii_ctx)
    if pii_ctx.mappings:
        logging.warning(
            "[WebSearch] PII stripped from query before Brave API: %d patterns masked",
            len(pii_ctx.mappings),
        )

    safe_max = max(1, int(WEB_SEARCH_MAX_RESULTS or 5))
    top = min(max(1, int(top or 5)), safe_max)
    logging.info(
        json.dumps(
            {
                "event": "web_search_query",
                "query": query[:200],
                "top": top,
                "source": "brave",
            },
            ensure_ascii=False,
        )
    )

    headers = {
        "X-Subscription-Token": WEB_SEARCH_API_KEY,
        "Accept": "application/json",
    }

    market_parts = str(WEB_SEARCH_MARKET or "pt-PT").split("-")
    country = market_parts[1] if len(market_parts) > 1 else "PT"
    country = str(country or "PT").lower()

    params = {
        "q": query,
        "count": top,
        "country": country,
        "text_decorations": "false",
        "result_filter": "web",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(WEB_SEARCH_ENDPOINT, headers=headers, params=params)
    except Exception as e:
        return {"error": f"Pesquisa web falhou: {str(e)}"}

    if resp.status_code != 200:
        return {
            "error": (
                f"Brave Search API {resp.status_code}: "
                f"{_sanitize_error_response(resp.text, 200)}"
            )
        }

    try:
        data = resp.json()
    except Exception:
        return {"error": "Resposta inválida da Brave Search API."}

    web_results = (data.get("web") or {}).get("results") or []
    results = []
    for item in web_results[:top]:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": str(item.get("title", "") or ""),
                "url": str(item.get("url", "") or ""),
                "snippet": str(item.get("description", "") or "")[:500],
            }
        )

    result = {
        "query": original_query,
        "total_estimated": len(web_results),
        "results": results,
        "results_count": len(results),
    }

    # Optional: enrich with Brave Answers when explicitly configured.
    if WEB_ANSWERS_ENABLED and WEB_ANSWERS_API_KEY:
        answer_headers = {
            "X-Subscription-Token": WEB_ANSWERS_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        answer_payload = {
            "messages": [{"role": "user", "content": query}],
            "model": WEB_ANSWERS_MODEL,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=max(5.0, float(WEB_ANSWERS_TIMEOUT_SECONDS or 20))) as client:
                answer_resp = await client.post(
                    WEB_ANSWERS_ENDPOINT,
                    headers=answer_headers,
                    json=answer_payload,
                )
            if answer_resp.status_code == 200:
                answer_data = answer_resp.json()
                answer_text = (
                    (answer_data.get("choices") or [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if isinstance(answer_text, str) and answer_text.strip():
                    result["answer"] = answer_text.strip()[:4000]
            else:
                logging.warning(
                    "[WebSearch] Brave Answers HTTP %s: %s",
                    answer_resp.status_code,
                    _sanitize_error_response(answer_resp.text, 200),
                )
        except Exception as e:
            logging.warning("[WebSearch] Brave Answers failed: %s", e)

    return result
