"""Shared fixtures: a small synthetic config/dataset so tests run offline in seconds.

Imports of later-phase modules happen INSIDE fixtures, so Phase 0 tests run before Phase 1 exists.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def cfg():
    from terra.config import SplitsCfg, load_config
    c = load_config()
    weather = c.weather.model_copy(update={"start_date": "2024-01-01", "end_date": "2024-05-31"})
    splits = SplitsCfg(train_start="2024-01-08", train_end="2024-03-31", val_start="2024-04-03",
                       val_end="2024-04-30", test_start="2024-05-03", test_end="2024-05-28")
    return c.model_copy(update={"weather": weather, "splits": splits})


@pytest.fixture(scope="session")
def tables(cfg):
    from terra.data.weather_tables import build_weather_tables
    return build_weather_tables(cfg, synthetic=True, save=False)


@pytest.fixture(scope="session")
def ds(cfg, tables):
    from terra.data.build_dataset import build_dataset
    return build_dataset(cfg, *tables, save=False)


@pytest.fixture(scope="session")
def frames(cfg, ds):
    from terra.features.framing import frame_all
    return frame_all(ds, cfg)
