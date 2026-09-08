from __future__ import annotations

from typing import Any

from shapely.geometry import Point, shape

from vesivek.config import VANTAA_BBOX_3067, VANTAA_WFS
from vesivek.models import SiteFrame
from vesivek.wfs.http import request_url, wfs_get


def _in_vantaa_window(easting: float, northing: float) -> bool:
    min_e, min_n, max_e, max_n = VANTAA_BBOX_3067
    return min_e <= easting <= max_e and min_n <= northing <= max_n


class VantaaWfsFetcher:
    """Vantaa open WFS — buildings (fallback) + kiinteistö plot polygons."""

    name = "Vantaan avoin WFS (gis.vantaa.fi, kiinteisto + rakennukset)"

    def fetch_site(self, easting: float, northing: float, address: str) -> SiteFrame | None:
        if not _in_vantaa_window(easting, northing):
            return None

        bldg_params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": "gis:rakennukset",
            "outputFormat": "application/json",
            "srsName": "EPSG:3067",
            "maxFeatures": "20",
            "CQL_FILTER": f"DWITHIN(geom,SRID=3067;POINT({easting:.3f} {northing:.3f}),50,meters)",
        }
        try:
            data = wfs_get(VANTAA_WFS, bldg_params)
        except RuntimeError:
            return None
        features = data.get("features") or []
        if not features:
            return None
        building = min(features, key=lambda f: shape(f["geometry"]).distance(Point(easting, northing)))
        props = building.get("properties") or {}
        plot = fetch_vantaa_plot(easting, northing)
        warnings = []
        if plot is None:
            warnings.append("Vantaan kiinteistöä ei saatu; runko on rakennuksen geometria.")
        return SiteFrame(
            crs="EPSG:3067",
            source_name=self.name,
            source_url=request_url(VANTAA_WFS, bldg_params),
            verified=True,
            building=building,
            plot=plot,
            address_query=address,
            matched_address=str(props.get("osoite") or props.get("katunimi") or address),
            easting=easting,
            northing=northing,
            feature_id=str(building.get("id") or ""),
            warnings=warnings,
            plot_source="Vantaa WFS kiinteisto:kiinteisto" if plot else None,
        )


def fetch_vantaa_plot(easting: float, northing: float) -> dict[str, Any] | None:
    if not _in_vantaa_window(easting, northing):
        return None
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "kiinteisto:kiinteisto",
        "outputFormat": "application/json",
        "srsName": "EPSG:3067",
        "maxFeatures": "5",
        "CQL_FILTER": f"INTERSECTS(geom,SRID=3067;POINT({easting:.3f} {northing:.3f}))",
    }
    try:
        data = wfs_get(VANTAA_WFS, params)
    except RuntimeError:
        return None
    feats = data.get("features") or []
    if not feats:
        return None
    pt = Point(easting, northing)
    plot = min(feats, key=lambda f: 0 if shape(f["geometry"]).contains(pt) else shape(f["geometry"]).distance(pt))
    return plot
