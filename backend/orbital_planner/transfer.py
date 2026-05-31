"""Analytical two-impulse Hohmann transfer (step-1 optimal baseline; Lambert in step 2)."""

from __future__ import annotations

import math

import numpy as np

from orbital_planner.constants import MU_EARTH_KM3_S2
from orbital_planner.orbital_motion import target_position_at, target_velocity_at
from orbital_planner.physics import apply_burn, simulate_trajectory
from orbital_planner.schemas import Burn, MissionPlan, Scenario, SpacecraftState, TargetSpec


def circular_speed(radius_km: float, mu: float = MU_EARTH_KM3_S2) -> float:
    return math.sqrt(mu / radius_km)


def hohmann_optimal_dv(r1_km: float, r2_km: float, mu: float = MU_EARTH_KM3_S2) -> float:
    """Total delta-v for a coplanar circular Hohmann transfer between radii r1 and r2."""
    r1 = max(r1_km, 1.0)
    r2 = max(r2_km, 1.0)
    v1 = circular_speed(r1, mu)
    v2 = circular_speed(r2, mu)
    dv1 = abs(v1 * (math.sqrt(2 * r2 / (r1 + r2)) - 1))
    dv2 = abs(v2 * (1 - math.sqrt(2 * r1 / (r1 + r2))))
    return dv1 + dv2


def hohmann_transfer_time(r1_km: float, r2_km: float, mu: float = MU_EARTH_KM3_S2) -> float:
    """Time from first burn to apoapsis on the transfer ellipse (half transfer period)."""
    r1 = max(r1_km, 1.0)
    r2 = max(r2_km, 1.0)
    a_transfer = (r1 + r2) / 2.0
    return math.pi * math.sqrt(a_transfer**3 / mu)


def hohmann_plan_for_radii(
    r1_km: float,
    r2_km: float,
    *,
    mu: float = MU_EARTH_KM3_S2,
) -> tuple[float, float, float]:
    """Return (dv1_mag, dv2_mag, nominal_transfer_time_s) for a coplanar Hohmann raise."""
    r1 = max(r1_km, 1.0)
    r2 = max(r2_km, 1.0)
    v1 = circular_speed(r1, mu)
    v2 = circular_speed(r2, mu)
    dv1 = v1 * (math.sqrt(2 * r2 / (r1 + r2)) - 1)
    dv2 = v2 * (1 - math.sqrt(2 * r1 / (r1 + r2)))
    t_transfer = hohmann_transfer_time(r1, r2, mu)
    return abs(dv1), abs(dv2), t_transfer


def optimal_dv_for_scenario(
    position: tuple[float, float, float],
    target_position: tuple[float, float, float],
    *,
    velocity: tuple[float, float] | None = None,
    time_limit_s: float = 7200.0,
    mu: float = MU_EARTH_KM3_S2,
    target: object | None = None,
) -> float:
    """Lambert two-impulse baseline; Hohmann when collinear or solver fails."""
    from orbital_planner.lambert import optimal_dv_lambert
    from orbital_planner.orbital_motion import target_position_at
    from orbital_planner.schemas import TargetSpec

    if velocity is not None and isinstance(target, TargetSpec):
        # Sample moving target at mid-transfer for Lambert estimate
        t_mid = time_limit_s * 0.5
        tgt_mid = target_position_at(target, t_mid)
        return optimal_dv_lambert(
            position, velocity, tgt_mid, time_limit_s=time_limit_s * 0.5, mu=mu
        )

    if velocity is not None:
        return optimal_dv_lambert(
            position, velocity, target_position, time_limit_s=time_limit_s, mu=mu
        )
    r1 = float(np.linalg.norm(position))
    r2 = float(np.linalg.norm(target_position))
    return hohmann_optimal_dv(r1, r2, mu)


