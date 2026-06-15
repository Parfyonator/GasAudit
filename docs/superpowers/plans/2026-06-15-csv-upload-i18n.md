# CSV Upload + EN/UK i18n Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CSV file-path input with an upload control, and add an EN/UK language switch (Ukrainian default) covering every visible string.

**Architecture:** A new `gasaudit/i18n.py` holds all UI strings as an `{lang: {key: text}}` table with a `translator(lang)` factory. `app.py` resolves the language from a sidebar segmented control and routes every string through it. CSV parsing is refactored in `gasaudit/io.py` to work from an in-memory string (uploaded file) as well as a path. `plots.py` and `rows.py:bar_html` take optional label arguments so their visible text translates without coupling them to the i18n module.

**Tech Stack:** Python 3.13, Streamlit, pandas, matplotlib, pytest.

---

## File Structure

- `gasaudit/i18n.py` (new) — `TRANSLATIONS` dict + `translator(lang)` factory. Single responsibility: string catalog + lookup.
- `gasaudit/io.py` (modify) — split parsing from file-opening; add `load_rows_from_text`.
- `gasaudit/rows.py` (modify) — add `rows_from_csv_text`; add optional labels to `bar_html`.
- `gasaudit/plots.py` (modify) — `plot_fuel_vs_town` gains optional `labels` dict.
- `app.py` (modify) — language switch, file uploader, all strings via `t`.
- `config.toml` (modify) — remove `csv_path`.
- `tests/test_i18n.py` (new), `tests/test_io.py` (add), `tests/test_rows.py` (add), `tests/test_app.py` (modify).

---

## Task 1: io.py — parse from text, not just a path

**Files:**
- Modify: `gasaudit/io.py:27-48`
- Test: `tests/test_io.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_io.py` (SAMPLE already exists in that file):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_io.py::test_load_rows_from_text_matches_load_rows -v`
Expected: FAIL with `ImportError: cannot import name 'load_rows_from_text'`

- [ ] **Step 3: Refactor io.py to extract the parser and add the text entry point**

Replace `gasaudit/io.py:27-48` (the whole `load_rows` function) with:

```python
def _parse_rows(reader, *, to_unit: str, min_highway_col: int) -> list[Row]:
    """Core parser over a csv.reader-like iterable of column lists."""
    conv = mi_to_km if to_unit == "km" else (lambda x: x)
    rows: list[Row] = []
    for cols in reader:
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
            Row(label=date, total=conv(total), min_highway=conv(min_hw), route=route)
        )
    return rows


def load_rows(path: str, *, to_unit: str = "mi", min_highway_col: int = 9) -> list[Row]:
    """Parse data rows from a file. File distances are miles; convert to `to_unit`."""
    with open(path, newline="", encoding="utf-8") as fh:
        return _parse_rows(csv.reader(fh, delimiter=";"),
                           to_unit=to_unit, min_highway_col=min_highway_col)


def load_rows_from_text(text: str, *, to_unit: str = "mi",
                        min_highway_col: int = 9) -> list[Row]:
    """Parse data rows from an in-memory CSV string (e.g. an uploaded file)."""
    import io as _io
    return _parse_rows(csv.reader(_io.StringIO(text), delimiter=";"),
                       to_unit=to_unit, min_highway_col=min_highway_col)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_io.py -v`
Expected: PASS (all io tests, including the two new ones and the pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add gasaudit/io.py tests/test_io.py
git commit -m "refactor: parse CSV rows from text as well as a path"
```

---

## Task 2: rows.py — rows_from_csv_text

**Files:**
- Modify: `gasaudit/rows.py` (add function next to `rows_from_csv` at line ~215; update the `load_rows` import to also import `load_rows_from_text`)
- Test: `tests/test_rows.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_rows.py`:

```python
from gasaudit.rows import rows_from_csv_text

_CSV_TEXT = (
    ";Показник;Залишок;;;;;;\n"
    "25-May;175010;175137;127;route;47;80;76;129;80\n"
    "26-May;175137;175190;53;ПТД;53;;85;0\n"
)


def test_rows_from_csv_text_seeds_rowinputs():
    rows = rows_from_csv_text(_CSV_TEXT)
    assert [r.label for r in rows] == ["25-May", "26-May"]
    assert rows[0].total_mi == pytest.approx(127.0)
    assert rows[0].min_highway_mi == pytest.approx(80.0)
    assert rows[0].town_mi == 0.0  # caller re-seeds the split
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rows.py::test_rows_from_csv_text_seeds_rowinputs -v`
Expected: FAIL with `ImportError: cannot import name 'rows_from_csv_text'`

