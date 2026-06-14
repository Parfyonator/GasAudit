"""Human-readable summary and example-split table. Distances shown in km."""
from __future__ import annotations

from gasaudit.io import MI_TO_KM
from gasaudit.model import Analysis, Row


def _km(value: float, work_unit: str) -> float:
    return value * MI_TO_KM if work_unit == "mi" else value


def summary_text(a: Analysis, work_unit: str) -> str:
    status = "FEASIBLE" if a.feasible else "INFEASIBLE"
    lines = [
        f"Status: {status}",
        f"Total distance: {a.total_dist:.1f} {work_unit} "
        f"({_km(a.total_dist, work_unit):.1f} km)",
        f"Fuel consumed (pinned): {a.consumed_fuel:.2f} L",
        f"Required total town distance: {a.town_required:.1f} {work_unit} "
        f"({_km(a.town_required, work_unit):.1f} km)",
        f"Town band (tolerance): {a.town_band[0]:.1f} … {a.town_band[1]:.1f} {work_unit}",
        f"Feasible town window: {a.feasible_window[0]:.1f} … "
        f"{a.feasible_window[1]:.1f} {work_unit}",
    ]
    if not a.feasible:
        lo, hi = a.feasible_window
        if a.town_required > hi:
            short = a.town_required - hi
            lines.append(
                f"  -> need {short:.1f} {work_unit} MORE town capacity: "
                f"routes force too much highway (lower min_highway on some rows)."
            )
        else:
            short = lo - a.town_required
            lines.append(
                f"  -> town floor exceeds the target by {short:.1f} {work_unit}: "
                f"lower town_min on some rows, or the report under-consumes fuel."
            )
    return "\n".join(lines)


def example_table(rows: list[Row], a: Analysis, work_unit: str) -> str:
    header = f"{'day':<8}{'town '+work_unit:>10}{'town km':>10}{'swing '+work_unit:>14}"
    out = [header]
    example = a.example or [float("nan")] * len(rows)
    for r, t, (lo, hi) in zip(rows, example, a.swing):
        out.append(
            f"{r.label:<8}{t:>10.1f}{_km(t, work_unit):>10.1f}"
            f"{f'{lo:.0f}-{hi:.0f}':>14}"
        )
    return "\n".join(out)
