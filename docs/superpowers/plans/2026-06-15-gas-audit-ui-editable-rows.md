# Editable Rows & Redesigned Interactive UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user manage report rows directly in the Streamlit UI (add / delete / ▲▼ reorder, CSV optional) and replace the plain sliders with labeled town/out-of-town bars (miles + km + liters), a 2-column totals table, and dual CSV export.

**Architecture:** A new pure module `gasaudit/rows.py` holds all workflow logic (row records, unit conversion, per-row segments, totals, add/delete/move, bar HTML, exports) and is fully unit-tested. `app.py` is rewritten as a thin Streamlit layer over it. The existing `model.py`/`io.py`/`report.py`/`plots.py`/`main.py` are unchanged.

**Tech Stack:** Python 3.13, Streamlit 1.58 (`st.dialog`, material icons, `download_button`), pandas, matplotlib, pytest.

---

## File Structure

- `gasaudit/rows.py` — NEW. Pure logic: `RowInput`, conversions, `row_segments`, `totals`, `to_model_rows`, add/delete/move, `bar_html`, `computed_table_df`, `input_csv_df`.
- `app.py` — REWRITTEN. Streamlit wiring only.
- `tests/test_rows.py` — NEW. Unit tests for `gasaudit/rows.py`.
- `tests/test_app.py` — UPDATED. AppTest smoke for the rewritten app.
- Everything else unchanged.

## Conventions

- `RowInput` distances are **always miles** (canonical). `unit` ∈ {`"mi"`,`"km"`} is the working/display unit.
- `MI_TO_KM = 1.609344` is reused from `gasaudit.io`.
- Liters use the working unit: `town_l = town_dist_in_unit × rates.town`, `out_l = out_dist_in_unit × rates.highway`.
- Run tests/python with `venv/bin/python`.

---

## Task 1: RowInput, unit helpers, clamp

**Files:**
- Create: `gasaudit/rows.py`
- Test: `tests/test_rows.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rows.py`:

```python
import pytest
from gasaudit.rows import RowInput, to_unit, from_unit, clamp_town


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gasaudit.rows'`.

- [ ] **Step 3: Write minimal implementation**

Create `gasaudit/rows.py`:

```python
"""Pure logic for the editable-row UI workflow. No Streamlit, no I/O side effects.

RowInput distances are always MILES (canonical). `unit` ('mi'|'km') is the display unit.
"""
from __future__ import annotations

from dataclasses import dataclass

from gasaudit.io import MI_TO_KM


@dataclass
class RowInput:
    label: str
    total_mi: float
    min_highway_mi: float = 0.0
    town_mi: float = 0.0


def to_unit(value_mi: float, unit: str) -> float:
    """Miles -> working unit."""
    return value_mi if unit == "mi" else value_mi * MI_TO_KM


def from_unit(value: float, unit: str) -> float:
    """Working unit -> miles."""
    return value if unit == "mi" else value / MI_TO_KM


def clamp_town(row: RowInput) -> None:
    """Clamp town_mi into [0, total_mi - min_highway_mi] in place."""
    hi = row.total_mi - row.min_highway_mi
    row.town_mi = min(max(row.town_mi, 0.0), hi)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/rows.py tests/test_rows.py
git commit -m "feat: RowInput, unit conversion, clamp_town"
```

---

## Task 2: row_segments and totals

**Files:**
- Modify: `gasaudit/rows.py`
- Test: `tests/test_rows.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rows.py`:

```python
from gasaudit.model import rates_from_norm
from gasaudit.rows import RowSegments, row_segments, totals


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: FAIL — `ImportError: cannot import name 'RowSegments'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/rows.py`:

```python
from gasaudit.model import Rates, Row


@dataclass(frozen=True)
class RowSegments:
    label: str
    town_mi: float
    town_km: float
    town_l: float
    out_mi: float
    out_km: float
    out_l: float
    total_l: float
    town_frac: float


