"""Matplotlib figures for the analysis. Each function returns a Figure."""
from __future__ import annotations

import matplotlib.pyplot as plt

from gasaudit.model import Analysis, Params, Row, rates_from_norm


def plot_row_bands(rows: list[Row], a: Analysis):
    """Per-day: full bar = total distance; shaded = town swing [lo,hi]; dot = example."""
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 1.5))
    labels = [r.label for r in rows]
    y = range(len(rows))
    ax.barh(list(y), [r.total for r in rows], color="#e8e8e8", label="total distance")
    for i, (r, (lo, hi)) in enumerate(zip(rows, a.swing)):
        ax.barh(i, hi - lo, left=lo, color="#6fa8dc", label="town swing" if i == 0 else "")
    if a.example is not None:
        ax.plot(a.example, list(y), "o", color="#cc0000", label="example split")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.set_xlabel("town distance (work unit)")
    ax.set_title("Per-row town swing room")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


def plot_fuel_vs_town(a: Analysis):
    """Total fuel as a function of total town distance, with target/band/window marked."""
    fig, ax = plt.subplots(figsize=(8, 5))
    lo_w, hi_w = a.feasible_window
    xs = [lo_w + (hi_w - lo_w) * k / 100 for k in range(101)]
    ys = [a.rates.highway * a.total_dist + a.rates.spread * x for x in xs]
    ax.plot(xs, ys, color="#333333")
    span = hi_w - lo_w
    if lo_w - span * 0.1 <= a.town_required <= hi_w + span * 0.1:
        ax.axvline(a.town_required, color="#cc0000", label="required town")
    else:
        ax.annotate(
            f"required town {a.town_required:.0f} (off-scale)",
            xy=(0.5, 0.9), xycoords="axes fraction",
            ha="center", color="#cc0000",
        )
    ax.axvspan(a.town_band[0], a.town_band[1], color="#cc0000", alpha=0.15,
               label="tolerance band")
    ax.axvspan(lo_w, hi_w, color="#6fa8dc", alpha=0.1, label="feasible window")
    ax.set_xlabel("total town distance")
    ax.set_ylabel("total fuel (L)")
    ax.set_title("Total fuel vs total town distance")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_swing_widths(rows: list[Row], a: Analysis):
    """Bar chart of each row's swing width (hi - lo), sorted descending."""
    widths = sorted(
        [(r.label, hi - lo) for r, (lo, hi) in zip(rows, a.swing)],
        key=lambda t: t[1], reverse=True,
    )
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 1.5))
    ax.barh([w[0] for w in widths], [w[1] for w in widths], color="#93c47d")
    ax.invert_yaxis()
    ax.set_xlabel("swing width (work unit)")
    ax.set_title("Where the flexibility is (per-row swing width)")
    fig.tight_layout()
    return fig


def plot_tolerance_sensitivity(rows: list[Row], params: Params):
    """How the total-town band width grows with end-fuel tolerance."""
    rates = rates_from_norm(params.norm, params.uplift)
    tols = [t / 10 for t in range(0, 31)]  # 0..3 L
    widths = [min(2 * t / rates.spread,
                  sum(r.town_max for r in rows) - sum(r.town_min for r in rows))
              for t in tols]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(tols, widths, color="#674ea7")
    ax.set_xlabel("end-fuel tolerance (±L)")
    ax.set_ylabel("total town band width (work unit)")
    ax.set_title("Tolerance sensitivity")
    fig.tight_layout()
    return fig
