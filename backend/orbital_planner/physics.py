"""Earth + optional third-body gravity with 3D RK4 integration and impulsive burns."""

from __future__ import annotations

import numpy as np

from orbital_planner.constants import DEFAULT_DT_S, EARTH_RADIUS_KM, MU_EARTH_KM3_S2
from orbital_planner.orbital_motion import target_body_mu, target_position_at
from orbital_planner.schemas import Burn, TargetSpec, TrajectoryPoint
from orbital_planner.vec3 import to_vec3


def _state_vector(
    position: tuple[float, float, float],
    velocity: tuple[float, float, float],
) -> np.ndarray:
    return np.array(
        [position[0], position[1], position[2], velocity[0], velocity[1], velocity[2]],
        dtype=float,
    )


def _unpack(state: np.ndarray) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return (
        (float(state[0]), float(state[1]), float(state[2])),
        (float(state[3]), float(state[4]), float(state[5])),
    )


def earth_acceleration(position: np.ndarray, mu: float = MU_EARTH_KM3_S2) -> np.ndarray:
    r_norm = np.linalg.norm(position)
    if r_norm < 1e-9:
        return np.zeros(3)
    return -mu * position / r_norm**3


def moon_acceleration(
    chaser_position: np.ndarray,
    t_s: float,
    target: TargetSpec,
) -> np.ndarray:
    """Gravitational acceleration toward a massive moon (restricted 3-body)."""
    mu_moon = target_body_mu(target)
    if mu_moon <= 0.0:
        return np.zeros(3)
    moon_pos = np.array(target_position_at(target, t_s), dtype=float)
    rel = moon_pos - chaser_position
    dist = float(np.linalg.norm(rel))
    if dist < 1e-6:
        return np.zeros(3)
    return mu_moon * rel / dist**3


def total_acceleration(
    position: np.ndarray,
    t_s: float,
    *,
    mu_earth: float = MU_EARTH_KM3_S2,
    target: TargetSpec | None = None,
) -> np.ndarray:
    accel = earth_acceleration(position, mu_earth)
    if target is not None and target_body_mu(target) > 0.0:
        accel = accel + moon_acceleration(position, t_s, target)
    return accel


def acceleration(position: np.ndarray, mu: float = MU_EARTH_KM3_S2) -> np.ndarray:
    return earth_acceleration(position, mu)


def gravity_breakdown_at(
    chaser_position: tuple[float, float, float],
    t_s: float,
    target: TargetSpec | None,
) -> dict[str, float]:
    pos = np.array(to_vec3(chaser_position), dtype=float)
    a_earth = earth_acceleration(pos)
    a_moon = (
        moon_acceleration(pos, t_s, target)
        if target is not None and target_body_mu(target) > 0.0
        else np.zeros(3)
    )
    a_total = a_earth + a_moon
    moon_pos = (
        np.array(target_position_at(target, t_s), dtype=float)
        if target is not None and target_body_mu(target) > 0.0
        else np.zeros(3)
    )
    rel_dist = float(np.linalg.norm(moon_pos - pos)) if target else 0.0
    return {
        "earth_accel_km_s2": float(np.linalg.norm(a_earth)),
        "moon_accel_km_s2": float(np.linalg.norm(a_moon)),
        "total_accel_km_s2": float(np.linalg.norm(a_total)),
        "moon_separation_km": rel_dist,
        "moon_mu_km3_s2": target_body_mu(target) if target else 0.0,
    }


def _derivatives(
    state: np.ndarray,
    t_s: float,
    mu_earth: float,
    target: TargetSpec | None,
) -> np.ndarray:
    position = state[:3]
    velocity = state[3:]
    accel = total_acceleration(position, t_s, mu_earth=mu_earth, target=target)
    return np.array(
        [velocity[0], velocity[1], velocity[2], accel[0], accel[1], accel[2]],
        dtype=float,
    )


def rk4_step(
    state: np.ndarray,
    t_s: float,
    dt: float,
    mu_earth: float,
    target: TargetSpec | None,
) -> np.ndarray:
    k1 = _derivatives(state, t_s, mu_earth, target)
    k2 = _derivatives(state + 0.5 * dt * k1, t_s + 0.5 * dt, mu_earth, target)
    k3 = _derivatives(state + 0.5 * dt * k2, t_s + 0.5 * dt, mu_earth, target)
    k4 = _derivatives(state + dt * k3, t_s + dt, mu_earth, target)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def apply_burn(
    velocity: tuple[float, float, float],
    dv: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        velocity[0] + dv[0],
        velocity[1] + dv[1],
        velocity[2] + dv[2],
    )


