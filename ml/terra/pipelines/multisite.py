"""Multi-site training: one model for all allowlisted sites, checked on sites it never saw.

Data per site (same recipe as Dewas, same virtual plant, site block swapped):
  real Open-Meteo archived forecasts (Previous Runs API) and actual weather (archive) -> twin targets.
Everything is leak-free exactly as for Dewas: features come from forecast weather, calendar/sun geometry,
static site descriptors (lat, lon, altitude) and generation up to the issue time; splits are by time.
NASA POWER is deliberately not a training input: it is a record of weather that happened (like the archive
weather), never a forecast, so using it as a feature would hand the model the future.

Outputs: data/processed/sites/<id>/{dataset,framed_solar,framed_wind}.parquet,
         artifacts/multisite/{loso_metrics.csv,pooled_test_by_site.csv,meta.json}
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from terra.config import TerraConfig, load_config
from terra.data.build_dataset import build_dataset, load_dataset
from terra.data.openmeteo import OpenMeteoClient
from terra.data.weather_tables import build_weather_tables
from terra.features.framing import frame_all
from terra.locations import Location, config_for, load_locations
from terra.logs import get_logger
from terra.paths import ARTIFACTS, DATA_PROCESSED

log = get_logger(__name__)
SITES_DIR = DATA_PROCESSED / "sites"


def site_dir(loc_id: str) -> Path:
    return SITES_DIR / loc_id


def build_site(cfg: TerraConfig, loc: Location, home: str, client: OpenMeteoClient | None = None) -> dict:
    """Fetch weather, build the twin dataset and the framed tables for one site."""
    scfg = config_for(cfg, loc)
    d = site_dir(loc.id)
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if loc.id == home:
        ds = load_dataset()                              # the existing, already-validated Dewas dataset
    else:
        act, fx = build_weather_tables(scfg, client or OpenMeteoClient(), save=False)
        real_demand = None
        if scfg.demand.shape_source == "india_hourly":
            from terra.real.loaders import load_india_hourly
            real_demand = load_india_hourly()["demand_mw"]
        ds = build_dataset(scfg, act, fx, real_demand, save=False, state_scale=False)
    ds.to_parquet(d / "dataset.parquet")
    frames = frame_all(ds, scfg)
    for s, f in frames.items():
        f.insert(0, "site", loc.id)
        f.to_parquet(d / f"framed_{s}.parquet")
    info = {"site": loc.id, "rows": len(ds), "solar_cf": round(float(ds["solar_mw"].mean() / scfg.solar.ac_capacity_mw), 3),
            "wind_cf": round(float(ds["wind_mw"].mean() / scfg.wind.capacity_mw), 3),
            "seconds": round(time.time() - t0, 1), "gap_rows": int(ds["gap_flag"].sum())}
    log.info("site %s built: %s", loc.id, info)
    return info


def build_all(only: list[str] | None = None) -> list[dict]:
    cfg = load_config()
    sites, home = load_locations()
    out = []
    for loc in sites:
        if only and loc.id not in only:
            continue
        out.append(build_site(cfg, loc, home))
    return out


def load_frames(source: str, ids: list[str]) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(site_dir(i) / f"framed_{source}.parquet") for i in ids], ignore_index=True)


# --------------------------------------------------------------------------------------------------------------
# evaluation and training
# --------------------------------------------------------------------------------------------------------------
KEEP_MODELS = ("persistence", "physics", "gbm", "ensemble")


def _gbm_params(source: str) -> dict | None:
    import yaml

    from terra.paths import CONFIG_DIR
    p = CONFIG_DIR / "gbm_params.yaml"
    return (yaml.safe_load(p.read_text()) or {}).get(source) if p.exists() else None


def _score(bundle, frame: pd.DataFrame, split: str, source: str, cap: float, label: str, site: str) -> pd.DataFrame:
    """Per-model metrics of `bundle` on one site's rows of one split (daylight hours for solar)."""
    from terra.eval.backtest import long_predictions
    from terra.eval.metrics import metrics_table
    rows = frame[frame["split"] == split]
    cal, preds, _ = bundle.predict(rows)
    preds = {k: v for k, v in preds.items() if k in KEEP_MODELS}
    preds["ensemble"] = cal
    lp = long_predictions(rows, preds, source).dropna(subset=["q50"])
    t = metrics_table(lp, cap, daylight_only=source == "solar")
    t.insert(0, "site", site)
    t.insert(1, "source", source)
    t.insert(2, "variant", label)
    t["split"] = split
    return t


