from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vesivek.models import MeasurementResult


def write_geojson(result: MeasurementResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    features: list[dict[str, Any]] = []

    building = dict(result.site.building)
    bprops = dict(building.get("properties") or {})
    bprops.update(
        {
            "rooli": "rakennus",
            "crs": "EPSG:3067",
            "wfs_lukittu": result.site.verified,
            "lahde": result.site.source_name,
        }
    )
    building["properties"] = bprops
    features.append(building)

    if result.site.plot:
        plot = dict(result.site.plot)
        pprops = dict(plot.get("properties") or {})
        pprops.update({"rooli": "tontti", "crs": "EPSG:3067", "wfs_lukittu": result.site.verified})
        plot["properties"] = pprops
        features.append(plot)

    features.append(
        {
            "type": "Feature",
            "properties": {
                "rooli": "julkisivu",
                "julkisivu": result.facade.label_fi,
                "pituus_m": result.facade.length_m,
                "luotettavuus": "wfs" if result.facade.verified else "esimerkki",
                "crs": "EPSG:3067",
            },
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [[list(e.start), list(e.end)] for e in result.facade.edges],
            },
        }
    )

    for rec in result.surfaces:
        if not rec.geometry:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "rooli": "pinta",
                    "tyyppi": rec.tyyppi,
                    "nimike": rec.label_fi,
                    "kind": rec.kind,
                    "arvo": rec.value,
                    "yksikko": rec.unit,
                    "luotettavuus": rec.luotettavuus,
                    "lahde": rec.lahde,
                    "huomio": rec.huomio,
                    "crs": "EPSG:3067",
                },
                "geometry": rec.geometry,
            }
        )

    fc = {
        "type": "FeatureCollection",
        "name": "vesivek_v1_julkisivukaista",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3067"}},
        "properties": {
            "osoite": result.site.address_query,
            "varoitus": "v1: ei putkia. Epävarmat pinta-alat merkitty luotettavuus-kenttään.",
        },
        "features": features,
    }
    path.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
