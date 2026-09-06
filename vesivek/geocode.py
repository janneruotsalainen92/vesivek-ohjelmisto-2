from __future__ import annotations

from dataclasses import dataclass

import requests

from vesivek.config import HTTP_TIMEOUT_S, NOMINATIM_URL, USER_AGENT
from vesivek.crs import wgs84_to_3067


@dataclass
class GeocodeHit:
    query: str
    display_name: str
    lon: float
    lat: float
    easting: float
    northing: float
    source: str


def geocode_address(address: str) -> GeocodeHit:
    """Geocode a Finnish street address. Does not invent coordinates."""
    q = (address or "").strip()
    if not q:
        raise ValueError("Osoite puuttuu.")

    params = {
        "q": q,
        "format": "json",
        "limit": 1,
        "countrycodes": "fi",
        "addressdetails": 1,
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=HTTP_TIMEOUT_S)
        resp.raise_for_status()
        rows = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            "Osoitetta ei voitu geokoodata (Nominatim ei vastannut). "
            "Anna toimiva verkko tai käytä --wfs stub / --geojson."
        ) from exc

    if not rows:
        raise RuntimeError(
            f"Osoitetta ei löytynyt: {q!r}. Metrejä ei keksitä. "
            "Tarkista kirjoitusasu tai käytä --wfs stub vain esimerkkigeometriaan."
        )

    row = rows[0]
    lon = float(row["lon"])
    lat = float(row["lat"])
    easting, northing = wgs84_to_3067(lon, lat)
    return GeocodeHit(
        query=q,
        display_name=str(row.get("display_name") or q),
        lon=lon,
        lat=lat,
        easting=easting,
        northing=northing,
        source="Nominatim (OpenStreetMap), muunnettu EPSG:3067",
    )