- [ ] **Step 3: Implement the function**

In `gasaudit/rows.py`, find the existing import of `load_rows` (near the top of the file) and add `load_rows_from_text` to it. For example, change:

```python
from gasaudit.io import load_rows
```

to:

```python
from gasaudit.io import load_rows, load_rows_from_text
```

(If `load_rows` is imported in a different form, add `load_rows_from_text` to that same import.)

Then add this function immediately after `rows_from_csv` (after line ~221):

```python
def rows_from_csv_text(text: str) -> list[RowInput]:
    """Seed RowInputs from an uploaded CSV string (miles); town_mi defaults to 0."""
    model_rows = load_rows_from_text(text, to_unit="mi")
    return [
        RowInput(label=m.label, total_mi=m.total, min_highway_mi=m.min_highway, town_mi=0.0)
        for m in model_rows
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rows.py::test_rows_from_csv_text_seeds_rowinputs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gasaudit/rows.py tests/test_rows.py
git commit -m "feat: rows_from_csv_text for uploaded CSV files"
```

---

## Task 3: i18n.py — translation catalog

**Files:**
- Create: `gasaudit/i18n.py`
- Test: `tests/test_i18n.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_i18n.py`:

```python
from gasaudit.i18n import TRANSLATIONS, translator


def test_uk_and_en_have_identical_keys():
    assert set(TRANSLATIONS["UK"]) == set(TRANSLATIONS["EN"])


def test_default_language_is_uk_resolvable():
    t = translator("UK")
    assert t("snap")  # non-empty Ukrainian string
    assert t("snap") != translator("EN")("snap")


def test_interpolation_formats_values():
    t = translator("EN")
    out = t("feasible", town=12.3, unit="mi", lo=5, hi=40)
    assert "12.3" in out and "mi" in out


def test_unknown_key_falls_back_to_raw_key():
    t = translator("EN")
    assert t("no_such_key_xyz") == "no_such_key_xyz"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gasaudit.i18n'`

- [ ] **Step 3: Create the module**

Create `gasaudit/i18n.py`:

