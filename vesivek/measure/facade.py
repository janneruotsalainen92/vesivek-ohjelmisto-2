from __future__ import annotations

import math
from typing import Any

from shapely.geometry import MultiPolygon, Polygon, shape

from vesivek.models import Edge, Facade, SiteFrame

COMPASS_FI = {
    "pohjoinen": "Pohjoinen julkisivu",
    "ita": "Itäinen julkisivu",
    "etela": "Eteläinen julkisivu",
    "lansi": "Läntinen julkisivu",
}

ALIASES = {
    "n": "pohjoinen",
    "north": "pohjoinen",
    "pohjoinen": "pohjoinen",
    "pohjois": "pohjoinen",
    "e": "ita",
    "east": "ita",
    "ita": "ita",
    "itä": "ita",
    "s": "etela",
    "south": "etela",
    "etela": "etela",
    "etelä": "etela",
    "w": "lansi",
    "west": "lansi",
    "lansi": "lansi",
    "länsi": "lansi",
}


def building_polygon(site: SiteFrame) -> Polygon:
    geom = shape(site.building["geometry"])
    if isinstance(geom, MultiPolygon):
        return max(geom.geoms, key=lambda g: g.area)
    if not isinstance(geom, Polygon):
        raise RuntimeError(f"Rakennuksen geometria ei ole alue: {geom.geom_type}")
    return geom


def extract_edges(site: SiteFrame) -> list[Edge]:
    poly = building_polygon(site)
    coords = list(poly.exterior.coords)
    edges: list[Edge] = []
    for i, (a, b) in enumerate(zip(coords, coords[1:])):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 0.05:
            continue
        # Exterior is CCW in valid polygons: interior left, outward right.
        nx, ny = dy / length, -dx / length
        edges.append(
            Edge(
                start=(float(a[0]), float(a[1])),
                end=(float(b[0]), float(b[1])),
                length_m=length,
                outward=(nx, ny),
                compass=_compass(nx, ny),
                index=i,
            )
        )
    if not edges:
        raise RuntimeError("Rakennuksesta ei saatu julkisivusärmiä.")
    return edges


def list_facades(site: SiteFrame) -> list[Facade]:
    edges = extract_edges(site)
    by_dir: dict[str, list[Edge]] = {k: [] for k in COMPASS_FI}
    for edge in edges:
        by_dir[edge.compass].append(edge)

    facades: list[Facade] = []
    for compass, group in by_dir.items():
        if not group:
            continue
        facades.append(
            Facade(
                key=compass,
                label_fi=COMPASS_FI[compass],
                compass=compass,
                length_m=sum(e.length_m for e in group),
                edges=group,
                verified=site.verified,
                source=site.source_name,
            )
        )
    facades.sort(key=lambda f: -f.length_m)

    for edge in edges:
        facades.append(
            Facade(
                key=f"reuna-{edge.index}",
                label_fi=f"Yksittäinen reuna {edge.index} ({COMPASS_FI[edge.compass]}, {edge.length_m:.2f} m)",
                compass=edge.compass,
                length_m=edge.length_m,
                edges=[edge],
                verified=site.verified,
                source=site.source_name,
            )
        )
    return facades


def choose_facade(site: SiteFrame, choice: str | None) -> Facade:
    facades = list_facades(site)
    if not facades:
        raise RuntimeError("Julkisivua ei voitu muodostaa WFS-geometriasta.")

    if not choice or choice.strip().lower() in {"auto", ""}:
        compass_only = [f for f in facades if f.key in COMPASS_FI]
        return max(compass_only or facades, key=lambda f: f.length_m)

    key = _normalize_choice(choice)
    for facade in facades:
        if facade.key == key:
            return facade
    known = ", ".join(sorted({f.key for f in facades if f.key in COMPASS_FI}))
    raise RuntimeError(f"Tuntematon julkisivu {choice!r}. Vaihtoehdot: {known} tai reuna-N.")


def _normalize_choice(choice: str) -> str:
    raw = choice.strip().lower().replace("ä", "a").replace("ö", "o")
    if raw in ALIASES:
        return ALIASES[raw]
    if raw.startswith("reuna-") or raw.startswith("reuna"):
        num = "".join(ch for ch in raw if ch.isdigit())
        return f"reuna-{num}" if num else raw
    return raw


def _compass(nx: float, ny: float) -> str:
    ang = math.degrees(math.atan2(nx, ny)) % 360.0
    if ang < 45 or ang >= 315:
        return "pohjoinen"
    if 45 <= ang < 135:
        return "ita"
    if 135 <= ang < 225:
        return "etela"
    return "lansi"


def facade_as_geojson(facade: Facade) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "julkisivu": facade.label_fi,
            "pituus_m": round(facade.length_m, 3),
            "luotettavuus": "wfs" if facade.verified else "esimerkki",
            "lahde": facade.source,
            "crs": "EPSG:3067",
        },
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [[list(e.start), list(e.end)] for e in facade.edges],
        },
    }