def _train(frame: pd.DataFrame, source: str, cfg: TerraConfig):
    from terra.pipelines.train import train_source
    t0 = time.time()
    bundle, _, _ = train_source(frame, source, cfg, None, _gbm_params(source))
    bundle.meta["train_seconds"] = round(time.time() - t0, 1)
    return bundle


def run_loso(sites: list[str] | None = None) -> pd.DataFrame:
    """For each site: Dewas-only model vs multi-site model trained WITHOUT that site vs a model trained only there.
    Calibration (CQR) and ensemble weights of the multi-site variant come from the other sites' validation data."""
    from terra.models.registry import load_object
    cfg = load_config()
    all_sites, home = load_locations()
    ids = [s.id for s in all_sites]
    rows = []
    for source in ("solar", "wind"):
        frames = {i: pd.read_parquet(site_dir(i) / f"framed_{source}.parquet") for i in ids}
        cap = cfg.capacity_mw(source)
        dewas_only = load_object(source, "bundle@latest")
        for h in sites or ids:
            t0 = time.time()
            others = pd.concat([frames[i] for i in ids if i != h], ignore_index=True)
            multi = _train(others, source, cfg)
            local = _train(frames[h], source, cfg)
            for split in ("val_cal", "test"):
                # the original split names: framed tables carry 'val'; split_val is applied inside train_source,
                # so evaluate on the same cut here
                from terra.pipelines.train import split_val
                fh = split_val(frames[h])
                rows += [_score(dewas_only, fh, split, source, cap, "dewas_only", h),
                         _score(multi, fh, split, source, cap, "multisite_unseen", h),
                         _score(local, fh, split, source, cap, "local_only", h)]
            log.info("LOSO %s %s done in %.0fs", source, h, time.time() - t0)
    out = pd.concat(rows, ignore_index=True)
    d = ARTIFACTS / "multisite"
    d.mkdir(parents=True, exist_ok=True)
    out.to_csv(d / "loso_metrics.csv", index=False)
    return out


def write_site_thresholds(cfg: TerraConfig, d: Path) -> None:
    """Alert thresholds per site, each from that site's own training split (leak-free, like the Dewas ones)."""
    from terra.engines.alerts import alert_thresholds
    out = {}
    for loc in load_locations()[0]:
        ds = pd.read_parquet(site_dir(loc.id) / "dataset.parquet")
        out[loc.id] = alert_thresholds(ds, config_for(cfg, loc))
    (d / "alert_thresholds.json").write_text(json.dumps(out, indent=1))


def train_pooled(save: bool = True) -> dict:
    """The model to serve: trained on all sites (seen-site accuracy reported per site)."""
    from terra.models.registry import save_object
    cfg = load_config()
    ids = [s.id for s in load_locations()[0]]
    out, per_site = {}, []
    for source in ("solar", "wind"):
        frames = {i: pd.read_parquet(site_dir(i) / f"framed_{source}.parquet") for i in ids}
        bundle = _train(pd.concat(frames.values(), ignore_index=True), source, cfg)
        from terra.pipelines.train import split_val
        for i in ids:
            fi = split_val(frames[i])
            per_site.append(_score(bundle, fi, "test", source, cfg.capacity_mw(source), "multisite_pooled", i))
        out[source] = bundle
        if save:
            bundle.meta.update({"sites": ids, "multisite": True})
            save_object(bundle, source, "bundle_multisite", bundle.meta)
    d = ARTIFACTS / "multisite"
    d.mkdir(parents=True, exist_ok=True)
    pd.concat(per_site, ignore_index=True).to_csv(d / "pooled_test_by_site.csv", index=False)
    write_site_thresholds(cfg, d)
    (d / "meta.json").write_text(json.dumps({"sites": ids, "trained": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    return out