```python
"""UI string catalog and language-aware lookup. UK is the default language."""
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "EN": {
        "page_title": "Gas Audit Wiggle Room",
        "title": "Gas Audit — Town/Highway Wiggle Room",
        "params_header": "Period parameters",
        "upload_csv": "Upload CSV",
        "norm_unit": "Norm unit",
        "norm": "Norm (L / 100 unit)",
        "uplift": "Uplift (town +, highway -)",
        "start_fuel": "Start fuel (L)",
        "end_fuel": "End fuel (L, pinned)",
        "refuels": "Refuels (L)",
        "tol": "End-fuel tolerance (±L)",
        "clear_rows": "Clear rows",
        "csv_error": "Could not load CSV: {exc}",
        "feasible": "FEASIBLE — required total town distance {town:.1f} {unit} "
                    "within window {lo:.0f}…{hi:.0f} {unit}",
        "infeasible": "INFEASIBLE — required town {town:.1f} {unit} outside window "
                      "{lo:.0f}…{hi:.0f} {unit}",
        "no_min_highway": "No per-row highway minimums set — town share can range "
                          "0..total each day (widest window). Add minimums to constrain it.",
        "date": "Date",
        "total_dist": "Total distance ({unit})",
        "min_highway": "Min highway ({unit})",
        "save": "Save",
        "add": "Add",
        "cancel": "Cancel",
        "total_gt_zero": "Total must be greater than 0.",
        "dialog_add": "Add row",
        "dialog_edit": "Edit row",
        "split_subheader": "Per-row town / out-of-town split",
        "snap": "Snap to target",
        "lock": "🔒 Lock total",
        "lock_help": "When on, moving one day's split shifts the other days to keep the "
                     "total litres (total fuel) constant.",
        "town_fixed": "town fixed at 0 — no wiggle room",
        "row_meta": "{label} · total {total:.0f} {unit} ({km:.0f} km) · "
                    "min highway {mh:.0f} {unit}",
        "tip_delete": "Delete row",
        "tip_edit": "Edit row",
        "tip_up": "Move up",
        "tip_down": "Move down",
        "add_row": "➕ Add row",
        "bar_town": "town",
        "bar_out": "out",
        "totals_subheader": "Totals",
        "dist_mi": "Distance (mi)",
        "dist_km": "Distance (km)",
        "fuel_l": "Fuel (L)",
        "in_town": "In town",
        "out_of_town": "Out of town",
        "grand_total_fuel": "Grand total fuel",
        "implied_end_fuel": "Implied end fuel",
        "vs_pinned": "{d:+.2f} vs pinned",
        "end_ok": "✅ End fuel matches the pinned target (within tolerance).",
        "end_no": "⚠️ End fuel does not match yet — adjust the splits.",
        "export_computed": "Export computed table (CSV)",
        "export_input": "Export input CSV (re-importable)",
        "plot_required_town": "required town",
        "plot_required_town_off": "required town {town:.0f} (off-scale)",
        "plot_tol_band": "tolerance band",
        "plot_feasible_window": "feasible window",
        "plot_xlabel": "total town distance",
        "plot_ylabel": "total fuel (L)",
        "plot_title": "Total fuel vs total town distance",
    },
    "UK": {
        "page_title": "Паливний аудит — запас гнучкості",
        "title": "Паливний аудит — запас гнучкості (місто/траса)",
        "params_header": "Параметри періоду",
        "upload_csv": "Завантажити CSV",
        "norm_unit": "Одиниця норми",
        "norm": "Норма (л / 100 одиниць)",
        "uplift": "Надбавка (місто +, траса −)",
        "start_fuel": "Паливо на початок (л)",
        "end_fuel": "Паливо на кінець (л, фіксоване)",
        "refuels": "Заправки (л)",
        "tol": "Допуск палива на кінець (±л)",
        "clear_rows": "Очистити рядки",
        "csv_error": "Не вдалося завантажити CSV: {exc}",
        "feasible": "ДОПУСТИМО — потрібна загальна відстань у місті {town:.1f} {unit} "
                    "у межах вікна {lo:.0f}…{hi:.0f} {unit}",
        "infeasible": "НЕДОПУСТИМО — потрібне місто {town:.1f} {unit} поза вікном "
                      "{lo:.0f}…{hi:.0f} {unit}",
        "no_min_highway": "Не задано мінімумів траси для рядків — частка міста може бути "
                          "від 0 до загальної щодня (найширше вікно). "
                          "Додайте мінімуми, щоб обмежити.",
        "date": "Дата",
        "total_dist": "Загальна відстань ({unit})",
        "min_highway": "Мінімум траси ({unit})",
        "save": "Зберегти",
        "add": "Додати",
        "cancel": "Скасувати",
        "total_gt_zero": "Загальна відстань має бути більшою за 0.",
        "dialog_add": "Додати рядок",
        "dialog_edit": "Редагувати рядок",
        "split_subheader": "Розподіл місто / поза містом за рядками",
        "snap": "Підігнати до цілі",
        "lock": "🔒 Зафіксувати суму",
        "lock_help": "Коли увімкнено, зміна розподілу за один день зсуває інші дні, "
                     "щоб зберегти загальні літри (загальне паливо) незмінними.",
        "town_fixed": "місто зафіксовано на 0 — немає запасу гнучкості",
        "row_meta": "{label} · загалом {total:.0f} {unit} ({km:.0f} км) · "
                    "мін. траса {mh:.0f} {unit}",
        "tip_delete": "Видалити рядок",
        "tip_edit": "Редагувати рядок",
        "tip_up": "Перемістити вгору",
        "tip_down": "Перемістити вниз",
        "add_row": "➕ Додати рядок",
        "bar_town": "місто",
        "bar_out": "поза містом",
        "totals_subheader": "Підсумки",
        "dist_mi": "Відстань (миль)",
        "dist_km": "Відстань (км)",
        "fuel_l": "Паливо (л)",
        "in_town": "У місті",
        "out_of_town": "Поза містом",
        "grand_total_fuel": "Загальне паливо",
        "implied_end_fuel": "Розраховане паливо на кінець",
        "vs_pinned": "{d:+.2f} від фіксованого",
        "end_ok": "✅ Паливо на кінець відповідає фіксованій цілі (у межах допуску).",
        "end_no": "⚠️ Паливо на кінець ще не збігається — скоригуйте розподіл.",
        "export_computed": "Експорт обчисленої таблиці (CSV)",
        "export_input": "Експорт вхідного CSV (для повторного імпорту)",
        "plot_required_town": "потрібне місто",
        "plot_required_town_off": "потрібне місто {town:.0f} (поза шкалою)",
        "plot_tol_band": "смуга допуску",
        "plot_feasible_window": "допустиме вікно",
        "plot_xlabel": "загальна відстань у місті",
        "plot_ylabel": "загальне паливо (л)",
        "plot_title": "Загальне паливо vs загальна відстань у місті",
    },
}


def translator(lang: str):
    """Return a t(key, **kwargs) lookup for `lang`, falling back to EN then the raw key."""
    table = TRANSLATIONS.get(lang) or TRANSLATIONS["EN"]

    def t(key: str, **kwargs) -> str:
        s = table.get(key)
        if s is None:
            s = TRANSLATIONS["EN"].get(key, key)
        return s.format(**kwargs) if kwargs else s

    return t
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add gasaudit/i18n.py tests/test_i18n.py
git commit -m "feat: EN/UK translation catalog with parity test"
```

