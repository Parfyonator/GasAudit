import matplotlib
matplotlib.use("Agg")
from streamlit.testing.v1 import AppTest


def test_app_runs_without_exception():
    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert not at.exception


def test_app_runs_with_empty_rows():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["rows"] = []
    at.run()
    assert not at.exception


def test_slider_drag_redraws_bar_same_run():
    # Regression: the bar above the slider must reflect the dragged value on the SAME
    # rerun (it used to lag by one interaction).
    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert at.slider, "expected at least one per-row town slider"
    at.slider[0].set_value(100.0).run()
    assert not at.exception
    assert any("town 100 mi" in m.value for m in at.markdown), \
        "bar did not redraw to the new slider value in the same run"


def test_snap_to_target_moves_sliders():
    # Regression: "Snap to target" must move the slider handles, not just the bars.
    at = AppTest.from_file("app.py", default_timeout=30).run()
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
