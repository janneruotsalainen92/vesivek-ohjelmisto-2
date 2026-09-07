from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import requests

from vesivek.config import HTTP_TIMEOUT_S, USER_AGENT


def wfs_get(base_url: str, params: dict[str, Any]) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    url = f"{base_url}?{urlencode(params)}"
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            resp = requests.get(base_url, params=params, headers=headers, timeout=HTTP_TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise RuntimeError("WFS-vastaus ei ole JSON-objekti")
            return data
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
    raise RuntimeError(f"WFS-haku epäonnistui ({base_url}): {last_exc}") from last_exc


def request_url(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url}?{urlencode(params)}"
