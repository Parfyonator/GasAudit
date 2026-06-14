import pytest
from gasaudit.io import mi_to_km, km_to_mi, load_rows

SAMPLE = """;Показник спідометра;Залишок пального;;;;;;
;175010;63;;;;;;
;;;;;;;;
;;;;;місто в милях;траса в милях;місто в км;траса км
25-May;175010;175137;127;ПТД-Клавдієво-ПТД;47;80;76;129;80
26-May;175137;175190;53;ПТД;53;;85;0
5-Jun;;;;;;;575;343
;0;;;;;;;
"""


def test_mi_km_roundtrip():
    assert mi_to_km(100.0) == pytest.approx(160.9344)
    assert km_to_mi(mi_to_km(100.0)) == pytest.approx(100.0)


def test_load_rows_picks_only_data_rows(tmp_path):
    f = tmp_path / "fuel.csv"
    f.write_text(SAMPLE, encoding="utf-8")
    rows = load_rows(str(f))
    assert [r.label for r in rows] == ["25-May", "26-May"]
    assert rows[0].total == pytest.approx(127.0)
    assert rows[0].min_highway == pytest.approx(80.0)  # column 9
    assert rows[0].route == "ПТД-Клавдієво-ПТД"
    assert rows[1].min_highway == pytest.approx(0.0)   # missing -> 0


def test_load_rows_converts_to_km_when_requested(tmp_path):
    f = tmp_path / "fuel.csv"
    f.write_text(SAMPLE, encoding="utf-8")
    rows = load_rows(str(f), to_unit="km")
    assert rows[0].total == pytest.approx(mi_to_km(127.0))
    assert rows[0].min_highway == pytest.approx(mi_to_km(80.0))
