"""Shared run pipeline: AI plan → physics score → outcome narrative."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Literal

from fastapi import HTTPException

from orbital_planner.reasoning import format_simulation_outcome
from orbital_planner.reward import score_mission
from orbital_planner.schemas import MissionPlan, Scenario, ScoreBreakdown
from orbital_planner.transfer import build_coplanar_hohmann_plan
from orbital_planner.vec3 import vec3_mag

MOCK_BASELINE_NOTE = (
    "Offline analytical baseline (Hohmann transfer — not Mesocosm AI).\n"
    "Burns are computed from orbital mechanics; scores come from the physics simulation only.\n"
    "Set ANTHROPIC_API_KEY in backend/.env for Claude Turn 1 planning."
)

PlannerMode = Literal["claude", "mock"]
AI_PLAN_TIMEOUT_S = 90.0
AI_OUTCOME_TIMEOUT_S = 45.0

MOCK_BASELINE_NOTE = (
    "Offline analytical baseline (Hohmann transfer — not Mesocosm AI).\n"
    "Burns are computed from orbital mechanics; scores come from the physics simulation only.\n"
    "Set ANTHROPIC_API_KEY in backend/.env for Claude Turn 1 planning."
)

PlannerMode = Literal["claude", "mock"]


def planner_mode(use_mock: bool) -> PlannerMode:
    if use_mock or not os.environ.get("ANTHROPIC_API_KEY"):
        return "mock"
    return "claude"


async def plan_for_scenario(scenario: Scenario, *, use_mock: bool) -> tuple[MissionPlan, str, PlannerMode]:
    mode = planner_mode(use_mock)
    if mode == "mock":
        plan = build_coplanar_hohmann_plan(
            scenario.spacecraft.position,
            scenario.spacecraft.velocity,
            scenario.target.position,
            time_limit_s=scenario.time_limit_s,
            target=scenario.target,
            scenario=scenario,
        )
        burns_txt = ", ".join(
            f"t={b.time_s:.0f}s Δv={vec3_mag(b.dv):.2f} km/s" for b in plan.burns
        ) or "none"
        reasoning = f"{MOCK_BASELINE_NOTE}\n\nBurn schedule: {burns_txt}."
        return MissionPlan(burns=plan.burns, reasoning=reasoning), reasoning, mode

    try:
        plan, raw = await asyncio.wait_for(
            asyncio.to_thread(_plan_with_claude, scenario),
            timeout=AI_PLAN_TIMEOUT_S,
        )
        reasoning = plan.reasoning or raw or ""
        return plan, reasoning, mode
    except (asyncio.TimeoutError, Exception):
        plan = build_coplanar_hohmann_plan(
            scenario.spacecraft.position,
            scenario.spacecraft.velocity,
            scenario.target.position,
            time_limit_s=scenario.time_limit_s,
            target=scenario.target,
            scenario=scenario,
        )
        burns_txt = ", ".join(
            f"t={b.time_s:.0f}s Δv={vec3_mag(b.dv):.2f} km/s" for b in plan.burns
        ) or "none"
        reasoning = (
            "Mesocosm AI planner unavailable — using analytical fallback.\n"
            f"Burn schedule: {burns_txt}."
        )
        return MissionPlan(burns=plan.burns, reasoning=reasoning), reasoning, "mock"


def _plan_with_claude(scenario: Scenario) -> tuple[MissionPlan, str]:
    from orbital_planner.agent import plan_mission_with_retry

    return plan_mission_with_retry(scenario)


def _explain_with_claude(
    scenario: Scenario,
    plan: MissionPlan,
    breakdown: ScoreBreakdown,
) -> str:
    from orbital_planner.agent import explain_mission_outcome

    return explain_mission_outcome(scenario, plan, breakdown)


async def score_narrative_for_run(
    scenario: Scenario,
    plan: MissionPlan,
    breakdown: ScoreBreakdown,
    *,
    mode: PlannerMode,
    ai_summary: bool = True,
) -> str:
    computed = format_simulation_outcome(scenario, breakdown)
    if mode == "mock" or not ai_summary:
        return computed

    try:
        ai_text = await asyncio.wait_for(
            asyncio.to_thread(_explain_with_claude, scenario, plan, breakdown),
            timeout=AI_OUTCOME_TIMEOUT_S,
        )
        return f"{computed}\n\nAgent summary:\n{ai_text}"
    except Exception:
        return computed


def score_breakdown(scenario: Scenario, plan: MissionPlan) -> ScoreBreakdown:
    return score_mission(scenario, plan)


def score_payload(breakdown: ScoreBreakdown) -> dict[str, Any]:
    return {
        "miss_km": breakdown.miss_km,
        "fuel_used": breakdown.fuel_used,
        "optimal_dv": breakdown.optimal_dv,
        "fuel_ratio": breakdown.fuel_ratio,
        "hit_score": breakdown.hit_score,
        "fuel_penalty": breakdown.fuel_penalty,
        "score": breakdown.score,
        "crashed": breakdown.crashed,
        "closest_approach_time_s": breakdown.closest_approach_time_s,
        "plane_offset_km": breakdown.plane_offset_km,
        "trajectory": [p.model_dump() for p in breakdown.trajectory],
        "target_trajectory": [p.model_dump() for p in breakdown.target_trajectory],
        "earth_spin_rad_s": breakdown.earth_spin_rad_s,
    }
