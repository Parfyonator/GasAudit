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