---

## Task 4: plots.py — translatable plot labels

**Files:**
- Modify: `gasaudit/plots.py:28-51` (`plot_fuel_vs_town`)
- Test: `tests/test_rows.py` is unrelated; reuse `tests/test_io.py`? No — plots are tested in `tests/test_rows.py`'s plot section. Add the new test there (that file already imports `plot_fuel_vs_town`).

NOTE: existing `tests/test_rows.py` calls `plot_fuel_vs_town(a)` with no labels — the new signature MUST keep `labels` optional so those calls still pass.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_rows.py` (in the plots section, after `test_all_plots_build_figures`):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rows.py::test_fuel_vs_town_accepts_custom_labels -v`
Expected: FAIL with `TypeError: plot_fuel_vs_town() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Add the optional labels argument**

Replace `gasaudit/plots.py:28-51` (the `plot_fuel_vs_town` function body up to `fig.tight_layout()`) with:

```python
def plot_fuel_vs_town(a: Analysis, labels: dict | None = None):
    """Total fuel as a function of total town distance, with target/band/window marked."""
    L = labels or {}
    fig, ax = plt.subplots(figsize=(8, 5))
    lo_w, hi_w = a.feasible_window
    xs = [lo_w + (hi_w - lo_w) * k / 100 for k in range(101)]
    ys = [a.rates.highway * a.total_dist + a.rates.spread * x for x in xs]
    ax.plot(xs, ys, color="#333333")
    span = hi_w - lo_w
    if lo_w - span * 0.1 <= a.town_required <= hi_w + span * 0.1:
        ax.axvline(a.town_required, color="#cc0000",
                   label=L.get("required_town", "required town"))
    else:
        ax.annotate(
            L.get("required_town_off",
                  f"required town {a.town_required:.0f} (off-scale)"),
            xy=(0.5, 0.9), xycoords="axes fraction",
            ha="center", color="#cc0000",
        )
    ax.axvspan(a.town_band[0], a.town_band[1], color="#cc0000", alpha=0.15,
               label=L.get("tolerance_band", "tolerance band"))
    ax.axvspan(lo_w, hi_w, color="#6fa8dc", alpha=0.1,
               label=L.get("feasible_window", "feasible window"))
    ax.set_xlabel(L.get("xlabel", "total town distance"))
    ax.set_ylabel(L.get("ylabel", "total fuel (L)"))
    ax.set_title(L.get("title", "Total fuel vs total town distance"))
    ax.legend(fontsize=8)
    fig.tight_layout()
```

(Keep whatever `return fig` / trailing lines already follow `fig.tight_layout()` unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rows.py -v`
Expected: PASS (new test plus the pre-existing plot tests that call `plot_fuel_vs_town(a)`)

- [ ] **Step 5: Commit**

```bash
git add gasaudit/plots.py tests/test_rows.py
git commit -m "feat: optional translatable labels for plot_fuel_vs_town"
```

---

## Task 5: rows.py — translatable bar labels

**Files:**
- Modify: `gasaudit/rows.py:182` (`bar_html` signature) and the two `<b>` label strings inside it (lines ~196 and ~205)
- Test: `tests/test_rows.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_rows.py`:

