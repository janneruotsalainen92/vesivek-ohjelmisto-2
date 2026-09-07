from __future__ import annotations

from pathlib import Path

from shapely.geometry import shape

from vesivek.models import SiteFrame
from vesivek.wfs.helsinki import HelsinkiWfsFetcher
from vesivek.wfs.hsy import HsyWfsFetcher
from vesivek.wfs.local import load_local_geojson
from vesivek.wfs.stub import StubWfsFetcher
from vesivek.wfs.vantaa import VantaaWfsFetcher, fetch_vantaa_plot


def list_fetchers() -> list[str]:
    return [
        HelsinkiWfsFetcher.name,
        HsyWfsFetcher.name,
        VantaaWfsFetcher.name,
        StubWfsFetcher.name,
        "Paikallinen GeoJSON (--geojson)",
    ]


def fetch_site(
    *,
    easting: float,
    northing: float,
    address: str,
    mode: str = "auto",
    geojson_path: Path | None = None,
) -> SiteFrame:
    """
    mode:
      auto  — live Helsinki, then HSY (+ Vantaa plot), then Vantaa, then stub
      live  — live only, fail if nothing verified
      stub  — sample GeoJSON only
      file  — --geojson
    """
    if geojson_path is not None:
        return load_local_geojson(geojson_path, address)

    mode = (mode or "auto").lower()
    if mode == "stub":
        site = StubWfsFetcher().fetch_site(easting, northing, address)
        if site is None:
            raise RuntimeError("Esimerkkigeometriaa ei löytynyt (data/sample/*.geojson).")
        return site

    live = [HelsinkiWfsFetcher(), HsyWfsFetcher(), VantaaWfsFetcher()]
    errors: list[str] = []
    for fetcher in live:
        try:
            site = fetcher.fetch_site(easting, northing, address)
        except Exception as exc:  # noqa: BLE001 — fetcher must not abort the chain
            errors.append(f"{fetcher.name}: {exc}")
            continue
        if site is not None:
            return _enrich_plot(site)

    if mode == "live":
        detail = (" | ".join(errors)) if errors else "ei osumia 50 m säteellä"
        raise RuntimeError(
            "Live-WFS ei palauttanut rakennusta. Metrejä ei keksitä. "
            f"({detail}). Käytä --wfs stub, --geojson tai toista osoitetta."
        )

    site = StubWfsFetcher().fetch_site(easting, northing, address)
    if site is None:
        raise RuntimeError("WFS epäonnistui eikä esimerkkigeometriaa ole saatavilla.")
    site.warnings.insert(
        0,
        "Live-WFS ei tuottanut osumaa; siirryttiin esimerkkigeometriaan. "
        + (("Tekniset virheet: " + " | ".join(errors)) if errors else ""),
    )
    return site


def _enrich_plot(site: SiteFrame) -> SiteFrame:
    if site.plot is not None:
        return site
    geom = shape(site.building["geometry"])
    c = geom.centroid
    plot = fetch_vantaa_plot(float(c.x), float(c.y))
    if plot is None:
        return site
    site.plot = plot
    site.plot_source = "Vantaa WFS kiinteisto:kiinteisto"
    site.warnings.append("Tontti täydennetty Vantaan avoimesta kiinteistö-WFS:stä.")
    return site
