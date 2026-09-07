from __future__ import annotations

from pathlib import Path

USER_AGENT = "vesivek-ohjelma-bot-kokeilu/0.2 (human-measurement-testing; local)"
HTTP_TIMEOUT_S = 25
DEFAULT_STICK_M = 1.00
MAX_PHOTOS_WARN = 100
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

HELSINKI_WFS = "https://kartta.hel.fi/ws/geoserver/avoindata/wfs"
HELSINKI_WMS = "https://kartta.hel.fi/ws/geoserver/avoindata/wms"
HSY_WFS = "https://kartta.hsy.fi/geoserver/wfs"
VANTAA_WFS = "https://gis.vantaa.fi/geoserver/wfs"
VANTAA_WMS = "https://gis.vantaa.fi/geoserver/wms"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Rough TM35FIN windows (not legal boundaries).
HSY_BBOX_3067 = (360000.0, 6660000.0, 420000.0, 6710000.0)
HELSINKI_BBOX_3067 = (380000.0, 6668000.0, 402000.0, 6692000.0)
VANTAA_BBOX_3067 = (378000.0, 6674000.0, 410000.0, 6702000.0)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() or (parent / "data" / "sample").exists():
            return parent
    return here.parents[1]


def sample_dir() -> Path:
    return repo_root() / "data" / "sample"


def default_output_dir() -> Path:
    return repo_root() / "tulokset"
