import pytest
from gasaudit.rows import RowInput, to_unit, from_unit, clamp_town


def test_to_from_unit_roundtrip():
    assert to_unit(100.0, "mi") == pytest.approx(100.0)
    assert to_unit(100.0, "km") == pytest.approx(160.9344)
    assert from_unit(to_unit(100.0, "km"), "km") == pytest.approx(100.0)
    assert from_unit(50.0, "mi") == pytest.approx(50.0)


def test_clamp_town_bounds():
    r = RowInput(label="d1", total_mi=100.0, min_highway_mi=30.0, town_mi=999.0)
    clamp_town(r)
    assert r.town_mi == pytest.approx(70.0)   # total - min_highway
    r2 = RowInput(label="d2", total_mi=100.0, min_highway_mi=0.0, town_mi=-5.0)
    clamp_town(r2)
    assert r2.town_mi == pytest.approx(0.0)