def row_segments(row: RowInput, unit: str, rates: Rates) -> RowSegments:
    clamp_town(row)
    town_mi = row.town_mi
    out_mi = row.total_mi - row.town_mi
    town_km = town_mi * MI_TO_KM
    out_km = out_mi * MI_TO_KM
    town_dist = town_mi if unit == "mi" else town_km
    out_dist = out_mi if unit == "mi" else out_km
    town_l = town_dist * rates.town
    out_l = out_dist * rates.highway
    frac = town_mi / row.total_mi if row.total_mi > 0 else 0.0
    return RowSegments(
        label=row.label, town_mi=town_mi, town_km=town_km, town_l=town_l,
        out_mi=out_mi, out_km=out_km, out_l=out_l, total_l=town_l + out_l,
        town_frac=frac,
    )


@dataclass(frozen=True)
class Totals:
    town_mi: float
    town_km: float
    town_l: float
    out_mi: float
    out_km: float
    out_l: float
    grand_l: float


def totals(rows: list[RowInput], unit: str, rates: Rates) -> Totals:
    segs = [row_segments(r, unit, rates) for r in rows]
    town_mi = sum(s.town_mi for s in segs)
    town_km = sum(s.town_km for s in segs)
    town_l = sum(s.town_l for s in segs)
    out_mi = sum(s.out_mi for s in segs)
    out_km = sum(s.out_km for s in segs)
    out_l = sum(s.out_l for s in segs)
    return Totals(town_mi, town_km, town_l, out_mi, out_km, out_l, town_l + out_l)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/rows.py tests/test_rows.py
git commit -m "feat: row_segments and totals"
```

---

## Task 3: to_model_rows and row management (add/delete/move)

**Files:**
- Modify: `gasaudit/rows.py`
- Test: `tests/test_rows.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rows.py`:

```python
from gasaudit.model import Row
from gasaudit.rows import to_model_rows, add_row, delete_row, move_up, move_down


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: FAIL — `ImportError: cannot import name 'to_model_rows'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/rows.py`:

```python
def to_model_rows(rows: list[RowInput], unit: str) -> list[Row]:
    return [
        Row(label=r.label, total=to_unit(r.total_mi, unit),
            min_highway=to_unit(r.min_highway_mi, unit), town_min=0.0)
        for r in rows
    ]


def add_row(rows: list[RowInput], label: str, total_mi: float,
            min_highway_mi: float) -> list[RowInput]:
    row = RowInput(label=label, total_mi=total_mi,
                   min_highway_mi=min(min_highway_mi, total_mi), town_mi=0.0)
    clamp_town(row)
    rows.append(row)
    return rows


def delete_row(rows: list[RowInput], i: int) -> list[RowInput]:
    if 0 <= i < len(rows):
        del rows[i]
    return rows


def move_up(rows: list[RowInput], i: int) -> list[RowInput]:
    if 0 < i < len(rows):
        rows[i - 1], rows[i] = rows[i], rows[i - 1]
    return rows


def move_down(rows: list[RowInput], i: int) -> list[RowInput]:
    if 0 <= i < len(rows) - 1:
        rows[i + 1], rows[i] = rows[i], rows[i + 1]
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/rows.py tests/test_rows.py
git commit -m "feat: to_model_rows and add/delete/move row management"
```

---

## Task 4: bar_html

**Files:**
- Modify: `gasaudit/rows.py`
- Test: `tests/test_rows.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rows.py`:

