from vesivek.measure.qc import build_mittaviivat
from vesivek.measure.strip import measure_strip
from vesivek.models import StickResult
from vesivek.valokuva import (
    DUAL_SOURCE_TOLERANCE,
    LUOTETTAVUUS_EI_VARMENNETTU,
    LUOTETTAVUUS_PRE_LOCK,
    coded_lock_rows,
    dual_source_verdict,
    is_clutter,
)


def _empty_stick() -> StickResult:
    return StickResult(found=False, length_m=1.0, length_px=None, pixels_per_m=None, image=None, huomio="ei")


def test_dual_agree_within_10_percent():
    v = dual_source_verdict(100.0, 105.0)
    assert v.status == "agree"
    assert v.rel_diff is not None and v.rel_diff <= DUAL_SOURCE_TOLERANCE


def test_dual_disagree_reports_both_no_average():
    v = dual_source_verdict(100.0, 140.0)
    assert v.status == "disagree"
    assert v.area_a == 100.0
    assert v.area_b == 140.0
    assert "keskiarv" in v.note.lower() or "A=" in v.note


def test_dual_one_source():
    v = dual_source_verdict(50.0, None)
    assert v.status == "one_source"
    assert v.n_sources == 1


def test_pre_lock_when_width_known_no_peite(rectangle_site, south_facade):
    records, _, strip = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 1.0},
        photo_confidence=0.8,
        stick=_empty_stick(),
        strip_width_m=2.0,
        strip_width_source="kayttaja",
        override=None,
        photo_count=1,
        photos_for_trees=None,
    )
    asf = next(r for r in records if r.tyyppi == "asfaltti" and r.kind == "area")
    assert asf.value is not None
    assert asf.luotettavuus == LUOTETTAVUUS_PRE_LOCK
    assert asf.lock_tila == "pre_lock"
    wall = next(r for r in records if r.tyyppi == "julkisivu_pituus")
    assert wall.luotettavuus == "wfs"
    assert wall.lock_tila == "lukittu"
    assert strip.dual_status == "one_source"


def test_hsv_shares_are_not_locked_metres(rectangle_site, south_facade):
    records, warnings, _ = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 0.7, "sepeli": 0.3},
        photo_confidence=0.6,
        stick=_empty_stick(),
        strip_width_m=1.0,
        strip_width_source="mittatikku",
        override=None,
        photo_count=2,
    )
    areas = [r for r in records if r.kind == "area" and r.tyyppi in {"asfaltti", "sepeli"}]
    assert areas
    assert all(r.luotettavuus != "wfs" for r in areas)
    assert any("HSV" in w or "PRE-LOCK" in w or "lukittuja metrejä" in w for w in warnings)


def test_occlusion_ei_varmennettu_not_pre_lock(rectangle_site, south_facade):
    records, _, _ = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 1.0},
        photo_confidence=0.8,
        stick=_empty_stick(),
        strip_width_m=1.5,
        strip_width_source="kayttaja",
        override={"peite": "autot,ruukut"},
        photo_count=1,
        occlusion=True,
        occlusion_note="peite=autot,ruukut",
    )
    asf = next(r for r in records if r.tyyppi == "asfaltti" and r.kind == "area")
    assert asf.luotettavuus == LUOTETTAVUUS_EI_VARMENNETTU
    assert asf.lock_tila == "ei_varmennettu"
    assert "ruukut" in (asf.peite or "") or "autot" in (asf.peite or "")


def test_clutter_is_not_a_surface(rectangle_site, south_facade):
    records, _, _ = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={},
        photo_confidence=1.0,
        stick=_empty_stick(),
        strip_width_m=1.0,
        strip_width_source="kayttaja",
        override={
            "osuudet": [
                {"tyyppi": "asfaltti", "osuus": 0.8},
                {"tyyppi": "ruukut", "osuus": 0.2},
            ]
        },
        photo_count=0,
    )
    types = {r.tyyppi for r in records}
    assert "ruukut" not in types
    assert is_clutter("ruukut")


def test_dual_disagree_on_plot_vs_buffer(rectangle_site, south_facade):
    rectangle_site.plot = {
        "type": "Feature",
        "properties": {"tunnus": "t"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-1.0, -3.0], [11.0, -3.0], [11.0, 9.0], [-1.0, 9.0], [-1.0, -3.0]]],
        },
    }
    records, warnings, strip = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 1.0},
        photo_confidence=0.8,
        stick=_empty_stick(),
        strip_width_m=1.0,
        strip_width_source="kayttaja",
        override=None,
        photo_count=1,
    )
    assert strip.dual_status == "disagree"
    assert strip.area_m2_plot is not None and strip.area_m2_buffer is not None
    rel = abs(strip.area_m2_plot - strip.area_m2_buffer) / max(strip.area_m2_plot, strip.area_m2_buffer)
    assert rel > DUAL_SOURCE_TOLERANCE
    assert any("Dual" in w or "dual" in w.lower() or "keskiarv" in w.lower() for w in warnings)
    asf = next(r for r in records if r.tyyppi == "asfaltti" and r.kind == "area")
    assert asf.lock_tila in {"pre_lock", "ei_varmennettu"}


def test_mv_ids_unique_and_tiered(rectangle_site, south_facade):
    _, _, strip = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 0.6, "seinänvierus": 0.4},
        photo_confidence=0.8,
        stick=_empty_stick(),
        strip_width_m=2.0,
        strip_width_source="kayttaja",
        override=None,
        photo_count=1,
    )
    ticks = build_mittaviivat(south_facade, strip.geometry, spacing_m=1.0, work_edges=strip.work_edges)
    ids = [t.id for t in ticks]
    assert ids
    assert len(ids) == len(set(ids))
    assert any(i.startswith("MV-") and i[3:6].isdigit() for i in ids)
    work = [t for t in ticks if t.tier == 2]
    assert work
    assert any(t.id.startswith("MV-ASF-") or t.id.startswith("MV-SEINA-") for t in work)
    assert all(not t.id.startswith("MV-NURMI") for t in ticks)


def test_coded_vs_todo_locks_listed():
    rows = coded_lock_rows()
    statuses = {s for s, _, _ in rows}
    assert "KOODATTU" in statuses and "TODO" in statuses
    keys = {k for _, k, _ in rows}
    assert "PRE-LOCK" in keys
    assert "dual ±10 %" in keys
    assert "asfaltti ortosta" in keys
