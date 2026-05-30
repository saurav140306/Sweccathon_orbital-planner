"""Physics sanity: Hohmann + moving target orbital motion."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from orbital_planner.orbital_motion import (
    earth_spin_angle,
    enrich_target,
    target_position_at,
)
from orbital_planner.physics import min_distance_to_moving_target
from orbital_planner.reward import score_mission
from orbital_planner.scenarios import INTERCEPT_01, RAISE_EASY
from orbital_planner.transfer import (
    build_coplanar_hohmann_plan,
    hohmann_optimal_dv,
    hohmann_transfer_time,
)


def test_hohmann_optimal_dv_matches_textbook():
    r1, r2 = 7000.0, 10000.0
    optimal = hohmann_optimal_dv(r1, r2)
    v1 = math.sqrt(398600 / r1)
    v2 = math.sqrt(398600 / r2)
    expected = v1 * (math.sqrt(2 * r2 / (r1 + r2)) - 1) + v2 * (1 - math.sqrt(2 * r1 / (r1 + r2)))
    assert abs(optimal - expected) < 1e-3


def test_hohmann_transfer_time_positive():
    t = hohmann_transfer_time(7000.0, 10000.0)
    assert 3500 < t < 4200


def test_target_revolution_moves_over_time():
    tg = enrich_target(INTERCEPT_01.target)
    p0 = target_position_at(tg, 0.0)
    p1 = target_position_at(tg, 1200.0)
    dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    assert dist > 500.0


def test_earth_spin_advances():
    assert earth_spin_angle(3600.0) > 0.2


def test_intercept01_elliptical_target_trajectory():
    """Intercept scenario uses elliptical chaser + moon; verify Kepler target sampling."""
    from orbital_planner.schemas import Burn, MissionPlan

    plan = MissionPlan(burns=[], reasoning="Coast on published elliptical elements.")
    result = score_mission(INTERCEPT_01, plan)
    assert not result.crashed
    assert len(result.target_trajectory) > 10
    assert result.target_trajectory[0].position != result.target_trajectory[-1].position
    tg = enrich_target(INTERCEPT_01.target)
    assert (tg.orbit_elements.eccentricity if tg.orbit_elements else 0) > 0.05


def test_moving_target_miss_differs_from_static():
    plan = build_coplanar_hohmann_plan(
        RAISE_EASY.spacecraft.position,
        RAISE_EASY.spacecraft.velocity,
        RAISE_EASY.target.position,
        time_limit_s=RAISE_EASY.time_limit_s,
    )
    from orbital_planner.physics import min_distance_to_target, simulate_trajectory

    pos = RAISE_EASY.spacecraft.position
    vel = RAISE_EASY.spacecraft.velocity
    traj, _, _, _ = simulate_trajectory(
        position=pos, velocity=vel, burns=plan.burns, time_limit_s=RAISE_EASY.time_limit_s
    )
    static_miss, _ = min_distance_to_target(traj, RAISE_EASY.target.position)
    moving_miss, _ = min_distance_to_moving_target(traj, enrich_target(RAISE_EASY.target))
    assert static_miss != moving_miss


def test_crash_scores_zero():
    from orbital_planner.schemas import Burn, MissionPlan

    plan = MissionPlan(
        burns=[Burn(time_s=0.0, dv=(-10.0, 0.0))],
        reasoning="Intentional retrograde deorbit.",
    )
    result = score_mission(INTERCEPT_01, plan)
    assert result.crashed
    assert result.score == 0.0
