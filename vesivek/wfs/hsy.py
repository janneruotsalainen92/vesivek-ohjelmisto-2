from __future__ import annotations

from typing import Any

from shapely.geometry import Point, shape

from vesivek.config import HSY_BBOX_3067, HSY_WFS
from vesivek.models import SiteFrame
from vesivek.wfs.http import request_url, wfs_get


def _in_hsy_window(easting: float, northing: float) -> bool:
    min_e, min_n, max_e, max_n = HSY_BBOX_3067
    return min_e <= easting <= max_e and min_n <= northing <= max_n


class HsyWfsFetcher:
    name = "HSY avoin WFS (kartta.hsy.fi, pks_rakennukset_paivittyva)"

    def fetch_site(self, easting: float, northing: float, address: str) -> SiteFrame | None:
        if not _in_hsy_window(easting, northing):
            return None

        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": "pks_rakennukset_paivittyva",
            "outputFormat": "application/json",
            "srsName": "EPSG:3067",
            "maxFeatures": "20",
            "CQL_FILTER": f"DWITHIN(geom,SRID=3067;POINT({easting:.3f} {northing:.3f}),50,meters)",
        }
        try:
            data = wfs_get(HSY_WFS, params)
        except RuntimeError:
            return None

        features = data.get("features") or []
        if not features:
            return None

        building = _pick_closest(features, easting, northing)
        props = building.get("properties") or {}
        matched = _format_hsy_address(props)
        return SiteFrame(
            crs="EPSG:3067",
            source_name=self.name,
            source_url=request_url(HSY_WFS, params),
            verified=True,
            building=building,
            plot=None,
            address_query=address,
            matched_address=matched,
            easting=easting,
            northing=northing,
            feature_id=str(building.get("id") or props.get("vtj_prt") or ""),
            warnings=["HSY-aineistossa ei haeta tonttia; runko on rakennuksen WFS-geometria."],
        )


def _format_hsy_address(props: dict[str, Any]) -> str | None:
    street = props.get("katu")
    num = props.get("osno1")
    extra = props.get("oski1") or ""
    if street and num:
        return f"{street} {num}{extra}".strip()
    return street


def _pick_closest(features: list[dict[str, Any]], easting: float, northing: float) -> dict[str, Any]:
    pt = Point(easting, northing)
    return min(features, key=lambda f: shape(f["geometry"]).distance(pt))
