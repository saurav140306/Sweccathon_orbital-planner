"""Deterministic, auditable mission scoring."""

from __future__ import annotations

import math

import numpy as np

from orbital_planner.constants import EARTH_SPIN_RAD_S
from orbital_planner.orbital_motion import enrich_target, sample_target_trajectory, target_position_at
from orbital_planner.physics import min_distance_to_moving_target, plane_offset_at_closest, simulate_trajectory
from orbital_planner.schemas import MissionPlan, Scenario, ScoreBreakdown
from orbital_planner.transfer import optimal_dv_for_scenario

# Score weights — intercept quality is the primary objective for this benchmark.
SCORE_WEIGHT_PROXIMITY = 0.75
SCORE_WEIGHT_FUEL = 0.10
SCORE_WEIGHT_BUDGET = 0.15

# Proximity scale — larger miss_scale = more forgiving miss-distance curve.
MISS_SCALE_TOLERANCE_MULT = 58.0
INCL_MISS_SCALE_FACTOR = 0.12
PLANE_TERM_WEIGHT = 0.07
PROXIMITY_EXPONENT = 0.52  # sub-linear: gentler penalty for large misses

# Easy tiers get a wider scale so simple scenarios score more generously.
TIER_MISS_SCALE: dict[str, float] = {
    "easy": 1.65,
    "medium": 1.35,
    "hard": 1.05,
    "expert": 0.95,
}

# Budget headroom — only 65% of nominal usage counts against the budget term.
BUDGET_USE_FACTOR = 0.65

# Fuel over-budget penalty is capped so a single constraint does not dominate the score.
FUEL_PENALTY_PER_KMS = 0.10
FUEL_PENALTY_CAP = 0.10  # max 10 points subtracted from final score


def miss_scale_km(scenario: Scenario, target) -> float:
    incl = target.inclination_rad
    tier_mult = TIER_MISS_SCALE.get(scenario.tier, 1.0)
    return (
        target.tolerance_km
        * MISS_SCALE_TOLERANCE_MULT
        * tier_mult
        * (1.0 + INCL_MISS_SCALE_FACTOR * math.sin(incl))
    )


def proximity_from_miss(
    miss_km: float,
    plane_offset_km: float,
    tolerance_km: float,
    miss_scale: float,
) -> float:
    miss_ratio = miss_km / max(miss_scale, 1.0)
    plane_ratio = plane_offset_km / max(miss_scale, 1.0)
    proximity = 1.0 / (
        1.0
        + miss_ratio ** PROXIMITY_EXPONENT
        + PLANE_TERM_WEIGHT * plane_ratio ** PROXIMITY_EXPONENT
    )
    tol = max(tolerance_km, 1.0)
    if miss_km <= tol:
        proximity = max(proximity, 0.90 + 0.10 * (1.0 - miss_km / tol))
    elif miss_km <= 5.0 * tol:
        proximity = max(
            proximity,
            0.50 + 0.40 * (1.0 - (miss_km - tol) / (4.0 * tol)),
        )
    return min(1.0, proximity)


def fuel_used(burns: list) -> float:
    total = 0.0
    for burn in burns:
        dv = np.array(burn.dv, dtype=float)
        total += float(np.linalg.norm(dv))
    return total


def score_mission(scenario: Scenario, plan: MissionPlan) -> ScoreBreakdown:
    """
    Simulate plan in 3D, compare to optimal baseline, return full breakdown.

    Proximity uses 3D miss distance plus a cross-track plane term for inclined targets.
    """
    pos = scenario.spacecraft.position
    vel = scenario.spacecraft.velocity
    target = enrich_target(scenario.target)
    target_pos = target_position_at(target, 0.0)

    trajectory, crashed, _, _ = simulate_trajectory(
        position=pos,
        velocity=vel,
        burns=plan.burns,
        time_limit_s=scenario.time_limit_s,
        target=target,
    )

    if crashed:
        return ScoreBreakdown(
            miss_km=float("inf"),
            fuel_used=fuel_used(plan.burns),
            optimal_dv=optimal_dv_for_scenario(
                pos,
                target_pos,
                velocity=vel,
                time_limit_s=scenario.time_limit_s,
                target=target,
            ),
            fuel_ratio=0.0,
            hit_score=0.0,
            fuel_penalty=0.0,
            score=0.0,
            crashed=True,
            closest_approach_time_s=0.0,
            plane_offset_km=0.0,
            trajectory=trajectory,
            target_trajectory=sample_target_trajectory(target, scenario.time_limit_s),
            earth_spin_rad_s=EARTH_SPIN_RAD_S,
        )

    miss_km, closest_t = min_distance_to_moving_target(trajectory, target)
    plane_offset = plane_offset_at_closest(trajectory, target, closest_t)
    used = fuel_used(plan.burns)
    optimal = optimal_dv_for_scenario(
        pos,
        target_pos,
        velocity=vel,
        time_limit_s=scenario.time_limit_s,
        target=target,
    )
    target_traj = sample_target_trajectory(target, scenario.time_limit_s)

    incl = target.inclination_rad
    miss_scale = miss_scale_km(scenario, target)
    fuel_ratio = optimal / max(used, 1e-6)
    proximity = proximity_from_miss(miss_km, plane_offset, target.tolerance_km, miss_scale)
    fuel_score = min(1.0, fuel_ratio)
    budget_score = max(0.0, 1.0 - BUDGET_USE_FACTOR * used / scenario.fuel_budget_dv)
    fuel_pen = min(
        max(0.0, used - scenario.fuel_budget_dv) * FUEL_PENALTY_PER_KMS,
        FUEL_PENALTY_CAP,
    )
    raw = (
        100.0
        * (
            SCORE_WEIGHT_PROXIMITY * proximity
            + SCORE_WEIGHT_FUEL * fuel_score
            + SCORE_WEIGHT_BUDGET * budget_score
        )
        - 100.0 * fuel_pen
    )
    final_score = round(max(0.0, raw), 1)

    return ScoreBreakdown(
        miss_km=round(miss_km, 3),
        fuel_used=round(used, 4),
        optimal_dv=round(optimal, 4),
        fuel_ratio=round(fuel_ratio, 4),
        hit_score=round(proximity, 4),
        fuel_penalty=round(fuel_pen, 4),
        score=final_score,
        crashed=False,
        closest_approach_time_s=round(closest_t, 1),
        plane_offset_km=round(plane_offset, 3),
        trajectory=trajectory,
        target_trajectory=target_traj,
        earth_spin_rad_s=EARTH_SPIN_RAD_S,
    )