```python
from gasaudit.rows import bar_html


def test_bar_html_contains_numbers_and_width():
    rates = rates_from_norm(20.0)
    r = RowInput(label="d1", total_mi=127.0, min_highway_mi=80.0, town_mi=47.0)
    seg = row_segments(r, "mi", rates)
    html = bar_html(seg)
    assert "47" in html and "80" in html          # town/out miles
    assert "76" in html and "129" in html          # town/out km (rounded)
    assert "width:37" in html or "width: 37" in html  # town_frac ~0.37 -> 37%
    assert "24.4" in html                           # total liters rounded


def test_bar_html_pure_town_row_has_no_out_segment():
    rates = rates_from_norm(20.0)
    r = RowInput(label="d2", total_mi=53.0, min_highway_mi=0.0, town_mi=53.0)
    seg = row_segments(r, "mi", rates)
    html = bar_html(seg)
    assert "width:100" in html or "width: 100" in html
    assert "out " not in html  # no out-of-town segment label
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: FAIL — `ImportError: cannot import name 'bar_html'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/rows.py`:

```python
def bar_html(seg: RowSegments) -> str:
    """Labeled two-segment bar (red town, grey out) + row-total liters, as inline-styled HTML."""
    town_pct = round(seg.town_frac * 100)
    out_pct = 100 - town_pct
    parts = []
    if town_pct > 0:
        parts.append(
            f'<div style="width:{town_pct}%;background:#d24b4b;color:#fff;'
            'display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'line-height:1.2;overflow:hidden;">'
            f'<b style="font-size:13px;white-space:nowrap;">town {seg.town_mi:.0f} mi · '
            f'{seg.town_km:.0f} km</b>'
            f'<small style="font-size:11px;opacity:.9;">({seg.town_l:.1f} L)</small></div>'
        )
    if out_pct > 0:
        parts.append(
            f'<div style="width:{out_pct}%;background:#c9d2d9;color:#243;'
            'display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'line-height:1.2;overflow:hidden;">'
            f'<b style="font-size:13px;white-space:nowrap;">out {seg.out_mi:.0f} mi · '
            f'{seg.out_km:.0f} km</b>'
            f'<small style="font-size:11px;opacity:.9;">({seg.out_l:.1f} L)</small></div>'
        )
    bar = (
        '<div style="display:flex;height:46px;border-radius:6px;overflow:hidden;'
        'box-shadow:inset 0 0 0 1px rgba(0,0,0,.15);flex:1;">' + "".join(parts) + "</div>"
    )
    return (
        '<div style="display:flex;align-items:center;">' + bar +
        f'<div style="min-width:74px;text-align:right;padding-left:12px;'
        f'font-weight:700;font-size:15px;">{seg.total_l:.1f} L</div></div>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/rows.py tests/test_rows.py
git commit -m "feat: bar_html labeled segment bar"
```

---

## Task 5: CSV exports (computed + re-importable) and rows_from_csv

**Files:**
- Modify: `gasaudit/rows.py`
- Test: `tests/test_rows.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rows.py`:

```python
from gasaudit.io import load_rows
from gasaudit.rows import computed_table_df, input_csv_df, rows_from_csv


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: FAIL — `ImportError: cannot import name 'computed_table_df'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/rows.py` (add `import pandas as pd` and `from gasaudit.io import load_rows` to the imports at the top of the file):

```python
def rows_from_csv(path: str) -> list[RowInput]:
    """Seed RowInputs from the CSV (miles); town_mi defaults to 0 (caller re-seeds)."""
    model_rows = load_rows(path, to_unit="mi")
    return [
        RowInput(label=m.label, total_mi=m.total, min_highway_mi=m.min_highway, town_mi=0.0)
        for m in model_rows
    ]


def computed_table_df(rows: list[RowInput], unit: str, rates: Rates) -> "pd.DataFrame":
    segs = [row_segments(r, unit, rates) for r in rows]
    data = [
        {
            "date": s.label,
            f"total {unit}": (s.town_mi + s.out_mi) if unit == "mi"
            else (s.town_km + s.out_km),
            f"town {unit}": s.town_mi if unit == "mi" else s.town_km,
            "town km": s.town_km,
            "town L": round(s.town_l, 2),
            f"out {unit}": s.out_mi if unit == "mi" else s.out_km,
            "out km": s.out_km,
            "out L": round(s.out_l, 2),
            "row L": round(s.total_l, 2),
        }
        for s in segs
    ]
    return pd.DataFrame(data)


def input_csv_df(rows: list[RowInput]) -> "pd.DataFrame":
    """Re-importable CSV (10 columns, ';' on export) round-tripping through io.load_rows.

    Columns 0..9: date, odo_start, odo_end, total_mi, route, town_mi, hwy_mi,
    town_km, hwy_km, min_highway_mi. Odometer synthesized cumulatively from 0.
    Totals must be (near-)integer to survive load_rows' int() parsing.
    """
    records = []
    cursor = 0
    for r in rows:
        delta = int(round(r.total_mi))
        odo_start, odo_end = cursor, cursor + delta
        cursor = odo_end
        out_mi = r.total_mi - r.town_mi
        records.append([
            r.label, odo_start, odo_end, delta, "",
            round(r.town_mi, 1), round(out_mi, 1),
            round(r.town_mi * MI_TO_KM, 1), round(out_mi * MI_TO_KM, 1),
            round(r.min_highway_mi, 1),
        ])
    cols = ["date", "odo_start", "odo_end", "total_mi", "route",
            "town_mi", "hwy_mi", "town_km", "hwy_km", "min_highway_mi"]
    return pd.DataFrame(records, columns=cols)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_rows.py -q`
Expected: PASS (15 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/rows.py tests/test_rows.py
git commit -m "feat: CSV exports and rows_from_csv seeding"
```

---

## Task 6: Rewrite app.py

**Files:**
- Rewrite: `app.py`
- Test: `tests/test_app.py` (update)

- [ ] **Step 1: Write the rewritten app.py**

Replace the entire contents of `app.py` with:

```python
"""Interactive wiggle-room explorer. Run: venv/bin/streamlit run app.py"""
from __future__ import annotations

import tomllib

import streamlit as st

from gasaudit.model import Params, analyze, rates_from_norm
from gasaudit.plots import plot_fuel_vs_town
from gasaudit import rows as R

st.set_page_config(page_title="Gas Audit Wiggle Room", layout="wide")
st.title("Gas Audit — Town/Highway Wiggle Room")

with open("config.toml", "rb") as fh:
    cfg = tomllib.load(fh)

# --- sidebar params ---
with st.sidebar:
    st.header("Period parameters")
    csv_path = st.text_input("CSV path", cfg["csv_path"])
    unit = st.selectbox("Norm unit", ["mi", "km"],
                        index=0 if cfg["norm"]["unit"] == "mi" else 1)
    norm = st.number_input("Norm (L / 100 unit)", value=float(cfg["norm"]["value"]))
    uplift = st.number_input("Uplift (town +, highway -)",
                             value=float(cfg["norm"]["uplift"]), step=0.01)
    start_fuel = st.number_input("Start fuel (L)", value=float(cfg["fuel"]["start_fuel"]))
    end_fuel = st.number_input("End fuel (L, pinned)", value=float(cfg["fuel"]["end_fuel"]))
    refuels = st.number_input("Refuels (L)", value=float(cfg["fuel"]["refuels"]))
    tol = st.number_input("End-fuel tolerance (±L)",
                          value=float(cfg["fuel"]["end_fuel_tol"]), step=0.1)
    st.divider()
    if st.button("Import CSV"):
        try:
            st.session_state.rows = R.rows_from_csv(csv_path)
            st.session_state.pop("seeded", None)
        except Exception as exc:  # noqa: BLE001 - surface any load failure to the user
            st.error(f"Could not load CSV: {exc}")
    if st.button("Clear rows"):
        st.session_state.rows = []

rates = rates_from_norm(norm, uplift)
params = Params(start_fuel=start_fuel, end_fuel=end_fuel, refuels=refuels,
                end_fuel_tol=tol, norm=norm, norm_unit=unit, uplift=uplift)

# --- session rows: seed from CSV once on first run ---
if "rows" not in st.session_state:
    try:
        st.session_state.rows = R.rows_from_csv(csv_path)
    except Exception:  # noqa: BLE001
        st.session_state.rows = []
rows = st.session_state.rows

# analysis on the model view (feasibility + example seed)
a = analyze(R.to_model_rows(rows, unit), params)

# one-time seed of town splits from the example distribution
if rows and not st.session_state.get("seeded") and a.example is not None:
    for r, ex in zip(rows, a.example):
        r.town_mi = R.from_unit(ex, unit)
        R.clamp_town(r)
    st.session_state.seeded = True

# red trash-button styling (best-effort: colors any button whose label is the delete icon)
st.markdown(
    "<style>div[data-testid='stButton'] button:has(span[data-testid='stIconMaterial'])"
    "{color:#d24b4b;border-color:#d24b4b;}</style>", unsafe_allow_html=True,
)

# --- feasibility banner ---
if a.feasible:
    st.success(f"FEASIBLE — required total town distance {a.town_required:.1f} {unit} "
               f"within window {a.feasible_window[0]:.0f}…{a.feasible_window[1]:.0f} {unit}")
else:
    st.error(f"INFEASIBLE — required town {a.town_required:.1f} {unit} outside window "
             f"{a.feasible_window[0]:.0f}…{a.feasible_window[1]:.0f} {unit}")

if rows and all(r.min_highway_mi == 0 for r in rows):
    st.info("No per-row highway minimums set — town share can range 0..total each day "
            "(widest window). Add minimums to constrain it.")

# --- add-row modal ---
@st.dialog("Add row")
def _add_row_dialog():
    label = st.text_input("Date", value=f"row {len(rows) + 1}")
    total = st.number_input(f"Total distance ({unit})", min_value=0.0, value=0.0, step=1.0)
    minhw = st.number_input(f"Min highway ({unit})", min_value=0.0, value=0.0, step=1.0)
    c1, c2 = st.columns(2)
    if c1.button("Add", type="primary"):
        if total <= 0:
            st.error("Total must be greater than 0.")
        else:
            R.add_row(rows, label, R.from_unit(total, unit), R.from_unit(minhw, unit))
            st.rerun()
    if c2.button("Cancel"):
        st.rerun()

# --- snap + add controls ---
st.subheader("Per-row town / out-of-town split")
cc1, cc2 = st.columns(2)
if cc1.button("Snap to target") and a.example is not None:
    for r, ex in zip(rows, a.example):
        r.town_mi = R.from_unit(ex, unit)
        R.clamp_town(r)
    st.rerun()
if cc2.button("➕ Add row"):
    _add_row_dialog()

# --- per-row blocks ---
# Widget keys use id(r) (stable per row object across reruns) so slider state stays
# bound to the right row after delete / reorder — index-based keys would go stale.
for i, r in enumerate(rows):
    c_del, c_mv, c_main = st.columns([0.06, 0.06, 0.88])
    if c_del.button(":material/delete:", key=f"del{id(r)}", help="Delete row"):
        R.delete_row(rows, i)
        st.rerun()
    if c_mv.button("▲", key=f"up{id(r)}", help="Move up"):
        R.move_up(rows, i)
        st.rerun()
    if c_mv.button("▼", key=f"down{id(r)}", help="Move down"):
        R.move_down(rows, i)
        st.rerun()
    with c_main:
        st.caption(
            f"{r.label} · total {R.to_unit(r.total_mi, unit):.0f} {unit} "
            f"({r.total_mi * R.MI_TO_KM:.0f} km) · min highway "
            f"{R.to_unit(r.min_highway_mi, unit):.0f} {unit}"
        )
        seg = R.row_segments(r, unit, rates)
        st.markdown(R.bar_html(seg), unsafe_allow_html=True)
        town_max = R.to_unit(r.total_mi - r.min_highway_mi, unit)
        if town_max <= 1e-9:
            st.caption("town fixed at 0 — no wiggle room")
        else:
            val = st.slider(
                "town", min_value=0.0, max_value=float(town_max),
                value=float(min(R.to_unit(r.town_mi, unit), town_max)),
                key=f"town{id(r)}", label_visibility="collapsed",
            )
            r.town_mi = R.from_unit(val, unit)

# --- totals table ---
t = R.totals(rows, unit, rates)
st.subheader("Totals")
st.table({
    "": ["Distance (mi)", "Distance (km)", "Fuel (L)"],
    "In town": [f"{t.town_mi:.0f}", f"{t.town_km:.0f}", f"{t.town_l:.1f}"],
    "Out of town": [f"{t.out_mi:.0f}", f"{t.out_km:.0f}", f"{t.out_l:.1f}"],
})

implied_end = start_fuel + refuels - t.grand_l
m1, m2 = st.columns(2)
m1.metric("Grand total fuel", f"{t.grand_l:.1f} L")
m2.metric("Implied end fuel", f"{implied_end:.2f} L", f"{implied_end - end_fuel:+.2f} vs pinned")
within = abs(implied_end - end_fuel) <= tol + 1e-9
st.write("✅ End fuel matches the pinned target (within tolerance)." if within
         else "⚠️ End fuel does not match yet — adjust the splits.")

# --- export ---
e1, e2 = st.columns(2)
e1.download_button(
    "Export computed table (CSV)",
    R.computed_table_df(rows, unit, rates).to_csv(index=False),
    file_name="gas_audit_computed.csv", mime="text/csv",
)
e2.download_button(
    "Export input CSV (re-importable)",
    R.input_csv_df(rows).to_csv(index=False, sep=";"),
    file_name="gas_audit_input.csv", mime="text/csv",
)

# --- context plot ---
st.pyplot(plot_fuel_vs_town(a))
```

- [ ] **Step 2: Add `MI_TO_KM` re-export to rows.py so `R.MI_TO_KM` works**

In `gasaudit/rows.py`, confirm the top imports include `from gasaudit.io import MI_TO_KM` (added in Task 1). `R.MI_TO_KM` resolves through the module namespace, so no extra code is needed. Verify by running:
Run: `venv/bin/python -c "from gasaudit import rows; print(rows.MI_TO_KM)"`
Expected: `1.609344`

- [ ] **Step 3: Update the AppTest smoke test**

Replace `tests/test_app.py` with:

```python
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
```

- [ ] **Step 4: Run the AppTest and the full suite**

Run: `venv/bin/python -m pytest tests/test_app.py -q`
Expected: PASS (2 passed) — app executes end-to-end with the real CSV and with empty rows.

Run: `venv/bin/python -m pytest -q`
Expected: all pass (model 18 + io/report/plots 6 + rows 15 + app 2 = 41).

- [ ] **Step 5: Launch the app manually to eyeball it**

Run: `venv/bin/streamlit run app.py`
Expected: feasibility banner; per-row blocks each with a red trash button, ▲/▼, a labeled red/grey bar (town/out mi·km + liters) with row-total liters at the right, and a slider beneath; "➕ Add row" opens the modal with Date/Total/Min; the totals table (In town | Out of town); two export buttons that download CSVs; the fuel-vs-town plot at the bottom. Drag a slider → the bar and the "Implied end fuel" update.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: rewrite app with editable rows, labeled bars, totals table, export"
```

---

## Task 7: README update and final full-suite run

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the README "Run" section**

In `README.md`, under the interactive-app description, replace the sentence about dragging
sliders with:

```markdown
In the interactive app you can import the CSV or build rows by hand: add rows (➕ opens a
Date / Total / Min-highway modal), delete (red trash button) or reorder (▲/▼) them, and drag
each row's slider to set the town / out-of-town split. Each row shows a labeled bar (miles, km,
litres per segment) and its total litres; the totals table and "implied end fuel" update live.
Export the computed table or a re-importable input CSV with the export buttons.
```

- [ ] **Step 2: Run the full suite**

Run: `venv/bin/python -m pytest -q`
Expected: all pass (41).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document editable-row interactive UI"
```

---

## Self-Review notes (already reconciled)

- **Spec coverage:** editable rows (Task 3 add/delete/move; Task 6 UI), CSV optional + import
  (Task 5 `rows_from_csv`, Task 6 sidebar), labeled bars mi+km+liters (Task 2 segments, Task 4
  `bar_html`, Task 6 render), row-total liters (bar_html), 2-column totals table (Task 2
  `totals`, Task 6 `st.table`), dual export (Task 5, Task 6 download buttons), add-row modal
  (Task 6 `st.dialog`), ▲/▼ reorder (Task 3, Task 6), canonical-miles storage + mi/km toggle
  (Task 1 conversions used throughout), fuel-vs-town plot kept (Task 6).
- **Naming consistency:** `RowInput`, `to_unit`, `from_unit`, `clamp_town`, `RowSegments`,
  `row_segments`, `Totals`, `totals`, `to_model_rows`, `add_row`, `delete_row`, `move_up`,
  `move_down`, `bar_html`, `rows_from_csv`, `computed_table_df`, `input_csv_df` — used
  identically across tasks. App imports the module as `R` and `MI_TO_KM` resolves via `R.MI_TO_KM`.
- **Out of scope (per spec):** drag-the-bar component, drag-and-drop reorder, inline row edit,
  auto-persist to disk.
```