def build_coplanar_hohmann_plan(
    position: tuple[float, float, float],
    velocity: tuple[float, float, float],
    target_position: tuple[float, float, float],
    *,
    mu: float = MU_EARTH_KM3_S2,
    time_limit_s: float = 7200.0,
    target: TargetSpec | None = None,
    scenario: Scenario | None = None,
) -> MissionPlan:
    """
    Two-burn Hohmann: prograde burn 1 at t=0, burn 2 at simulated apoapsis
    (max radius) with prograde circularization magnitude.
    """
    r1 = float(np.linalg.norm(position))
    r2 = float(np.linalg.norm(target_position))
    dv1_mag, dv2_mag, _ = hohmann_plan_for_radii(r1, r2, mu=mu)

    v = np.array(velocity, dtype=float)
    v_hat = v / (np.linalg.norm(v) + 1e-12)
    dv1 = tuple((dv1_mag * v_hat).tolist())
    if len(dv1) == 2:
        dv1 = (dv1[0], dv1[1], 0.0)
    vel_after_1 = apply_burn(velocity, dv1)

    # Coast on transfer ellipse until apoapsis (maximum radius).
    coast, crashed, _, _ = simulate_trajectory(
        position=position,
        velocity=vel_after_1,
        burns=[],
        time_limit_s=time_limit_s,
        sample_every_s=5.0,
        target=target,
    )
    if crashed or len(coast) < 2:
        raise RuntimeError("Hohmann coast arc crashed or too short")

    apo_point = max(coast, key=lambda p: np.linalg.norm(p.position))
    apo_t = apo_point.t_s
    apo_vel = np.array(apo_point.velocity, dtype=float)
    apo_vhat = apo_vel / (np.linalg.norm(apo_vel) + 1e-12)
    dv2 = tuple((dv2_mag * apo_vhat).tolist())
    if len(dv2) == 2:
        dv2 = (dv2[0], dv2[1], 0.0)

    burns = [
        Burn(time_s=0.0, dv=dv1),
        Burn(time_s=apo_t, dv=dv2),
    ]
    return MissionPlan(burns=burns, reasoning="")


def build_rendezvous_plan(scenario: Scenario) -> MissionPlan:
    """
    Mock planner: Hohmann transfer + velocity match to moving target at apoapsis,
    or co-orbit phasing burn when radii already match.
    """
    import numpy as np

    from orbital_planner.orbital_motion import enrich_target

    sc = scenario.spacecraft
    tg = enrich_target(scenario.target)
    r_sc = float(np.linalg.norm(sc.position))
    r_tg = float(tg.orbit_radius_km)

    if abs(r_sc - r_tg) < 200.0:
        angle_sc = math.atan2(sc.position[1], sc.position[0])
        angle_tg = tg.initial_angle_rad or math.atan2(tg.position[1], tg.position[0])
        dtheta = (angle_tg - angle_sc + math.pi) % (2 * math.pi) - math.pi
        v = np.array(sc.velocity, dtype=float)
        v_hat = v / (np.linalg.norm(v) + 1e-12)
        dv_mag = min(0.45, abs(dtheta) * np.linalg.norm(v) * 0.35)
        dv = tuple((dv_mag * v_hat * (1 if dtheta > 0 else -1)).tolist())
        if len(dv) == 2:
            dv = (dv[0], dv[1], 0.0)
        plan = MissionPlan(burns=[Burn(time_s=0.0, dv=dv)], reasoning="")
        return plan

    plan = build_coplanar_hohmann_plan(
        sc.position,
        sc.velocity,
        tg.position,
        time_limit_s=scenario.time_limit_s,
        target=tg,
        scenario=scenario,
    )
    if len(plan.burns) < 2:
        return plan

    apo_t = plan.burns[1].time_s
    coast, _, _, _ = simulate_trajectory(
        position=sc.position,
        velocity=apply_burn(sc.velocity, plan.burns[0].dv),
        burns=[],
        time_limit_s=apo_t + 1.0,
        sample_every_s=5.0,
        target=tg,
    )
    apo_pt = max(coast, key=lambda p: np.linalg.norm(p.position))
    vel = np.array(apo_pt.velocity, dtype=float)
    tgt_vel = np.array(target_velocity_at(tg, apo_t), dtype=float)
    dv2 = tgt_vel - vel
    burns = [
        plan.burns[0],
        Burn(time_s=apo_t, dv=(float(dv2[0]), float(dv2[1]), float(dv2[2]) if len(dv2) > 2 else 0.0)),
    ]
    return MissionPlan(burns=burns, reasoning="")
