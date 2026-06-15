# CSV upload + EN/UK i18n — Design

**Date:** 2026-06-15
**Status:** Approved

## Goal

Two user-facing updates to the Streamlit wiggle-room explorer (`app.py`):

1. Replace the CSV *path* text input with a file **upload** control.
2. Add an **EN/UK language switch** (Ukrainian default) covering every visible
   string, with professional Ukrainian translations.

## Context

- CSV today: a sidebar "CSV path" text input + "Import CSV" button calling
  `R.rows_from_csv(path)`, which ends in `open(path)` in `gasaudit/io.py`. The
  default path points into `supp_mat/`, which is gitignored and absent in a
  Codespace — so the app currently starts empty there anyway.
- UI text today: all strings are hardcoded inline in `app.py`. No i18n layer.
- Only one plot is rendered by `app.py`: `plot_fuel_vs_town` in
  `gasaudit/plots.py`. The other three plot functions are unused by the app.

## 1. CSV upload

- Replace the "CSV path" text input and "Import CSV" button with
  `st.file_uploader(label, type=["csv"])`.
- **Start empty.** Remove the first-run auto-seed from `cfg["csv_path"]`;
  `st.session_state.rows` defaults to `[]`. Remove the now-unused `csv_path`
  key from `config.toml` and the code that reads it.
- **Parse without touching disk.** Refactor `gasaudit/io.py` to split parsing
  from file-opening:
  - Extract the row-parsing loop into a core helper that consumes an iterable
    of text lines (or an open text stream).
  - Keep `load_rows(path, *, to_unit, min_highway_col)` as a thin wrapper that
    opens the file and delegates to the core helper (signature unchanged — keeps
    existing tests/CLI working).
  - Add `load_rows_from_text(text, *, to_unit, min_highway_col)` that wraps the
    text in `io.StringIO` and delegates to the same core helper.
  - In `gasaudit/rows.py`, add `rows_from_csv_text(text)` mirroring
    `rows_from_csv(path)`.
- **App wiring.** Read the uploaded file as
  `uploaded.getvalue().decode("utf-8")` and call `R.rows_from_csv_text(text)`.
  The format is the same `;`-delimited layout the app already imports/exports.
- **No edit-clobbering.** `st.file_uploader` returns the file on every rerun, so
  track the uploaded file's identity (e.g. `uploaded.file_id`) in
  `st.session_state`. Only re-import — replacing `st.session_state.rows` and
  clearing the `seeded` flag — when a genuinely new file arrives. Load failures
  are surfaced with `st.error`. The "Clear rows" button stays.

## 2. EN/UK i18n

- **New module `gasaudit/i18n.py`:**
  - `TRANSLATIONS = {"UK": {...}, "EN": {...}}` keyed by short string keys.
  - `translator(lang) -> callable` returning `t(key, **kwargs)` that looks up
    the key for `lang` and applies `.format(**kwargs)` for strings with
    interpolated values/units. Missing key falls back to `EN`, then to the raw
    key (so a gap is visible, never a crash).
- **Switch widget.** `st.segmented_control("Мова / Language", ["UK", "EN"],
  default="UK")` pinned at the very top of the sidebar (above the parameters).
  Guard a `None` deselection back to `"UK"`.
- **Every visible string** moves behind `t(...)`:
  - Page/title: page title, app title.
  - Sidebar: params header, upload label, norm unit, norm, uplift, start/end
    fuel, refuels, tolerance, Clear rows.
  - Banners: feasible, infeasible, "no per-row minimums" info.
  - Add/Edit row dialog: dialog titles, Date, Total distance, Min highway,
    Add/Save, Cancel, "Total must be greater than 0".
  - Splits section: subheader, "Snap to target", "🔒 Lock total" + its help
    text, "town fixed at 0 — no wiggle room", row metadata caption, the
    delete/edit/move-up/move-down tooltips, "➕ Add row".
  - Totals: subheader, table row labels (Distance mi/km, Fuel L), column headers
    (In town / Out of town), Grand total fuel, Implied end fuel, "vs pinned"
    delta, the two end-fuel match messages.
  - Export: both download-button labels.
  - CSV: "Could not load CSV: {exc}".
- **Plot translation.** `plot_fuel_vs_town(a, labels)` gains a `labels` dict
  argument built in `app.py` from `t`, so the chart's axis titles, legend
  entries ("required town", "tolerance band", "feasible window"), annotation,
  and title translate too. `plots.py` stays decoupled from `i18n` — it only
  receives ready strings, with the current English text as defaults.

### Domain-term glossary (for the record)

| English | Ukrainian |
|---|---|
| wiggle room | запас гнучкості |
| town / in town | місто / у місті |
| out of town / highway | поза містом / траса |
| uplift | надбавка |
| norm | норма |
| odometer | одометр |
| feasible / infeasible | допустимо / недопустимо |
| refuels | заправки |
| start / end fuel | паливо на початок / кінець |
| total fuel | загальне паливо |

(Final wording chosen during implementation; no separate review gate.)

## 3. Testing

- `tests/test_i18n.py`:
  - Parity: `TRANSLATIONS["UK"]` and `TRANSLATIONS["EN"]` have identical key
    sets (catches any missed translation).
  - Formatting: an interpolated key renders correctly via `translator`.
  - Fallback: an unknown key returns the raw key without raising.
- `tests/` for io: `load_rows_from_text` yields the same rows as `load_rows` for
  a sample `;`-delimited CSV string.
- Existing tests unchanged — `load_rows(path)` signature is preserved.

## Files touched

- `gasaudit/i18n.py` (new)
- `gasaudit/io.py` (refactor: extract core parser, add `load_rows_from_text`)
- `gasaudit/rows.py` (add `rows_from_csv_text`)
- `gasaudit/plots.py` (`plot_fuel_vs_town` gains `labels` arg)
- `app.py` (uploader, language switch, all strings behind `t`)
- `config.toml` (remove `csv_path`)
- `tests/test_i18n.py` (new), io test addition

## Out of scope

- Translating the three unused plot functions in `plots.py`.
- Persisting language choice across sessions.
- Non-UTF-8 CSV encodings.
