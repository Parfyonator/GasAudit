import matplotlib
matplotlib.use("Agg")
from streamlit.testing.v1 import AppTest
from gasaudit.rows import RowInput


def test_app_runs_without_exception():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["lang"] = "EN"
    at.run()
    assert not at.exception


def test_app_runs_with_empty_rows():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["lang"] = "EN"
    at.session_state["rows"] = []
    at.run()
    assert not at.exception


def test_slider_drag_redraws_bar_same_run():
    # Regression: the bar above the slider must reflect the dragged value on the SAME
    # rerun (it used to lag by one interaction).
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["lang"] = "EN"
    at.session_state["rows"] = [RowInput(label="day 1", total_mi=200.0, min_highway_mi=0.0)]
    at.run()
    assert at.slider, "expected at least one per-row town slider"
    at.slider[0].set_value(100.0).run()
    assert not at.exception
    assert any("town 100 mi" in m.value for m in at.markdown), \
        "bar did not redraw to the new slider value in the same run"


def test_snap_to_target_moves_sliders():
    # Regression: "Snap to target" must move the slider handles, not just the bars.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["lang"] = "EN"
    # Pre-seed rows that mirror the real CSV data so the period becomes feasible when
    # refuels is set to 98 below (total ~604 mi, town_required ~305 mi ∈ window).
    at.session_state["rows"] = [
        RowInput(label="25-May", total_mi=127.0, min_highway_mi=0.0),
        RowInput(label="26-May", total_mi=53.0, min_highway_mi=0.0),
        RowInput(label="27-May", total_mi=66.0, min_highway_mi=0.0),
        RowInput(label="28-May", total_mi=42.0, min_highway_mi=0.0),
        RowInput(label="29-May", total_mi=31.0, min_highway_mi=0.0),
        RowInput(label="30-May", total_mi=100.0, min_highway_mi=0.0),
        RowInput(label="1-Jun", total_mi=33.0, min_highway_mi=0.0),
        RowInput(label="2-Jun", total_mi=9.0, min_highway_mi=0.0),
        RowInput(label="3-Jun", total_mi=81.0, min_highway_mi=0.0),
        RowInput(label="4-Jun", total_mi=62.0, min_highway_mi=0.0),
    ]
    at.run()
    # Make the period feasible so an example split exists (default config is infeasible).
    for ni in at.number_input:
        if ni.label and "Refuels" in ni.label:
            ni.set_value(98.0)
    at.run()
    snap = [b for b in at.button if b.label == "Snap to target"]
    assert snap, "Snap to target button missing"
    # zero the sliders first so we can prove Snap moved them
    for s in at.slider:
        s.set_value(0.0)
    at.run()
    snap[0].click().run()
    assert not at.exception
    assert any(s.value > 0 for s in at.slider), "Snap did not move the slider handles"


def test_lock_total_keeps_sum_constant_when_one_slider_moves():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["lang"] = "EN"
    at.session_state["rows"] = [
        RowInput(label="day 1", total_mi=200.0, min_highway_mi=0.0),
        RowInput(label="day 2", total_mi=200.0, min_highway_mi=0.0),
    ]
    at.run()
    for ni in at.number_input:
        if ni.label and "Refuels" in ni.label:
            # 60 keeps the 400 mi period feasible (needed 83 L within the 68..92 L band),
            # so town_required ~250 mi seeds both sliders to a non-zero split. With the old
            # 98 the period was infeasible, sliders stayed at 0, and the lock assertion
            # passed vacuously (0 -> 0) without ever exercising the rebalance.
            ni.set_value(60.0)
    at.run()
    for tg in at.toggle:
        if tg.label and "Lock" in tg.label:
            tg.set_value(True)
    at.run()
    before = sum(s.value for s in at.slider)
    assert before > 0, "sliders should seed to a non-zero split for a meaningful lock test"
    s0 = at.slider[0]
    s0.set_value(min(s0.value + 30.0, s0.max)).run()
    assert not at.exception
    after = sum(s.value for s in at.slider)
    assert abs(after - before) < 0.5, f"lock broke: total town {before} -> {after}"
