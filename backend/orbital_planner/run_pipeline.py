"""Shared run pipeline: Mesocosm AI plan → physics score → Mesocosm AI outcome."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Literal

from orbital_planner.mesocosm_agent import (
    explain_mission_outcome,
    mesocosm_available,
    plan_mission_with_retry,
)
from orbital_planner.reasoning import format_simulation_outcome
from orbital_planner.reward import score_mission
from orbital_planner.schemas import MissionPlan, Scenario, ScoreBreakdown
from orbital_planner.transfer import build_coplanar_hohmann_plan
from orbital_planner.vec3 import vec3_mag

PlannerMode = Literal["mesocosm", "mock"]
AI_PLAN_TIMEOUT_S = 120.0
AI_OUTCOME_TIMEOUT_S = 90.0


def planner_mode(use_mock: bool) -> PlannerMode:
    if use_mock:
        return "mock"
    return "mesocosm"


def mesocosm_ready() -> bool:
    if os.environ.get("MESOCOSM_FORCE_AVAILABLE", "").lower() in ("1", "true", "yes"):
        return True
    return mesocosm_available()


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
        reasoning = (
            "Offline analytical baseline (use_mock=true).\n"
            f"Burn schedule: {burns_txt}."
        )
        return MissionPlan(burns=plan.burns, reasoning=reasoning), reasoning, mode

    if not mesocosm_ready():
        raise RuntimeError(
            "Mesocosm AI is not reachable. Start Ollama (ollama serve) and pull a model "
            f"(ollama pull {os.environ.get('MESOCOSM_MODEL', 'llama3.2').split('/')[-1]}), "
            "or set MESOCOSM_API_BASE to your OpenAI-compatible endpoint."
        )

    plan, raw = await asyncio.wait_for(
        asyncio.to_thread(plan_mission_with_retry, scenario),
        timeout=AI_PLAN_TIMEOUT_S,
    )
    reasoning = plan.reasoning or raw or ""
    return plan, reasoning, mode


async def score_narrative_for_run(
    scenario: Scenario,
    plan: MissionPlan,
    breakdown: ScoreBreakdown,
    *,
    mode: PlannerMode,
) -> str:
    if mode == "mock":
        return format_simulation_outcome(scenario, breakdown)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(explain_mission_outcome, scenario, plan, breakdown),
            timeout=AI_OUTCOME_TIMEOUT_S,
        )
    except Exception:
        return format_simulation_outcome(scenario, breakdown)


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
