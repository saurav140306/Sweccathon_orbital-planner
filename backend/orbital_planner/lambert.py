"""Lambert optimal two-impulse Δv baseline via lamberthub (with Hohmann fallback)."""

from __future__ import annotations

import math

import numpy as np
from lamberthub import izzo2015

from orbital_planner.constants import MU_EARTH_KM3_S2
from orbital_planner.transfer import hohmann_optimal_dv, hohmann_transfer_time


from orbital_planner.vec3 import to_vec3


def _to_3d(position: tuple[float, float, float] | tuple[float, float]) -> np.ndarray:
    v = to_vec3(position)
    return np.array(v, dtype=float)


def _is_collinear(
    r1: tuple[float, float, float] | tuple[float, float],
    r2: tuple[float, float, float] | tuple[float, float],
    *,
    tol: float = 1e-3,
) -> bool:
    a = _to_3d(r1)
    b = _to_3d(r2)
    cross = np.cross(a, b)
    return float(np.linalg.norm(cross)) < tol * float(np.linalg.norm(a)) * float(np.linalg.norm(b))


def _circular_velocity_at(
    position: tuple[float, float, float] | tuple[float, float],
    mu: float = MU_EARTH_KM3_S2,
) -> np.ndarray:
    r = _to_3d(position)
    r_norm = float(np.linalg.norm(r))
    if r_norm < 1.0:
        return np.zeros(3)
    ref = np.array([0.0, 0.0, 1.0]) if abs(r[2]) < 0.9 * r_norm else np.array([1.0, 0.0, 0.0])
    tangent = np.cross(ref, r)
    t_norm = float(np.linalg.norm(tangent))
    if t_norm < 1e-12:
        tangent = np.array([-r[1], r[0], 0.0])
        t_norm = float(np.linalg.norm(tangent))
    tangent = tangent / t_norm
    speed = math.sqrt(mu / r_norm)
    return tangent * speed


def lambert_two_impulse_dv(
    position: tuple[float, float, float] | tuple[float, float],
    velocity: tuple[float, float, float] | tuple[float, float],
    target_position: tuple[float, float, float] | tuple[float, float],
    transfer_time_s: float,
    *,
    mu: float = MU_EARTH_KM3_S2,
) -> float | None:
    """
    Total Δv for Lambert departure + circularization at target for a fixed TOF.
    Returns None if the Lambert solver fails.
    """
    r1 = _to_3d(position)
    r2 = _to_3d(target_position)
    v0 = np.array(to_vec3(velocity), dtype=float)

    try:
        v1_lam, v2_lam = izzo2015(mu, r1, r2, transfer_time_s, prograde=True)
    except Exception:
        return None

    if not np.all(np.isfinite(v1_lam)) or not np.all(np.isfinite(v2_lam)):
        return None

    dv1 = float(np.linalg.norm(v1_lam - v0))
    v_circ = _circular_velocity_at(target_position, mu)
    dv2 = float(np.linalg.norm(v_circ - v2_lam))
    return dv1 + dv2


def optimal_dv_lambert(
    position: tuple[float, float, float] | tuple[float, float],
    velocity: tuple[float, float, float] | tuple[float, float],
    target_position: tuple[float, float, float] | tuple[float, float],
    *,
    time_limit_s: float = 7200.0,
    mu: float = MU_EARTH_KM3_S2,
) -> float:
    """
    Minimum two-impulse Δv over a grid of Lambert transfer times.
    Falls back to Hohmann when geometry is (near) collinear.
    """
    if _is_collinear(position, target_position):
        return hohmann_optimal_dv(
            float(np.linalg.norm(position)),
            float(np.linalg.norm(target_position)),
            mu,
        )

    r1 = float(np.linalg.norm(position))
    r2 = float(np.linalg.norm(target_position))
    t_hohmann = hohmann_transfer_time(r1, r2, mu)
    t_min = max(300.0, 0.35 * t_hohmann)
    t_max = min(time_limit_s * 0.95, 1.8 * t_hohmann)

    candidates = np.linspace(t_min, t_max, 24)
    best = float("inf")

    for tof in candidates:
        total = lambert_two_impulse_dv(
            position, velocity, target_position, float(tof), mu=mu
        )
        if total is not None and total < best:
            best = total

    if math.isfinite(best):
        return best

    # Last-resort analytic bound
    return hohmann_optimal_dv(r1, r2, mu)
