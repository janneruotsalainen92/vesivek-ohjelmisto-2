from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon

from vesivek.measure.classify import SURFACE_LABELS, count_trees, merge_fractions
from vesivek.models import Facade, SiteFrame, StickResult, SurfaceRecord

LINEAR_TYPES = {"pensas"}
AREA_TYPES = {"asfaltti", "laatta", "sepeli", "nurmikko", "multa", "tuntematon"}


def load_surface_override(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("pinnat-tiedoston on oltava JSON-objekti.")
    return data


def measure_strip(
    *,
    site: SiteFrame,
    facade: Facade,
    fractions: dict[str, float],
    photo_confidence: float,
    stick: StickResult,
    strip_width_m: float | None,
    strip_width_source: str,
    override: dict[str, Any] | None,
    photo_count: int,
    photos_for_trees: list | None = None,
) -> tuple[list[SurfaceRecord], list[str]]:
    warnings: list[str] = []
    records: list[SurfaceRecord] = []

    length = facade.length_m
    records.append(
        SurfaceRecord(
            tyyppi="julkisivu_pituus",
            label_fi=f"Julkisivun pituus ({facade.label_fi})",
            kind="linear",
            value=round(length, 3),
            unit="m",
            luotettavuus="wfs" if facade.verified else "esimerkki",
            lahde=facade.source,
            huomio="Lukittu WFS-geometriaan EPSG:3067. Ei kuvista keksitty.",
            share=1.0,
            geometry=_line_geom(facade),
        )
    )

    shares = _shares_from_override_or_photos(override, fractions, warnings)
    width, width_src, width_note = _resolve_width(strip_width_m, strip_width_source, override, warnings)

    cursor = 0.0
    for tyyppi, share in shares:
        if share <= 0.005:
            continue
        linear = length * share
        label = SURFACE_LABELS.get(tyyppi, tyyppi)
        geom = _band_geom(facade, cursor, cursor + share, width) if width else None
        cursor += share

        if tyyppi in LINEAR_TYPES:
            records.append(
                SurfaceRecord(
                    tyyppi=tyyppi,
                    label_fi=label,
                    kind="linear",
                    value=round(linear, 3),
                    unit="m",
                    luotettavuus=_linear_reliability(site, photo_confidence, override),
                    lahde="käyttäjän pinnat.json" if override else "valokuvien osuus × WFS-pituus",
                    huomio=(
                        "Lineaarinen piirre julkisivun suuntaan. Pituus = WFS-särmä × osuus. "
                        "Sijainti kaistalla on arvio, ei rekisteröity paikkatieto."
                    ),
                    share=share,
                    geometry=geom,
                )
            )
            continue

        area = (linear * width) if width else None
        if area is None:
            huomio = (
                "Pinta-alaa ei lasketa: kaistan leveys on mittaamatta. "
                f"Lineaarinen osuus WFS-julkisivulla on {linear:.2f} m. "
                "Anna --kaistan-leveys tai mittatikku."
            )
            luot = "epavarma"
        else:
            huomio = (
                f"A = {linear:.2f} m (WFS) × {width:.2f} m ({width_src}). {width_note} "
                "Sijainti julkisivulla on osuuksien mukainen kaista, ei tarkka paikanmittaus."
            )
            luot = _area_reliability(site, width_src, photo_confidence, override)

        records.append(
            SurfaceRecord(
                tyyppi=tyyppi,
                label_fi=label,
                kind="area",
                value=None if area is None else round(area, 3),
                unit="m²",
                luotettavuus=luot,
                lahde="valokuvat + WFS-pituus" if not override else "pinnat.json + WFS-pituus",
                huomio=huomio,
                share=share,
                geometry=geom,
            )
        )

        if area is None:
            records.append(
                SurfaceRecord(
                    tyyppi=f"{tyyppi}_pituus",
                    label_fi=f"{label} (osuus julkisivulla)",
                    kind="linear",
                    value=round(linear, 3),
                    unit="m",
                    luotettavuus="arvio" if photo_count else "epavarma",
                    lahde="valokuvien osuus × WFS-pituus",
                    huomio="Pituus lukittu WFS-särmään; materiaali on kuvista arvioitu.",
                    share=share,
                    geometry=_line_geom(facade),
                )
            )

    if photos_for_trees:
        n, note = count_trees(photos_for_trees)
        if n is not None:
            records.append(
                SurfaceRecord(
                    tyyppi="puu",
                    label_fi="Puut (kpl)",
                    kind="count",
                    value=float(n),
                    unit="kpl",
                    luotettavuus="arvio",
                    lahde="valokuvat (heuristiikka)",
                    huomio=note,
                    share=0.0,
                    geometry=None,
                )
            )

    if not site.verified:
        warnings.append("Runko ei ole live-WFS-lukittu tälle osoitteelle — metrit ovat esimerkkigeometriaa.")
    if photo_count == 0:
        warnings.append("Ei valokuvia: pintaosuuksia ei ole, vain WFS-julkisivun pituus.")
    return records, warnings


def _shares_from_override_or_photos(
    override: dict[str, Any] | None,
    fractions: dict[str, float],
    warnings: list[str],
) -> list[tuple[str, float]]:
    if override and override.get("osuudet"):
        items: list[tuple[str, float]] = []
        for row in override["osuudet"]:
            tyyppi = str(row.get("tyyppi") or "tuntematon")
            if "alku" in row and "loppu" in row:
                share = max(0.0, float(row["loppu"]) - float(row["alku"]))
            else:
                share = float(row.get("osuus") or 0.0)
            items.append((tyyppi, share))
        total = sum(s for _, s in items) or 1.0
        warnings.append("Pintaosuudet käyttäjän pinnat.json-tiedostosta (ei keksitty).")
        return [(t, s / total) for t, s in items if s > 0]

    ordered = sorted(
        ((k, v) for k, v in fractions.items() if v > 0.01),
        key=lambda kv: -kv[1],
    )
    if not ordered:
        warnings.append("Pintaosuuksia ei saatu kuvista.")
        return []
    warnings.append(
        "Pintaosuudet on arvioitu valokuvien väreistä. "
        "Järjestys kaistalla on osuuksien mukainen, ei paikannettu metreinä."
    )
    return ordered


def _resolve_width(
    strip_width_m: float | None,
    strip_width_source: str,
    override: dict[str, Any] | None,
    warnings: list[str],
) -> tuple[float | None, str, str]:
    if override and override.get("kaistan_leveys_m"):
        w = float(override["kaistan_leveys_m"])
        src = str(override.get("kaistan_leveys_lahde") or "kayttaja")
        return w, src, "Leveys pinnat.json-tiedostosta."
    if strip_width_m and strip_width_m > 0:
        return strip_width_m, strip_width_source, f"Leveyden lähde: {strip_width_source}."
    warnings.append("Kaistan leveyttä ei ole — m²-sarakkeet jäävät tyhjiksi / epävarmoiksi.")
    return None, "puuttuu", "Leveyttä ei keksitä."


def _area_reliability(site: SiteFrame, width_src: str, conf: float, override: dict | None) -> str:
    if not site.verified:
        return "esimerkki"
    if width_src in {"kayttaja", "käyttäjä", "pinnat.json"} or override:
        return "kayttaja"
    if width_src == "mittatikku" and conf >= 0.45:
        return "mittatikku"
    if width_src == "mittatikku":
        return "arvio"
    return "epavarma"


def _linear_reliability(site: SiteFrame, conf: float, override: dict | None) -> str:
    if override:
        return "kayttaja"
    if not site.verified:
        return "esimerkki"
    if conf >= 0.45:
        return "arvio"
    return "epavarma"


def _line_geom(facade: Facade) -> dict[str, Any]:
    return {
        "type": "MultiLineString",
        "coordinates": [[list(e.start), list(e.end)] for e in facade.edges],
    }


def _band_geom(facade: Facade, t0: float, t1: float, width: float | None) -> dict[str, Any] | None:
    if not width or width <= 0 or t1 <= t0:
        return None
    polys: list[list[list[float]]] = []
    # Walk edges in order, mapping normalized [0,1] onto cumulative length.
    total = facade.length_m or 1.0
    acc = 0.0
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
        n = (edge.outward[0] * width, edge.outward[1] * width)
        ring = [p0, p1, (p1[0] + n[0], p1[1] + n[1]), (p0[0] + n[0], p0[1] + n[1]), p0]
        try:
            poly = Polygon(ring)
            if poly.is_valid and poly.area > 0:
                polys.append([list(c) for c in poly.exterior.coords])
        except Exception:
            continue
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys}
    return {"type": "MultiPolygon", "coordinates": [[p] for p in polys]}


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
