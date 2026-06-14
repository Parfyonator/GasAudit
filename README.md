# Gas Audit — Town/Highway Wiggle Room

Computes how much a ~10-day fuel report's per-day town/highway split can vary while the
pinned start fuel, end fuel, and refuels stay consistent with the mileage.

## Setup

    venv/bin/pip install -r requirements.txt

## Configure

Edit `config.toml` (fuel levels, refuels, norm, unit, tolerance). For any day with forced
intercity travel, add the minimum highway distance as **column 9** (miles) in the CSV
`supp_mat/ПАЛИВО_ОБЛІК.csv`; days left blank default to 0 (widest, least-constrained window).

## Run

- Static analysis + plots:  `venv/bin/python main.py`  (writes `output/*.png`)
- Interactive explorer:      `venv/bin/streamlit run app.py`

In the interactive app, drag each day's town/highway slider and watch the **implied end fuel**
move toward your pinned target; "Snap to target" fills a valid split for you.

## How it works

Town fuel rate = norm × (1 + uplift), highway = norm × (1 − uplift). Total fuel =
`highway_rate × total_distance + spread × total_town_distance`, so the pinned fuel forces a
single required total town distance. The per-row highway minimums bound which distributions
are feasible; the tool reports each row's swing room and an example valid split, and flags
the report as INFEASIBLE (with the shortfall) when the routes can't reach the target.

## Layout

- `gasaudit/model.py` — pure, unit-tested math core (rates, feasibility, swing room).
- `gasaudit/io.py` — CSV loader + mi/km conversion.
- `gasaudit/report.py` — text summary + example-split table (distances shown in km).
- `gasaudit/plots.py` — four matplotlib charts.
- `main.py` — CLI static path. `app.py` — Streamlit interactive explorer.
- `tests/` — `venv/bin/python -m pytest -q`
