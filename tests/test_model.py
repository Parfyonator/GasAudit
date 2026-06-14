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
