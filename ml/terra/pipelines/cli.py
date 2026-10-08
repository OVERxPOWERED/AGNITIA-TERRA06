"""TERRA command line. Installed as the `terra` command (see ml/pyproject.toml [project.scripts]).

Commands (run in this order the first time):
  terra fetch-weather            # Open-Meteo -> data/interim/weather_*.parquet   (needs internet)
  terra build-dataset            # -> data/processed/dataset.parquet   (--synthetic for offline dev)
  terra frame                    # -> data/processed/framed_{solar,wind}.parquet
  terra train [--chronos-dir artifacts/chronos]   # models, ensemble, CQR -> artifacts/
  terra evaluate                 # engines (hybrid, trust, alerts, value-of-forecast, DSM, impact)
  terra report                   # docs/accuracy-report.md + plots
  terra forecast --mode replay   # one run -> artifacts/runs/<issue>/
  terra export-kaggle            # bundle for the Kaggle GPU notebooks
Imports are inside each command so the CLI works before later phases exist.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import pandas as pd
import typer

from terra.config import load_config
from terra.paths import ARTIFACTS, CONFIG_DIR, DATA_DIR, DATA_INTERIM, DATA_PROCESSED, ensure_dirs

app = typer.Typer(add_completion=False, help="TERRA forecasting pipeline")


@app.command("fetch-weather")
def fetch_weather(offline: bool = typer.Option(False, help="only use cached responses")) -> None:
    from terra.data.openmeteo import OpenMeteoClient
    from terra.data.weather_tables import build_weather_tables
    cfg = load_config()
    ensure_dirs()
    act, fx = build_weather_tables(cfg, OpenMeteoClient(offline=offline))
    typer.echo(f"actual {act.shape}, forecast {fx.shape} -> {DATA_INTERIM}")


@app.command("build-dataset")
def build_dataset_cmd(synthetic: bool = typer.Option(False, help="use synthetic weather (offline dev only)")) -> None:
    from terra.data.build_dataset import build_dataset
    from terra.data.quality import check_dataset
    from terra.data.weather_tables import build_weather_tables
    cfg = load_config()
    ensure_dirs()
    if synthetic:
        act, fx = build_weather_tables(cfg, synthetic=True)
    else:
        act = pd.read_parquet(DATA_INTERIM / "weather_actual.parquet")
        fx = pd.read_parquet(DATA_INTERIM / "weather_forecast.parquet")
    real_demand = None
    if cfg.demand.shape_source == "india_hourly":
        from terra.real.loaders import load_india_hourly
        real_demand = load_india_hourly()["demand_mw"]
    ds = build_dataset(cfg, act, fx, real_demand)
    problems = check_dataset(ds, cfg)
    if problems:
        typer.echo("QUALITY PROBLEMS:\n- " + "\n- ".join(problems))
        raise typer.Exit(code=1)
    typer.echo(f"dataset OK: {ds.shape} -> {DATA_PROCESSED / 'dataset.parquet'}")


@app.command()
def frame() -> None:
    from terra.data.build_dataset import load_dataset
    from terra.features.framing import frame_all
    cfg = load_config()
    for s, f in frame_all(load_dataset(), cfg).items():
        f.to_parquet(DATA_PROCESSED / f"framed_{s}.parquet")
        typer.echo(f"{s}: {f.shape} {f['split'].value_counts().to_dict()}")


@app.command()
def train(chronos_dir: Optional[Path] = typer.Option(None, help="folder with <source>_<model>.parquet from Kaggle")
          ) -> None:
    from terra.pipelines.train import train_all
    cfg = load_config()
    frames = {s: pd.read_parquet(DATA_PROCESSED / f"framed_{s}.parquet") for s in ("solar", "wind")}
    external = None
    if chronos_dir:
        external = {s: {p.stem.split("_", 1)[1]: pd.read_parquet(p) for p in sorted(chronos_dir.glob(f"{s}_*.parquet"))}
                    for s in ("solar", "wind")}
    params_file = CONFIG_DIR / "gbm_params.yaml"
    gbm_params = None
    if params_file.exists():                      # written by the tuning step (task T4.5.1)
        import yaml
        gbm_params = yaml.safe_load(params_file.read_text())
    train_all(frames, cfg, external, gbm_params=gbm_params)
    typer.echo(f"models saved under {ARTIFACTS / 'models'}")


@app.command()
def evaluate() -> None:
    from terra.pipelines.evaluate import evaluate_all
    r = evaluate_all(load_config())
    typer.echo(r["impact"])


@app.command()
def report() -> None:
    from terra.eval.report import write_reports
    write_reports(load_config())
    typer.echo("docs/accuracy-report.md written")


@app.command()
def forecast(mode: str = typer.Option("replay", help="live | replay"),
             at: Optional[str] = typer.Option(None, help="replay 'now', e.g. 2026-05-10T00:00")) -> None:
    from terra.pipelines.forecast import run_forecast
    out = run_forecast(load_config(), mode, at)
    typer.echo(f"run written: {out}")


@app.command("export-kaggle")
def export_kaggle() -> None:
    """Bundle dataset + config + terra source for the Kaggle GPU notebooks (task T4.3.x / T4.4.x).

    Contains all splits because Chronos-2 must PREDICT val+test; fine-tuning code only ever reads the
    train/val date ranges (enforced in Chronos2Forecaster.finetune_lora).
    """
    from terra.paths import REPO_ROOT
    out = DATA_DIR / "kaggle_upload"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy(DATA_PROCESSED / "dataset.parquet", out / "dataset.parquet")
    shutil.copy(CONFIG_DIR / "site.yaml", out / "site.yaml")
    shutil.copytree(REPO_ROOT / "ml" / "terra", out / "terra_src" / "terra",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for s in ("solar", "wind"):
        f = pd.read_parquet(DATA_PROCESSED / f"framed_{s}.parquet", columns=["issue_time_utc", "split"])
        issues = f.loc[f["split"].isin(["val", "test"]), ["issue_time_utc"]].drop_duplicates()
        issues.to_parquet(out / f"issues_{s}.parquet")
    typer.echo(f"Kaggle bundle -> {out}\nUpload: kaggle datasets version -p {out} -m 'update' --dir-mode zip")


@app.command()
def calibrate() -> None:
    from terra.real.calibrate_solar import run as cal_solar
    from terra.real.calibrate_state import run as cal_state
    from terra.real.calibrate_wind import run as cal_wind
    cal_solar()
    cal_wind()
    cal_state()
    typer.echo("calibration written to config/calibration/ and docs/calibration.md")


@app.command("real-benchmark")
def real_benchmark() -> None:
    from terra.real.benchmarks import run_all
    run_all()
    typer.echo("docs/real-data-results.md written")


if __name__ == "__main__":
    app()
