from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vesivek.config import DEFAULT_STICK_M, default_output_dir
from vesivek.geocode import GeocodeHit, geocode_address
from vesivek.measure.classify import classify_photo, merge_fractions
from vesivek.measure.facade import choose_facade, list_facades
from vesivek.measure.photos import collect_photos
from vesivek.measure.stick import detect_stick, estimate_strip_width_m
from vesivek.measure.strip import load_surface_override, measure_strip
from vesivek.models import Facade, MeasurementResult, SiteFrame, StickResult
from vesivek.output.excel import write_excel
from vesivek.output.geojson_out import write_geojson
from vesivek.output.png import write_png
from vesivek.wfs.chain import fetch_site
from vesivek.wfs.stub import StubWfsFetcher


@dataclass
class RunRequest:
    osoite: str
    kuvat: list[Path]
    julkisivu: str | None = "auto"
    mittatikku_m: float = DEFAULT_STICK_M
    kaistan_leveys_m: float | None = None
    wfs_mode: str = "auto"
    geojson: Path | None = None
    pinnat: Path | None = None
    output_dir: Path | None = None
    skip_geocode: bool = False


def resolve_site(req: RunRequest) -> tuple[SiteFrame, GeocodeHit | None]:
    if req.wfs_mode == "stub":
        site = StubWfsFetcher().fetch_site(0.0, 0.0, req.osoite)
        if site is None:
            raise RuntimeError("Stub-geometria puuttuu.")
        return site, None

    if req.geojson is not None:
        # Local file does not need a live geocode, but we still try for metadata.
        hit = None
        try:
            hit = geocode_address(req.osoite)
            easting, northing = hit.easting, hit.northing
        except Exception:
            easting = northing = 0.0
        site = fetch_site(
            easting=easting,
            northing=northing,
            address=req.osoite,
            mode="file",
            geojson_path=req.geojson,
        )
        return site, hit

    hit = geocode_address(req.osoite)
    site = fetch_site(
        easting=hit.easting,
        northing=hit.northing,
        address=req.osoite,
        mode=req.wfs_mode,
        geojson_path=None,
    )
    return site, hit


def list_site_facades(osoite: str, wfs_mode: str = "auto", geojson: Path | None = None) -> tuple[SiteFrame, list[Facade]]:
    req = RunRequest(osoite=osoite, kuvat=[], wfs_mode=wfs_mode, geojson=geojson)
    site, _ = resolve_site(req)
    return site, list_facades(site)


def run_measurement(req: RunRequest) -> MeasurementResult:
    warnings: list[str] = []
    site, _hit = resolve_site(req)
    warnings.extend(site.warnings)

    facade = choose_facade(site, req.julkisivu)
    photos, photo_notes = collect_photos(req.kuvat)
    warnings.extend(photo_notes)

    photo_infos = [classify_photo(p) for p in photos]
    fractions, photo_conf = merge_fractions(photo_infos)

    stick = detect_stick(photos, req.mittatikku_m) if photos else StickResult(
        found=False,
        length_m=req.mittatikku_m,
        length_px=None,
        pixels_per_m=None,
        image=None,
        huomio="Ei kuvia — mittatikkua ei etsitty.",
    )
    warnings.append(stick.huomio)

    width = req.kaistan_leveys_m
    width_src = "kayttaja" if width else "puuttuu"
    if width is None and stick.found:
        est, note = estimate_strip_width_m(photos, stick)
        if est:
            width = est
            width_src = "mittatikku"
            warnings.append(note)

    override = load_surface_override(req.pinnat)

    records, strip_notes = measure_strip(
        site=site,
        facade=facade,
        fractions=fractions,
        photo_confidence=photo_conf,
        stick=stick,
        strip_width_m=width,
        strip_width_source=width_src,
        override=override,
        photo_count=len(photos),
        photos_for_trees=photo_infos,
    )
    warnings.extend(strip_notes)

    out_dir = _prepare_output_dir(req)
    result = MeasurementResult(
        site=site,
        facade=facade,
        surfaces=records,
        photos=photo_infos,
        stick=stick,
        strip_width_m=width,
        strip_width_source=width_src,
        warnings=_unique(warnings),
        output_dir=out_dir,
    )
    result.png_path = write_png(result, out_dir / "julkisivukaista.png")
    result.geojson_path = write_geojson(result, out_dir / "julkisivukaista.geojson")
    result.xlsx_path = write_excel(result, out_dir / "mittaus.xlsx")
    (out_dir / "huomiot.txt").write_text("\n".join(result.warnings) + "\n", encoding="utf-8")
    return result


def _prepare_output_dir(req: RunRequest) -> Path:
    base = req.output_dir or default_output_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(req.osoite)
    out = base / f"{slug}-{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return (cleaned.strip("-") or "mittaus")[:48]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = (item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
