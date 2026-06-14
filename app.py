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