```python
from gasaudit.rows import bar_html, row_segments
from gasaudit.model import rates_from_norm


def test_bar_html_uses_custom_segment_labels():
    r = RowInput(label="d1", total_mi=100.0, min_highway_mi=0.0, town_mi=40.0)
    rates = rates_from_norm(20.0)
    seg = row_segments(r, "mi", rates)
    html = bar_html(seg, town_label="місто", out_label="поза містом")
    assert "місто 40 mi" in html
    assert "поза містом 60 mi" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rows.py::test_bar_html_uses_custom_segment_labels -v`
Expected: FAIL with `TypeError: bar_html() got an unexpected keyword argument 'town_label'`

- [ ] **Step 3: Add optional label params to bar_html**

In `gasaudit/rows.py`, change the `bar_html` signature from:

```python
def bar_html(seg: RowSegments) -> str:
```

to:

```python
def bar_html(seg: RowSegments, town_label: str = "town", out_label: str = "out") -> str:
```

Then in the town `<b>` line, change:

```python
            f'<b style="font-size:13px;white-space:nowrap;">town {seg.town_mi:.0f} mi · '
```

to:

```python
            f'<b style="font-size:13px;white-space:nowrap;">{town_label} {seg.town_mi:.0f} mi · '
```

And in the out `<b>` line, change:

```python
            f'<b style="font-size:13px;white-space:nowrap;">out {seg.out_mi:.0f} mi · '
```

to:

```python
            f'<b style="font-size:13px;white-space:nowrap;">{out_label} {seg.out_mi:.0f} mi · '
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rows.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gasaudit/rows.py tests/test_rows.py
git commit -m "feat: optional segment labels for bar_html"
```

---

## Task 6: app.py — language switch, uploader, all strings translated

**Files:**
- Modify: `app.py` (full rewrite below)
- Modify: `config.toml` (remove `csv_path`)
- Modify: `tests/test_app.py` (pin language to EN so label assertions hold)

- [ ] **Step 1: Update the existing app tests to pin EN, then watch them fail**

In `tests/test_app.py`, set the language to EN at the start of every test by inserting
`at.session_state["lang"] = "EN"` immediately after each `AppTest.from_file(...)` and
before the first `.run()`. Concretely, each test that does:

```python
    at = AppTest.from_file("app.py", default_timeout=30).run()
```

becomes:

```python
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["lang"] = "EN"
    at.run()
```

and `test_app_runs_with_empty_rows` (which already splits creation and `.run()`) gets
`at.session_state["lang"] = "EN"` added next to its `at.session_state["rows"] = []` line.

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL — the current `app.py` still has the path input / hardcoded strings and
no `lang` handling (e.g. tests pass today but will exercise the new behavior after Step 2; if they pass now that is fine — Step 2 is what must keep them passing).

- [ ] **Step 2: Rewrite app.py**

Replace the entire contents of `app.py` with:

