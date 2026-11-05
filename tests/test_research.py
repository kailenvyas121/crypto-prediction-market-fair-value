"""Sign conventions and helpers used by the studies."""

import numpy as np
import pandas as pd
import pytest

from pinpricer.research.markouts import maker_sign
from pinpricer.research.positioning import _oos_r2


def test_maker_pnl_sign():
    # Taker buys YES at 40¢ and YES settles: the maker (short YES) loses 60¢.
    # Taker buys NO (yes_price 40¢) and YES settles: the maker (long YES at 40¢) gains 60¢.
    s = maker_sign(pd.Series(["yes", "no"]))
    pnl = s * (0.40 - 1.0)
    assert pnl == pytest.approx([-0.60, 0.60])


def test_oos_r2_is_zero_for_noise_and_one_for_signal():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((4000, 1))
    assert _oos_r2(x[:2000], 3 * x[:2000, 0], x[2000:], 3 * x[2000:, 0]) == pytest.approx(1.0)
    y = rng.standard_normal(4000)
    assert abs(_oos_r2(x[:2000], y[:2000], x[2000:], y[2000:])) < 0.01
