"""Mesocosm AI agent — planning, score analysis, and reasoning via OpenAI-compatible LLM."""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any

import httpx

from orbital_planner.calculations import build_calculation_snapshot
from orbital_planner.orbital_motion import enrich_target
from orbital_planner.reward import (
    BUDGET_USE_FACTOR,
    SCORE_WEIGHT_BUDGET,
    SCORE_WEIGHT_FUEL,
    SCORE_WEIGHT_PROXIMITY,
)
from orbital_planner.schemas import MissionPlan, Scenario, ScoreBreakdown

# Mesocosm local default matches `mesocosm run local --model ollama/llama3.2`
DEFAULT_API_BASE = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.2"

TURN1_SYSTEM = """You are the Mesocosm AI orbital mission planner for a 3D Earth-centered inertial (ECI) model.
You perform mission analysis, burn planning, and reasoning — not a separate assistant.

Units: kilometers, km/s, seconds. Earth mu = 398600 km³/s², radius = 6371 km.
The target is a satellite or moon on a Keplerian orbit (possibly inclined and elliptical).
Moon gravity perturbs the chaser; burns are impulsive Δv vectors in 3D [dx, dy, dz].

After you commit, the Mesocosm environment simulates your plan and returns authoritative scores.
Do NOT invent simulation results in Turn 1.

Reply with STRICT JSON only — no markdown fences:
{"burns":[{"time_s":0,"dv":[0.0,0.0,0.0]}],"reasoning":"Mesocosm Turn 1 trace","commit":true}

Turn 1 reasoning MUST include your own orbital calculations in plain English:
- starting geometry (altitudes, speeds, orbit tilt if relevant)
- transfer strategy and why
- burn schedule with times, Δv magnitudes, and directions
- fuel budget check and closest-approach expectation
- commit decision

Rules: burns sorted by time_s; respect fuel budget; avoid Earth impact (r < 6371 km)."""

TURN2_SYSTEM = """You are the Mesocosm AI mission analyst.
Explain simulation results and score breakdown in plain English for a general audience.
Use ONLY the numbers provided — never invent scores, miss distances, or fuel values.
Show your calculation reasoning: how proximity, fuel efficiency, and budget map to the final score."""


def mesocosm_model_name() -> str:
    raw = os.environ.get("MESOCOSM_MODEL", DEFAULT_MODEL)
    return raw.split("/", 1)[-1] if raw.startswith("ollama/") else raw


def mesocosm_api_base() -> str:
    return os.environ.get("MESOCOSM_API_BASE", DEFAULT_API_BASE).rstrip("/")


def mesocosm_available() -> bool:
    """True when the configured Mesocosm LLM endpoint responds."""
    base = mesocosm_api_base()
    root = base[:-3] if base.endswith("/v1") else base
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{root}/api/tags")
            if r.status_code == 200:
                return True
            r = client.get(f"{base}/models")
            return r.status_code == 200
    except Exception:
        return False


