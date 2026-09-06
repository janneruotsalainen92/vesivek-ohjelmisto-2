from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from vesivek.models import SiteFrame


def load_local_geojson(path: Path, address: str) -> SiteFrame:
    raw = json.loads(path.read_text(encoding="utf-8"))
    features = _features(raw)
    if not features:
        raise RuntimeError(f"GeoJSON ei sisällä kohteita: {path}")

    buildings = [f for f in features if _looks_like_building(f)]
    plots = [f for f in features if _looks_like_plot(f)]
    building = buildings[0] if buildings else features[0]
    plot = plots[0] if plots else None
    if plot is building:
        plot = None

    geom = shape(building["geometry"])
    c = geom.centroid
    return SiteFrame(
        crs="EPSG:3067",
        source_name=f"Paikallinen GeoJSON ({path.name})",
        source_url=None,
        verified=False,
        building=building,
        plot=plot,
        address_query=address,
        matched_address=None,
        easting=float(c.x),
        northing=float(c.y),
        feature_id=str(building.get("id") or ""),
        warnings=[
            "Paikallinen GeoJSON. Metrit tulevat tiedoston geometriasta. "
            "Merkitse luotettavaksi vasta kun tiedosto on virallinen WFS-ote EPSG:3067-koordinaateissa."
        ],
    )


def _features(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if raw.get("type") == "FeatureCollection":
        return list(raw.get("features") or [])
    if raw.get("type") == "Feature":
        return [raw]
    if raw.get("type") in {"Polygon", "MultiPolygon"}:
        return [{"type": "Feature", "properties": {}, "geometry": raw}]
    return []


def _looks_like_plot(feat: dict[str, Any]) -> bool:
    props = feat.get("properties") or {}
    blob = " ".join(str(k) for k in props) + " " + " ".join(str(v) for v in props.values())
    keys = blob.lower()
    return any(s in keys for s in ("kiinteist", "tontti", "plot", "parcel"))


def _looks_like_building(feat: dict[str, Any]) -> bool:
    props = feat.get("properties") or {}
    blob = " ".join(str(k) for k in props) + " " + " ".join(str(v) for v in props.values())
    keys = blob.lower()
    return any(s in keys for s in ("rakenn", "building", "ratu", "vtj_prt"))
