"""Moon third-body gravity tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from orbital_planner.constants import MU_MOON_KM3_S2
from orbital_planner.orbital_motion import enrich_target, target_position_at
from orbital_planner.physics import gravity_breakdown_at, moon_acceleration, simulate_trajectory
from orbital_planner.scenarios import INTERCEPT_01, RAISE_EASY


def test_moon_acceleration_pulls_toward_body():
    tg = enrich_target(INTERCEPT_01.target)
    chaser = np.array([9000.0, 0.0])
    moon_pos = np.array(target_position_at(tg, 0.0))
    rel = moon_pos - chaser
    expected_mag = MU_MOON_KM3_S2 / float(np.linalg.norm(rel)) ** 2
    a = moon_acceleration(chaser, 0.0, tg)
    assert float(np.linalg.norm(a)) == pytest.approx(expected_mag, rel=1e-4)
    assert float(np.dot(a, rel)) > 0


def test_satellite_has_no_third_body_mu():
    tg = enrich_target(RAISE_EASY.target)
    assert tg.gravitational_parameter_km3_s2 == 0.0


def test_moon_gravity_changes_trajectory():
    sc = INTERCEPT_01.spacecraft
    tg = enrich_target(INTERCEPT_01.target)
    traj_earth, _, _, _ = simulate_trajectory(
        position=sc.position,
        velocity=sc.velocity,
        burns=[],
        time_limit_s=3600.0,
        sample_every_s=60.0,
        target=None,
    )
    traj_moon, _, _, _ = simulate_trajectory(
        position=sc.position,
        velocity=sc.velocity,
        burns=[],
        time_limit_s=3600.0,
        sample_every_s=60.0,
        target=tg,
    )
    p0 = np.array(traj_earth[-1].position)
    p1 = np.array(traj_moon[-1].position)
    assert float(np.linalg.norm(p1 - p0)) > 0.01


def test_gravity_breakdown_includes_moon_term():
    tg = enrich_target(INTERCEPT_01.target)
    sc = INTERCEPT_01.spacecraft
    g = gravity_breakdown_at(sc.position, 0.0, tg)
    assert g["moon_mu_km3_s2"] == MU_MOON_KM3_S2
    assert g["moon_accel_km_s2"] > 0.0
    assert g["earth_accel_km_s2"] > g["moon_accel_km_s2"]
