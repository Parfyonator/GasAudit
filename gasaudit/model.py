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
