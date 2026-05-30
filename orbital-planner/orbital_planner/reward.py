"""Deterministic, auditable mission scoring."""

from __future__ import annotations

import numpy as np

from orbital_planner.constants import EARTH_SPIN_RAD_S
from orbital_planner.orbital_motion import sample_target_trajectory, target_position_at
from orbital_planner.physics import min_distance_to_moving_target, simulate_trajectory
from orbital_planner.schemas import MissionPlan, Scenario, ScoreBreakdown
from orbital_planner.transfer import optimal_dv_for_scenario


def fuel_used(burns: list) -> float:
    total = 0.0
    for burn in burns:
        dv = np.array(burn.dv, dtype=float)
        total += float(np.linalg.norm(dv))
    return total


def score_mission(scenario: Scenario, plan: MissionPlan) -> ScoreBreakdown:
    """
    Simulate plan, compare to optimal baseline, return full breakdown.

    Score formula (spec):
        proximity   = 1 / (1 + miss_km / miss_scale)   # continuous; differs per scenario
        fuel_score  = min(1, optimal_dv / fuel_used)
        budget_score = max(0, 1 - fuel_used / fuel_budget)
        fuel_pen    = max(0, fuel_used - fuel_budget) * 0.5
        score       = round(100 * (0.50*proximity + 0.30*fuel_score + 0.20*budget_score) - 100*fuel_pen, 1)
    """
    pos = scenario.spacecraft.position
    vel = scenario.spacecraft.velocity
    target = scenario.target
    target_pos = target_position_at(target, 0.0)

    trajectory, crashed, _, _ = simulate_trajectory(
        position=pos,
        velocity=vel,
        burns=plan.burns,
        time_limit_s=scenario.time_limit_s,
        target=scenario.target,
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
            trajectory=trajectory,
            target_trajectory=sample_target_trajectory(target, scenario.time_limit_s),
            earth_spin_rad_s=EARTH_SPIN_RAD_S,
        )

    miss_km, closest_t = min_distance_to_moving_target(trajectory, target)
    used = fuel_used(plan.burns)
    optimal = optimal_dv_for_scenario(
        pos,
        target_pos,
        velocity=vel,
        time_limit_s=scenario.time_limit_s,
        target=target,
    )
    target_traj = sample_target_trajectory(target, scenario.time_limit_s)

    miss_scale = scenario.target.tolerance_km * 20.0
    fuel_ratio = optimal / max(used, 1e-6)
    proximity = 1.0 / (1.0 + miss_km / max(miss_scale, 1.0))
    fuel_score = min(1.0, fuel_ratio)
    budget_score = max(0.0, 1.0 - used / scenario.fuel_budget_dv)
    fuel_pen = max(0.0, used - scenario.fuel_budget_dv) * 0.5
    raw = (
        100.0
        * (0.50 * proximity + 0.30 * fuel_score + 0.20 * budget_score)
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
        trajectory=trajectory,
        target_trajectory=target_traj,
        earth_spin_rad_s=EARTH_SPIN_RAD_S,
    )
