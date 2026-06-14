import pytest
from gasaudit.rows import (
    RowInput, to_unit, from_unit, clamp_town,
    RowSegments, row_segments, totals,
    to_model_rows, add_row, update_row, delete_row, move_up, move_down, rebalance,
    bar_html,
    computed_table_df, input_csv_df, rows_from_csv,
)


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


from gasaudit.model import Row


def test_to_model_rows_converts_units():
    rows = [RowInput(label="d1", total_mi=100.0, min_highway_mi=20.0, town_mi=30.0)]
    mr_mi = to_model_rows(rows, "mi")
    assert isinstance(mr_mi[0], Row)
    assert mr_mi[0].total == pytest.approx(100.0)
    assert mr_mi[0].min_highway == pytest.approx(20.0)
    mr_km = to_model_rows(rows, "km")
    assert mr_km[0].total == pytest.approx(100.0 * 1.609344)
    assert mr_km[0].min_highway == pytest.approx(20.0 * 1.609344)


def test_add_row_appends_and_clamps():
    rows = []
    add_row(rows, "d1", 100.0, 30.0)
    assert len(rows) == 1
    assert rows[0].label == "d1"
    assert rows[0].town_mi == pytest.approx(0.0)  # seeded 0, within [0,70]
    assert rows[0].min_highway_mi == pytest.approx(30.0)


def test_delete_row_removes_index():
    rows = [RowInput("a", 10.0), RowInput("b", 20.0), RowInput("c", 30.0)]
    delete_row(rows, 1)
    assert [r.label for r in rows] == ["a", "c"]


def test_move_up_down_and_boundaries():
    rows = [RowInput("a", 1.0), RowInput("b", 2.0), RowInput("c", 3.0)]
    move_up(rows, 2)
    assert [r.label for r in rows] == ["a", "c", "b"]
    move_down(rows, 0)
    assert [r.label for r in rows] == ["c", "a", "b"]
    move_up(rows, 0)   # boundary no-op
    assert [r.label for r in rows] == ["c", "a", "b"]
    move_down(rows, 2) # boundary no-op
    assert [r.label for r in rows] == ["c", "a", "b"]


def test_rebalance_preserves_sum_proportionally():
    # index 0 was raised 20->50 (sum now 150); lock target is the old total 120
    out = rebalance([50.0, 40.0, 60.0], [100.0, 100.0, 100.0], 0, 120.0)
    assert sum(out) == pytest.approx(120.0)
    assert out[0] == pytest.approx(50.0)        # moved entry unchanged
    assert out[1] == pytest.approx(28.0)        # 40 - 30*40/100
    assert out[2] == pytest.approx(42.0)        # 60 - 30*60/100


def test_rebalance_grows_others_when_moved_decreased():
    # index 0 lowered 50->10 (sum now 110); target is old total 150
    out = rebalance([10.0, 40.0, 60.0], [100.0, 100.0, 100.0], 0, 150.0)
    assert sum(out) == pytest.approx(150.0)
    assert out[0] == pytest.approx(10.0)
    assert out[1] == pytest.approx(64.0)        # +40*60/100
    assert out[2] == pytest.approx(76.0)        # +40*40/100


def test_rebalance_pulls_moved_when_others_exhausted():
    # others can only give 10 total; moved must come back so the total holds
    out = rebalance([90.0, 5.0, 5.0], [100.0, 10.0, 10.0], 0, 20.0)
    assert sum(out) == pytest.approx(20.0)
    assert out[1] == pytest.approx(0.0) and out[2] == pytest.approx(0.0)
    assert out[0] == pytest.approx(20.0)        # pulled back from 90


def test_rebalance_pool_restricts_to_rows_below():
    # moved index 1 (raised 30->50, sum now 130); old total 110; only index 2 may absorb,
    # index 0 (above) stays fixed.
    out = rebalance([20.0, 50.0, 60.0], [100.0, 100.0, 100.0], 1, 110.0, pool=[2])
    assert out[0] == pytest.approx(20.0)   # row above untouched
    assert out[1] == pytest.approx(50.0)   # moved row kept
    assert out[2] == pytest.approx(40.0)   # only this row absorbed the change
    assert sum(out) == pytest.approx(110.0)


def test_rebalance_empty_pool_pulls_moved_back():
    # last row moved with nothing below to absorb -> moved reverts to hold the total
    out = rebalance([20.0, 50.0, 80.0], [100.0, 100.0, 100.0], 2, 100.0, pool=[])
    assert out == pytest.approx([20.0, 50.0, 30.0])


