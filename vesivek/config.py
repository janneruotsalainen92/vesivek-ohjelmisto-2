from __future__ import annotations

from pathlib import Path

USER_AGENT = "vesivek-ohjelma-mvp/0.1 (human-measurement-testing; local)"
HTTP_TIMEOUT_S = 20
DEFAULT_STICK_M = 1.00
MAX_PHOTOS_WARN = 100
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

HELSINKI_WFS = "https://kartta.hel.fi/ws/geoserver/avoindata/wfs"
HSY_WFS = "https://kartta.hsy.fi/geoserver/wfs"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Rough TM35FIN window for the capital region (not a legal boundary).
HSY_BBOX_3067 = (360000.0, 6660000.0, 420000.0, 6710000.0)
HELSINKI_BBOX_3067 = (380000.0, 6668000.0, 402000.0, 6692000.0)


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
