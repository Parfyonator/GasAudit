# Gas Audit Wiggle-Room Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tool that, given a reporting period's pinned start/end fuel, refuels, and per-day mileages, computes how much the town/highway split can vary per row (the "wiggle room"), checks feasibility against per-row highway minimums, and presents it interactively (Streamlit) plus as static plots.

**Architecture:** A pure, unit-tested math core (`gasaudit/model.py`) computes rates, the forced total town distance, per-row feasible bands, swing room, feasibility, and an example valid split. Thin layers sit on top: CSV loading (`io.py`), text reporting (`report.py`), matplotlib charts (`plots.py`), a Streamlit app (`app.py`, primary interface), and a CLI (`main.py`). The model is distance-unit-agnostic — callers convert to the norm's unit before calling it; reporting converts back to km for display.

**Tech Stack:** Python 3.13, numpy, pandas, matplotlib, streamlit, pytest. Config via `config.toml` (stdlib `tomllib`).

---

## File Structure

- `gasaudit/__init__.py` — package marker.
- `gasaudit/model.py` — pure math: `Rates`, `Row`, `Params`, `Analysis`, and the functions that compute everything. No I/O, no matplotlib.
- `gasaudit/io.py` — parse the messy CSV into `Row` objects; mi↔km helpers.
- `gasaudit/report.py` — text summary + example-distribution table (mi + km).
- `gasaudit/plots.py` — four matplotlib figures, each a pure `(Analysis, ...) -> Figure`.
- `app.py` — Streamlit interactive front-end (primary interface).
- `main.py` — CLI/static path: load config + CSV, print summary, write PNGs.
- `config.toml` — period parameters.
- `tests/test_model.py`, `tests/test_io.py` — unit tests.
- `output/` — generated PNGs (gitignored).
- `requirements.txt`, `.gitignore`.

## Conventions used throughout

- Internal "distance unit" is whatever the norm is in (`Params.norm_unit`, `"mi"` or `"km"`). The model never knows the unit; callers pass distances already in that unit.
- `MI_TO_KM = 1.609344`.
- Floating tolerance for comparisons: `EPS = 1e-9`.
- All `model.py` dataclasses are `frozen=True`.

---

## Task 1: Project scaffold, dependencies, package skeleton

**Files:**
- Create: `requirements.txt`, `.gitignore`, `gasaudit/__init__.py`, `tests/__init__.py`
- Modify: install into existing `venv`

- [ ] **Step 1: Write requirements.txt**

```
numpy
pandas
matplotlib
streamlit
pytest
```

- [ ] **Step 2: Write .gitignore**

```
venv/
__pycache__/
*.pyc
output/
.pytest_cache/
```

- [ ] **Step 3: Create package markers**

Create `gasaudit/__init__.py` containing exactly:

```python
"""Gas audit town/highway wiggle-room analysis."""
```

Create `tests/__init__.py` as an empty file.

- [ ] **Step 4: Install dependencies**

Run: `venv/bin/pip install -r requirements.txt`
Expected: installs numpy, pandas, matplotlib, streamlit, pytest without error.

- [ ] **Step 5: Verify pytest runs**

Run: `venv/bin/python -m pytest -q`
Expected: "no tests ran" (exit code 5) — confirms pytest is importable.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore gasaudit/__init__.py tests/__init__.py
git commit -m "chore: scaffold gasaudit package and dependencies"
```

---

## Task 2: Rates from norm

**Files:**
- Create: `gasaudit/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'Rates'`.

- [ ] **Step 3: Write minimal implementation**

Create `gasaudit/model.py`:

```python
"""Pure math core for gas-audit wiggle-room analysis.

Distance-unit-agnostic: all distances are in the norm's unit. Callers convert.
"""
from __future__ import annotations

from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class Rates:
    base: float       # litres per distance-unit (norm / 100)
    town: float       # base * (1 + uplift)
    highway: float    # base * (1 - uplift)

    @property
    def spread(self) -> float:
        return self.town - self.highway


