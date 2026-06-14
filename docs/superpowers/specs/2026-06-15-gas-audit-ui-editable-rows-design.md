# Gas Audit — Editable Rows & Redesigned Interactive UI

**Date:** 2026-06-15
**Status:** Design — awaiting user review
**Builds on:** `2026-06-14-gas-audit-wiggle-design.md` (model/io/report/plots unchanged in behavior)

## Goal

Redesign the Streamlit app so the user can manage rows directly in the UI (add / delete /
reorder, CSV optional), and replace the plain per-row sliders with labeled town/out-of-town
bars showing miles, km, and liters. Add table-style totals and CSV export.

## What changes / what stays

- **Unchanged:** `gasaudit/model.py`, `gasaudit/io.py`, `gasaudit/report.py`, `gasaudit/plots.py`
  (their behavior). `main.py` CLI unchanged.
- **New:** `gasaudit/rows.py` — pure logic for the editable-row workflow (segments, totals,
  add/delete/move, exports, bar HTML). Fully unit-tested.
- **Rewritten:** `app.py` — wires Streamlit widgets to `gasaudit/rows.py`.
- **New tests:** `tests/test_rows.py` (pure logic) + an updated `tests/test_app.py` AppTest.

## Data model

Rows live in `st.session_state.rows` as a list of `RowInput`, stored **canonically in miles**
(the odometer's native unit) so switching the mi/km display unit never corrupts values.

```python
@dataclass
class RowInput:
    label: str          # date string, e.g. "25-May"
    total_mi: float     # odometer delta, miles
    min_highway_mi: float = 0.0   # forced highway minimum, miles
    town_mi: float = 0.0          # chosen town split, miles (0..total-min_highway)
```

- Seeded on first load from the CSV (via `io.load_rows(path, to_unit="mi")`), or empty if no
  CSV / import is skipped.
- `town_mi` seed: the model's example split if feasible, else `min row town` (0). On import,
  if the CSV carries a town value (column 5), use it; otherwise seed to the example split.

### Units

- Sidebar `unit` (mi|km) is the **working/display unit**, also the norm's unit.
- `RowInput` is always miles. A conversion layer produces working-unit values for the model,
  the bars, and the totals. `MI_TO_KM = 1.609344` (reuse `io.MI_TO_KM`).
- The bar always shows **both** units (`town 47 mi · 76 km`); fuel is computed in the norm's
  unit: `liters = distance_in_working_unit × rate` where `rate ∈ {rates.town, rates.highway}`.

## `gasaudit/rows.py` — pure functions

All functions are I/O-free and unit-tested. `unit` is `"mi"` or `"km"`; `rates` is a
`model.Rates`.

- `rows_from_csv(path) -> list[RowInput]` — load via `io.load_rows(path, to_unit="mi")`,
  carrying `total_mi` and `min_highway_mi`, with `town_mi = 0.0`. (`io.load_rows` does not
  currently surface the CSV town column; the caller re-seeds `town_mi` from the model's example
  split after loading.)
- `to_model_rows(rows, unit) -> list[model.Row]` — convert miles→unit; build `model.Row(label,
  total, min_highway, town_min=0, route="")`. (The chosen `town` is NOT part of `model.Row`;
  it only feeds feasibility/bounds.)
- `dist_in_unit(value_mi, unit) -> float` and `other_unit_value(value_mi, unit)` helpers, plus
  `to_km(value_mi)` / display conversions.
- `RowSegments` dataclass + `row_segments(row, unit, rates) -> RowSegments` with:
  `town_mi, town_km, town_l, out_mi, out_km, out_l, total_l, town_frac` (fraction 0..1 for the
  bar width). `town_frac = town/total` in the working unit (guard total==0 → 0).
- `clamp_town(row) -> None` — clamp `row.town_mi` into `[0, total_mi - min_highway_mi]`.
- `totals(rows, unit, rates) -> Totals` dataclass: `town_mi, town_km, town_l, out_mi, out_km,
  out_l, grand_l`.
- Row management (each **mutates `rows` in place and returns it**; `move_*` at a boundary is a
  no-op): `add_row(rows, label, total_mi, min_highway_mi) -> list` (appends, town seeded to 0
  then clamped), `delete_row(rows, i)`, `move_up(rows, i)`, `move_down(rows, i)`.
- `bar_html(seg: RowSegments) -> str` — returns the labeled two-segment bar markup (red town,
  grey out, both-unit + liters labels, row-total at right). Pure string; tested by asserting it
  contains the expected numbers and segment widths. Uses inline styles only (no external CSS).
- Export builders (return `pandas.DataFrame`):
  `computed_table_df(rows, unit, rates)` — columns: `date, total <unit>, town <unit>, town km,
  town L, out <unit>, out km, out L, row L`. Plus the math is row-consistent.
  `input_csv_df(rows)` — columns matching the input schema so it round-trips through
  `io.load_rows`: the 0-based layout `date, odo_start, odo_end, total_mi, route, town_mi,
  hwy_mi, town_km, hwy_km, min_highway_mi`. `odo_start/odo_end` synthesized cumulatively from a
  base (e.g. 0) so totals are preserved; `route` blank.

## `app.py` — layout and behavior

Top-to-bottom:

1. **Sidebar** — period params (unit, norm, uplift, start/end fuel, refuels, tolerance) as today,
   plus a **CSV path** input and an **"Import CSV"** button that replaces `session_state.rows`.
   A **"Clear rows"** button empties the list.
2. **Feasibility banner** (`st.success`/`st.error`) and the no-minimums `st.info` notice
   (driven by `to_model_rows` + `analyze`).
3. **Per-row block** — for each row `i`, a `st.columns` layout:
   - **col 0 (narrow):** red trash button `st.button("", icon=":material/delete:", key=f"del{i}")`
     → `delete_row`; CSS injected once to color it red and give it row-ish height.
   - **col 1 (narrow):** stacked **▲** / **▼** buttons → `move_up` / `move_down`.
   - **col 2 (wide):** caption line (`label · total mi (km) · min highway`); the **bar HTML**
     via `st.markdown(bar_html(seg), unsafe_allow_html=True)`; a **slider** directly beneath
     (`min=0`, `max=total-min_highway` in working unit, value=current town) whose `on_change`
     writes the chosen town back to `session_state.rows[i].town_mi` (converted to miles).
     Zero-width rows (`max<=min`) show a fixed read-out and no slider.
   - **col 3 (narrow):** row-total **liters** (also shown on the bar's right edge; keep one — on
     the bar, per the mockup).
4. **➕ Add row** button → opens an `st.dialog("Add row")` modal with **Date**, **Total
   distance (`unit`)**, **Min highway (`unit`)** number/text inputs and **Add** / **Cancel**.
   On Add: convert entered working-unit distances → miles, call `add_row`, close dialog, rerun.
5. **Totals table** — render the `Totals` as a 2-column table (In town | Out of town) × rows
   (Distance mi, Distance km, Fuel L) via `st.table`/`st.markdown`; then **grand total fuel**
   and the **implied end fuel vs pinned** line with the ✅/⚠️ tolerance check (logic as today,
   driven by `totals(...).grand_l`).
6. **Export** — two `st.download_button`s: "Export computed table (CSV)" →
   `computed_table_df(...).to_csv(index=False)`, and "Export input CSV (re-importable)" →
   `input_csv_df(...).to_csv(index=False, sep=";")`.
7. **`plot_fuel_vs_town(a)`** kept below for context. The old `plot_row_bands` is NOT shown in
   the app (the new bars replace it); the function remains for `main.py`.

### State & reruns

- `session_state.rows` is the single source of truth. Widget keys are index-based
  (`del{i}`, `up{i}`, `down{i}`, `town{i}`). After any add/delete/move, call `st.rerun()` so
  keys re-bind cleanly.
- Slider `on_change` callbacks update `town_mi`; the bar re-renders from the updated value.
- "Snap to target" remains: reseed every `town_mi` from the model's example split.

## Error handling

- Import of a missing/invalid CSV path → `st.error`, leave existing rows unchanged.
- Add-row modal validation: total must be > 0; min_highway clamped to `[0, total]`; blank date
  allowed (defaults to `row N`). Invalid input shows an inline error in the dialog, no append.
- Empty row list → totals all zero; feasibility banner shows the analyze() result for zero rows
  (already handled: infeasible unless consumed fuel is ~0); no per-row block rendered.

## Testing

- `tests/test_rows.py` (pure, fast):
  - `row_segments` math: town/out mi, km (×1.609344), liters (×rate), total_l, town_frac; a
    pure-town row (out=0) and a constrained row.
  - `totals` aggregation across rows.
  - `add_row` / `delete_row` / `move_up` / `move_down` (incl. boundary no-ops at ends).
  - `clamp_town` bounds.
  - unit handling: same `RowInput` rendered in mi vs km gives consistent liters (fuel identical;
    distances differ by the conversion).
  - `bar_html` contains expected numbers and the correct town width percentage.
  - `computed_table_df` columns/values; `input_csv_df` round-trips through `io.load_rows`
    (write to a temp file, reload, assert totals/min_highway preserved).
- `tests/test_app.py`: `AppTest` smoke — app runs without exception on the real CSV and with an
  empty row list; assert sliders count matches non-zero-width rows; exercise one delete via the
  widget API if practical (else cover delete in `test_rows.py`).

## Components / files

- `gasaudit/rows.py` — new pure module (the workflow logic).
- `app.py` — rewritten UI.
- `tests/test_rows.py`, `tests/test_app.py` — tests.
- Everything else unchanged.

## Out of scope

- Drag-and-drop reordering (using ▲/▼ buttons instead).
- Dragging the colored bar directly (slider beneath is the control).
- Persisting rows to disk automatically (export is the save mechanism).
- Editing an existing row's date/total/min inline (delete + re-add; revisit if needed).

## Open assumptions (flag if wrong)

- Entered distances in the Add-row modal are in the current working unit.
- The computed-table export is for pasting into the report; the input CSV export uses `;`
  separator and the existing column order so `io.load_rows` reads it back.
- Approximating the exact red full-height trash button via CSS is acceptable; functional delete
  is the hard requirement.
