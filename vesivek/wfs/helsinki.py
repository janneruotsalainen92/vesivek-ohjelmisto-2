from __future__ import annotations

from typing import Any
from shapely.geometry import Point, shape

from vesivek.config import HELSINKI_BBOX_3067, HELSINKI_WFS
from vesivek.models import SiteFrame
from vesivek.wfs.http import request_url, wfs_get


def _in_helsinki_window(easting: float, northing: float) -> bool:
    min_e, min_n, max_e, max_n = HELSINKI_BBOX_3067
    return min_e <= easting <= max_e and min_n <= northing <= max_n


def _cql_dwithin(easting: float, northing: float, metres: float) -> str:
    return f"DWITHIN(geom,SRID=3067;POINT({easting:.3f} {northing:.3f}),{metres:.1f},meters)"


def _cql_intersects(easting: float, northing: float) -> str:
    return f"INTERSECTS(geom,SRID=3067;POINT({easting:.3f} {northing:.3f}))"


class HelsinkiWfsFetcher:
    name = "Helsingin avoin WFS (kartta.hel.fi)"

    def fetch_site(self, easting: float, northing: float, address: str) -> SiteFrame | None:
        addr_l = (address or "").lower()
        if "vantaa" in addr_l and "helsinki" not in addr_l:
            return None
        if not _in_helsinki_window(easting, northing):
            return None

        bldg_params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": "avoindata:Rakennukset_alue",
            "outputFormat": "application/json",
            "srsName": "EPSG:3067",
            "maxFeatures": "20",
            "CQL_FILTER": _cql_dwithin(easting, northing, 50),
        }
        try:
            buildings = wfs_get(HELSINKI_WFS, bldg_params)
        except RuntimeError:
            return None

        features = buildings.get("features") or []
        if not features:
            return None

        building = _pick_building(features, easting, northing, address)
        props = building.get("properties") or {}
        matched = _format_hel_address(props)

        plot_feature = None
        plot_params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": "avoindata:Kiinteisto_alue",
            "outputFormat": "application/json",
            "srsName": "EPSG:3067",
            "maxFeatures": "3",
            "CQL_FILTER": _cql_intersects(easting, northing),
        }
        try:
            plots = wfs_get(HELSINKI_WFS, plot_params)
            plot_feats = plots.get("features") or []
            if plot_feats:
                plot_feature = plot_feats[0]
        except RuntimeError:
            plot_feature = None

        warnings: list[str] = []
        if plot_feature is None:
            warnings.append("Tonttia (Kiinteisto_alue) ei saatu; runko on rakennuksen WFS-geometria.")

        return SiteFrame(
            crs="EPSG:3067",
            source_name=self.name,
            source_url=request_url(HELSINKI_WFS, bldg_params),
            verified=True,
            building=building,
            plot=plot_feature,
            address_query=address,
            matched_address=matched,
            easting=easting,
            northing=northing,
            feature_id=str(building.get("id") or props.get("id") or ""),
            warnings=warnings,
        )


def _format_hel_address(props: dict[str, Any]) -> str | None:
    street = props.get("katunimi_suomi")
    num = props.get("osoitenumero")
    if street and num:
        return f"{street} {num}, Helsinki"
    if street:
        return f"{street}, Helsinki"
    return None


def _pick_building(features: list[dict[str, Any]], easting: float, northing: float, address: str) -> dict[str, Any]:
    pt = Point(easting, northing)
    needle = (address or "").lower()

    def score(feat: dict[str, Any]) -> tuple[int, float]:
        geom = shape(feat["geometry"])
        dist = geom.distance(pt)
        props = feat.get("properties") or {}
        text = " ".join(
            str(props.get(k) or "")
            for k in ("katunimi_suomi", "osoitenumero", "tyyppi")
        ).lower()
        match = 1 if street_tokens(needle) and all(t in text for t in street_tokens(needle) if t.isdigit() or len(t) > 3) else 0
        # Prefer residential if several are equally close.
        typ = str(props.get("tyyppi") or "")
        resid = 1 if "Asuin" in typ else 0
        return (match, resid, -dist)

    return max(features, key=score)


def street_tokens(text: str) -> list[str]:
    raw = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return [t for t in raw.split() if t not in {"helsinki", "finland", "suomi", "the"}]