def rates_from_norm(norm: float, uplift: float = 0.15) -> Rates:
    base = norm / 100.0
    return Rates(base=base, town=base * (1 + uplift), highway=base * (1 - uplift))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/model.py tests/test_model.py
git commit -m "feat: rates from fuel norm and uplift"
```

---

## Task 3: total_fuel and required_town

**Files:**
- Modify: `gasaudit/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_model.py`:

```python
from gasaudit.model import total_fuel, required_town


def test_total_fuel_uses_only_total_town():
    r = rates_from_norm(20.0)
    # 100 dist total, 40 of it town
    assert total_fuel(r, 100.0, 40.0) == pytest.approx(0.17 * 100 + 0.06 * 40)


def test_required_town_inverts_total_fuel():
    r = rates_from_norm(20.0)
    fuel = total_fuel(r, 100.0, 40.0)
    assert required_town(r, 100.0, fuel) == pytest.approx(40.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'total_fuel'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/model.py`:

```python
def total_fuel(rates: Rates, total_dist: float, town_dist: float) -> float:
    """Period fuel = highway-rate * total distance + spread * total town distance."""
    return rates.highway * total_dist + rates.spread * town_dist


def required_town(rates: Rates, total_dist: float, fuel: float) -> float:
    """The total town distance that makes total_fuel equal `fuel`."""
    return (fuel - rates.highway * total_dist) / rates.spread
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/model.py tests/test_model.py
git commit -m "feat: total_fuel and required_town inversion"
```

---

## Task 4: Row dataclass and feasible town window

**Files:**
- Modify: `gasaudit/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'Row'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/model.py`:

```python
@dataclass(frozen=True)
class Row:
    label: str
    total: float            # odometer delta, in the norm's distance unit
    min_highway: float = 0.0
    min_town: float = 0.0
    route: str = ""

    @property
    def town_min(self) -> float:
        return self.min_town

    @property
    def town_max(self) -> float:
        return self.total - self.min_highway

    def validate(self) -> "Row":
        if self.town_max < self.town_min - EPS:
            raise ValueError(
                f"row {self.label!r}: min_highway ({self.min_highway}) + "
                f"min_town ({self.min_town}) exceed total ({self.total})"
            )
        return self


def feasible_window(rows: list[Row]) -> tuple[float, float]:
    """Min and max achievable TOTAL town distance across all rows."""
    return (sum(r.town_min for r in rows), sum(r.town_max for r in rows))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/model.py tests/test_model.py
git commit -m "feat: Row with town bounds and feasible window"
```

---

## Task 5: Example distribution (water-fill)

**Files:**
- Modify: `gasaudit/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'example_distribution'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/model.py`:

```python
def example_distribution(rows: list[Row], target_town: float) -> list[float] | None:
    """A concrete per-row town split summing to target_town, each within its band.

    Fills proportionally to each row's spare capacity above its town floor.
    Returns None if target_town is outside the feasible window.
    """
    lo, hi = feasible_window(rows)
    if target_town < lo - EPS or target_town > hi + EPS:
        return None
    caps = [r.town_max - r.town_min for r in rows]
    total_cap = sum(caps)
    remaining = target_town - lo
    if total_cap <= EPS:
        return [r.town_min for r in rows]
    return [r.town_min + remaining * c / total_cap for r, c in zip(rows, caps)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/model.py tests/test_model.py
git commit -m "feat: example town distribution via proportional fill"
```

---

## Task 6: Per-row swing room

**Files:**
- Modify: `gasaudit/model.py`
- Test: `tests/test_model.py`

**Concept:** Given an allowed range `[sum_lo, sum_hi]` for the TOTAL town distance, each row `i`
can range as far as the other rows can compensate:
`hi_i = min(town_max_i, sum_hi − Σ_{j≠i} town_min_j)`,
`lo_i = max(town_min_i, sum_lo − Σ_{j≠i} town_max_j)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'swing_room'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/model.py`:

```python
def swing_room(
    rows: list[Row], sum_lo: float, sum_hi: float
) -> list[tuple[float, float]]:
    """Per-row achievable town range, given the TOTAL town must lie in [sum_lo, sum_hi]
    and other rows compensate within their own bounds."""
    all_min = sum(r.town_min for r in rows)
    all_max = sum(r.town_max for r in rows)
    out: list[tuple[float, float]] = []
    for r in rows:
        others_min = all_min - r.town_min
        others_max = all_max - r.town_max
        hi = min(r.town_max, sum_hi - others_min)
        lo = max(r.town_min, sum_lo - others_max)
        out.append((lo, hi))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/model.py tests/test_model.py
git commit -m "feat: per-row swing room given total-town band"
```

---

## Task 7: Params and analyze() aggregator

**Files:**
- Modify: `gasaudit/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_model.py`:

```python
from gasaudit.model import Params, analyze


def _rows():
    return [
        Row(label="d1", total=100.0, min_highway=20.0),  # town [0,80]
        Row(label="d2", total=60.0, min_highway=0.0),    # town [0,60]
    ]


def test_analyze_feasible_basic():
    rows = _rows()
    # choose end fuel so that consumed fuel implies a town target inside the window
    # rates: base .20, hwy .17, spread .06 ; total dist 160
    # pick town target 50 -> fuel = .17*160 + .06*50 = 27.2 + 3.0 = 30.2
    p = Params(start_fuel=40.0, end_fuel=40.0 - 30.2, refuels=0.0, norm=20.0)
    a = analyze(rows, p)
    assert a.total_dist == pytest.approx(160.0)
    assert a.consumed_fuel == pytest.approx(30.2)
    assert a.town_required == pytest.approx(50.0)
    assert a.feasible is True
    assert a.feasible_window == (pytest.approx(0.0), pytest.approx(140.0))
    assert a.example is not None
    assert sum(a.example) == pytest.approx(50.0)


def test_analyze_infeasible_too_much_town_needed():
    rows = _rows()  # max town 140
    # demand town target 200 -> fuel = .17*160 + .06*200 = 27.2 + 12 = 39.2
    p = Params(start_fuel=50.0, end_fuel=50.0 - 39.2, refuels=0.0, norm=20.0)
    a = analyze(rows, p)
    assert a.town_required == pytest.approx(200.0)
    assert a.feasible is False
    assert a.example is None


def test_analyze_tolerance_opens_band():
    rows = _rows()
    p = Params(start_fuel=40.0, end_fuel=40.0 - 30.2, refuels=0.0, norm=20.0,
               end_fuel_tol=0.3)
    a = analyze(rows, p)
    # band half-width = tol / spread = 0.3 / 0.06 = 5.0
    assert a.town_band[0] == pytest.approx(45.0)
    assert a.town_band[1] == pytest.approx(55.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'Params'`.

- [ ] **Step 3: Write minimal implementation**

Append to `gasaudit/model.py`:

```python
@dataclass(frozen=True)
class Params:
    start_fuel: float
    end_fuel: float
    refuels: float = 0.0
    norm: float = 20.0
    norm_unit: str = "mi"     # "mi" or "km" — informational for the model
    uplift: float = 0.15
    end_fuel_tol: float = 0.0


@dataclass(frozen=True)
class Analysis:
    rates: Rates
    total_dist: float
    consumed_fuel: float
    town_required: float
    town_band: tuple[float, float]        # from end_fuel_tol
    feasible_window: tuple[float, float]
    allowed: tuple[float, float]          # town_band intersect feasible_window
    feasible: bool
    swing: list[tuple[float, float]]      # per-row town range
    example: list[float] | None           # per-row town split hitting town_required


def analyze(rows: list[Row], params: Params) -> Analysis:
    for r in rows:
        r.validate()
    rates = rates_from_norm(params.norm, params.uplift)
    total_dist = sum(r.total for r in rows)
    consumed = params.start_fuel + params.refuels - params.end_fuel
    town_req = required_town(rates, total_dist, consumed)
    tol_dist = params.end_fuel_tol / rates.spread
    band = (town_req - tol_dist, town_req + tol_dist)
    window = feasible_window(rows)
    allowed = (max(band[0], window[0]), min(band[1], window[1]))
    feasible = allowed[0] <= allowed[1] + EPS
    if feasible:
        swing = swing_room(rows, allowed[0], allowed[1])
        target = min(max(town_req, window[0]), window[1])
        example = example_distribution(rows, target)
    else:
        swing = [(r.town_min, r.town_min) for r in rows]
        example = None
    return Analysis(
        rates=rates, total_dist=total_dist, consumed_fuel=consumed,
        town_required=town_req, town_band=band, feasible_window=window,
        allowed=allowed, feasible=feasible, swing=swing, example=example,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_model.py -q`
Expected: PASS (15 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/model.py tests/test_model.py
git commit -m "feat: Params, Analysis, and analyze() aggregator"
```

---

## Task 8: CSV loading and unit conversion

**Files:**
- Create: `gasaudit/io.py`
- Test: `tests/test_io.py`

**Notes on the CSV** (`supp_mat/ПАЛИВО_ОБЛІК.csv`, `;`-separated): data rows are those whose
col0 is a non-empty date label AND col1, col2 parse as integers with col2 > col1. Columns:
`0` date, `1` odo_start, `2` odo_end, `3` total (delta), `4` route, `5` town_mi, `6` hwy_mi,
`7` town_km, `8` hwy_km. A manually-added column `9` holds `min_highway` (miles); if absent or
blank it defaults to 0. Header rows, the start-fuel row, and the scratch/footer rows are skipped
by the data-row rule. Distances are in **miles** in the file.

- [ ] **Step 1: Write the failing test**

Create `tests/test_io.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_io.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gasaudit.io'`.

- [ ] **Step 3: Write minimal implementation**

Create `gasaudit/io.py`:

```python
"""Load the fuel CSV into model.Row objects; distance-unit helpers."""
from __future__ import annotations

import csv

from gasaudit.model import Row

MI_TO_KM = 1.609344


def mi_to_km(x: float) -> float:
    return x * MI_TO_KM


def km_to_mi(x: float) -> float:
    return x / MI_TO_KM


def _is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except (TypeError, ValueError):
        return False


def load_rows(path: str, *, to_unit: str = "mi", min_highway_col: int = 9) -> list[Row]:
    """Parse data rows. File distances are miles; convert to `to_unit` ('mi' or 'km')."""
    conv = mi_to_km if to_unit == "km" else (lambda x: x)
    rows: list[Row] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for cols in csv.reader(fh, delimiter=";"):
            if len(cols) < 7:
                continue
            date, odo_s, odo_e = cols[0].strip(), cols[1].strip(), cols[2].strip()
            if not date or not _is_int(odo_s) or not _is_int(odo_e):
                continue
            if int(odo_e) <= int(odo_s):
                continue
            total = float(int(odo_e) - int(odo_s))
            route = cols[4].strip() if len(cols) > 4 else ""
            mh_raw = cols[min_highway_col].strip() if len(cols) > min_highway_col else ""
            min_hw = float(mh_raw.replace(",", ".")) if mh_raw else 0.0
            rows.append(
                Row(label=date, total=conv(total),
                    min_highway=conv(min_hw), route=route)
            )
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_io.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/io.py tests/test_io.py
git commit -m "feat: CSV loader and mi/km conversion"
```

---

## Task 9: Text report

**Files:**
- Create: `gasaudit/report.py`
- Test: `tests/test_model.py` (reuse pytest; add a report test block)

**Display rule:** distances are reported in km. If the analysis ran in miles, multiply by
`MI_TO_KM`; if in km, show as-is. `report` takes the working unit so it can convert.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_io.py` (it already imports pytest):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_io.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gasaudit.report'`.

- [ ] **Step 3: Write minimal implementation**

Create `gasaudit/report.py`:

```python
"""Human-readable summary and example-split table. Distances shown in km."""
from __future__ import annotations

from gasaudit.io import MI_TO_KM
from gasaudit.model import Analysis, Row


def _km(value: float, work_unit: str) -> float:
    return value * MI_TO_KM if work_unit == "mi" else value


def summary_text(a: Analysis, work_unit: str) -> str:
    status = "FEASIBLE" if a.feasible else "INFEASIBLE"
    lines = [
        f"Status: {status}",
        f"Total distance: {a.total_dist:.1f} {work_unit} "
        f"({_km(a.total_dist, work_unit):.1f} km)",
        f"Fuel consumed (pinned): {a.consumed_fuel:.2f} L",
        f"Required total town distance: {a.town_required:.1f} {work_unit} "
        f"({_km(a.town_required, work_unit):.1f} km)",
        f"Town band (tolerance): {a.town_band[0]:.1f} … {a.town_band[1]:.1f} {work_unit}",
        f"Feasible town window: {a.feasible_window[0]:.1f} … "
        f"{a.feasible_window[1]:.1f} {work_unit}",
    ]
    if not a.feasible:
        lo, hi = a.feasible_window
        if a.town_required > hi:
            short = a.town_required - hi
            lines.append(
                f"  -> need {short:.1f} {work_unit} MORE town capacity: "
                f"routes force too much highway (lower min_highway on some rows)."
            )
        else:
            short = lo - a.town_required
            lines.append(
                f"  -> {short:.1f} {work_unit} too much town: raise min_highway "
                f"or the report over-consumes."
            )
    return "\n".join(lines)


def example_table(rows: list[Row], a: Analysis, work_unit: str) -> str:
    header = f"{'day':<8}{'town '+work_unit:>10}{'town km':>10}{'swing '+work_unit:>14}"
    out = [header]
    example = a.example or [float("nan")] * len(rows)
    for r, t, (lo, hi) in zip(rows, example, a.swing):
        out.append(
            f"{r.label:<8}{t:>10.1f}{_km(t, work_unit):>10.1f}"
            f"{f'{lo:.0f}-{hi:.0f}':>14}"
        )
    return "\n".join(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_io.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/report.py tests/test_io.py
git commit -m "feat: text summary and example-split table"
```

---

## Task 10: Plots

**Files:**
- Create: `gasaudit/plots.py`
- Test: `tests/test_io.py` (smoke test — figures build without error)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_io.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_io.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gasaudit.plots'`.

- [ ] **Step 3: Write minimal implementation**

Create `gasaudit/plots.py`:

```python
"""Matplotlib figures for the analysis. Each function returns a Figure."""
from __future__ import annotations

import matplotlib.pyplot as plt

from gasaudit.model import Analysis, Params, Row, analyze, rates_from_norm, total_fuel


def plot_row_bands(rows: list[Row], a: Analysis):
    """Per-day: full bar = total distance; shaded = town swing [lo,hi]; dot = example."""
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 1.5))
    labels = [r.label for r in rows]
    y = range(len(rows))
    ax.barh(list(y), [r.total for r in rows], color="#e8e8e8", label="total distance")
    for i, (r, (lo, hi)) in enumerate(zip(rows, a.swing)):
        ax.barh(i, hi - lo, left=lo, color="#6fa8dc", label="town swing" if i == 0 else "")
    if a.example is not None:
        ax.plot(a.example, list(y), "o", color="#cc0000", label="example split")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.set_xlabel("town distance (work unit)")
    ax.set_title("Per-row town swing room")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


def plot_fuel_vs_town(a: Analysis):
    """Total fuel as a function of total town distance, with target/band/window marked."""
    fig, ax = plt.subplots(figsize=(8, 5))
    lo_w, hi_w = a.feasible_window
    xs = [lo_w + (hi_w - lo_w) * k / 100 for k in range(101)]
    ys = [a.rates.highway * a.total_dist + a.rates.spread * x for x in xs]
    ax.plot(xs, ys, color="#333333")
    ax.axvline(a.town_required, color="#cc0000", label="required town")
    ax.axvspan(a.town_band[0], a.town_band[1], color="#cc0000", alpha=0.15,
               label="tolerance band")
    ax.axvspan(lo_w, hi_w, color="#6fa8dc", alpha=0.1, label="feasible window")
    ax.set_xlabel("total town distance")
    ax.set_ylabel("total fuel (L)")
    ax.set_title("Total fuel vs total town distance")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_swing_widths(rows: list[Row], a: Analysis):
    """Bar chart of each row's swing width (hi - lo), sorted descending."""
    widths = sorted(
        [(r.label, hi - lo) for r, (lo, hi) in zip(rows, a.swing)],
        key=lambda t: t[1], reverse=True,
    )
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 1.5))
    ax.barh([w[0] for w in widths], [w[1] for w in widths], color="#93c47d")
    ax.invert_yaxis()
    ax.set_xlabel("swing width (work unit)")
    ax.set_title("Where the flexibility is (per-row swing width)")
    fig.tight_layout()
    return fig


def plot_tolerance_sensitivity(rows: list[Row], params: Params):
    """How the total-town band width grows with end-fuel tolerance."""
    rates = rates_from_norm(params.norm, params.uplift)
    tols = [t / 10 for t in range(0, 31)]  # 0..3 L
    widths = [min(2 * t / rates.spread,
                  sum(r.town_max for r in rows) - sum(r.town_min for r in rows))
              for t in tols]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(tols, widths, color="#674ea7")
    ax.set_xlabel("end-fuel tolerance (±L)")
    ax.set_ylabel("total town band width (work unit)")
    ax.set_title("Tolerance sensitivity")
    fig.tight_layout()
    return fig
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_io.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add gasaudit/plots.py tests/test_io.py
git commit -m "feat: four analysis plots"
```

---

## Task 11: Config file and CLI (main.py)

**Files:**
- Create: `config.toml`, `main.py`
- Modify: none

- [ ] **Step 1: Write config.toml**

```toml
# Period parameters for the gas-audit analysis.
csv_path = "supp_mat/ПАЛИВО_ОБЛІК.csv"

[fuel]
start_fuel = 63.0      # litres at period start
end_fuel = 40.0        # litres at period end (pinned target)
refuels = 0.0          # total litres added during the period
end_fuel_tol = 0.0     # ± litres rounding tolerance on end fuel

[norm]
value = 20.0           # litres per 100 distance-units
unit = "mi"            # "mi" or "km" — the unit the norm is expressed in
uplift = 0.15          # town = +uplift, highway = -uplift
```

- [ ] **Step 2: Write main.py (manual-run script; no unit test — verified by running)**

```python
"""CLI: load config + CSV, run the analysis, print summary, write plots to output/."""
from __future__ import annotations

import os
import tomllib

import matplotlib
matplotlib.use("Agg")

from gasaudit.io import load_rows
from gasaudit.model import Params, analyze
from gasaudit.plots import (
    plot_fuel_vs_town, plot_row_bands, plot_swing_widths, plot_tolerance_sensitivity,
)
from gasaudit.report import example_table, summary_text


def main(config_path: str = "config.toml") -> None:
    with open(config_path, "rb") as fh:
        cfg = tomllib.load(fh)
    unit = cfg["norm"]["unit"]
    rows = load_rows(cfg["csv_path"], to_unit=unit)
    params = Params(
        start_fuel=cfg["fuel"]["start_fuel"],
        end_fuel=cfg["fuel"]["end_fuel"],
        refuels=cfg["fuel"]["refuels"],
        end_fuel_tol=cfg["fuel"]["end_fuel_tol"],
        norm=cfg["norm"]["value"],
        norm_unit=unit,
        uplift=cfg["norm"]["uplift"],
    )
    a = analyze(rows, params)
    print(summary_text(a, work_unit=unit))
    print()
    print(example_table(rows, a, work_unit=unit))

    os.makedirs("output", exist_ok=True)
    plot_row_bands(rows, a).savefig("output/row_bands.png", dpi=120)
    plot_fuel_vs_town(a).savefig("output/fuel_vs_town.png", dpi=120)
    plot_swing_widths(rows, a).savefig("output/swing_widths.png", dpi=120)
    plot_tolerance_sensitivity(rows, params).savefig(
        "output/tolerance.png", dpi=120)
    print("\nPlots written to output/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the CLI against the real CSV**

First add a `min_highway` column (col 9) to the real CSV for the travel days, or accept the
default 0 (then town window is widest). Then run:

Run: `venv/bin/python main.py`
Expected: prints a summary block starting with `Status: FEASIBLE` or `INFEASIBLE`, an example
table with one line per day, and `Plots written to output/`. Four PNGs appear in `output/`.

- [ ] **Step 4: Eyeball the plots**

Open `output/row_bands.png` and `output/fuel_vs_town.png`. Confirm the town swing bars and the
required-town line render sensibly.

- [ ] **Step 5: Commit**

```bash
git add config.toml main.py
git commit -m "feat: config and CLI static-analysis entry point"
```

---

## Task 12: Streamlit interactive app (app.py)

**Files:**
- Create: `app.py`
- Modify: none

- [ ] **Step 1: Write app.py**

```python
"""Interactive wiggle-room explorer. Run: venv/bin/streamlit run app.py"""
from __future__ import annotations

import tomllib

import streamlit as st

from gasaudit.io import MI_TO_KM, load_rows
from gasaudit.model import Params, analyze, rates_from_norm, total_fuel
from gasaudit.plots import plot_fuel_vs_town, plot_row_bands

st.set_page_config(page_title="Gas Audit Wiggle Room", layout="wide")
st.title("Gas Audit — Town/Highway Wiggle Room")

with open("config.toml", "rb") as fh:
    cfg = tomllib.load(fh)

with st.sidebar:
    st.header("Period parameters")
    csv_path = st.text_input("CSV path", cfg["csv_path"])
    unit = st.selectbox("Norm unit", ["mi", "km"],
                        index=0 if cfg["norm"]["unit"] == "mi" else 1)
    norm = st.number_input("Norm (L / 100 unit)", value=float(cfg["norm"]["value"]))
    uplift = st.number_input("Uplift (town +, highway -)",
                             value=float(cfg["norm"]["uplift"]), step=0.01)
    start_fuel = st.number_input("Start fuel (L)", value=float(cfg["fuel"]["start_fuel"]))
    end_fuel = st.number_input("End fuel (L, pinned)",
                               value=float(cfg["fuel"]["end_fuel"]))
    refuels = st.number_input("Refuels (L)", value=float(cfg["fuel"]["refuels"]))
    tol = st.number_input("End-fuel tolerance (±L)",
                          value=float(cfg["fuel"]["end_fuel_tol"]), step=0.1)

rows = load_rows(csv_path, to_unit=unit)
params = Params(start_fuel=start_fuel, end_fuel=end_fuel, refuels=refuels,
                end_fuel_tol=tol, norm=norm, norm_unit=unit, uplift=uplift)
a = analyze(rows, params)
rates = rates_from_norm(norm, uplift)

# Feasibility banner
if a.feasible:
    st.success(f"FEASIBLE — required total town distance "
               f"{a.town_required:.1f} {unit} within window "
               f"{a.feasible_window[0]:.0f}…{a.feasible_window[1]:.0f} {unit}")
else:
    st.error(f"INFEASIBLE — required town {a.town_required:.1f} {unit} outside window "
             f"{a.feasible_window[0]:.0f}…{a.feasible_window[1]:.0f} {unit}")

# Per-row sliders, seeded from the example split (snap-to-target)
st.subheader("Per-row town distance")
if "town_values" not in st.session_state or st.button("Snap to target"):
    st.session_state.town_values = list(
        a.example if a.example is not None else [r.town_min for r in rows]
    )

town_values = []
for i, (r, (lo, hi)) in enumerate(zip(rows, a.swing)):
    seed = st.session_state.town_values[i] if i < len(st.session_state.town_values) else lo
    seed = min(max(seed, r.town_min), r.town_max)
    val = st.slider(
        f"{r.label}  (total {r.total:.0f} {unit}, town allowed {r.town_min:.0f}…"
        f"{r.town_max:.0f})",
        min_value=float(r.town_min), max_value=float(r.town_max),
        value=float(seed),
    )
    town_values.append(val)

# Live readouts from the current slider state
current_town = sum(town_values)
current_fuel = total_fuel(rates, a.total_dist, current_town)
implied_end = start_fuel + refuels - current_fuel

c1, c2, c3 = st.columns(3)
c1.metric("Total town distance", f"{current_town:.1f} {unit}",
          f"{current_town - a.town_required:+.1f} vs required")
c2.metric("Total fuel", f"{current_fuel:.2f} L")
c3.metric("Implied end fuel", f"{implied_end:.2f} L",
          f"{implied_end - end_fuel:+.2f} vs pinned")

within = abs(implied_end - end_fuel) <= tol + 1e-9
st.write("✅ End fuel matches the pinned target (within tolerance)." if within
         else "⚠️ End fuel does not match yet — adjust the sliders.")

st.pyplot(plot_row_bands(rows, a))
st.pyplot(plot_fuel_vs_town(a))
```

- [ ] **Step 2: Smoke-check the app imports**

Run: `venv/bin/python -c "import ast; ast.parse(open('app.py').read()); print('app.py parses')"`
Expected: `app.py parses`.

- [ ] **Step 3: Launch the app manually**

Run: `venv/bin/streamlit run app.py`
Expected: a browser tab opens; the feasibility banner, per-row sliders, three live metrics, and
two plots render. Dragging a slider updates the "Implied end fuel" metric live. "Snap to target"
resets sliders to a valid split.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: Streamlit interactive wiggle-room explorer"
```

---

## Task 13: README and final full-suite run

**Files:**
- Create: `README.md`
- Modify: none

- [ ] **Step 1: Write README.md**

```markdown
# Gas Audit — Town/Highway Wiggle Room

Computes how much a 10-day fuel report's per-day town/highway split can vary while the
pinned start fuel, end fuel, and refuels stay consistent with the mileage.

## Setup
    venv/bin/pip install -r requirements.txt

## Configure
Edit `config.toml` (fuel levels, refuels, norm, unit, tolerance). Add a `min_highway`
value as column 9 (miles) in the CSV for any day with forced intercity travel.

## Run
- Static analysis + plots:  `venv/bin/python main.py`  (writes output/*.png)
- Interactive explorer:     `venv/bin/streamlit run app.py`

## How it works
Town fuel rate = norm × (1 + uplift), highway = norm × (1 − uplift). Total fuel =
highway_rate × total_distance + spread × total_town_distance, so the pinned fuel forces a
single total town distance. The per-row highway minimums bound which distributions are
feasible; the tool reports each row's swing room and an example valid split.
```

- [ ] **Step 2: Run the full test suite**

Run: `venv/bin/python -m pytest -q`
Expected: all tests pass (model + io/report/plots), no failures.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: usage README"
```

---

## Self-Review notes (already reconciled)

- **Spec coverage:** forced numbers (Task 7), per-row feasible band (Task 4), swing room
  (Task 6), tolerance sensitivity (Tasks 7 & 10), example valid split (Task 5/9), four plots
  (Task 10), interactive Streamlit primary interface (Task 12), CLI (Task 11), shared
  unit-tested model (Tasks 2–7). Units as settings + km display (io + report).
- **Naming consistency:** `required_town`, `feasible_window`, `example_distribution`,
  `swing_room`, `analyze`, `Analysis`, `Params`, `Row`, `Rates` used identically across tasks.
- **Out of scope (per spec):** automatic route-string parsing for min_highway (manual column);
  generating the filled official PDF.
