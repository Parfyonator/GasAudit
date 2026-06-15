import matplotlib
matplotlib.use("Agg")

import main as main_mod

# A minimal config (no csv_path — the CLI takes the CSV as an argument) plus a tiny
# CSV. This is a smoke test: it exercises main()'s config+CSV wiring end-to-end and
# would have caught the KeyError regression from removing csv_path from config.toml.
_CONFIG = """\
[fuel]
start_fuel = 63.0
end_fuel = 40.0
refuels = 0.0
end_fuel_tol = 0.0

[norm]
value = 20.0
unit = "mi"
uplift = 0.15
"""

_CSV = (
    ";h;;;;;;\n"
    "25-May;175010;175137;127;route;47;80;76;129;80\n"
    "26-May;175137;175190;53;route;53;;85;0\n"
)


def test_main_runs_and_writes_plots(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text(_CONFIG, encoding="utf-8")
    csv = tmp_path / "fuel.csv"
    csv.write_text(_CSV, encoding="utf-8")
    monkeypatch.chdir(tmp_path)  # so output/ lands in the temp dir, not the repo

    main_mod.main(config_path=str(cfg), csv_path=str(csv))

    assert (tmp_path / "output" / "fuel_vs_town.png").exists()
