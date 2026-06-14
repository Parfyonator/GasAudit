import pytest
from gasaudit.model import Rates, rates_from_norm


def test_rates_from_norm_default_uplift():
    r = rates_from_norm(20.0)  # 20 L / 100 dist-units, uplift 0.15
    assert r.base == pytest.approx(0.20)
    assert r.town == pytest.approx(0.23)
    assert r.highway == pytest.approx(0.17)
    assert r.spread == pytest.approx(0.06)


def test_rates_from_norm_custom_uplift():
    r = rates_from_norm(19.0, uplift=0.20)
    assert r.base == pytest.approx(0.19)
    assert r.town == pytest.approx(0.19 * 1.20)
    assert r.highway == pytest.approx(0.19 * 0.80)


from gasaudit.model import total_fuel, required_town


def test_total_fuel_uses_only_total_town():
    r = rates_from_norm(20.0)
    # 100 dist total, 40 of it town
    assert total_fuel(r, 100.0, 40.0) == pytest.approx(0.17 * 100 + 0.06 * 40)


def test_required_town_inverts_total_fuel():
    r = rates_from_norm(20.0)
    fuel = total_fuel(r, 100.0, 40.0)
    assert required_town(r, 100.0, fuel) == pytest.approx(40.0)


from gasaudit.model import Row, feasible_window


def test_row_town_bounds():
    r = Row(label="d1", total=100.0, min_highway=30.0, min_town=5.0)
    assert r.town_min == 5.0
    assert r.town_max == 70.0  # total - min_highway


def test_feasible_window_sums_bounds():
    rows = [
        Row(label="d1", total=100.0, min_highway=30.0),  # town in [0, 70]
        Row(label="d2", total=50.0, min_highway=0.0),    # town in [0, 50]
    ]
    lo, hi = feasible_window(rows)
    assert lo == pytest.approx(0.0)
    assert hi == pytest.approx(120.0)


def test_row_rejects_highway_over_total():
    with pytest.raises(ValueError):
        Row(label="bad", total=10.0, min_highway=20.0).validate()


from gasaudit.model import example_distribution


def test_example_distribution_hits_target_and_respects_bounds():
    rows = [
        Row(label="d1", total=100.0, min_highway=30.0),  # town [0,70]
        Row(label="d2", total=50.0, min_highway=10.0),   # town [0,40]
    ]
    split = example_distribution(rows, 55.0)
    assert split is not None
    assert sum(split) == pytest.approx(55.0)
    for r, t in zip(rows, split):
        assert r.town_min - 1e-9 <= t <= r.town_max + 1e-9


def test_example_distribution_returns_none_when_infeasible():
    rows = [Row(label="d1", total=100.0, min_highway=30.0)]  # town max 70
    assert example_distribution(rows, 90.0) is None


def test_example_distribution_zero_capacity():
    rows = [Row(label="d1", total=10.0, min_highway=10.0)]  # town fixed at 0
    assert example_distribution(rows, 0.0) == pytest.approx([0.0])


from gasaudit.model import swing_room


def test_swing_room_single_target_value():
    # Exact target (sum_lo == sum_hi). Each row's freedom is bounded by others.
    rows = [
        Row(label="d1", total=100.0, min_highway=0.0),  # town [0,100]
        Row(label="d2", total=100.0, min_highway=0.0),  # town [0,100]
    ]
    swing = swing_room(rows, 80.0, 80.0)  # total town must be 80
    # d1 can be as low as 80-100=-> max(0,-20)=0, as high as min(100, 80-0)=80
    assert swing[0][0] == pytest.approx(0.0)
    assert swing[0][1] == pytest.approx(80.0)
    assert swing[1] == swing[0]


def test_swing_room_band_widens_freedom():
    rows = [
        Row(label="d1", total=100.0, min_highway=0.0),
        Row(label="d2", total=100.0, min_highway=0.0),
    ]
    swing = swing_room(rows, 70.0, 90.0)  # total town in [70,90]
    # d1 high = min(100, 90 - 0) = 90 ; d1 low = max(0, 70 - 100) = 0
    assert swing[0] == (pytest.approx(0.0), pytest.approx(90.0))
