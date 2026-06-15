"""Pure logic for the editable-row UI workflow. No Streamlit, no I/O side effects.

RowInput distances are always MILES (canonical). `unit` ('mi'|'km') is the display unit.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from gasaudit.io import MI_TO_KM, load_rows, load_rows_from_text
from gasaudit.model import Rates, Row


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
    # Note: normalizes row.town_mi in place (idempotent) so segment math can't go out of range.
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


def update_row(rows: list[RowInput], i: int, label: str, total_mi: float,
               min_highway_mi: float) -> list[RowInput]:
    """Edit an existing row's label/total/min in place; re-clamp min and town."""
    if 0 <= i < len(rows):
        r = rows[i]
        r.label = label
        r.total_mi = total_mi
        r.min_highway_mi = min(min_highway_mi, total_mi)
        clamp_town(r)
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


def rebalance(values: list[float], maxima: list[float], moved_index: int,
              target_sum: float, pool: list[int] | None = None) -> list[float]:
    """Adjust the entries in `pool` so the total returns to `target_sum`, keeping each
    within [0, maxima[j]].

    Used by the "lock total" mode: when one day's town split moves, other days shift to
    keep the grand total town distance (hence total fuel) constant. `pool` is the set of
    indices allowed to absorb the change (the app passes only the rows BELOW the moved one);
    it defaults to every index except `moved_index`. The change is spread proportionally —
    to current value when the pool must shrink, to remaining capacity when it must grow. If
    the pool can't absorb it all, the moved entry is pulled back so the total is preserved
    exactly when possible.
    """
    out = [min(max(v, 0.0), m) for v, m in zip(values, maxima)]
    if pool is None:
        pool = [j for j in range(len(out)) if j != moved_index]
    else:
        pool = [j for j in pool if j != moved_index]
    for _ in range(1000):
        delta = sum(out) - target_sum
        if abs(delta) <= 1e-9:
            break
        if delta > 0:  # pool must shrink
            active = [j for j in pool if out[j] > 1e-9]
            weight = sum(out[j] for j in active)
            if weight <= 1e-9:
                break
            for j in active:
                out[j] = max(0.0, out[j] - delta * out[j] / weight)
        else:  # pool must grow
            active = [j for j in pool if out[j] < maxima[j] - 1e-9]
            weight = sum(maxima[j] - out[j] for j in active)
            if weight <= 1e-9:
                break
            for j in active:
                out[j] = min(maxima[j], out[j] + (-delta) * (maxima[j] - out[j]) / weight)
    residual = sum(out) - target_sum
    if abs(residual) > 1e-9:  # pool exhausted: pull the moved entry back
        out[moved_index] = min(max(out[moved_index] - residual, 0.0), maxima[moved_index])
    return out


def bar_html(seg: RowSegments, town_label: str = "town", out_label: str = "out") -> str:
    """Full-width labeled two-segment bar (red town, grey out), as inline-styled HTML.

    Bar only — the row-total liters is rendered separately by the app so the bar's width
    matches the slider beneath it.
    """
    town_pct = round(seg.town_frac * 100)
    out_pct = 100 - town_pct
    parts = []
    if town_pct > 0 and seg.town_mi > 0:
        parts.append(
            f'<div style="width:{town_pct}%;background:#d24b4b;color:#fff;'
            'display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'line-height:1.2;overflow:hidden;">'
            f'<b style="font-size:13px;white-space:nowrap;">{town_label} {seg.town_mi:.0f} mi · '
            f'{seg.town_km:.0f} km</b>'
            f'<small style="font-size:11px;opacity:.9;">({seg.town_l:.1f} L)</small></div>'
        )
    if out_pct > 0 and seg.out_mi > 0:
        parts.append(
            f'<div style="width:{out_pct}%;background:#c9d2d9;color:#243;'
            'display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'line-height:1.2;overflow:hidden;">'
            f'<b style="font-size:13px;white-space:nowrap;">{out_label} {seg.out_mi:.0f} mi · '
            f'{seg.out_km:.0f} km</b>'
            f'<small style="font-size:11px;opacity:.9;">({seg.out_l:.1f} L)</small></div>'
        )
    return (
        '<div style="display:flex;height:46px;width:100%;border-radius:6px;overflow:hidden;'
        'box-shadow:inset 0 0 0 1px rgba(0,0,0,.15);">' + "".join(parts) + "</div>"
    )


def rows_from_csv(path: str) -> list[RowInput]:
    """Seed RowInputs from the CSV (miles); town_mi defaults to 0 (caller re-seeds)."""
    model_rows = load_rows(path, to_unit="mi")
    return [
        RowInput(label=m.label, total_mi=m.total, min_highway_mi=m.min_highway, town_mi=0.0)
        for m in model_rows
    ]


def rows_from_csv_text(text: str) -> list[RowInput]:
    """Seed RowInputs from an uploaded CSV string (miles); town_mi defaults to 0."""
    model_rows = load_rows_from_text(text, to_unit="mi")
    return [
        RowInput(label=m.label, total_mi=m.total, min_highway_mi=m.min_highway, town_mi=0.0)
        for m in model_rows
    ]


def computed_table_df(rows: list[RowInput], unit: str, rates: Rates) -> pd.DataFrame:
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
    # Pass explicit columns so an empty row list still exports a header row.
    cols = ["date", f"total {unit}", f"town {unit}", "town km", "town L",
            f"out {unit}", "out km", "out L", "row L"]
    return pd.DataFrame(data, columns=cols)


def input_csv_df(rows: list[RowInput]) -> pd.DataFrame:
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
