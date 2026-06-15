"""CLI: load config + CSV, run the analysis, print summary, write plots to output/."""
from __future__ import annotations

import os
import tomllib

import matplotlib
matplotlib.use("Agg")

from gasaudit.io import load_rows
from gasaudit.model import Params, analyze
from gasaudit.plots import (
    plot_fuel_vs_town, plot_row_bands, plot_swing_widths, plot_tolerance_sensitivity,
)
from gasaudit.report import example_table, summary_text


DEFAULT_CSV = "supp_mat/ПАЛИВО_ОБЛІК.csv"


def main(config_path: str = "config.toml", csv_path: str = DEFAULT_CSV) -> None:
    with open(config_path, "rb") as fh:
        cfg = tomllib.load(fh)
    unit = cfg["norm"]["unit"]
    rows = load_rows(csv_path, to_unit=unit)
    params = Params(
        start_fuel=cfg["fuel"]["start_fuel"],
        end_fuel=cfg["fuel"]["end_fuel"],
        refuels=cfg["fuel"]["refuels"],
        end_fuel_tol=cfg["fuel"]["end_fuel_tol"],
        norm=cfg["norm"]["value"],
        norm_unit=unit,
        uplift=cfg["norm"]["uplift"],
    )
    a = analyze(rows, params)
    if all(r.min_highway == 0 for r in rows):
        print(
            "NOTE: no per-row highway minimums set (CSV has no 10th 'min_highway' "
            "field), so every day's town share can range 0..total — the feasible "
            "window is the widest possible. Add minimums to constrain it.\n"
        )
    print(summary_text(a, work_unit=unit))
    print()
    print(example_table(rows, a, work_unit=unit))

    os.makedirs("output", exist_ok=True)
    plot_row_bands(rows, a).savefig("output/row_bands.png", dpi=120)
    plot_fuel_vs_town(a).savefig("output/fuel_vs_town.png", dpi=120)
    plot_swing_widths(rows, a).savefig("output/swing_widths.png", dpi=120)
    plot_tolerance_sensitivity(rows, params).savefig(
        "output/tolerance.png", dpi=120)
    print("\nPlots written to output/")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Gas-audit static analysis: print summary + write plots to output/.")
    p.add_argument("csv_path", nargs="?", default=DEFAULT_CSV,
                   help=f"path to the fuel CSV (default: {DEFAULT_CSV})")
    p.add_argument("--config", default="config.toml", help="path to config.toml")
    args = p.parse_args()
    main(args.config, args.csv_path)
