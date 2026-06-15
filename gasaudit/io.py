"""Load the fuel CSV into model.Row objects; distance-unit helpers."""
from __future__ import annotations

import csv

from gasaudit.model import Row

MI_TO_KM = 1.609344


def mi_to_km(x: float) -> float:
    return x * MI_TO_KM


def km_to_mi(x: float) -> float:
    return x / MI_TO_KM


def _is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except (TypeError, ValueError):
        return False


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