```python
"""Interactive wiggle-room explorer. Run: venv/bin/streamlit run app.py"""
from __future__ import annotations

import tomllib

import streamlit as st

from gasaudit.model import Params, analyze, rates_from_norm
from gasaudit.plots import plot_fuel_vs_town
from gasaudit.i18n import translator
from gasaudit import rows as R

# Language is resolved from session_state BEFORE set_page_config (which must be the first
# Streamlit call). The sidebar segmented control writes session_state["lang"]; its change
# triggers a rerun, so the title/text pick up the new language on the next run.
lang = st.session_state.get("lang") or "UK"
_ = translator(lang)

st.set_page_config(page_title=_("page_title"), layout="wide")
st.title(_("title"))

with open("config.toml", "rb") as fh:
    cfg = tomllib.load(fh)

# --- sidebar params ---
with st.sidebar:
    st.segmented_control("Мова / Language", ["UK", "EN"], key="lang")
    st.header(_("params_header"))
    uploaded = st.file_uploader(_("upload_csv"), type=["csv"])
    if uploaded is not None and st.session_state.get("uploaded_id") != uploaded.file_id:
        try:
            text = uploaded.getvalue().decode("utf-8")
            st.session_state.rows = R.rows_from_csv_text(text)
            st.session_state.uploaded_id = uploaded.file_id
            st.session_state.pop("seeded", None)
        except Exception as exc:  # noqa: BLE001 - surface any load failure to the user
            st.error(_("csv_error", exc=exc))
    unit = st.selectbox(_("norm_unit"), ["mi", "km"],
                        index=0 if cfg["norm"]["unit"] == "mi" else 1)
    norm = st.number_input(_("norm"), value=float(cfg["norm"]["value"]))
    uplift = st.number_input(_("uplift"),
                             value=float(cfg["norm"]["uplift"]), step=0.01)
    start_fuel = st.number_input(_("start_fuel"), value=float(cfg["fuel"]["start_fuel"]))
    end_fuel = st.number_input(_("end_fuel"), value=float(cfg["fuel"]["end_fuel"]))
    refuels = st.number_input(_("refuels"), value=float(cfg["fuel"]["refuels"]))
    tol = st.number_input(_("tol"),
                          value=float(cfg["fuel"]["end_fuel_tol"]), step=0.1)
    st.divider()
    if st.button(_("clear_rows")):
        st.session_state.rows = []
        st.session_state.pop("uploaded_id", None)

rates = rates_from_norm(norm, uplift)
params = Params(start_fuel=start_fuel, end_fuel=end_fuel, refuels=refuels,
                end_fuel_tol=tol, norm=norm, norm_unit=unit, uplift=uplift)

# --- session rows: start empty; rows arrive via upload or manual add ---
if "rows" not in st.session_state:
    st.session_state.rows = []
rows = st.session_state.rows

# analysis on the model view (feasibility + example seed)
a = analyze(R.to_model_rows(rows, unit), params)

# one-time seed of town splits from the example distribution
if rows and not st.session_state.get("seeded") and a.example is not None:
    for r, ex in zip(rows, a.example):
        r.town_mi = R.from_unit(ex, unit)
        R.clamp_town(r)
        st.session_state[f"town{id(r)}"] = float(R.to_unit(r.town_mi, unit))
    st.session_state.seeded = True

# Keep each slider's widget-state (keyed by id(r), stored in the WORKING unit) in sync.
# Sliders read their value from session_state, so programmatic changes (Snap to target,
# unit toggle, Edit) actually move the handles — passing value= would be ignored once a
# keyed widget has state. Seed new rows, rewrite on a mi/km change, and clamp to current
# bounds (min highway can change via Edit).
unit_changed = st.session_state.get("prev_unit") != unit
st.session_state.prev_unit = unit
for r in rows:
    k = f"town{id(r)}"
    town_max_u = R.to_unit(max(r.total_mi - r.min_highway_mi, 0.0), unit)
    if k not in st.session_state or unit_changed:
        st.session_state[k] = float(R.to_unit(r.town_mi, unit))
    st.session_state[k] = float(min(max(st.session_state[k], 0.0), town_max_u))

# red trash-button styling (best-effort: colors any button whose label is the delete icon)
st.markdown(
    "<style>div[data-testid='stButton'] button:has(span[data-testid='stIconMaterial'])"
    "{color:#d24b4b;border-color:#d24b4b;}</style>", unsafe_allow_html=True,
)

# --- feasibility banner ---
if a.feasible:
    st.success(_("feasible", town=a.town_required, unit=unit,
                 lo=a.feasible_window[0], hi=a.feasible_window[1]))
else:
    st.error(_("infeasible", town=a.town_required, unit=unit,
               lo=a.feasible_window[0], hi=a.feasible_window[1]))

if rows and all(r.min_highway_mi == 0 for r in rows):
    st.info(_("no_min_highway"))

# --- add / edit row modal (shared form; add when index is None) ---
def _row_form(index):
    if index is None:
        d_label, d_total, d_min = f"row {len(rows) + 1}", 0.0, 0.0
    else:
        rr = rows[index]
        d_label = rr.label
        d_total = R.to_unit(rr.total_mi, unit)
        d_min = R.to_unit(rr.min_highway_mi, unit)
    label = st.text_input(_("date"), value=d_label)
    total = st.number_input(_("total_dist", unit=unit), min_value=0.0,
                            value=float(d_total), step=1.0)
    minhw = st.number_input(_("min_highway", unit=unit), min_value=0.0,
                            value=float(d_min), step=1.0)
    c1, c2 = st.columns(2)
    if c1.button(_("save") if index is not None else _("add"), type="primary"):
        if total <= 0:
            st.error(_("total_gt_zero"))
        else:
            if index is None:
                R.add_row(rows, label, R.from_unit(total, unit), R.from_unit(minhw, unit))
            else:
                R.update_row(rows, index, label,
                             R.from_unit(total, unit), R.from_unit(minhw, unit))
            st.rerun()
    if c2.button(_("cancel")):
        st.rerun()


@st.dialog(_("dialog_add"))
def _add_row_dialog():
    _row_form(None)


@st.dialog(_("dialog_edit"))
def _edit_row_dialog(index):
    _row_form(index)


def _locked_rebalance(moved_id):
    """Slider on_change callback: when 'Lock total' is on, shift the other rows to keep the
    grand total town distance (hence total fuel) constant. Runs before the rerun, so it may
    modify other sliders' session_state."""
    if not st.session_state.get("lock"):
        return
    u = st.session_state.get("prev_unit", unit)
    movable = [r for r in st.session_state.rows
               if R.to_unit(r.total_mi - r.min_highway_mi, u) > 1e-9]
    ids = [id(r) for r in movable]
    if moved_id not in ids:
        return
    keys = [f"town{i}" for i in ids]
    values = [st.session_state[k] for k in keys]
    maxima = [R.to_unit(r.total_mi - r.min_highway_mi, u) for r in movable]
    prev = st.session_state.get("prev_town", {})
    target = sum(prev.get(i, v) for i, v in zip(ids, values))  # total before this move
    moved_idx = ids.index(moved_id)
    below = list(range(moved_idx + 1, len(ids)))  # only rows below absorb the change
    new_vals = R.rebalance(values, maxima, moved_idx, target, pool=below)
    for k, nv in zip(keys, new_vals):
        st.session_state[k] = float(nv)

# --- snap + lock controls (right-aligned) ---
st.subheader(_("split_subheader"))
_c, c_snap, c_lock = st.columns([0.6, 0.22, 0.18])
if c_snap.button(_("snap")) and a.example is not None:
    for r, ex in zip(rows, a.example):
        r.town_mi = R.from_unit(ex, unit)
        R.clamp_town(r)
        st.session_state[f"town{id(r)}"] = float(R.to_unit(r.town_mi, unit))
    st.rerun()
c_lock.toggle(_("lock"), key="lock", help=_("lock_help"))

# --- per-row blocks ---
# Widget keys use id(r) (stable per row object across reruns) so slider state stays
# bound to the right row after delete / reorder — index-based keys would go stale.
for i, r in enumerate(rows):
    c_del, c_mv, c_main, c_total = st.columns([0.06, 0.06, 0.78, 0.1])
    if c_del.button(":material/delete:", key=f"del{id(r)}", help=_("tip_delete")):
        R.delete_row(rows, i)
        st.rerun()
    if c_del.button(":material/edit:", key=f"edit{id(r)}", help=_("tip_edit")):
        _edit_row_dialog(i)
    if c_mv.button("▲", key=f"up{id(r)}", help=_("tip_up")):
        R.move_up(rows, i)
        st.rerun()
    if c_mv.button("▼", key=f"down{id(r)}", help=_("tip_down")):
        R.move_down(rows, i)
        st.rerun()
    with c_main:
        # Reserve the bar's spot ABOVE the slider, but fill it AFTER reading the slider
        # so it reflects the new value on the same rerun (no extra click needed).
        bar_slot = st.empty()
        town_max = R.to_unit(r.total_mi - r.min_highway_mi, unit)
        if town_max <= 1e-9:
            st.caption(_("town_fixed"))
        else:
            # Gap so the slider's floating value bubble sits below the bar, not over it.
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            # Value comes from session_state[key] (seeded/synced above), not value=,
            # so Snap/unit-toggle/Edit move the handle.
            val = st.slider(
                "town", min_value=0.0, max_value=float(town_max),
                key=f"town{id(r)}", label_visibility="collapsed",
                on_change=_locked_rebalance, args=(id(r),),
            )
            r.town_mi = R.from_unit(val, unit)
        seg = R.row_segments(r, unit, rates)
        bar_slot.markdown(R.bar_html(seg, _("bar_town"), _("bar_out")),
                          unsafe_allow_html=True)
        # Row metadata under the slider (was above the bar, where it crowded it).
        st.caption(_("row_meta", label=r.label, total=R.to_unit(r.total_mi, unit),
                     unit=unit, km=r.total_mi * R.MI_TO_KM,
                     mh=R.to_unit(r.min_highway_mi, unit)))
    c_total.markdown(f"**{seg.total_l:.1f} L**")

# Baseline for the lock callback: the settled slider values at the end of each run.
st.session_state.prev_town = {
    id(r): st.session_state[f"town{id(r)}"]
    for r in rows if f"town{id(r)}" in st.session_state
}

# --- add row (below the rows) ---
if st.button(_("add_row")):
    _add_row_dialog()

# --- totals table ---
t = R.totals(rows, unit, rates)
st.subheader(_("totals_subheader"))
st.table({
    "": [_("dist_mi"), _("dist_km"), _("fuel_l")],
    _("in_town"): [f"{t.town_mi:.0f}", f"{t.town_km:.0f}", f"{t.town_l:.1f}"],
    _("out_of_town"): [f"{t.out_mi:.0f}", f"{t.out_km:.0f}", f"{t.out_l:.1f}"],
})

implied_end = start_fuel + refuels - t.grand_l
m1, m2 = st.columns(2)
m1.metric(_("grand_total_fuel"), f"{t.grand_l:.1f} L")
m2.metric(_("implied_end_fuel"), f"{implied_end:.2f} L",
          _("vs_pinned", d=implied_end - end_fuel))
within = abs(implied_end - end_fuel) <= tol + 1e-9
st.write(_("end_ok") if within else _("end_no"))

# --- export ---
e1, e2 = st.columns(2)
e1.download_button(
    _("export_computed"),
    R.computed_table_df(rows, unit, rates).to_csv(index=False),
    file_name="gas_audit_computed.csv", mime="text/csv",
)
e2.download_button(
    _("export_input"),
    R.input_csv_df(rows).to_csv(index=False, sep=";"),
    file_name="gas_audit_input.csv", mime="text/csv",
)

# --- context plot ---
plot_labels = {
    "required_town": _("plot_required_town"),
    "required_town_off": _("plot_required_town_off", town=a.town_required),
    "tolerance_band": _("plot_tol_band"),
    "feasible_window": _("plot_feasible_window"),
    "xlabel": _("plot_xlabel"),
    "ylabel": _("plot_ylabel"),
    "title": _("plot_title"),
}
st.pyplot(plot_fuel_vs_town(a, plot_labels))
```

