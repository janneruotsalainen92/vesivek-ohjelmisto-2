from vesivek.measure.classify import FM007_CLASSES, SURFACE_LABELS
from vesivek.measure.kaista import build_strip, split_width_bands
from vesivek.measure.strip import measure_strip
from vesivek.models import StickResult
from tests.conftest import write_stick_image
from vesivek.measure.stick import detect_stick


def _empty_stick() -> StickResult:
    return StickResult(
        found=False,
        length_m=1.0,
        length_px=None,
        pixels_per_m=None,
        image=None,
        huomio="ei",
    )


def test_fm007_class_labels():
    for key in ("seinänvierus", "rajapuska", "päätylaatta", "asfaltti", "sepeli", "laatta"):
        assert key in FM007_CLASSES
        assert key in SURFACE_LABELS


def test_no_invented_area_without_width(rectangle_site, south_facade):
    records, warnings, strip = measure_strip(
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
    assert strip.geometry is None
    assert strip.area_m2 is None
    areas = [r for r in records if r.kind == "area"]
    assert areas
    assert all(r.value is None for r in areas)
    assert any(r.ala_m2 is None for r in areas)
    assert any("EI LASKETTU" in (r.huomio or "") or "ei lasketa" in (r.huomio or "").lower() or "mittaamatta" in (r.huomio or "").lower() for r in areas)
    length = next(r for r in records if r.tyyppi == "julkisivu_pituus")
    assert length.value == 10.0
    assert length.unit == "m"
    assert length.luotettavuus == "wfs"
    assert length.pituus_m == 10.0
    assert length.ala_m2 is None


def test_area_from_outward_strip_not_wall_pie(rectangle_site, south_facade):
    records, _, strip = measure_strip(
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
    assert strip.geometry is not None
    assert strip.clip.startswith("puskuri")
    areas = {r.tyyppi: r for r in records if r.kind == "area" and r.value is not None}
    assert abs(areas["asfaltti"].value - 10.0) < 0.3  # 10 m × 1 m band
    assert abs(areas["nurmikko"].value - 10.0) < 0.3
    # Bands are stacked away from the wall (south = -Y), not sequential along X.
    from shapely.geometry import shape

    asf = shape(areas["asfaltti"].geometry)
    cy = asf.centroid.y
    assert cy < 0  # outward from south wall at y=0


def test_override_width_shares_and_rajapuska_line(rectangle_site, south_facade):
    override = {
        "kaistan_leveys_m": 2.0,
        "kaistan_leveys_lahde": "kayttaja",
        "jaottelu": "seinasta",
        "osuudet": [
            {"tyyppi": "seinänvierus", "osuus": 0.25},
            {"tyyppi": "asfaltti", "osuus": 0.50},
            {"tyyppi": "rajapuska", "osuus": 0.25},
        ],
    }
    records, _, strip = measure_strip(
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
    assert strip.area_m2 is not None
    seina = next(r for r in records if r.tyyppi == "seinänvierus" and r.kind == "area")
    asf = next(r for r in records if r.tyyppi == "asfaltti" and r.kind == "area")
    hedge_m = next(r for r in records if r.tyyppi == "rajapuska" and r.kind == "linear")
    hedge_a = next(r for r in records if r.tyyppi == "rajapuska" and r.kind == "area")
    assert abs(seina.value - 5.0) < 0.4  # 10 × 0.5
    assert abs(asf.value - 10.0) < 0.4
    assert hedge_m.unit == "m"
    assert abs(hedge_m.value - 10.0) < 1e-6
    assert hedge_a.unit == "m²"
    assert seina.ala_m2 == seina.value


def test_occlusion_marks_ei_varmennettu(rectangle_site, south_facade):
    records, warnings, _ = measure_strip(
        site=rectangle_site,
        facade=south_facade,
        fractions={"asfaltti": 1.0},
        photo_confidence=0.8,
        stick=_empty_stick(),
        strip_width_m=1.5,
        strip_width_source="kayttaja",
        override={"peite": "autot"},
        photo_count=1,
        photos_for_trees=None,
        occlusion=True,
        occlusion_note="peite=autot",
    )
    areas = [r for r in records if r.kind == "area" and r.tyyppi == "asfaltti"]
    assert areas
    assert areas[0].luotettavuus == "ei_varmennettu"
    assert areas[0].peite
    assert any("EI VARMENNETTU" in (r.huomio or "") for r in areas)


def test_plot_clip_gives_width_without_inventing(rectangle_site, south_facade):
    # Plot extends 3 m south of the south wall.
    plot = {
        "type": "Feature",
        "properties": {"tunnus": "test-tontti"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-1.0, -3.0], [11.0, -3.0], [11.0, 9.0], [-1.0, 9.0], [-1.0, -3.0]]],
        },
    }
    rectangle_site.plot = plot
    strip = build_strip(rectangle_site, south_facade, width_m=None, width_source="puuttuu")
    assert strip.geometry is not None
    assert strip.clip == "tontti"
    assert strip.width_source == "tontti"
    assert abs((strip.area_m2 or 0) - 30.0) < 1.5  # 10 m × 3 m
    bands = split_width_bands(
        south_facade,
        strip.geometry,
        [("asfaltti", 1.0)],
        strip.max_width_m or 3.0,
    )
    assert bands and bands[0].geometry.area > 20


def test_stick_scale(tmp_path):
    path = write_stick_image(tmp_path / "tikku.png", stick_px=200)
    stick = detect_stick([path], length_m=1.0)
    assert stick.found
    assert stick.pixels_per_m is not None
    assert 160 < stick.pixels_per_m < 260