def simulate_trajectory(
    *,
    position: tuple[float, float, float],
    velocity: tuple[float, float, float],
    burns: list[Burn],
    time_limit_s: float,
    dt_s: float = DEFAULT_DT_S,
    mu: float = MU_EARTH_KM3_S2,
    earth_radius_km: float = EARTH_RADIUS_KM,
    target: TargetSpec | None = None,
    sample_every_s: float | None = 30.0,
) -> tuple[list[TrajectoryPoint], bool, float, float]:
    pos3 = to_vec3(position)
    vel3 = to_vec3(velocity)
    burns_sorted = sorted(burns, key=lambda b: b.time_s)
    burn_index = 0

    state = _state_vector(pos3, vel3)
    trajectory: list[TrajectoryPoint] = [
        TrajectoryPoint(t_s=0.0, position=pos3, velocity=vel3)
    ]
    next_sample_t = sample_every_s if sample_every_s is not None else time_limit_s + 1.0

    t = 0.0
    crashed = np.linalg.norm(state[:3]) < earth_radius_km

    while t < time_limit_s and not crashed:
        while burn_index < len(burns_sorted) and burns_sorted[burn_index].time_s <= t + 1e-9:
            burn = burns_sorted[burn_index]
            pos, vel = _unpack(state)
            vel = apply_burn(vel, to_vec3(burn.dv))
            state = _state_vector(pos, vel)
            trajectory.append(TrajectoryPoint(t_s=t, position=pos, velocity=vel))
            burn_index += 1

        step = min(dt_s, time_limit_s - t)
        state = rk4_step(state, t, step, mu, target)
        t += step

        pos, vel = _unpack(state)
        if np.linalg.norm(state[:3]) < earth_radius_km:
            crashed = True
            trajectory.append(TrajectoryPoint(t_s=t, position=pos, velocity=vel))
            break

        if sample_every_s is not None and t + 1e-9 >= next_sample_t:
            trajectory.append(TrajectoryPoint(t_s=t, position=pos, velocity=vel))
            next_sample_t += sample_every_s

    if not crashed:
        pos, vel = _unpack(state)
        if trajectory[-1].t_s < t - 1e-9:
            trajectory.append(TrajectoryPoint(t_s=t, position=pos, velocity=vel))

    return trajectory, crashed, t, 0.0


def min_distance_to_moving_target(
    trajectory: list[TrajectoryPoint],
    target: TargetSpec,
) -> tuple[float, float]:
    best_dist = float("inf")
    best_t = 0.0
    for point in trajectory:
        tgt = np.array(target_position_at(target, point.t_s), dtype=float)
        chaser = np.array(point.position, dtype=float)
        dist = float(np.linalg.norm(chaser - tgt))
        if dist < best_dist:
            best_dist = dist
            best_t = point.t_s
    return best_dist, best_t


def min_distance_to_target(
    trajectory: list[TrajectoryPoint],
    target_position: tuple[float, float, float],
) -> tuple[float, float]:
    target = np.array(to_vec3(target_position), dtype=float)
    best_dist = float("inf")
    best_t = 0.0
    for point in trajectory:
        dist = float(np.linalg.norm(np.array(point.position, dtype=float) - target))
        if dist < best_dist:
            best_dist = dist
            best_t = point.t_s
    return best_dist, best_t


def plane_offset_at_closest(
    trajectory: list[TrajectoryPoint],
    target: TargetSpec,
    closest_t: float,
) -> float:
    """Cross-track separation at closest approach (km), using target orbit normal."""
    from orbital_planner.orbital_motion import target_velocity_at

    ca = min(trajectory, key=lambda p: abs(p.t_s - closest_t))
    chaser = np.array(ca.position, dtype=float)
    tgt = np.array(target_position_at(target, ca.t_s), dtype=float)
    tgt_vel = np.array(target_velocity_at(target, ca.t_s), dtype=float)
    h = np.cross(tgt, tgt_vel)
    h_norm = float(np.linalg.norm(h))
    if h_norm < 1e-9:
        return abs(float(chaser[2] - tgt[2]))
    h_hat = h / h_norm
    rel = chaser - tgt
    return abs(float(np.dot(rel, h_hat)))
