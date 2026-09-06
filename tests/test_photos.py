from vesivek.measure.classify import classify_photo
from vesivek.measure.photos import collect_photos
from tests.conftest import write_color_image


def test_collects_many_images_no_six_cap(tmp_path):
    folder = tmp_path / "erä"
    folder.mkdir()
    for i in range(9):
        write_color_image(folder / f"kuva_{i}.jpg", (80, 80, 80))
    extra = tmp_path / "toinen"
    extra.mkdir()
    write_color_image(extra / "lisa.png", (80, 80, 80))
    found, _ = collect_photos([folder, extra])
    assert len(found) == 10


def test_asphalt_image_classifies_as_asfaltti(tmp_path):
    path = write_color_image(tmp_path / "asf.jpg", (75, 75, 78), size=(320, 240))
    info = classify_photo(path)
    assert info.fractions["asfaltti"] > 0.5


def test_grass_image_classifies_green(tmp_path):
    path = write_color_image(tmp_path / "nurmi.jpg", (40, 160, 50), size=(320, 240))
    info = classify_photo(path)
    assert info.fractions["nurmikko"] + info.fractions["pensas"] > 0.5
