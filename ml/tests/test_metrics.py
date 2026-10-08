import numpy as np
import pytest

from terra.eval.metrics import mae, picp, pinball, rmse, skill


def test_basic_metrics():
    y, p = np.array([1.0, 2.0, 3.0]), np.array([1.0, 3.0, 5.0])
    assert mae(y, p) == pytest.approx(1.0)
    assert rmse(y, p) == pytest.approx(np.sqrt(5 / 3))
    assert skill(0.5, 1.0) == pytest.approx(0.5)


def test_pinball_asymmetry():
    y = np.array([10.0])
    assert pinball(y, np.array([8.0]), 0.9) == pytest.approx(1.8)
    assert pinball(y, np.array([12.0]), 0.9) == pytest.approx(0.2)


def test_picp():
    y = np.array([1, 5, 9.0])
    assert picp(y, np.array([0, 0, 0.0]), np.array([2, 6, 8.0])) == pytest.approx(2 / 3)
