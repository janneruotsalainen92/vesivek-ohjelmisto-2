from pathlib import Path

from vesivek.pipeline import RunRequest, run_measurement
from tests.conftest import write_color_image, write_stick_image


def test_stub_pipeline_writes_png_and_excel(tmp_path):
    photos = tmp_path / "kuvat"
    photos.mkdir()
    write_color_image(photos / "a.jpg", (70, 70, 72))
    write_color_image(photos / "b.jpg", (50, 140, 55))
    write_stick_image(photos / "tikku.jpg", stick_px=180)

    req = RunRequest(
        osoite="Esimerkkitontti",
        kuvat=[photos],
        julkisivu="etela",
        mittatikku_m=1.0,
        kaistan_leveys_m=1.2,
        wfs_mode="stub",
        skip_geocode=True,
        output_dir=tmp_path / "out",
    )
    result = run_measurement(req)
    assert result.png_path and result.png_path.exists()
    assert result.xlsx_path and result.xlsx_path.exists()
    assert result.geojson_path and result.geojson_path.exists()
    assert result.site.crs == "EPSG:3067"
    assert result.facade.length_m > 1
    length = next(r for r in result.surfaces if r.tyyppi == "julkisivu_pituus")
    assert abs((length.value or 0) - result.facade.length_m) < 0.01
    assert length.unit == "m"
    # User-supplied width → areas computed, still flagged as user/example
    areas = [r for r in result.surfaces if r.kind == "area" and r.value is not None]
    assert areas
    assert result.png_path.stat().st_size > 1000
    assert result.xlsx_path.stat().st_size > 1000
