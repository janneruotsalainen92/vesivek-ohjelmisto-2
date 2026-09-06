from vesivek.measure.stick import detect_stick
from vesivek.measure.strip import measure_strip
from vesivek.models import StickResult
from tests.conftest import write_stick_image


def _empty_stick() -> StickResult:
    return StickResult(
        found=False,
        length_m=1.0,
        length_px=None,
        pixels_per_m=None,
        image=None,
        huomio="ei",
    )


def test_no_invented_area_without_width(rectangle_site, south_facade):
    records, warnings = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 1.0},
        photo_confidence=0.8,
        stick=_empty_stick(),
        strip_width_m=None,
        strip_width_source="puuttuu",
        override=None,
        photo_count=1,
        photos_for_trees=None,
    )
    areas = [r for r in records if r.kind == "area"]
    assert areas
    assert all(r.value is None for r in areas)
    assert any("leveys" in w.lower() or "MITTAAMATTA" in w or "ei ole" in w for w in warnings)
    length = next(r for r in records if r.tyyppi == "julkisivu_pituus")
    assert length.value == 10.0
    assert length.luotettavuus == "wfs"


def test_area_is_wfs_length_times_width(rectangle_site, south_facade):
    records, _ = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 0.5, "nurmikko": 0.5},
        photo_confidence=0.7,
        stick=_empty_stick(),
        strip_width_m=2.0,
        strip_width_source="kayttaja",
        override=None,
        photo_count=1,
        photos_for_trees=None,
    )
    areas = {r.tyyppi: r for r in records if r.kind == "area"}
    assert abs(areas["asfaltti"].value - 10.0) < 1e-6  # 5 m × 2 m
    assert abs(areas["nurmikko"].value - 10.0) < 1e-6


def test_override_json_segments(rectangle_site, south_facade):
    override = {
        "kaistan_leveys_m": 1.0,
        "kaistan_leveys_lahde": "kayttaja",
        "osuudet": [
            {"tyyppi": "asfaltti", "alku": 0.0, "loppu": 0.4},
            {"tyyppi": "pensas", "alku": 0.4, "loppu": 1.0},
        ],
    }
    records, _ = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={},
        photo_confidence=1.0,
        stick=_empty_stick(),
        strip_width_m=None,
        strip_width_source="puuttuu",
        override=override,
        photo_count=0,
        photos_for_trees=None,
    )
    asphalt = next(r for r in records if r.tyyppi == "asfaltti")
    hedge = next(r for r in records if r.tyyppi == "pensas")
    assert abs(asphalt.value - 4.0) < 1e-6  # 4 m × 1 m
    assert asphalt.unit == "m²"
    assert hedge.kind == "linear"
    assert abs(hedge.value - 6.0) < 1e-6


def test_stick_scale(tmp_path):
    path = write_stick_image(tmp_path / "tikku.png", stick_px=200)
    stick = detect_stick([path], length_m=1.0)
    assert stick.found
    assert stick.pixels_per_m is not None
    assert 160 < stick.pixels_per_m < 260
