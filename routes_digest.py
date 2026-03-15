"""routes_digest.py — Daily Digest endpoints (Task 6.3)."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from auth import get_current_user
from config import DEVOPS_ORG, DEVOPS_PROJECT
from http_helpers import devops_request_with_retry as _devops_request_with_retry
from route_deps import security, limiter, _user_or_ip_rate_key, log_audit
from tools import _devops_url, _devops_headers

logger = logging.getLogger(__name__)

router = APIRouter()

_DIGEST_FIELDS = [
    "System.Id",
    "System.Title",
    "System.State",
    "System.WorkItemType",
    "System.AssignedTo",
    "System.CreatedDate",
]


def _digest_format_item(raw_item: dict) -> dict:
    fields = raw_item.get("fields", {}) if isinstance(raw_item, dict) else {}
    assigned = fields.get("System.AssignedTo", "")
    if isinstance(assigned, dict):
        assigned_to = assigned.get("displayName", "")
    else:
        assigned_to = str(assigned or "")
    wi_id = raw_item.get("id")
    return {
        "id": wi_id,
        "title": fields.get("System.Title", ""),
        "state": fields.get("System.State", ""),
        "type": fields.get("System.WorkItemType", ""),
        "assigned_to": assigned_to,
        "created_date": fields.get("System.CreatedDate", ""),
        "url": f"https://dev.azure.com/{DEVOPS_ORG}/{DEVOPS_PROJECT}/_workitems/edit/{wi_id}" if wi_id else "",
    }


async def _run_digest_section(section_name: str, wiql_query: str) -> dict:
    headers = _devops_headers()
    section = {"count": 0, "items": []}
    batch_errors = []

    try:
        wiql_resp = await _devops_request_with_retry(
            "POST",
            _devops_url("wit/wiql?api-version=7.1"),
            headers,
            {"query": wiql_query},
            max_retries=3,
            timeout=60,
        )
        if "error" in wiql_resp:
            section["error"] = wiql_resp["error"]
            return section

        ids = [wi.get("id") for wi in wiql_resp.get("workItems", []) if wi.get("id")]
        section["count"] = len(ids)
        if not ids:
            return section

        details = []
        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            batch_resp = await _devops_request_with_retry(
                "POST",
                _devops_url("wit/workitemsbatch?api-version=7.1"),
                headers,
                {"ids": batch, "fields": _DIGEST_FIELDS},
                max_retries=3,
                timeout=60,
            )
            if "error" in batch_resp:
                batch_errors.append(batch_resp["error"])
                continue
            details.extend(batch_resp.get("value", []))

        section["items"] = [_digest_format_item(item) for item in details]
        if batch_errors:
            section["error"] = "; ".join(batch_errors[:3])
        return section
    except Exception as e:
        section["error"] = f"{section_name} failed: {str(e)}"
        return section


@router.get("/api/digest")
@limiter.shared_limit(
    "10/minute",
    scope="chat_budget",
    key_func=_user_or_ip_rate_key,
)
async def api_digest(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)

    sections_wiql = {
        "created_yesterday": (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{DEVOPS_PROJECT}' "
            "AND [System.WorkItemType] = 'User Story' "
            "AND [System.CreatedDate] >= @Today-1 "
            "AND [System.CreatedDate] < @Today "
            "ORDER BY [System.CreatedDate] DESC"
        ),
        "old_bugs": (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{DEVOPS_PROJECT}' "
            "AND [System.WorkItemType] = 'Bug' "
            "AND [System.State] = 'Active' "
            "AND [System.CreatedDate] < @Today-7 "
            "ORDER BY [System.CreatedDate] ASC"
        ),
        "unassigned": (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{DEVOPS_PROJECT}' "
            "AND [System.State] <> 'Closed' "
            "AND [System.State] <> 'Removed' "
            "AND [System.AssignedTo] = '' "
            "ORDER BY [System.ChangedDate] DESC"
        ),
        "closed_this_week": (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{DEVOPS_PROJECT}' "
            "AND [System.State] = 'Closed' "
            "AND [Microsoft.VSTS.Common.ClosedDate] >= @StartOfWeek "
            "ORDER BY [Microsoft.VSTS.Common.ClosedDate] DESC"
        ),
    }

    payload = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "project": DEVOPS_PROJECT,
    }
    section_items = list(sections_wiql.items())
    section_results = await asyncio.gather(
        *[_run_digest_section(section_name, wiql_query) for section_name, wiql_query in section_items],
        return_exceptions=True,
    )
    for (section_name, _), result in zip(section_items, section_results):
        if isinstance(result, Exception):
            payload[section_name] = {
                "count": 0,
                "items": [],
                "error": f"{section_name} failed: {str(result)}",
            }
        else:
            payload[section_name] = result
    return payload
