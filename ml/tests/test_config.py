import pytest
from pydantic import ValidationError

from terra.config import BatteryCfg, SplitsCfg, load_config


def test_load_default_config():
    c = load_config()
    assert c.capacity_mw("hybrid") == c.solar.ac_capacity_mw + c.wind.capacity_mw
    assert len(c.hash()) == 12


def test_battery_soc_order_validated():
    with pytest.raises(ValidationError):
        BatteryCfg(power_mw=10, energy_mwh=20, soc_min_frac=0.5, soc_init_frac=0.3, soc_max_frac=0.9)


def test_splits_need_gaps():
    with pytest.raises(ValidationError):
        SplitsCfg(train_start="2024-01-01", train_end="2024-03-31", val_start="2024-04-01",
                  val_end="2024-04-30", test_start="2024-05-03", test_end="2024-05-30")
