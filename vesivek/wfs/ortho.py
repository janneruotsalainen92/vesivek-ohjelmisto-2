from __future__ import annotations

from vesivek.config import (
    HELSINKI_WMS,
    HTTP_TIMEOUT_S,
    USER_AGENT,
    VANTAA_BBOX_3067,
    VANTAA_WMS,
)
from vesivek.wfs.http import request_url

import requests


def fetch_ortho_png(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    *,
    width_px: int = 1400,
    prefer: str | None = None,
) -> tuple[bytes | None, tuple[float, float, float, float] | None, str | None]:
    """Fetch an open municipal orthophoto for the strip bbox (EPSG:3067)."""
    pad = 8.0
    bbox = (minx - pad, miny - pad, maxx + pad, maxy + pad)
    aspect = max((bbox[3] - bbox[1]) / max(bbox[2] - bbox[0], 1e-6), 0.25)
    height_px = max(400, min(1800, int(width_px * aspect)))

    candidates: list[tuple[str, str, str]] = []
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    in_vantaa = VANTAA_BBOX_3067[0] <= cx <= VANTAA_BBOX_3067[2] and VANTAA_BBOX_3067[1] <= cy <= VANTAA_BBOX_3067[3]
    if in_vantaa or prefer == "vantaa":
        candidates.append((VANTAA_WMS, "taustakartta:ortoilmakuva", "Vantaa WMS ortoilmakuva"))
    candidates.append((HELSINKI_WMS, "avoindata:Ortoilmakuva_2024", "Helsingin WMS ortoilmakuva"))
    candidates.append((HELSINKI_WMS, "avoindata:Ortoilmakuva", "Helsingin WMS ortoilmakuva"))

    headers = {"User-Agent": USER_AGENT, "Accept": "image/png"}
    for base, layer, label in candidates:
        params = {
            "service": "WMS",
            "version": "1.1.1",
            "request": "GetMap",
            "layers": layer,
            "srs": "EPSG:3067",
            "bbox": f"{bbox[0]:.3f},{bbox[1]:.3f},{bbox[2]:.3f},{bbox[3]:.3f}",
            "width": str(width_px),
            "height": str(height_px),
            "format": "image/png",
            "transparent": "true",
        }
        try:
            resp = requests.get(base, params=params, headers=headers, timeout=HTTP_TIMEOUT_S)
            ctype = (resp.headers.get("content-type") or "").lower()
            if resp.ok and "png" in ctype and len(resp.content) > 800:
                return resp.content, bbox, f"{label} ({request_url(base, params)})"
        except requests.RequestException:
            continue
    return None, None, None
