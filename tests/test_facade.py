from vesivek.measure.facade import choose_facade, list_facades


def test_rectangle_facade_lengths_locked_to_geometry(rectangle_site):
    facades = {f.key: f for f in list_facades(rectangle_site) if f.key in {"etela", "pohjoinen", "ita", "lansi"}}
    assert abs(facades["etela"].length_m - 10.0) < 1e-6
    assert abs(facades["pohjoinen"].length_m - 10.0) < 1e-6
    assert abs(facades["ita"].length_m - 8.0) < 1e-6
    assert abs(facades["lansi"].length_m - 8.0) < 1e-6
    assert all(f.verified for f in facades.values())


def test_choose_south_alias(rectangle_site):
    facade = choose_facade(rectangle_site, "etelä")
    assert facade.key == "etela"
    assert abs(facade.length_m - 10.0) < 1e-6


def test_unknown_facade_raises(rectangle_site):
    try:
        choose_facade(rectangle_site, "kattolape")
    except RuntimeError as exc:
        assert "Tuntematon" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
