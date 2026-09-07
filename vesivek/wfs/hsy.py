from __future__ import annotations

import re
from typing import Any

from shapely.geometry import Point, shape

from vesivek.config import HSY_BBOX_3067, HSY_WFS
from vesivek.models import SiteFrame
from vesivek.wfs.http import request_url, wfs_get


def _in_hsy_window(easting: float, northing: float) -> bool:
    min_e, min_n, max_e, max_n = HSY_BBOX_3067
    return min_e <= easting <= max_e and min_n <= northing <= max_n


def parse_street_number(address: str) -> tuple[str | None, int | None, str | None]:
    """'Mailatie 14, Vantaa' → ('Mailatie', 14, None). Does not invent a match."""
    main = (address or "").split(",")[0].strip()
    m = re.search(r"^(.*?)(\d+)\s*([a-zA-ZÄÖÅäöå])?$", main)
    if not m:
        return None, None, None
    street = m.group(1).strip()
    num = int(m.group(2))
    letter = (m.group(3) or "").strip() or None
    return street or None, num, letter


class HsyWfsFetcher:
    name = "HSY avoin WFS (kartta.hsy.fi, pks_rakennukset_paivittyva)"

    def fetch_site(self, easting: float, northing: float, address: str) -> SiteFrame | None:
        if not _in_hsy_window(easting, northing):
            return None

        street, num, _letter = parse_street_number(address)
        features: list[dict[str, Any]] = []
        used_params: dict[str, Any] | None = None

        if street and num is not None:
            params = _base_params()
            # Escape single quotes in CQL.
            safe = street.replace("'", "''")
            params["CQL_FILTER"] = f"katu='{safe}' AND osno1={num}"
            params["maxFeatures"] = "20"
            try:
                data = wfs_get(HSY_WFS, params)
                features = data.get("features") or []
                used_params = params
            except RuntimeError:
                features = []

        if not features:
            params = _base_params()
            params["CQL_FILTER"] = f"DWITHIN(geom,SRID=3067;POINT({easting:.3f} {northing:.3f}),80,meters)"
            try:
                data = wfs_get(HSY_WFS, params)
                features = data.get("features") or []
                used_params = params
            except RuntimeError:
                return None

        if not features:
            return None

        building = _pick_building(features, easting, northing, address)
        props = building.get("properties") or {}
        matched = _format_hsy_address(props)
        return SiteFrame(
            crs="EPSG:3067",
            source_name=self.name,
            source_url=request_url(HSY_WFS, used_params or params),
            verified=True,
            building=building,
            plot=None,
            address_query=address,
            matched_address=matched,
            easting=easting,
            northing=northing,
            feature_id=str(building.get("id") or props.get("vtj_prt") or ""),
            warnings=["HSY-aineistossa ei ole tonttia; tontti haetaan Vantaan/Helsingin WFS:stä jos mahdollista."],
        )


def _base_params() -> dict[str, Any]:
    return {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "pks_rakennukset_paivittyva",
        "outputFormat": "application/json",
        "srsName": "EPSG:3067",
        "maxFeatures": "20",
    }


def _format_hsy_address(props: dict[str, Any]) -> str | None:
    street = props.get("katu")
    num = props.get("osno1")
    extra = props.get("oski1") or ""
    if street and num:
        return f"{street} {num}{extra}".strip()
    return street


def _pick_building(features: list[dict[str, Any]], easting: float, northing: float, address: str) -> dict[str, Any]:
    pt = Point(easting, northing)
    street, num, _ = parse_street_number(address)
    street_l = (street or "").lower()

    def score(feat: dict[str, Any]) -> tuple:
        props = feat.get("properties") or {}
        katu = str(props.get("katu") or "").lower()
        osno = props.get("osno1")
        try:
            osno_i = int(float(osno)) if osno is not None else None
        except (TypeError, ValueError):
            osno_i = None
        addr_hit = 1 if street_l and street_l in katu and osno_i == num else 0
        dist = shape(feat["geometry"]).distance(pt)
        return (addr_hit, -dist)

    return max(features, key=score)
