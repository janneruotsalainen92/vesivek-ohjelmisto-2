from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import mapping

from vesivek.measure.classify import (
    AREA_TYPES,
    LINEAR_TYPES,
    SURFACE_LABELS,
    WALL_TO_EDGE,
    count_trees,
    to_fm007_fractions,
)
from vesivek.measure.kaista import (
    along_wall_slice,
    build_strip,
    geom_to_geojson,
    split_width_bands,
)
from vesivek.models import Facade, SiteFrame, StickResult, StripInfo, SurfaceRecord


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
    occlusion: bool = False,
    occlusion_note: str = "",
) -> tuple[list[SurfaceRecord], list[str], StripInfo]:
    warnings: list[str] = []
    records: list[SurfaceRecord] = []

    length = facade.length_m
    records.append(
        SurfaceRecord(
            tyyppi="julkisivu_pituus",
            label_fi=f"Julkisivun pituus ({facade.label_fi})",
            kind="wfs",
            value=round(length, 3),
            unit="m",
            luotettavuus="wfs" if facade.verified else "esimerkki",
            lahde=facade.source,
            huomio="Lukittu WFS-geometriaan EPSG:3067. Ei kuvista keksitty.",
            share=1.0,
            geometry=_line_geom(facade),
            pituus_m=round(length, 3),
            ala_m2=None,
        )
    )

    width_in, width_src, width_note = _resolve_width(strip_width_m, strip_width_source, override, warnings)
    strip = build_strip(site, facade, width_m=width_in, width_source=width_src)
    warnings.append(strip.huomio)

    area_ok = strip.area_m2 is not None and strip.width_m is not None
    if not area_ok:
        warnings.append("Pinta-aloja ei lasketa ilman tunnettua kaistan leveyttä (mittatikku, --kaistan-leveys tai tontin reuna).")

    peite = _peite(override, occlusion, occlusion_note)
    if peite:
        warnings.append(f"Peite: {peite} — pinta-alat merkitään EI VARMENNETTU, metrejä ei teeskennellä tarkemmiksi.")

    shares = _shares_wall_to_edge(override, fractions, warnings)
    max_w = strip.max_width_m or strip.width_m or 0.0

    from shapely.geometry import shape as shp_shape

    strip_shp = shp_shape(strip.geometry) if strip.geometry else None
    bands = split_width_bands(facade, strip_shp, shares, max_w) if area_ok and shares else []
    band_by_type = {b.tyyppi: b for b in bands}

    for tyyppi, share in shares:
        if share <= 0.005:
            continue
        label = SURFACE_LABELS.get(tyyppi, tyyppi)
        linear = length * share if _along_wall_linear(tyyppi) else length
        band = band_by_type.get(tyyppi)
        geom = geom_to_geojson(band.geometry) if band is not None else None
        poly_area = float(band.geometry.area) if band is not None else None

        if tyyppi in LINEAR_TYPES:
            rec_lin = SurfaceRecord(
                tyyppi=tyyppi,
                label_fi=f"{label} (viiva)",
                kind="linear",
                value=round(length, 3),
                unit="m",
                luotettavuus=_linear_reliability(site, photo_confidence, override),
                lahde="WFS-julkisivun pituus (rajan suuntainen viiva)",
                huomio=(
                    "Lineaarinen piirre julkisivun suuntaan. Pituus = lukittu WFS-särmä, "
                    "ei kaistan leveydestä riippuva. Rajapuska piirretään kaistan ulkoreunaan."
                ),
                share=share,
                geometry=_line_geom(facade) if tyyppi == "julkisivu_pituus" else _outer_line(facade, strip_shp),
                pituus_m=round(length, 3),
                ala_m2=None,
                peite=peite,
            )
            records.append(rec_lin)

        if tyyppi in AREA_TYPES or (tyyppi in LINEAR_TYPES and area_ok):
            if not area_ok:
                huomio = (
                    "Pinta-alaa ei lasketa: kaistan leveys on mittaamatta. "
                    f"WFS-julkisivun pituus {length:.2f} m. "
                    "Anna --kaistan-leveys, mittatikku, tai hae tontin reuna."
                )
                luot = "epavarma"
                area_val = None
            else:
                area_val = None if poly_area is None else round(poly_area, 2)
                luot = _area_reliability(site, strip.width_source, photo_confidence, override, peite)
                huomio = (
                    f"Kaistapolygoni seinästä ulos ({strip.clip}). "
                    f"{width_note} {strip.huomio}"
                )
                if peite:
                    luot = "ei_varmennettu"
                    huomio = f"EI VARMENNETTU ({peite}). {huomio} Neliöitä ei merkitä varmennetuiksi peitteen alla."

            records.append(
                SurfaceRecord(
                    tyyppi=tyyppi,
                    label_fi=label,
                    kind="area",
                    value=area_val,
                    unit="m²",
                    luotettavuus=luot,
                    lahde=(
                        "valokuvat + kaistapolygoni (WFS)"
                        if not override
                        else "pinnat.json + kaistapolygoni (WFS)"
                    ),
                    huomio=huomio,
                    share=share,
                    geometry=geom,
                    pituus_m=round(linear, 3) if tyyppi in LINEAR_TYPES else None,
                    ala_m2=area_val,
                    peite=peite,
                )
            )

            if area_val is None and tyyppi not in LINEAR_TYPES:
                records.append(
                    SurfaceRecord(
                        tyyppi=f"{tyyppi}_pituus",
                        label_fi=f"{label} (osuus leveydestä, ei m²)",
                        kind="linear",
                        value=round(share * length, 3),
                        unit="m",
                        luotettavuus="arvio" if photo_count else "epavarma",
                        lahde="valokuvien osuus (leveyssuunta) × WFS-pituus — ei pinta-ala",
                        huomio="Vain lineaarinen tunnusluku. m² = EI LASKETTU ilman leveyttä.",
                        share=share,
                        geometry=_line_geom(facade),
                        pituus_m=round(share * length, 3),
                        ala_m2=None,
                    )
                )

    _maybe_paatylaatta(records, site, facade, strip, strip_shp, override, peite, warnings, photo_confidence)

    if photos_for_trees:
        n, note = count_trees(photos_for_trees)
        if n is not None and n > 0:
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
    if photo_count == 0 and not override:
        warnings.append("Ei valokuvia: pintaosuuksia ei ole, vain WFS-julkisivun pituus ja kaistapolygoni.")
    return records, warnings, strip


