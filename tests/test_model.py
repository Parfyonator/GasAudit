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
