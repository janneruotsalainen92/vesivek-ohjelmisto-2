from __future__ import annotations

from functools import lru_cache

from pyproj import CRS, Transformer

from vesivek import CRS_TM35FIN

WGS84 = "EPSG:4326"


@lru_cache(maxsize=4)
def _to_3067() -> Transformer:
    return Transformer.from_crs(CRS.from_user_input(WGS84), CRS.from_user_input(CRS_TM35FIN), always_xy=True)


@lru_cache(maxsize=4)
def _to_wgs84() -> Transformer:
    return Transformer.from_crs(CRS.from_user_input(CRS_TM35FIN), CRS.from_user_input(WGS84), always_xy=True)


def wgs84_to_3067(lon: float, lat: float) -> tuple[float, float]:
    easting, northing = _to_3067().transform(lon, lat)
    return float(easting), float(northing)


def tm35_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    lon, lat = _to_wgs84().transform(easting, northing)
    return float(lon), float(lat)
