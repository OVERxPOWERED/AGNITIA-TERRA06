"""M3 / M3-FT: Chronos-2 foundation model (amazon/chronos-2, Apache-2.0) with weather covariates.

Install: pip install "chronos-forecasting>=2.0" torch   (peft also needed for LoRA fine-tuning)
API facts used (verified against chronos2/pipeline.py):
- Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cuda"|"cpu")
- predict_df(df, future_df=None, id_column="item_id", timestamp_column="timestamp", target="target",
             prediction_length=..., quantile_levels=[...]) -> columns
             item_id, timestamp, target_name, predictions, "<q>" for each quantile level (e.g. "0.05")
- fit(inputs, prediction_length, validation_inputs=None, finetune_mode="full"|"lora", lora_config=None,
      context_length=None, learning_rate=1e-6, num_steps=1000, batch_size=256, output_dir=None, ...)
  inputs = [{"target": 1-d array, "past_covariates": {name: array}, "future_covariates": {name: None}}]
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from terra.config import TerraConfig
from terra.logs import get_logger
from terra.models.base import finalize_quantiles
from terra.schema import LEAD_BUCKETS, QCOLS, QUANTILES, TARGETS

log = get_logger(__name__)
COVARIATES = ("ghi", "cloud", "t2m", "ws100", "ws10", "rho")   # + "phys" (physics MW)


def _covariate_series(ds: pd.DataFrame, source: str, prefix: str) -> pd.DataFrame:
    """Covariates named without prefix so past and future share keys."""
    d = prefix[2]
    cov = {c: ds[f"{prefix}{c}"] for c in COVARIATES}
    cov["phys"] = ds[f"phys{d}_{source}_mw"]
    return pd.DataFrame(cov, index=ds.index)


def build_inputs(ds: pd.DataFrame, source: str, issues: pd.DatetimeIndex, context_h: int,
                 horizon_h: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long context_df (history up to issue) and future_df (lead-resolved covariates) for many issues."""
    y = ds[TARGETS[source]]
    past_cov = _covariate_series(ds, source, "fx1_")             # day-ahead quality covariates in history
    lead_cov = {p: _covariate_series(ds, source, p) for _, _, _, p in LEAD_BUCKETS}
    ctx, fut = [], []
    for t0 in issues:
        item = t0.strftime("%Y-%m-%dT%H")
        hist_idx = pd.date_range(t0 - pd.Timedelta(hours=context_h - 1), t0, freq="h")
        c = past_cov.reindex(hist_idx).copy()
        c["target"] = y.reindex(hist_idx).to_numpy()
        c["item_id"], c["timestamp"] = item, hist_idx.tz_convert(None)
        ctx.append(c)
        rows = []
        for lead in range(1, horizon_h + 1):
            p = next(pr for lo, hi, _, pr in LEAD_BUCKETS if lo <= lead <= hi)
            ts = t0 + pd.Timedelta(hours=lead)
            rows.append(lead_cov[p].loc[ts].to_dict() | {"item_id": item, "timestamp": ts.tz_convert(None)})
        fut.append(pd.DataFrame(rows))
    context_df = pd.concat(ctx, ignore_index=True).ffill().bfill()
    future_df = pd.concat(fut, ignore_index=True).ffill().bfill()
    return context_df, future_df


class Chronos2Forecaster:
    """Wraps the pipeline; predictions are aligned to (issue_time_utc, target_time_utc)."""

    name = "chronos2_zs"

    def __init__(self, model_id: str = "amazon/chronos-2", device: str | None = None,
                 context_h: int = 1024, batch_issues: int = 64):
        import torch
        from chronos import Chronos2Pipeline
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.pipeline = Chronos2Pipeline.from_pretrained(model_id, device_map=self.device)
        self.context_h = context_h
        self.batch_issues = batch_issues

    def predict_issues(self, ds: pd.DataFrame, source: str, issues: pd.DatetimeIndex, capacity: float,
                       horizon_h: int = 48) -> pd.DataFrame:
        out = []
        t0 = time.time()
        for i in range(0, len(issues), self.batch_issues):
            batch = issues[i:i + self.batch_issues]
            ctx, fut = build_inputs(ds, source, batch, self.context_h, horizon_h)
            pred = self.pipeline.predict_df(ctx, future_df=fut, id_column="item_id", timestamp_column="timestamp",
                                            target="target", prediction_length=horizon_h,
                                            quantile_levels=list(QUANTILES))
            qcols = [str(q) for q in QUANTILES]
            missing = [c for c in qcols if c not in pred.columns]
            if missing:   # column names can be "0.05" or "0.050000..." depending on version
                lookup = {float(c): c for c in pred.columns if _is_float(c)}
                qcols = [lookup[q] for q in QUANTILES]
            q = finalize_quantiles(pred[qcols].to_numpy(), capacity)
            res = pd.DataFrame(q, columns=list(QCOLS))
            res["issue_time_utc"] = pd.to_datetime(pred["item_id"], format="%Y-%m-%dT%H").dt.tz_localize("UTC")
            res["target_time_utc"] = pd.to_datetime(pred["timestamp"]).dt.tz_localize("UTC")
            out.append(res)
            log.info("chronos2 %s %d/%d issues", source, min(i + self.batch_issues, len(issues)), len(issues))
        df = pd.concat(out, ignore_index=True)
        df["lead_h"] = ((df["target_time_utc"] - df["issue_time_utc"]) / pd.Timedelta(hours=1)).astype(int)
        if source == "solar":
            df.loc[ds["zenith"].reindex(df["target_time_utc"]).to_numpy() >= 90, list(QCOLS)] = 0.0
        df.attrs["seconds"] = round(time.time() - t0, 1)
        return df

    # ---------- fine-tuning (run on Kaggle GPU; see ml/kaggle/README.md) ----------
    def finetune_lora(self, ds: pd.DataFrame, cfg: TerraConfig, out_dir: str | Path, num_steps: int = 1500,
                      learning_rate: float = 1e-5, batch_size: int = 32) -> float:
        """LoRA fine-tune on train split, validate on val split. Returns wall-clock seconds."""
        b = cfg.splits.bounds()

        def task(source: str, lo: pd.Timestamp, hi: pd.Timestamp) -> dict:
            sl = ds.loc[lo:hi]
            cov = _covariate_series(sl, source, "fx1_")
            return {"target": sl[TARGETS[source]].to_numpy("float32"),
                    "past_covariates": {c: cov[c].to_numpy("float32") for c in cov.columns},
                    "future_covariates": {c: None for c in cov.columns}}

        train = [task(s, *b["train"]) for s in ("solar", "wind")]
        val = [task(s, *b["val"]) for s in ("solar", "wind")]
        t0 = time.time()
        self.pipeline = self.pipeline.fit(train, prediction_length=cfg.forecast.horizon_h, validation_inputs=val,
                                          finetune_mode="lora", lora_config={"r": 8, "lora_alpha": 16},
                                          context_length=self.context_h, learning_rate=learning_rate,
                                          num_steps=num_steps, batch_size=batch_size, output_dir=str(out_dir))
        self.name = "chronos2_ft"
        return time.time() - t0


def _is_float(s: object) -> bool:
    try:
        float(str(s))
        return True
    except ValueError:
        return False
