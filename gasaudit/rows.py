"""Pure logic for the editable-row UI workflow. No Streamlit, no I/O side effects.

RowInput distances are always MILES (canonical). `unit` ('mi'|'km') is the display unit.
"""
from __future__ import annotations

from dataclasses import dataclass

from gasaudit.io import MI_TO_KM
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
