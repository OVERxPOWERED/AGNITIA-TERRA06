"""Compare twin monthly capacity factor with Madhya Pradesh official monthly CF (R4) and suggest scaling."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from terra.config import load_config  # noqa: E402
from terra.data.build_dataset import load_dataset  # noqa: E402
from terra.paths import CONFIG_DIR, DOCS_IMAGES  # noqa: E402
from terra.real.calibrate_solar import _append_doc  # noqa: E402
from terra.real.loaders import load_cea_mp_monthly  # noqa: E402


def run() -> dict:
    cfg = load_config()
    ds = load_dataset()
    mp = load_cea_mp_monthly()
    month = ds.index.tz_convert("Asia/Kolkata").to_period("M").astype(str)
    twin = pd.DataFrame({
        "solar": ds["twin_solar_mw"].groupby(month).mean() / cfg.capacity_mw("solar"),
        "wind": ds["twin_wind_mw"].groupby(month).mean() / cfg.capacity_mw("wind"),
    })
    rows, scales = [], {}
    for s in ("solar", "wind"):
        m = mp[mp["source"] == s].set_index("month")["cf"]
        common = twin.index.intersection(m.index)
        comp = pd.DataFrame({"twin_cf": twin.loc[common, s], "mp_cf": m.loc[common]})
        comp["ratio"] = comp["mp_cf"] / comp["twin_cf"]
        rows.append(comp.assign(source=s))
        by_cal_month = comp["ratio"].groupby(pd.PeriodIndex(comp.index, freq="M").month).mean()
        mad = float((comp["ratio"] - 1).abs().mean())
        # only scale if the twin is systematically off by more than 10 %
        scales[s] = {int(k): float(min(max(v, 0.8), 1.2)) for k, v in by_cal_month.items()} if mad > 0.10 else {}
        fig, ax = plt.subplots(figsize=(8, 3))
        comp[["twin_cf", "mp_cf"]].plot(ax=ax, marker="o")
        ax.set_title(f"{s.title()}: TERRA twin vs Madhya Pradesh official monthly capacity factor")
        ax.set_ylabel("capacity factor")
        fig.tight_layout()
        DOCS_IMAGES.mkdir(parents=True, exist_ok=True)
        fig.savefig(DOCS_IMAGES / f"calibration_state_{s}.png", dpi=150)
        plt.close(fig)
    table = pd.concat(rows)
    out = {"source": "CEA Monthly RE Generation Reports (Madhya Pradesh)", "monthly_scale": scales}
    (CONFIG_DIR / "calibration").mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "calibration" / "state.yaml").write_text(yaml.safe_dump(out, sort_keys=False))
    _append_doc(["## Madhya Pradesh monthly capacity factor (R4)", "", table.round(3).to_markdown(), "",
                 "![solar](images/calibration_state_solar.png)", "", "![wind](images/calibration_state_wind.png)", "",
                 f"Suggested monthly scaling (empty = twin within 10 %, no scaling): `{scales}`", ""])
    return out
