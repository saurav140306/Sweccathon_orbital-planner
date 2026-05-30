"""Lambert optimal baseline tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from orbital_planner.lambert import optimal_dv_lambert
from orbital_planner.scenarios import RAISE_EASY
from orbital_planner.transfer import hohmann_optimal_dv


def test_lambert_collinear_matches_hohmann():
    sc = RAISE_EASY.spacecraft
    tg = RAISE_EASY.target
    lambert = optimal_dv_lambert(
        sc.position, sc.velocity, tg.position, time_limit_s=RAISE_EASY.time_limit_s
    )
    hohmann = hohmann_optimal_dv(
        __import__("numpy").linalg.norm(sc.position),
        __import__("numpy").linalg.norm(tg.position),
    )
    assert abs(lambert - hohmann) < 0.05


def test_lambert_non_collinear_finite():
    dv = optimal_dv_lambert(
        (7000.0, 0.0),
        (0.0, 7.546),
        (0.0, 10000.0),
        time_limit_s=7200.0,
    )
    assert dv > 0.5
    assert dv < 5.0
