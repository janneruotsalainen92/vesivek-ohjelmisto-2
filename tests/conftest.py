from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vesivek.models import Edge, Facade, SiteFrame


@pytest.fixture
def rectangle_site() -> SiteFrame:
    # 10 m east × 8 m north, CCW exterior, origin at SW corner.
    coords = [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0], [0.0, 0.0]]
    building = {
        "type": "Feature",
        "id": "test-rect",
        "properties": {"tyyppi": "test"},
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }
    return SiteFrame(
        crs="EPSG:3067",
        source_name="test",
        source_url=None,
        verified=True,
        building=building,
        plot=None,
        address_query="Testikatu 1",
        matched_address="Testikatu 1",
        easting=5.0,
        northing=4.0,
        feature_id="test-rect",
        warnings=[],
    )


@pytest.fixture
def south_facade() -> Facade:
    edge = Edge(
        start=(0.0, 0.0),
        end=(10.0, 0.0),
        length_m=10.0,
        outward=(0.0, -1.0),
        compass="etela",
        index=0,
    )
    return Facade(
        key="etela",
        label_fi="Eteläinen julkisivu",
        compass="etela",
        length_m=10.0,
        edges=[edge],
        verified=True,
        source="test",
    )


def write_color_image(path: Path, rgb: tuple[int, int, int], size: tuple[int, int] = (240, 180)) -> Path:
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[:, :] = rgb
    Image.fromarray(arr, "RGB").save(path)
    return path


def write_stick_image(path: Path, stick_px: int = 200) -> Path:
    w, h = 400, 300
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = (70, 70, 70)  # asphalt-like
    # Yellow vertical mittatikku, stick_px tall.
    x0, y0 = 40, 40
    arr[y0 : y0 + stick_px, x0 : x0 + 8] = (240, 210, 20)
    Image.fromarray(arr, "RGB").save(path)
    return path
