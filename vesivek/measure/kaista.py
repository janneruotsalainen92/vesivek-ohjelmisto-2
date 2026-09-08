from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from vesivek.models import Facade, SiteFrame, StripInfo
from vesivek.valokuva import dual_source_verdict


SEARCH_M = 40.0


@dataclass
class OffsetBand:
    tyyppi: str
    d0: float
    d1: float
    geometry: Any


def facade_lines(facade: Facade) -> list[LineString]:
    return [LineString([e.start, e.end]) for e in facade.edges]


def offset_polygon(facade: Facade, width_m: float):
    """Closed polygon of the outward offset of every facade edge."""
    if width_m <= 0:
        return None
    parts = []
    for edge in facade.edges:
        nx, ny = edge.outward
        p0, p1 = edge.start, edge.end
        ring = [
            p0,
            p1,
            (p1[0] + nx * width_m, p1[1] + ny * width_m),
            (p0[0] + nx * width_m, p0[1] + ny * width_m),
            p0,
        ]
        from shapely.geometry import Polygon

        poly = Polygon(ring)
        if not poly.is_valid:
            poly = make_valid(poly)
        if not poly.is_empty:
            parts.append(poly)
    if not parts:
        return None
    merged = unary_union(parts)
    return merged if not merged.is_empty else None


def building_shape(site: SiteFrame):
    return make_valid(shape(site.building["geometry"]))


def plot_shape(site: SiteFrame):
    if not site.plot or not site.plot.get("geometry"):
        return None
    return make_valid(shape(site.plot["geometry"]))


def build_strip(
    site: SiteFrame,
    facade: Facade,
    *,
    width_m: float | None,
    width_source: str,
) -> StripInfo:
    """
    Digitize the kaista outward from the WFS facade (EPSG:3067 snap):

    - plot/tontti edge when a plot polygon is available (geometric, not invented)
    - buffer of ``width_m`` (--kaistan-leveys or mittatikku)
    - dual ±10 %: if both exist, report A/B and never average
    - otherwise no area geometry (EI LASKETTU)
    """
    building = building_shape(site)
    plot = plot_shape(site)

    plot_geom = None
    plot_area = None
    if plot is not None:
        raw = offset_polygon(facade, SEARCH_M)
        if raw is not None:
            yard = plot.difference(building)
            plot_geom = _clean(raw.intersection(yard))
            if plot_geom is not None:
                plot_area = float(plot_geom.area)

    buf_geom = None
    buf_area = None
    if width_m and width_m > 0:
        raw = offset_polygon(facade, width_m)
        if raw is not None:
            buf = raw.difference(building)
            if plot is not None:
                buf = buf.intersection(plot)
            buf_geom = _clean(buf)
            if buf_geom is not None:
                buf_area = float(buf_geom.area)

    dual = dual_source_verdict(plot_area, buf_area)

    # Draw the WFS-snapped plot strip when present; else the measured buffer.
    # Dual disagree → still draw plot (A) and keep B as a number only.
    if plot_geom is not None:
        strip = plot_geom
        clip = "tontti"
        src = "tontti"
        drawn_width = None
        note_core = (
            f"Kaista = WFS-julkisivu → tontin reuna (EPSG:3067). "
            f"Pinta-ala A={plot_area:.2f} m² geometriasta."
        )
        if width_m:
            clip = "tontti+puskuri"
            src = width_source if width_source not in {"puuttuu", "tontti"} else "tontti"
            drawn_width = float(width_m)
            note_core += f" Puskuri B={buf_area:.2f} m² ({width_source})." if buf_area else ""
        mean_w, max_w = _widths(facade, strip)
        if drawn_width is None:
            drawn_width = mean_w
        return StripInfo(
            geometry=mapping(strip),
            width_m=drawn_width,
            width_source=src,
            mean_width_m=mean_w,
            max_width_m=max_w,
            clip=clip,
            area_m2=round(plot_area, 3) if dual.status != "disagree" else round(plot_area, 3),
            huomio=note_core + " " + dual.note,
            area_m2_plot=round(plot_area, 3) if plot_area else None,
            area_m2_buffer=round(buf_area, 3) if buf_area else None,
            dual_status=dual.status,
            dual_note=dual.note,
        )

    if buf_geom is not None and width_m:
        mean_w, max_w = _widths(facade, buf_geom)
        return StripInfo(
            geometry=mapping(buf_geom),
            width_m=float(width_m),
            width_source=width_source,
            mean_width_m=mean_w,
            max_width_m=max_w,
            clip="puskuri",
            area_m2=round(buf_area, 3) if buf_area else None,
            huomio=(
                f"Kaista = WFS-julkisivun puskuri {width_m:.2f} m ({width_source}), "
                f"pinta-ala {buf_area:.2f} m². {dual.note}"
            ),
            area_m2_plot=None,
            area_m2_buffer=round(buf_area, 3) if buf_area else None,
            dual_status=dual.status,
            dual_note=dual.note,
        )

    return _empty(
        "Kaistan leveyttä ei ole: ei tontin reunaa eikä --kaistan-leveys / mittatikkua. "
        "m² merkitään EI LASKETTU."
    )


