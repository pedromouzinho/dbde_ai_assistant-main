from __future__ import annotations

from starlette.requests import Request

import app


def _make_request(host: str, origin: str, scheme: str = "https") -> Request:
    headers = [
        (b"host", host.encode("utf-8")),
        (b"origin", origin.encode("utf-8")),
        (b"x-forwarded-proto", scheme.encode("utf-8")),
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": scheme,
        "path": "/api/auth/login",
        "headers": headers,
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": (host, 443 if scheme == "https" else 80),
    }
    return Request(scope)


def test_origin_allowlist_accepts_same_origin_custom_domain(monkeypatch):
    monkeypatch.setattr(app, "_allowed_origins_set", {"https://millennium-ai-assistant.azurewebsites.net"})
    request = _make_request("dbdeai.pt", "https://dbdeai.pt")

    assert app._origin_allowed_for_request(request, "https://dbdeai.pt") is True


def test_origin_allowlist_rejects_unknown_cross_origin(monkeypatch):
    monkeypatch.setattr(app, "_allowed_origins_set", {"https://millennium-ai-assistant.azurewebsites.net"})
    request = _make_request("dbdeai.pt", "https://evil.example")

    assert app._origin_allowed_for_request(request, "https://evil.example") is False


def test_origin_allowlist_still_accepts_configured_origin(monkeypatch):
    monkeypatch.setattr(
        app,
        "_allowed_origins_set",
        {"https://millennium-ai-assistant.azurewebsites.net", "https://dbdeai.pt"},
    )
    request = _make_request(
        "millennium-ai-assistant.azurewebsites.net",
        "https://dbdeai.pt",
    )

    assert app._origin_allowed_for_request(request, "https://dbdeai.pt") is True
