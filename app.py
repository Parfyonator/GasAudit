"""Interactive wiggle-room explorer. Run: venv/bin/streamlit run app.py"""
from __future__ import annotations

import tomllib

import streamlit as st

from gasaudit.io import load_rows
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

if all(r.min_highway == 0 for r in rows):
    st.info(
        "No per-row highway minimums set (no 10th 'min_highway' field in the CSV). "
        "Town share can range 0..total each day — widest possible window. "
        "Add minimums to constrain it."
    )

# Per-row sliders, seeded from the example split (snap-to-target)
st.subheader("Per-row town distance")
snap = st.button("Snap to target")
if "town_values" not in st.session_state or snap:
    st.session_state.town_values = list(
        a.example if a.example is not None else [r.town_min for r in rows]
    )

town_values = []
for i, (r, (lo, hi)) in enumerate(zip(rows, a.swing)):
    if r.town_max <= r.town_min + 1e-9:
        st.write(
            f"{r.label}  (total {r.total:.0f} {unit}, town fixed at "
            f"{r.town_min:.0f} {unit} — no wiggle room)"
        )
        town_values.append(r.town_min)
        continue
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
