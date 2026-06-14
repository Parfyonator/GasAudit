import pytest
from gasaudit.rows import RowInput, to_unit, from_unit, clamp_town, RowSegments, row_segments, totals


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


from gasaudit.model import rates_from_norm


def test_row_segments_mi_unit():
    rates = rates_from_norm(20.0)  # town 0.23, highway 0.17 per unit
    r = RowInput(label="d1", total_mi=127.0, min_highway_mi=80.0, town_mi=47.0)
    seg = row_segments(r, "mi", rates)
    assert seg.town_mi == pytest.approx(47.0)
    assert seg.out_mi == pytest.approx(80.0)
    assert seg.town_km == pytest.approx(47.0 * 1.609344)
    assert seg.out_km == pytest.approx(80.0 * 1.609344)
    assert seg.town_l == pytest.approx(47.0 * 0.23)
    assert seg.out_l == pytest.approx(80.0 * 0.17)
    assert seg.total_l == pytest.approx(47.0 * 0.23 + 80.0 * 0.17)
    assert seg.town_frac == pytest.approx(47.0 / 127.0)


def test_row_segments_km_unit_changes_only_liters_basis():
    rates = rates_from_norm(20.0)
    r = RowInput(label="d1", total_mi=100.0, min_highway_mi=0.0, town_mi=40.0)
    seg = row_segments(r, "km", rates)
    # distances in km use the converted values for the liters basis
    assert seg.town_l == pytest.approx(40.0 * 1.609344 * 0.23)
    assert seg.town_frac == pytest.approx(0.40)  # fraction is unit-independent


def test_row_segments_zero_total_fraction_safe():
    rates = rates_from_norm(20.0)
    r = RowInput(label="z", total_mi=0.0, min_highway_mi=0.0, town_mi=0.0)
    seg = row_segments(r, "mi", rates)
    assert seg.town_frac == pytest.approx(0.0)


def test_totals_aggregates_rows():
    rates = rates_from_norm(20.0)
    rows = [
        RowInput(label="a", total_mi=100.0, town_mi=40.0),
        RowInput(label="b", total_mi=60.0, town_mi=60.0),
    ]
    t = totals(rows, "mi", rates)
    assert t.town_mi == pytest.approx(100.0)   # 40 + 60
    assert t.out_mi == pytest.approx(60.0)     # 60 + 0
    assert t.grand_l == pytest.approx(t.town_l + t.out_l)
    assert t.town_l == pytest.approx((40.0 + 60.0) * 0.23)
    assert t.out_l == pytest.approx(60.0 * 0.17)