- [ ] **Step 3: Remove csv_path from config.toml**

In `config.toml`, delete the line:

```toml
csv_path = "supp_mat/ПАЛИВО_ОБЛІК.csv"
```

(and the comment line above it `# Period parameters for the gas-audit analysis.` may stay or go — leave the `[fuel]`/`[norm]` sections untouched).

- [ ] **Step 4: Run the app tests to verify they pass**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS (all 5 tests; they now pin `lang="EN"`, so the English labels "Refuels",
"Snap to target", "Lock", and the bar text "town 100 mi" match).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (all tests across all files).

- [ ] **Step 6: Manual smoke check**

Run: `venv/bin/streamlit run app.py` (or in the Codespace it auto-starts). Verify:
- The sidebar shows a `UK | EN` segmented control at the top, UK selected, and the whole UI is Ukrainian.
- Switching to EN flips every label, the totals table headers, the metrics, and the chart axis/legend text.
- "Завантажити CSV" / "Upload CSV" accepts a `;`-delimited file and rows appear; editing a slider then re-running does not wipe edits; uploading a different file replaces the rows.

- [ ] **Step 7: Commit**

```bash
git add app.py config.toml tests/test_app.py
git commit -m "feat: CSV upload control + EN/UK language switch (UK default)"
```

---

## Self-Review Notes

- **Spec coverage:** CSV upload-only + start empty (Task 6 + config), parse-from-text (Tasks 1–2), i18n catalog + switch + all strings (Tasks 3, 6), plot translation (Task 4), bar-label translation (Task 5, a faithful extension of "every visible string"), tests (Tasks 1–6). All spec sections map to a task.
- **Signatures are consistent:** `load_rows_from_text`, `rows_from_csv_text`, `translator(lang)->t(key, **kw)`, `plot_fuel_vs_town(a, labels=None)` with dict keys `required_town/required_town_off/tolerance_band/feasible_window/xlabel/ylabel/title`, `bar_html(seg, town_label, out_label)` — used identically wherever referenced.
- **Backward compatibility:** `load_rows(path)` signature unchanged; `plot_fuel_vs_town`/`bar_html` new args are optional with the original English defaults, so any untouched caller and the pre-existing plot tests keep working.
- **Unit symbols** (mi/km/L) are intentionally left untranslated in both languages; only words are translated. This is a deliberate scope decision noted in the spec's Out of Scope.
```
