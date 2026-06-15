import pytest
from gasaudit.io import mi_to_km, km_to_mi, load_rows

# SAMPLE has a fabricated 10th field on the 25-May row (value 80) to exercise the
# "10th field IS present → read min_highway" path. The real production file currently
# has no 10th field on any row, so all defaults are 0 — tested by
# test_real_csv_defaults_min_highway_to_zero below.
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


from gasaudit.model import Row, Params, analyze
from gasaudit.report import summary_text, example_table


def test_summary_text_mentions_feasibility_and_target():
    rows = [Row(label="d1", total=100.0, min_highway=20.0),
            Row(label="d2", total=60.0, min_highway=0.0)]
    p = Params(start_fuel=40.0, end_fuel=40.0 - 30.2, norm=20.0)
    a = analyze(rows, p)
    txt = summary_text(a, work_unit="mi")
    assert "FEASIBLE" in txt.upper()
    assert "50" in txt  # required town distance (miles) appears


def test_example_table_has_row_per_day_and_km(tmp_path):
    rows = [Row(label="d1", total=100.0, min_highway=20.0),
            Row(label="d2", total=60.0, min_highway=0.0)]
    p = Params(start_fuel=40.0, end_fuel=40.0 - 30.2, norm=20.0)
    a = analyze(rows, p)
    table = example_table(rows, a, work_unit="mi")
    assert "d1" in table and "d2" in table
    # km column present: town miles 0..80 -> some km value with 'km' header
    assert "km" in table.lower()


import matplotlib
matplotlib.use("Agg")
from gasaudit.plots import (
    plot_row_bands, plot_fuel_vs_town, plot_swing_widths, plot_tolerance_sensitivity,
)


def _analysis():
    rows = [Row(label="d1", total=100.0, min_highway=20.0),
            Row(label="d2", total=60.0, min_highway=0.0)]
    p = Params(start_fuel=40.0, end_fuel=40.0 - 30.2, norm=20.0, end_fuel_tol=0.3)
    return rows, analyze(rows, p), p


def test_all_plots_build_figures():
    rows, a, p = _analysis()
    for fig in (
        plot_row_bands(rows, a),
        plot_fuel_vs_town(a),
        plot_swing_widths(rows, a),
        plot_tolerance_sensitivity(rows, p),
    ):
        assert fig is not None
        assert len(fig.axes) >= 1


def test_plots_and_report_survive_infeasible():
    rows = [Row(label="d1", total=100.0, min_highway=80.0),
            Row(label="d2", total=60.0, min_highway=50.0)]
    p = Params(start_fuel=50.0, end_fuel=5.0, norm=20.0)  # demands far more town than possible
    a = analyze(rows, p)
    assert not a.feasible and a.example is None
    assert "INFEASIBLE" in summary_text(a, "mi")
    assert "nan" in example_table(rows, a, "mi")
    for fig in (plot_row_bands(rows, a), plot_fuel_vs_town(a), plot_swing_widths(rows, a)):
        assert fig is not None


def test_real_csv_defaults_min_highway_to_zero():
    rows = load_rows("supp_mat/ПАЛИВО_ОБЛІК.csv")
    assert len(rows) >= 1
    assert all(r.min_highway == 0.0 for r in rows)


from gasaudit.io import load_rows_from_text


def test_load_rows_from_text_matches_load_rows(tmp_path):
    f = tmp_path / "fuel.csv"
    f.write_text(SAMPLE, encoding="utf-8")
    from_path = load_rows(str(f))
    from_text = load_rows_from_text(SAMPLE)
    assert [r.label for r in from_text] == [r.label for r in from_path]
    assert from_text[0].total == pytest.approx(from_path[0].total)
    assert from_text[0].min_highway == pytest.approx(from_path[0].min_highway)


def test_load_rows_from_text_converts_to_km():
    rows = load_rows_from_text(SAMPLE, to_unit="km")
    assert rows[0].total == pytest.approx(mi_to_km(127.0))


def test_fuel_vs_town_accepts_custom_labels():
    rows, a, p = _analysis()
    labels = {
        "required_town": "RT", "required_town_off": "RT off",
        "tolerance_band": "TB", "feasible_window": "FW",
        "xlabel": "X", "ylabel": "Y", "title": "T",
    }
    fig = plot_fuel_vs_town(a, labels)
    ax = fig.axes[0]
    assert ax.get_xlabel() == "X"
    assert ax.get_ylabel() == "Y"
    assert ax.get_title() == "T"
