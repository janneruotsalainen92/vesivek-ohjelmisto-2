from __future__ import annotations

from shapely.geometry import LineString, shape

from vesivek.measure.kaista import SEARCH_M, _clean
from vesivek.models import Facade, QcTick


def build_mittaviivat(
    facade: Facade,
    strip,
    *,
    spacing_m: float = 1.0,
    work_band_m: float | None = None,
) -> list[QcTick]:
    """
    Optional QC ticks with unique MV-* ids:
    - wall → strip boundary, ~1 m along the facade
    - short wall ↔ work-surface ticks (seinänvierus / first metres)
    """
    if strip is None:
        return []
    if isinstance(strip, dict):
        strip = shape(strip)
    strip = _clean(strip)
    if strip is None:
        return []

    ticks: list[QcTick] = []
    n = 1
    for edge in facade.edges:
        steps = max(1, int(round(edge.length_m / max(spacing_m, 0.2))))
        for i in range(steps + 1):
            t = i / steps
            px = edge.start[0] + (edge.end[0] - edge.start[0]) * t
            py = edge.start[1] + (edge.end[1] - edge.start[1]) * t
            nx, ny = edge.outward
            ray = LineString([(px, py), (px + nx * SEARCH_M, py + ny * SEARCH_M)])
            inter = ray.intersection(strip)
            if inter.is_empty:
                continue
            end = _far(inter, (px, py))
            if end is None:
                continue
            length = float(LineString([(px, py), end]).length)
            if length < 0.05:
                continue
            ticks.append(
                QcTick(
                    id=f"MV-{n:03d}",
                    kind="seina-raja" if i % 5 == 0 else "tikku-1m",
                    start=(px, py),
                    end=end,
                    length_m=round(length, 3),
                    huomio="seinä → kaistan ulkoreuna" if i % 5 == 0 else "1 m -kokeilu seinältä rajalle",
                )
            )
            n += 1
            short_w = work_band_m if work_band_m and work_band_m > 0 else min(1.2, length * 0.2)
            if short_w > 0.15 and i % 5 == 0:
                sx = px + nx * short_w
                sy = py + ny * short_w
                ticks.append(
                    QcTick(
                        id=f"MV-{n:03d}",
                        kind="pinta",
                        start=(px, py),
                        end=(sx, sy),
                        length_m=round(short_w, 3),
                        huomio="lyhyt seinä↔pintareuna (työkaista)",
                    )
                )
                n += 1
    return ticks


def ticks_geojson(ticks: list[QcTick]) -> list[dict]:
    feats = []
    for t in ticks:
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "rooli": "mittaviiva",
                    "id": t.id,
                    "kind": t.kind,
                    "pituus_m": t.length_m,
                    "huomio": t.huomio,
                    "crs": "EPSG:3067",
                },
                "geometry": {"type": "LineString", "coordinates": [list(t.start), list(t.end)]},
            }
        )
    return feats


def _far(inter, origin: tuple[float, float]) -> tuple[float, float] | None:
    if inter.geom_type == "Point":
        return (float(inter.x), float(inter.y))
    if inter.geom_type == "LineString":
        coords = list(inter.coords)
    elif inter.geom_type == "MultiLineString":
        coords = [c for g in inter.geoms for c in g.coords]
    elif inter.geom_type == "GeometryCollection":
        coords = []
        for g in inter.geoms:
            if g.geom_type == "LineString":
                coords.extend(g.coords)
            elif g.geom_type == "Point":
                coords.append((g.x, g.y))
    else:
        return None
    if not coords:
        return None
    return max(coords, key=lambda p: (p[0] - origin[0]) ** 2 + (p[1] - origin[1]) ** 2)
