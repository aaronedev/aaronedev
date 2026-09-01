from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpJsonTransportError(Exception):
    """Raised when a JSON HTTP request cannot reach its destination."""


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_headers = dict(headers or {})
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            status = getattr(response, "status", 200)
    except HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read()
        except OSError:
            raw = b""
    except (URLError, TimeoutError) as exc:
        raise HttpJsonTransportError("HTTP request failed") from exc
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = {}
    return {"status": status, "json": parsed}
