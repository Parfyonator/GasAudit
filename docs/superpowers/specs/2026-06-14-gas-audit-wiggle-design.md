# Gas Audit — Town/Highway "Wiggle Room" Analysis

**Date:** 2026-06-14
**Status:** Design — awaiting user review

## Problem

A car's fuel must be reported every ~10 days on an official form (Донесення / Подорожній
лист). The report must be self-consistent: fuel consumed must match mileage given the car's
fuel norm. Each day's mileage is fixed by the odometer, but the driver may split that mileage
between **town** (higher consumption) and **highway/outside-town** (lower consumption) driving.

The user wants to understand, for a reporting period with **pinned start fuel, pinned end
fuel, and known refuels**, how much freedom ("wiggle room") exists in the per-day town/highway
split, and how (or whether) the total reported expenditure can vary.

## Fuel model

For one day with total distance `m` (odometer delta), split into town `t` and highway `m − t`:

```
base       = norm / 100                      (L per distance-unit; e.g. 20/100 = 0.20 L/mi)
rate_town  = base × (1 + uplift)             (default uplift 0.15  → 0.23 L/mi)
rate_hwy   = base × (1 − uplift)             (default          → 0.17 L/mi)
spread     = rate_town − rate_hwy            (= 2 × base × uplift  → 0.06 L/mi)

fuel_day   = rate_hwy · m + spread · t
```

Summed over the whole period (`M` = total distance, `T` = total town distance):

```
TotalFuel = rate_hwy · M + spread · T
```

### The central consequence (the "gotcha")

`M` is fixed by the odometer. Pinned start/end fuel + refuels fix the period's consumed fuel
`F = start + refuels − end`. Therefore:

```
T_required = (F − rate_hwy · M) / spread        ← a single forced value
```

- **The reported total expenditure does NOT depend on how town miles are distributed across
  days** — only on the grand total `T`. With both fuel levels hard-pinned, total expenditure
  is locked; the only freedom is *which rows* carry the town miles.
- Total expenditure can move **only** if the end fuel is allowed a rounding tolerance
  `±tol` liters. That tolerance is the sole source of a real band in total expenditure and in
  `T_required`.

## Units

- The car's **odometer is in miles**; the daily odometer delta equals town-miles + highway-miles.
- The **official report wants kilometres**: distances are converted `km = miles × 1.609344`.
- Norm unit (mi or km), norm value, and the town/highway uplift are all **settings**.
  This car: norm = 20 L/100 mi, uplift = 0.15.

## Inputs

1. **CSV** `supp_mat/ПАЛИВО_ОБЛІК.csv` — existing table. Relevant per-row fields:
   odometer start, odometer end (→ daily total miles), town miles, highway miles, route string.
   Header rows carry start odometer and start fuel (63 L).
2. **New manual CSV column** `min_highway_mi` — per row, the minimum highway distance forced
   by the route (0 for in-base days; the shortest intercity road distance for travel days).
3. **Period parameters** (config / CLI args, not all present in the CSV):
   - `start_fuel` (L), `end_fuel` (L), `refuels` (L, total added during period)
   - `norm`, `norm_unit` (mi|km), `uplift` (default 0.15)
   - `end_fuel_tol` (L, default 0 — rounding tolerance on end fuel)
   - optional per-row town floor `min_town_mi` (default 0)

## Per-row feasible band

For each row `i` with total miles `m_i`:

```
t_i ∈ [ t_min_i , t_max_i ]
  t_max_i = m_i − min_highway_mi_i        (all non-forced-highway miles can be town)
  t_min_i = min_town_mi_i                 (default 0)
```

A distribution `{t_i}` is **valid** iff every `t_i` is in its band AND `Σ t_i = T_required`
(within tolerance band `[T_lo, T_hi]` derived from `end_fuel_tol`).

## Outputs / analysis

1. **Forced numbers:** `F`, `T_required` (and the `[T_lo, T_hi]` band under tolerance),
   equivalent total town/highway km, total fuel.
2. **Feasibility check:** is `T_required ∈ [Σ t_min_i, Σ t_max_i]`? Report slack on each side
   (`Σt_max − T_required` and `T_required − Σt_min`). If infeasible, say by how much and which
   rows are binding.
3. **Per-row swing room:** for each row, the min and max `t_i` achievable while the remaining
   rows still compensate to keep `Σ t = T_required`:
   - `t_i_hi = min( t_max_i , T_required − Σ_{j≠i} t_min_j )`
   - `t_i_lo = max( t_min_i , T_required − Σ_{j≠i} t_max_j )`
   This is each row's true degree of freedom. Width `t_i_hi − t_i_lo` = that row's wiggle.
4. **Tolerance sensitivity:** how `T_required` band and total swing widen as `end_fuel_tol`
   grows (small sweep, e.g. 0…3 L).
5. **A concrete valid distribution:** one example split (e.g. proportional fill) that satisfies
   all constraints, to drop straight into a report — emitted as a small table (miles + km).

## Visualisations (matplotlib → PNG in `output/`)

- **Per-row feasible band** floating-bar chart: for each day, full bar = total miles, shaded
  segment = town swing room `[t_i_lo, t_i_hi]`, marker = the example distribution's value.
- **Total-fuel vs total-town-share** line: fuel as a function of `T` from 0…M, with `T_required`
  and the tolerance band marked — shows directly how little (or much) the total can move.
- **Swing-room bar chart:** per-row wiggle width, sorted — shows where the flexibility is.
- **Tolerance sensitivity:** total-town-distance band width vs `end_fuel_tol`.

## Components

- `gasaudit/model.py` — pure functions: rates from norm/uplift, `total_fuel(M, T)`,
  `t_required(F, M, rates)`, per-row bands, swing room, example distribution. No I/O. Unit-testable.
- `gasaudit/io.py` — parse the CSV (handle the messy header/footer rows) into clean per-row
  records; unit conversion helpers (mi↔km).
- `gasaudit/report.py` — assemble the textual summary and the example-distribution table.
- `gasaudit/plots.py` — the four charts.
- `main.py` — wire it together: load config + CSV, run analysis, print summary, write plots.
- `config.toml` (or CLI args) — the period parameters above.
- `tests/` — unit tests for `model.py` (the math) and `io.py` (CSV quirks).

## Dependencies

`numpy`, `pandas`, `matplotlib` (install into existing `venv`). Python 3.13.

## Out of scope (for now)

- Automatic route-string parsing to derive `min_highway_mi` (manual column for now).
- Generating the filled official PDF/form. This tool produces the numbers + plots that inform
  what to write; it does not reproduce the scanned form.
- Per-row fuel rounding effects — the official report only carries period totals, so per-row
  fuel is never reported and introduces no rounding.

## Open assumptions (flag if wrong)

- Odometer is in miles; daily delta = town + highway miles. (Confirmed by CSV: deltas match
  the miles columns.)
- `end_fuel` and `refuels` are supplied per period (not in the current CSV).
- "Within reason" per row = highway ≥ route minimum, town ≥ 0 (overridable).