def test_update_row_edits_and_reclamps():
    rows = [RowInput(label="d1", total_mi=100.0, min_highway_mi=20.0, town_mi=70.0)]
    update_row(rows, 0, "d1-new", 60.0, 50.0)
    r = rows[0]
    assert r.label == "d1-new"
    assert r.total_mi == pytest.approx(60.0)
    assert r.min_highway_mi == pytest.approx(50.0)
    assert r.town_mi == pytest.approx(10.0)  # re-clamped to total - min_highway = 10
    # min_highway clamped to total
    update_row(rows, 0, "d1-new", 40.0, 999.0)
    assert rows[0].min_highway_mi == pytest.approx(40.0)
    assert rows[0].town_mi == pytest.approx(0.0)


def test_bar_html_contains_numbers_and_width():
    rates = rates_from_norm(20.0)
    r = RowInput(label="d1", total_mi=127.0, min_highway_mi=80.0, town_mi=47.0)
    seg = row_segments(r, "mi", rates)
    html = bar_html(seg)
    assert "47" in html and "80" in html          # town/out miles
    assert "76" in html and "129" in html          # town/out km (rounded)
    assert "width:37" in html or "width: 37" in html  # town_frac ~0.37 -> 37%
    assert "(10.8 L)" in html and "(13.6 L)" in html   # per-segment liters
    assert "width:100%" in html                         # full-width bar


def test_bar_html_pure_town_row_has_no_out_segment():
    rates = rates_from_norm(20.0)
    r = RowInput(label="d2", total_mi=53.0, min_highway_mi=0.0, town_mi=53.0)
    seg = row_segments(r, "mi", rates)
    html = bar_html(seg)
    assert "width:100" in html or "width: 100" in html
    assert "out " not in html  # no out-of-town segment label


def test_bar_html_zero_total_row_has_no_segments():
    rates = rates_from_norm(20.0)
    r = RowInput(label="z", total_mi=0.0, min_highway_mi=0.0, town_mi=0.0)
    html = bar_html(row_segments(r, "mi", rates))
    assert "town " not in html and "out " not in html  # no ghost segments
    assert "height:46px" in html  # bar container still renders (empty)


from gasaudit.io import load_rows


def test_computed_table_df_columns_and_values():
    rates = rates_from_norm(20.0)
    rows = [RowInput(label="d1", total_mi=100.0, min_highway_mi=20.0, town_mi=30.0)]
    df = computed_table_df(rows, "mi", rates)
    assert list(df.columns) == [
        "date", "total mi", "town mi", "town km", "town L",
        "out mi", "out km", "out L", "row L",
    ]
    assert df.iloc[0]["town mi"] == pytest.approx(30.0)
    assert df.iloc[0]["out mi"] == pytest.approx(70.0)
    assert df.iloc[0]["row L"] == pytest.approx(30.0 * 0.23 + 70.0 * 0.17)


def test_computed_table_df_empty_keeps_headers():
    rates = rates_from_norm(20.0)
    df = computed_table_df([], "mi", rates)
    assert list(df.columns) == [
        "date", "total mi", "town mi", "town km", "town L",
        "out mi", "out km", "out L", "row L",
    ]
    assert len(df) == 0


def test_input_csv_df_roundtrips_through_load_rows(tmp_path):
    rows = [
        RowInput(label="d1", total_mi=127.0, min_highway_mi=80.0, town_mi=47.0),
        RowInput(label="d2", total_mi=53.0, min_highway_mi=0.0, town_mi=53.0),
    ]
    df = input_csv_df(rows)
    f = tmp_path / "out.csv"
    df.to_csv(f, index=False, sep=";")
    reloaded = load_rows(str(f))
    assert [r.label for r in reloaded] == ["d1", "d2"]
    assert reloaded[0].total == pytest.approx(127.0)
    assert reloaded[0].min_highway == pytest.approx(80.0)
    assert reloaded[1].total == pytest.approx(53.0)


def test_rows_from_csv_reads_real_file():
    rows = rows_from_csv("supp_mat/ПАЛИВО_ОБЛІК.csv")
    assert len(rows) >= 1
    assert all(isinstance(r, RowInput) for r in rows)
    assert rows[0].total_mi == pytest.approx(127.0)
    assert all(r.town_mi == 0.0 for r in rows)  # seeded 0; app re-seeds to example
