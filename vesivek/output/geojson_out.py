from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vesivek.measure.qc import ticks_geojson
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
        pprops.update(
            {
                "rooli": "tontti",
                "crs": "EPSG:3067",
                "wfs_lukittu": result.site.verified,
                "lahde": result.site.plot_source or result.site.source_name,
            }
        )
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

    if result.strip and result.strip.geometry:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "rooli": "kaista",
                    "clip": result.strip.clip,
                    "leveys_m": result.strip.width_m,
                    "leveys_lahde": result.strip.width_source,
                    "ala_m2": result.strip.area_m2,
                    "ala_m2_plot": result.strip.area_m2_plot,
                    "ala_m2_buffer": result.strip.area_m2_buffer,
                    "dual": result.strip.dual_status,
                    "huomio": result.strip.huomio,
                    "crs": "EPSG:3067",
                },
                "geometry": result.strip.geometry,
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
                    "pituus_m": rec.pituus_m,
                    "ala_m2": rec.ala_m2,
                    "yksikko": rec.unit,
                    "luotettavuus": rec.luotettavuus,
                    "lock_tila": rec.lock_tila,
                    "lahde": rec.lahde,
                    "peite": rec.peite,
                    "ala_m2_b": rec.ala_m2_b,
                    "huomio": rec.huomio,
                    "crs": "EPSG:3067",
                },
                "geometry": rec.geometry,
            }
        )

    features.extend(ticks_geojson(result.qc_ticks))

    fc = {
        "type": "FeatureCollection",
        "name": "vesivek_julkisivukaista",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3067"}},
        "properties": {
            "osoite": result.site.address_query,
            "varoitus": (
                "bot-kokeilu: ei putkia. m² vain kun leveys tunnetaan. "
                "Epävarmat / peitetyt pinta-alat merkitty luotettavuus-kenttään."
            ),
        },
        "features": features,
    }
    path.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