def _chat(system: str, user: str, *, max_tokens: int = 1024) -> str:
    payload = {
        "model": mesocosm_model_name(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.25,
    }
    api_key = os.environ.get("MESOCOSM_API_KEY", "mesocosm")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{mesocosm_api_base()}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"]).strip()


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


def parse_plan(raw: str) -> MissionPlan:
    return MissionPlan.model_validate(_extract_json(raw))


def _build_turn1_prompt(scenario: Scenario) -> str:
    sc = scenario.spacecraft
    tg = enrich_target(scenario.target)
    incl_deg = math.degrees(tg.inclination_rad)
    orbit_note = ""
    if incl_deg > 0.5:
        orbit_note = f"\n  inclination_deg: {incl_deg:.1f}\n  raan_deg: {math.degrees(tg.raan_rad):.1f}"
    return f"""Mesocosm Turn 1 — plan and calculate a transfer.

scenario_id: {scenario.id}
name: {scenario.name}
tier: {scenario.tier}

spacecraft:
  position_km: [{sc.position[0]}, {sc.position[1]}, {sc.position[2]}]
  velocity_km_s: [{sc.velocity[0]}, {sc.velocity[1]}, {sc.velocity[2]}]

target ({tg.kind}):
  position_at_t0_km: [{tg.position[0]}, {tg.position[1]}, {tg.position[2]}]
  velocity_at_t0_km_s: [{tg.velocity[0] if tg.velocity else 0}, {tg.velocity[1] if tg.velocity else 0}, {(tg.velocity[2] if tg.velocity and len(tg.velocity) > 2 else 0)}]
  semi_major_axis_km: {tg.semi_major_axis_km or 0}
  eccentricity: {tg.eccentricity}
  tolerance_km: {tg.tolerance_km}{orbit_note}

fuel_budget_dv: {scenario.fuel_budget_dv}
time_limit_s: {scenario.time_limit_s}

Output JSON plan only. Include full Mesocosm reasoning with your orbital calculations."""


def _score_component_lines(scenario: Scenario, breakdown: ScoreBreakdown) -> str:
    prox_pts = breakdown.hit_score * SCORE_WEIGHT_PROXIMITY * 100
    fuel_pts = min(1.0, breakdown.fuel_ratio) * SCORE_WEIGHT_FUEL * 100
    budget_pts = (
        max(0.0, 1.0 - BUDGET_USE_FACTOR * breakdown.fuel_used / scenario.fuel_budget_dv)
        * SCORE_WEIGHT_BUDGET
        * 100
    )
    pen_pts = breakdown.fuel_penalty * 100
    w_p = SCORE_WEIGHT_PROXIMITY * 100
    w_f = SCORE_WEIGHT_FUEL * 100
    w_b = SCORE_WEIGHT_BUDGET * 100
    lines = [
        f"final_score: {breakdown.score}/100",
        f"proximity_component ({w_p:.0f}% weight): {breakdown.hit_score * 100:.1f}% → {prox_pts:.1f} pts",
        f"fuel_efficiency ({w_f:.0f}% weight): {breakdown.fuel_ratio * 100:.0f}% vs ideal → {fuel_pts:.1f} pts",
        f"budget_headroom ({w_b:.0f}% weight): → {budget_pts:.1f} pts",
    ]
    if pen_pts > 0:
        lines.append(f"over_budget_penalty: −{pen_pts:.1f} pts")
    return "\n".join(lines)


def _build_turn2_prompt(
    scenario: Scenario,
    plan: MissionPlan,
    breakdown: ScoreBreakdown,
) -> str:
    tg = enrich_target(scenario.target)
    burns_txt = "\n".join(
        f"  - t={b.time_s:.0f}s dv={list(b.dv)}" for b in plan.burns
    ) or "  (no burns)"
    snap = build_calculation_snapshot(scenario, breakdown.closest_approach_time_s, score=breakdown)
    chaser = snap.chaser
    target = snap.target

    return f"""Mesocosm Turn 2 — explain simulation, calculations, and scoring.

Scenario: {scenario.name} ({scenario.tier})

Your committed burns:
{burns_txt}

Simulation results (authoritative):
- closest_approach_km: {breakdown.miss_km}
- closest_approach_time_s: {breakdown.closest_approach_time_s}
- plane_offset_km: {breakdown.plane_offset_km}
- fuel_used_km_s: {breakdown.fuel_used} / budget {scenario.fuel_budget_dv}
- optimal_dv_km_s: {breakdown.optimal_dv}
- crashed: {breakdown.crashed}
- target_tolerance_km: {tg.tolerance_km}

Score breakdown (Mesocosm formula):
{_score_component_lines(scenario, breakdown)}

Orbital snapshot at closest approach (T+{breakdown.closest_approach_time_s:.0f}s):
- chaser radius_km: {chaser.get('radius_km', 'n/a')}
- chaser speed_km_s: {chaser.get('speed_km_s', 'n/a')}
- target radius_km: {target.get('radius_km', 'n/a')}

Write 8–12 sentences:
1) Did we reach the target (miss vs tolerance)?
2) Walk through the score calculation using the component lines above.
3) One improvement for a higher score next time.

Plain text only — no JSON."""


def plan_mission(scenario: Scenario) -> tuple[MissionPlan, str]:
    """Mesocosm AI Turn 1 — plan burns with calculated reasoning."""
    raw = _chat(TURN1_SYSTEM, _build_turn1_prompt(scenario), max_tokens=1400)
    return parse_plan(raw), raw


def explain_mission_outcome(
    scenario: Scenario,
    plan: MissionPlan,
    breakdown: ScoreBreakdown,
) -> str:
    """Mesocosm AI Turn 2 — explain simulation, calculations, and score."""
    return _chat(
        TURN2_SYSTEM,
        _build_turn2_prompt(scenario, plan, breakdown),
        max_tokens=768,
    )


def plan_mission_with_retry(scenario: Scenario) -> tuple[MissionPlan, str]:
    try:
        return plan_mission(scenario)
    except (json.JSONDecodeError, ValueError, KeyError) as first_err:
        raw = _chat(
            TURN1_SYSTEM,
            _build_turn1_prompt(scenario)
            + f"\n\nYour previous reply was invalid ({first_err}). Return only valid JSON.",
            max_tokens=1400,
        )
        return parse_plan(raw), raw