def _maybe_paatylaatta(
    records: list[SurfaceRecord],
    site: SiteFrame,
    facade: Facade,
    strip: StripInfo,
    strip_shp,
    override: dict[str, Any] | None,
    peite: str | None,
    warnings: list[str],
    photo_confidence: float,
) -> None:
    spec = (override or {}).get("paatylaatta") or (override or {}).get("päätylaatta")
    already = any(r.tyyppi == "päätylaatta" and r.kind == "area" for r in records)
    if already and not spec:
        for rec in records:
            if rec.tyyppi == "päätylaatta" and rec.kind == "area" and rec.value is not None:
                rec.luotettavuus = "arvio" if rec.luotettavuus != "ei_varmennettu" else rec.luotettavuus
                rec.huomio = "Päätylaatta kuvista (ARVIO). " + rec.huomio
        return
    if not spec:
        if any(r.tyyppi == "päätylaatta" for r in records):
            return
        warnings.append("Päätylaattaa ei mitattu: merkitään EI LASKETTU, ellei pinnat.json anna palaa.")
        records.append(
            SurfaceRecord(
                tyyppi="päätylaatta",
                label_fi="Päätylaatta",
                kind="area",
                value=None,
                unit="m²",
                luotettavuus="arvio",
                lahde="ei mitattu",
                huomio="Päätylaatta voi näkyä päätykuvissa. Palaa ei mitattu — EI LASKETTU (ei keksittyä m²).",
                share=0.0,
                geometry=None,
                ala_m2=None,
                peite=peite,
            )
        )
        return

    has_geom_spec = any(k in spec for k in ("alku", "loppu", "osuus_pituudesta", "leveys_m", "kaistan_osuus"))
    if not has_geom_spec:
        records.append(
            SurfaceRecord(
                tyyppi="päätylaatta",
                label_fi="Päätylaatta",
                kind="area",
                value=None,
                unit="m²",
                luotettavuus="arvio",
                lahde="pinnat.json",
                huomio=str(spec.get("huomio") or "Päätylaatta merkitty ilman mitattua palaa — EI LASKETTU."),
                share=0.0,
                geometry=None,
                ala_m2=None,
                peite=peite,
            )
        )
        return

    t0 = float(spec.get("alku", spec.get("osuus_pituudesta_alku", 0.85)))
    t1 = float(spec.get("loppu", 1.0))
    if "osuus_pituudesta" in spec and "alku" not in spec:
        span = float(spec["osuus_pituudesta"])
        t0, t1 = max(0.0, 1.0 - span), 1.0
    depth = spec.get("leveys_m") or spec.get("kaistan_osuus")
    width_m = None
    if spec.get("leveys_m"):
        width_m = float(spec["leveys_m"])
    elif strip.max_width_m and spec.get("kaistan_osuus"):
        width_m = float(strip.max_width_m) * float(spec["kaistan_osuus"])

    if strip.geometry is None or (width_m is None and strip.width_m is None):
        records.append(
            SurfaceRecord(
                tyyppi="päätylaatta",
                label_fi="Päätylaatta",
                kind="area",
                value=None,
                unit="m²",
                luotettavuus="arvio",
                lahde="pinnat.json",
                huomio="Päätylaatta määritelty, mutta kaistan leveyttä ei ole — EI LASKETTU.",
                share=t1 - t0,
                geometry=None,
                ala_m2=None,
                peite=peite,
            )
        )
        return

    geom = along_wall_slice(facade, strip_shp, t0, t1, width_m or (strip.max_width_m or 0) * 0.08)
    area = None if geom is None else round(float(geom.area), 2)
    luot = "arvio"
    huomio = "Päätylaatta ARVIO (pinnat.json + kaistaleikkaus). Ei WFS-lukittu pala."
    if peite:
        luot = "ei_varmennettu"
        huomio = f"EI VARMENNETTU ({peite}). " + huomio
    records.append(
        SurfaceRecord(
            tyyppi="päätylaatta",
            label_fi="Päätylaatta",
            kind="area",
            value=area,
            unit="m²",
            luotettavuus=luot,
            lahde="pinnat.json + kaistapolygoni",
            huomio=huomio,
            share=t1 - t0,
            geometry=mapping(geom) if geom is not None else None,
            ala_m2=area,
            peite=peite,
        )
    )


