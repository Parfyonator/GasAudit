"""Pure math core for gas-audit wiggle-room analysis.

Distance-unit-agnostic: all distances are in the norm's unit. Callers convert.
"""
from __future__ import annotations

from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class Rates:
    base: float       # litres per distance-unit (norm / 100)
    town: float       # base * (1 + uplift)
    highway: float    # base * (1 - uplift)

    @property
    def spread(self) -> float:
        return self.town - self.highway


def rates_from_norm(norm: float, uplift: float = 0.15) -> Rates:
    base = norm / 100.0
    return Rates(base=base, town=base * (1 + uplift), highway=base * (1 - uplift))


def total_fuel(rates: Rates, total_dist: float, town_dist: float) -> float:
    """Period fuel = highway-rate * total distance + spread * total town distance."""
    return rates.highway * total_dist + rates.spread * town_dist


def required_town(rates: Rates, total_dist: float, fuel: float) -> float:
    """The total town distance that makes total_fuel equal `fuel`."""
    return (fuel - rates.highway * total_dist) / rates.spread


@dataclass(frozen=True)
class Row:
    label: str
    total: float            # odometer delta, in the norm's distance unit
    min_highway: float = 0.0
    min_town: float = 0.0
    route: str = ""

    @property
    def town_min(self) -> float:
        return self.min_town

    @property
    def town_max(self) -> float:
        return self.total - self.min_highway

    def validate(self) -> "Row":
        if self.town_max < self.town_min - EPS:
            raise ValueError(
                f"row {self.label!r}: min_highway ({self.min_highway}) + "
                f"min_town ({self.min_town}) exceed total ({self.total})"
            )
        return self


def feasible_window(rows: list[Row]) -> tuple[float, float]:
    """Min and max achievable TOTAL town distance across all rows."""
    return (sum(r.town_min for r in rows), sum(r.town_max for r in rows))


def example_distribution(rows: list[Row], target_town: float) -> list[float] | None:
    """A concrete per-row town split summing to target_town, each within its band.

    Fills proportionally to each row's spare capacity above its town floor.
    Returns None if target_town is outside the feasible window.
    """
    lo, hi = feasible_window(rows)
    if target_town < lo - EPS or target_town > hi + EPS:
        return None
    caps = [r.town_max - r.town_min for r in rows]
    total_cap = sum(caps)
    remaining = target_town - lo
    if total_cap <= EPS:
        return [r.town_min for r in rows]
    return [r.town_min + remaining * c / total_cap for r, c in zip(rows, caps)]


def swing_room(
    rows: list[Row], sum_lo: float, sum_hi: float
) -> list[tuple[float, float]]:
    """Per-row achievable town range, given the TOTAL town must lie in [sum_lo, sum_hi]
    and other rows compensate within their own bounds."""
    all_min = sum(r.town_min for r in rows)
    all_max = sum(r.town_max for r in rows)
    out: list[tuple[float, float]] = []
    for r in rows:
        others_min = all_min - r.town_min
        others_max = all_max - r.town_max
        hi = min(r.town_max, sum_hi - others_min)
        lo = max(r.town_min, sum_lo - others_max)
        out.append((lo, hi))
    return out


@dataclass(frozen=True)
class Params:
    start_fuel: float
    end_fuel: float
    refuels: float = 0.0
    norm: float = 20.0
    norm_unit: str = "mi"     # "mi" or "km" — informational for the model
    uplift: float = 0.15
    end_fuel_tol: float = 0.0


@dataclass(frozen=True)
class Analysis:
    rates: Rates
    total_dist: float
    consumed_fuel: float
    town_required: float
    town_band: tuple[float, float]        # from end_fuel_tol
    feasible_window: tuple[float, float]
    allowed: tuple[float, float]          # town_band intersect feasible_window
    feasible: bool
    swing: list[tuple[float, float]]      # per-row town range
    example: list[float] | None           # per-row town split hitting town_required


def analyze(rows: list[Row], params: Params) -> Analysis:
    for r in rows:
        r.validate()
    rates = rates_from_norm(params.norm, params.uplift)
    total_dist = sum(r.total for r in rows)
    consumed = params.start_fuel + params.refuels - params.end_fuel
    town_req = required_town(rates, total_dist, consumed)
    tol_dist = params.end_fuel_tol / rates.spread
    band = (town_req - tol_dist, town_req + tol_dist)
    window = feasible_window(rows)
    allowed = (max(band[0], window[0]), min(band[1], window[1]))
    feasible = allowed[0] <= allowed[1] + EPS
    if feasible:
        swing = swing_room(rows, allowed[0], allowed[1])
        target = min(max(town_req, window[0]), window[1])
        example = example_distribution(rows, target)
    else:
        swing = [(r.town_min, r.town_min) for r in rows]
        example = None
    return Analysis(
        rates=rates, total_dist=total_dist, consumed_fuel=consumed,
        town_required=town_req, town_band=band, feasible_window=window,
        allowed=allowed, feasible=feasible, swing=swing, example=example,
    )
