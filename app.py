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
            text = uploaded.getvalue().decode("utf-8-sig")  # -sig strips Excel's BOM
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