def _shares_wall_to_edge(
    override: dict[str, Any] | None,
    fractions: dict[str, float],
    warnings: list[str],
) -> list[tuple[str, float]]:
    """Width shares from the wall outward. Not a pie of wall-length shares."""
    if override and override.get("osuudet"):
        items: list[tuple[str, float]] = []
        jaottelu = str(override.get("jaottelu") or "seinasta").lower()
        if jaottelu in {"pituus", "julkisivu", "pie"}:
            warnings.append(
                "pinnat.json jaottelu=pituus on vanha seinänsuuntainen malli; "
                "kaista piirretään silti seinästä ulos. Osuudet tulkitaan leveysosuuksina jos alku/loppu puuttuu."
            )
        for row in override["osuudet"]:
            tyyppi = str(row.get("tyyppi") or "tuntematon")
            if tyyppi == "pensas":
                tyyppi = "rajapuska"
            if "osuus" in row:
                share = float(row.get("osuus") or 0.0)
            elif "alku" in row and "loppu" in row:
                # Legacy along-wall numbers: still used as width shares so we do not
                # draw a wall-length pie. Documented in README.
                share = max(0.0, float(row["loppu"]) - float(row["alku"]))
            else:
                share = 0.0
            items.append((tyyppi, share))
        total = sum(s for _, s in items) or 1.0
        warnings.append("Pintaosuudet käyttäjän pinnat.json-tiedostosta, jaottelu seinästä ulos (ei keksitty).")
        ordered = [(t, s / total) for t, s in items if s > 0]
        return _order_wall_to_edge(ordered)

    mapped = to_fm007_fractions(fractions)
    ordered = [(k, v) for k, v in mapped.items() if v > 0.02 and k != "päätylaatta"]
    if not ordered:
        warnings.append("Pintaosuuksia ei saatu kuvista.")
        return []
    warnings.append(
        "Pintaosuudet on arvioitu valokuvien väreistä leveyssuunnassa (seinä → reuna). "
        "Tämä ei ole paikannettu maastomittaus."
    )
    return _order_wall_to_edge(ordered)


def _order_wall_to_edge(items: list[tuple[str, float]]) -> list[tuple[str, float]]:
    rank = {name: i for i, name in enumerate(WALL_TO_EDGE)}
    return sorted(items, key=lambda kv: rank.get(kv[0], 50))


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
    warnings.append("Kaistan leveyttä ei annettu käsin — käytetään tontin reunaa jos WFS palauttaa tontin.")
    return None, "puuttuu", "Leveyttä ei keksitä."


def _peite(override: dict[str, Any] | None, occlusion: bool, occlusion_note: str) -> str | None:
    if override and override.get("peite"):
        raw = override["peite"]
        if isinstance(raw, list):
            return ",".join(str(x) for x in raw)
        return str(raw)
    if occlusion:
        return occlusion_note or "autot"
    return None


def _along_wall_linear(tyyppi: str) -> bool:
    return tyyppi in LINEAR_TYPES


def _area_reliability(
    site: SiteFrame,
    width_src: str,
    conf: float,
    override: dict | None,
    peite: str | None,
) -> str:
    if peite:
        return "ei_varmennettu"
    if not site.verified:
        return "esimerkki"
    if width_src == "tontti":
        return "tontti" if conf >= 0.45 or override else "arvio"
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


def _outer_line(facade: Facade, strip) -> dict[str, Any] | None:
    if strip is None:
        return _line_geom(facade)
    from shapely.geometry import LineString
    from vesivek.measure.kaista import SEARCH_M

    coords = []
    for edge in facade.edges:
        for t, pt in ((0.0, edge.start), (1.0, edge.end)):
            nx, ny = edge.outward
            px, py = pt
            ray = LineString([(px, py), (px + nx * SEARCH_M, py + ny * SEARCH_M)])
            inter = ray.intersection(strip)
            if inter.is_empty:
                coords.append([px, py])
                continue
            if inter.geom_type == "LineString":
                coords.append(list(inter.coords[-1]))
            elif inter.geom_type == "MultiLineString":
                last = list(inter.geoms[-1].coords[-1])
                coords.append(last)
            else:
                coords.append([px, py])
    if len(coords) < 2:
        return _line_geom(facade)
    return {"type": "LineString", "coordinates": coords}
