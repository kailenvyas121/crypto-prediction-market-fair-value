"""Pricing invariants for the fair-value engine."""

import numpy as np
import pytest

from pinpricer.model import fv


def test_averaging_discount_matches_monte_carlo():
    # 60 one-second prints over the final minute, starting 5 minutes out, σ = 1 per second
    rng = np.random.default_rng(1)
    tau, n = 300, 60
    paths = rng.standard_normal((200_000, tau)).cumsum(1)
    avg = paths[:, -n:].mean(1)
    assert avg.var() == pytest.approx(tau - fv.AVG_DISCOUNT * n, rel=0.02)


def test_student_t_converges_to_normal_and_fattens_tails():
    s, k, v = 100.0, np.array([99.0, 100.0, 101.0, 103.0]), 1e-4
    assert fv.prob_above(s, k, v, nu=1e6) == pytest.approx(fv.prob_above(s, k, v), abs=1e-4)
    t, n = fv.prob_above(s, k, v, nu=4.0), fv.prob_above(s, k, v)
    assert t[1] == pytest.approx(0.5, abs=1e-3)
    assert t[2] < n[2] and t[3] > n[3]  # less mass near 1σ, more beyond 2.5σ


def test_ladder_is_monotone_in_strike():
    p = fv.prob_above(100.0, np.linspace(95, 105, 41), 4e-4, nu=4.2)
    assert np.all(np.diff(p) < 0)


def test_fit_nu_recovers_known_tail():
    nu = 4.0
    z = np.random.default_rng(2).standard_t(nu, 100_000) * np.sqrt((nu - 2) / nu)
    assert fv.fit_student_t_nu(z) == pytest.approx(nu, abs=0.4)
