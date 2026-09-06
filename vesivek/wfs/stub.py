from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from vesivek.config import sample_dir
from vesivek.models import SiteFrame


STUB_NOTE = (
    "Käytössä on esimerkkigeometria (Pohjoinen Hesperiankatu 3 / tontti 91-14-462-17). "
    "Metrit ovat tämän WFS-otteen EPSG:3067-geometriaa — eivät syötetyn osoitteen mittoja, "
    "ellei osoite ole sama kohde."
)


class StubWfsFetcher:
    name = "Paikallinen esimerkkigeometria (EPSG:3067 stub)"

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or sample_dir()

    def fetch_site(self, easting: float, northing: float, address: str) -> SiteFrame | None:
        building_fc = _load_fc(self.data_dir / "rakennus_3067.geojson")
        plot_fc = _load_fc(self.data_dir / "tontti_3067.geojson")
        if not building_fc:
            return None
        building = building_fc["features"][0]
        plot = plot_fc["features"][0] if plot_fc and plot_fc.get("features") else None
        geom = shape(building["geometry"])
        c = geom.centroid
        props = building.get("properties") or {}
        matched = None
        if props.get("katunimi_suomi"):
            matched = f"{props.get('katunimi_suomi')} {props.get('osoitenumero') or ''}, Helsinki".strip()
        return SiteFrame(
            crs="EPSG:3067",
            source_name=self.name,
            source_url=None,
            verified=False,
            building=building,
            plot=plot,
            address_query=address,
            matched_address=matched,
            easting=float(c.x),
            northing=float(c.y),
            feature_id=str(building.get("id") or ""),
            warnings=[STUB_NOTE],
        )


def _load_fc(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection" or not data.get("features"):
        return None
    return data
