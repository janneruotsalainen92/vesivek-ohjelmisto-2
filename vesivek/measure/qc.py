from __future__ import annotations

from shapely.geometry import LineString, shape

from vesivek.measure.kaista import SEARCH_M, _clean
from vesivek.models import Facade, QcTick
from vesivek.valokuva import SKIP_TICK_CLASSES, WORK_SURFACE_TICK_CLASSES, assert_unique_mv_ids, mv_work_prefix


def build_mittaviivat(
    facade: Facade,
    strip,
    *,
    spacing_m: float = 1.0,
    work_edges: list | None = None,
) -> list[QcTick]:
    """
    Valokuva mittaviivat (QC layer; final presentation may hide ticks):

    1. Buildings: MV-### wall→boundary + ~1 m ticks, snapped to WFS facade
    2. Work surfaces: short wall↔edge with MV-ASF-*, MV-LAATTA-*, MV-TERASSI-*,
       MV-KATOS-*, MV-SEINA-*, MV-SEPELI-*, MV-RAJA-*, MV-PAATY-*
    3. No ticks on grass / single bush / occlusion fills
    """
    if strip is None:
        return []
    if isinstance(strip, dict):
        strip = shape(strip)
    strip = _clean(strip)
    if strip is None:
        return []

    ticks: list[QcTick] = []
    n_bldg = 1
    work_counters: dict[str, int] = {k: 1 for k in WORK_SURFACE_TICK_CLASSES}

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
            ex, ey = float(end[0]), float(end[1])
            length = float(LineString([(px, py), (ex, ey)]).length)
            if length < 0.05:
                continue
            kind = "seina-raja" if i % 5 == 0 else "tikku-1m"
            ticks.append(
                QcTick(
                    id=f"MV-{n_bldg:03d}",
                    kind=kind,
                    start=(float(px), float(py)),
                    end=(ex, ey),
                    length_m=round(length, 3),
                    huomio="seinä → kaistan ulkoreuna (taso 1, WFS-snap)" if kind == "seina-raja" else "1 m -tikku seinältä rajalle (taso 1)",
                    tyyppi="rakennus",
                    tier=1,
                )
            )
            n_bldg += 1

            if i % 5 != 0:
                continue
            for item in work_edges or []:
                if len(item) == 3:
                    tyyppi, _d0, d1 = item
                elif len(item) == 2:
                    tyyppi, d1 = item
                else:
                    continue
                if tyyppi in SKIP_TICK_CLASSES:
                    continue
                prefix = mv_work_prefix(tyyppi)
                if not prefix:
                    continue
                short = float(d1)
                if short < 0.12 or short > length + 0.05:
                    short = min(short, length)
                if short < 0.12:
                    continue
                idx = work_counters[tyyppi]
                work_counters[tyyppi] = idx + 1
                sx = px + nx * short
                sy = py + ny * short
                ticks.append(
                    QcTick(
                        id=f"{prefix}-{idx:03d}",
                        kind="tyokaista",
                        start=(float(px), float(py)),
                        end=(float(sx), float(sy)),
                        length_m=round(short, 3),
                        huomio=f"työkaista {tyyppi} seinä↔reuna (taso 2, WFS-snap)",
                        tyyppi=tyyppi,
                        tier=2,
                    )
                )

    assert_unique_mv_ids([t.id for t in ticks])
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
                    "tier": t.tier,
                    "tyyppi": t.tyyppi,
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
    flat: list[tuple[float, float]] = []
    for p in coords:
        try:
            flat.append((float(p[0]), float(p[1])))
        except (TypeError, IndexError, ValueError):
            continue
    if not flat:
        return None
    return max(flat, key=lambda p: (p[0] - origin[0]) ** 2 + (p[1] - origin[1]) ** 2)
