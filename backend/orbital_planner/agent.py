"""Anthropic Claude mission planner with strict JSON output."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import Anthropic

from orbital_planner.schemas import MissionPlan, Scenario

SYSTEM = """You are an orbital mission planner for a 2D Earth-centered model.
Units: kilometers, km/s, seconds. Earth mu = 398600 km^3/s^2, radius = 6371 km.
The target is a satellite (massless) or moon (massive body, μ≈4902.8 km³/s²) on a Keplerian ellipse.
Moon gravity perturbs the chaser: a_moon = μ_moon (r_moon − r) / |r_moon − r|³.
The moon's orbit is fixed (restricted 3-body); chaser integrated with Earth + moon gravity via RK4.
Plan burns to rendezvous: minimize closest approach to the target's instantaneous position.
Impulsive burns add a delta-v vector instantly at the given time.
Reply with STRICT JSON only — no markdown fences, no text outside the object:
{"burns":[{"time_s":0,"dv":[0.0,0.0]}],"reasoning":"Multi-line Mesocosm agent trace: observe scenario, strategy, burn schedule, commit check","commit":true}
Rules:
- reasoning MUST be a multi-sentence agent trace (like a Mesocosm replay turn): observation → strategy → burns → risks → commit
- burns sorted by time_s ascending; times within the scenario time limit
- dv is [dx, dy] in km/s; respect the fuel budget (sum of |dv|)
- avoid crashing into Earth (radius < 6371 km)
- account for target orbital motion when timing burns
"""


def _build_user_prompt(scenario: Scenario) -> str:
    from orbital_planner.orbital_motion import enrich_target

    sc = scenario.spacecraft
    tg = enrich_target(scenario.target)
    return f"""Plan a transfer for this scenario.

id: {scenario.id}
name: {scenario.name}
tier: {scenario.tier}

spacecraft:
  position_km: [{sc.position[0]}, {sc.position[1]}]
  velocity_km_s: [{sc.velocity[0]}, {sc.velocity[1]}]

target ({tg.kind}, elliptical orbit):
  position_at_t0_km: [{tg.position[0]}, {tg.position[1]}]
  velocity_at_t0_km_s: [{tg.velocity[0] if tg.velocity else 0}, {tg.velocity[1] if tg.velocity else 0}]
  semi_major_axis_km: {tg.semi_major_axis_km or 0}
  eccentricity: {tg.eccentricity}
  periapsis_km / apoapsis_km: {tg.orbit_elements.periapsis_km if tg.orbit_elements else 0} / {tg.orbit_elements.apoapsis_km if tg.orbit_elements else 0}
  moon_mu_km3_s2: {tg.gravitational_parameter_km3_s2 or 0}
  body_radius_km: {tg.body_radius_km or 0}
  period_min: {(tg.revolution_period_s or 0) / 60:.1f}
  tolerance_km: {tg.tolerance_km}

fuel_budget_dv: {scenario.fuel_budget_dv}
time_limit_s: {scenario.time_limit_s}

Output the JSON plan only."""


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


def parse_plan(raw: str) -> MissionPlan:
    data = _extract_json(raw)
    return MissionPlan.model_validate(data)


def plan_mission(
    scenario: Scenario,
    *,
    model: str = "claude-sonnet-4-20250514",
    api_key: str | None = None,
) -> tuple[MissionPlan, str]:
    """Call Claude once; returns (plan, raw_text)."""
    client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": _build_user_prompt(scenario)}],
    )
    raw = message.content[0].text
    return parse_plan(raw), raw


def plan_mission_with_retry(scenario: Scenario, **kwargs: Any) -> tuple[MissionPlan, str]:
    try:
        return plan_mission(scenario, **kwargs)
    except (json.JSONDecodeError, ValueError, KeyError) as first_err:
        client = Anthropic(api_key=kwargs.get("api_key") or os.environ["ANTHROPIC_API_KEY"])
        message = client.messages.create(
            model=kwargs.get("model", "claude-sonnet-4-20250514"),
            max_tokens=1024,
            system=SYSTEM,
            messages=[
                {"role": "user", "content": _build_user_prompt(scenario)},
                {
                    "role": "user",
                    "content": (
                        f"Your previous reply was invalid ({first_err}). "
                        "Return only valid JSON matching the schema."
                    ),
                },
            ],
        )
        raw = message.content[0].text
        return parse_plan(raw), raw
