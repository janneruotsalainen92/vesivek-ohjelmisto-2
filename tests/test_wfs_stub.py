from pathlib import Path

from shapely.geometry import shape

from vesivek.config import sample_dir
from vesivek.wfs.local import load_local_geojson
from vesivek.wfs.stub import StubWfsFetcher


def test_stub_is_epsg_3067_and_metric():
    site = StubWfsFetcher().fetch_site(0, 0, "esimerkki")
    assert site is not None
    assert site.crs == "EPSG:3067"
    assert site.verified is False
    geom = shape(site.building["geometry"])
    assert geom.area > 10
    # TM35FIN Helsinki-ish window
    assert 380000 < geom.centroid.x < 400000
    assert 6660000 < geom.centroid.y < 6690000
    assert any("esimerkki" in w.lower() or "Esimerkki" in w or "eivät" in w for w in site.warnings)


def test_sample_files_exist():
    assert (sample_dir() / "rakennus_3067.geojson").exists()
    assert (sample_dir() / "tontti_3067.geojson").exists()


def test_local_geojson_loader():
    path = sample_dir() / "rakennus_3067.geojson"
    site = load_local_geojson(path, "oma tiedosto")
    assert site.crs == "EPSG:3067"
    assert site.verified is False
    assert "GeoJSON" in site.source_name