def split_width_bands(
    facade: Facade,
    strip,
    shares: list[tuple[str, float]],
    max_width_m: float,
) -> list[OffsetBand]:
    """Split the strip into wall→edge bands (perpendicular), not along-wall pies."""
    if strip is None or not shares or max_width_m <= 0:
        return []
    from shapely.geometry import shape as shp_shape

    if isinstance(strip, dict):
        strip = shp_shape(strip)
    strip = _clean(strip)
    if strip is None:
        return []

    total = sum(s for _, s in shares) or 1.0
    bands: list[OffsetBand] = []
    d0 = 0.0
    n = len(shares)
    for i, (tyyppi, share) in enumerate(shares):
        frac = share / total
        if i == n - 1:
            d1 = max_width_m + 0.05
        else:
            d1 = d0 + max_width_m * frac
        outer = offset_polygon(facade, d1)
        if outer is None:
            continue
        if d0 > 1e-6:
            inner = offset_polygon(facade, d0)
            band = outer.difference(inner) if inner is not None else outer
        else:
            band = outer
        geom = _clean(band.intersection(strip))
        if geom is not None and geom.area > 1e-4:
            bands.append(OffsetBand(tyyppi=tyyppi, d0=d0, d1=min(d1, max_width_m), geometry=geom))
        d0 = d1
    return bands


def along_wall_slice(facade: Facade, strip, t0: float, t1: float, width_m: float | None):
    """Optional end-slab (päätylaatta): slice of the strip along the wall, t in [0,1]."""
    from shapely.geometry import Polygon, shape as shp_shape

    if t1 <= t0:
        return None
    if isinstance(strip, dict):
        strip = shp_shape(strip)
    total = facade.length_m or 1.0
    acc = 0.0
    parts = []
    w = width_m or SEARCH_M
    for edge in facade.edges:
        a0 = acc / total
        a1 = (acc + edge.length_m) / total
        acc += edge.length_m
        lo = max(t0, a0)
        hi = min(t1, a1)
        if hi - lo <= 1e-6:
            continue
        u0 = (lo - a0) / max(a1 - a0, 1e-9)
        u1 = (hi - a0) / max(a1 - a0, 1e-9)
        p0 = _lerp(edge.start, edge.end, u0)
        p1 = _lerp(edge.start, edge.end, u1)
        nx, ny = edge.outward
        ring = [
            p0,
            p1,
            (p1[0] + nx * w, p1[1] + ny * w),
            (p0[0] + nx * w, p0[1] + ny * w),
            p0,
        ]
        parts.append(Polygon(ring))
    if not parts:
        return None
    raw = unary_union(parts)
    if strip is not None:
        raw = raw.intersection(strip)
    return _clean(raw)


def geom_to_geojson(geom) -> dict[str, Any] | None:
    if geom is None or geom.is_empty:
        return None
    return mapping(geom)


def _widths(facade: Facade, strip) -> tuple[float, float]:
    samples: list[float] = []
    for edge in facade.edges:
        n = max(8, int(edge.length_m) + 1)
        for i in range(n + 1):
            t = i / n
            px = edge.start[0] + (edge.end[0] - edge.start[0]) * t
            py = edge.start[1] + (edge.end[1] - edge.start[1]) * t
            nx, ny = edge.outward
            ray = LineString([(px, py), (px + nx * SEARCH_M, py + ny * SEARCH_M)])
            inter = ray.intersection(strip)
            if inter.is_empty:
                continue
            samples.append(float(inter.length))
    if not samples:
        area = float(strip.area)
        mean = area / max(facade.length_m, 1e-6)
        return mean, mean
    return sum(samples) / len(samples), max(samples)


def _clean(geom):
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom.is_empty:
        return None
    if geom.geom_type == "GeometryCollection":
        polys = [g for g in geom.geoms if g.geom_type in {"Polygon", "MultiPolygon"} and not g.is_empty]
        if not polys:
            return None
        geom = unary_union(polys)
    return geom if not geom.is_empty else None


def _empty(note: str) -> StripInfo:
    return StripInfo(
        geometry=None,
        width_m=None,
        width_source="puuttuu",
        mean_width_m=None,
        max_width_m=None,
        clip="puuttuu",
        area_m2=None,
        huomio=note,
    )


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
