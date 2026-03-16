"""Camada B — testes de tools de pesquisa semântica."""

from __future__ import annotations

import pytest


class _MockResponse:
    def __init__(self, status_code: int, data: dict, text: str = ""):
        self.status_code = status_code
        self._data = data
        self.text = text or str(data)

    def json(self):
        return self._data


@pytest.mark.asyncio
class TestKnowledgeTools:
    async def test_search_workitems_returns_items_with_scores(self, monkeypatch, mock_search_results):
        import tools_knowledge

        async def _fake_embedding(_text):
            return [0.1, 0.2, 0.3]

        async def _fake_search(**kwargs):
            _ = kwargs
            return {
                "value": [
                    {
                        "id": "WI-1",
                        "content": "[US] autenticação SSO para app mobile",
                        "url": "https://dev.azure.com/mock/1",
                        "tag": "User Story",
                        "status": "Active",
                        "@search.score": 0.92,
                    }
                ]
            }

        async def _identity_rerank(query, items):
            _ = query
            return items, {"applied": False}

        monkeypatch.setattr(tools_knowledge, "get_embedding", _fake_embedding)
        monkeypatch.setattr(tools_knowledge, "search_request_with_retry", _fake_search)
        monkeypatch.setattr(tools_knowledge, "_rerank_items_post_retrieval", _identity_rerank)

        result = await tools_knowledge.tool_search_workitems("autenticação SSO", top=5)
        assert result["total_results"] == 1
        assert "score" in result["items"][0]

    async def test_search_website_handles_empty_results(self, monkeypatch):
        import tools_knowledge

        async def _fake_embedding(_text):
            return [0.1, 0.2, 0.3]

        async def _fake_search(**kwargs):
            _ = kwargs
            return {"value": []}

        async def _identity_rerank(query, items):
            _ = query
            return items, {"applied": False}

        monkeypatch.setattr(tools_knowledge, "get_embedding", _fake_embedding)
        monkeypatch.setattr(tools_knowledge, "search_request_with_retry", _fake_search)
        monkeypatch.setattr(tools_knowledge, "_rerank_items_post_retrieval", _identity_rerank)

        result = await tools_knowledge.tool_search_website("zz_no_docs", top=5)
        assert result["total_results"] == 0
        assert result["items"] == []

    async def test_search_workitems_falls_back_to_story_index_when_legacy_index_is_missing(self, monkeypatch):
        import story_devops_index
        import tools_knowledge

        async def _fake_embedding(_text):
            return [0.1, 0.2, 0.3]

        async def _missing_legacy_search(**kwargs):
            _ = kwargs
            return {"error": "Search 404: index not found"}

        async def _story_search(**kwargs):
            _ = kwargs
            return {
                "items": [
                    {
                        "id": 994513,
                        "title": "REVAMPFEE MVP2 | Jornada exemplo",
                        "content": "Story semelhante do índice dedicado.",
                        "url": "https://dev.azure.com/mock/_workitems/edit/994513",
                        "type": "Feature",
                        "state": "Active",
                        "area": r"IT.DIT\DIT\ADMChannels\DBKS\AM24\MSE",
                        "score": 0.91,
                        "origin": "azure_ai_search_story_devops",
                    }
                ],
                "total_results": 1,
                "source": "azure_ai_search_story_devops",
            }

        monkeypatch.setattr(tools_knowledge, "get_embedding", _fake_embedding)
        monkeypatch.setattr(tools_knowledge, "search_request_with_retry", _missing_legacy_search)
        monkeypatch.setattr(tools_knowledge, "_LEGACY_INDEX_AVAILABILITY", {"devops": None, "omni": None})
        monkeypatch.setattr(story_devops_index, "search_story_devops_index", _story_search)

        result = await tools_knowledge.tool_search_workitems("revamp fee", top=5)
        assert result["total_results"] == 1
        assert result["items"][0]["id"] == 994513
        assert result["_fallback"]["source"] == "azure_ai_search_story_devops"

    async def test_search_website_falls_back_to_story_index_when_legacy_index_is_missing(self, monkeypatch):
        import story_knowledge_index
        import tools_knowledge

        async def _fake_embedding(_text):
            return [0.1, 0.2, 0.3]

        async def _missing_legacy_search(**kwargs):
            _ = kwargs
            return {"error": "Search 404: index not found"}

        async def _story_search(**kwargs):
            _ = kwargs
            return {
                "items": [
                    {
                        "id": "doc-1",
                        "title": "Fluxo Revamp Fee",
                        "content": "Resumo funcional do fluxo.",
                        "url": "https://example.com/revamp-fee",
                        "tag": "Mapa funcional",
                        "score": 0.84,
                        "origin": "azure_ai_search_story_knowledge",
                    }
                ],
                "total_results": 1,
                "source": "azure_ai_search_story_knowledge",
            }

        monkeypatch.setattr(tools_knowledge, "get_embedding", _fake_embedding)
        monkeypatch.setattr(tools_knowledge, "search_request_with_retry", _missing_legacy_search)
        monkeypatch.setattr(tools_knowledge, "_LEGACY_INDEX_AVAILABILITY", {"devops": None, "omni": None})
        monkeypatch.setattr(story_knowledge_index, "search_story_knowledge_index", _story_search)

        result = await tools_knowledge.tool_search_website("revamp fee", top=5)
        assert result["total_results"] == 1
        assert result["items"][0]["id"] == "doc-1"
        assert result["_fallback"]["source"] == "azure_ai_search_story_knowledge"

    async def test_search_uploaded_document_topk_ordering(self, monkeypatch):
        import tools_upload

        async def _fake_load_indexed_chunks(conv_id, user_sub=""):
            _ = (conv_id, user_sub)
            return [
                (
                    "spec.pdf",
                    {"index": 0, "start": 0, "end": 100, "embedding": [1.0, 0.0], "text": "auth sso"},
                ),
                (
                    "spec.pdf",
                    {"index": 1, "start": 101, "end": 200, "embedding": [0.8, 0.2], "text": "deploy"},
                ),
                (
                    "spec.pdf",
                    {"index": 2, "start": 201, "end": 300, "embedding": [0.0, 1.0], "text": "outro"},
                ),
            ]

        async def _fake_embedding(_text):
            return [1.0, 0.0]

        monkeypatch.setattr(tools_upload, "_load_indexed_chunks", _fake_load_indexed_chunks)
        monkeypatch.setattr(tools_upload, "get_embedding", _fake_embedding)

        result = await tools_upload.tool_search_uploaded_document("auth", conv_id="conv-1")
        assert result["total_results"] >= 1
        scores = [item["score"] for item in result["items"]]
        assert scores == sorted(scores, reverse=True)

    async def test_reranking_reorders_items(self, monkeypatch):
        import tools_knowledge

        class _FakeClient:
            async def post(self, url, headers=None, json=None):
                _ = (url, headers, json)
                return _MockResponse(
                    200,
                    {
                        "results": [
                            {"index": 1, "relevance_score": 0.95},
                            {"index": 0, "relevance_score": 0.51},
                        ]
                    },
                )

        monkeypatch.setattr(tools_knowledge, "RERANK_ENABLED", True)
        monkeypatch.setattr(tools_knowledge, "RERANK_ENDPOINT", "https://mock-rerank")
        monkeypatch.setattr(tools_knowledge, "RERANK_AUTH_MODE", "")
        monkeypatch.setattr(tools_knowledge, "RERANK_API_KEY", "")
        monkeypatch.setattr(tools_knowledge, "_get_http_client", lambda: _FakeClient())

        items = [
            {"id": "A", "content": "item A"},
            {"id": "B", "content": "item B"},
        ]
        ranked, meta = await tools_knowledge._rerank_items_post_retrieval("query", items)
        assert meta.get("applied") is True
        assert ranked[0]["id"] == "B"

    async def test_embedding_timeout_or_failure_returns_error(self, monkeypatch):
        import tools_knowledge

        async def _no_embedding(_text):
            return None

        monkeypatch.setattr(tools_knowledge, "get_embedding", _no_embedding)
        result = await tools_knowledge.tool_search_workitems("qualquer", top=5)
        assert "error" in result
