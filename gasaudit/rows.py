"""Pure logic for the editable-row UI workflow. No Streamlit, no I/O side effects.

RowInput distances are always MILES (canonical). `unit` ('mi'|'km') is the display unit.
"""
from __future__ import annotations

from dataclasses import dataclass

from gasaudit.io import MI_TO_KM


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
