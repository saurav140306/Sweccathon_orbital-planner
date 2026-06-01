"""Orbital Planner — Mesocosm environment."""

from __future__ import annotations

import json
import math
import random
import re
from typing import Any

from bench_common.env_sdk.base import BaseEnv, StepResult

from orbital_planner.orbital_motion import enrich_target
from orbital_planner.reward import score_mission
from orbital_planner.scenarios import ALL_SCENARIOS, SCENARIOS
from orbital_planner.schemas import Burn, MissionPlan

MAX_STEPS = 5


def _scenario_for_seed(rng: random.Random) -> Any:
    return ALL_SCENARIOS[rng.randrange(len(ALL_SCENARIOS))]


def _observation(scenario: Any, steps_remaining: int) -> dict[str, Any]:
    tg = enrich_target(scenario.target)
    sc = scenario.spacecraft
    return {
        "scenario_id": scenario.id,
        "name": scenario.name,
        "tier": scenario.tier,
        "spacecraft": {
            "position_km": [round(sc.position[0], 2), round(sc.position[1], 2)],
            "velocity_km_s": [round(sc.velocity[0], 4), round(sc.velocity[1], 4)],
        },
        "target": {
            "kind": tg.kind,
            "position_km": [round(tg.position[0], 2), round(tg.position[1], 2)],
            "velocity_km_s": [
                round(tg.velocity[0], 4) if tg.velocity else 0.0,
                round(tg.velocity[1], 4) if tg.velocity else 0.0,
            ],
            "tolerance_km": tg.tolerance_km,
            "semi_major_axis_km": round(tg.semi_major_axis_km or 0.0, 1),
            "eccentricity": round(tg.eccentricity or 0.0, 4),
            "orbit_type": tg.orbit_type,
        },
        "fuel_budget_dv": scenario.fuel_budget_dv,
        "time_limit_s": scenario.time_limit_s,
        "steps_remaining": steps_remaining,
        "instruction": (
            'Reply with JSON only: {"burns":[{"time_s":0,"dv":[dx,dy]}],'
            '"reasoning":"Multi-line Mesocosm trace: observe → strategy → burns → commit",'
            '"commit":true}. '
            "Units: km, km/s, seconds. Earth mu=398600 km³/s², radius=6371 km. "
            "Target moves on Kepler ellipse; moon targets exert third-body gravity."
        ),
    }


def _parse_action(action: Any) -> tuple[list[Burn], bool, str, str | None]:
    if isinstance(action, dict):
        data = action
    else:
        text = str(action).strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], True, "", f"Invalid JSON: {exc}"

    if not isinstance(data, dict):
        return [], True, "", "Action must be a JSON object"

    burns_raw = data.get("burns", [])
    if not isinstance(burns_raw, list):
        return [], True, "", "burns must be an array"

    burns: list[Burn] = []
    for item in burns_raw:
        if not isinstance(item, dict):
            return [], True, "", "each burn must be an object"
        t = float(item.get("time_s", 0))
        dv = item.get("dv", [0, 0])
        if not isinstance(dv, (list, tuple)) or len(dv) != 2:
            return [], True, "", "dv must be [dx, dy]"
        burns.append(Burn(time_s=t, dv=(float(dv[0]), float(dv[1]))))

    burns.sort(key=lambda b: b.time_s)
    commit = bool(data.get("commit", True))
    reasoning = str(data.get("reasoning", "")).strip()
    return burns, commit, reasoning, None


def _downsample_traj(points: list, every: int = 4) -> list[dict]:
    out: list[dict] = []
    for i, p in enumerate(points):
        if i % every != 0 and i != len(points) - 1:
            continue
        out.append(
            {
                "t_s": round(p.t_s, 1),
                "x": round(p.position[0], 1),
                "y": round(p.position[1], 1),
            }
        )
    return out


class OrbitalPlannerEnv(BaseEnv):
    def __init__(self) -> None:
        self._rng = random.Random(0)
        self._scenario = ALL_SCENARIOS[0]
        self._step_count = 0

    def reset(self, seed: int | None = None, **params: Any) -> dict[str, Any]:
        self._rng = random.Random(seed)
        scenario_id = params.get("scenario_id")
        if scenario_id and scenario_id in SCENARIOS:
            self._scenario = SCENARIOS[str(scenario_id)]
        elif seed is not None:
            # Deterministic: one of all 14 scenarios per episode seed (0..13 → full catalog).
            self._scenario = ALL_SCENARIOS[int(seed) % len(ALL_SCENARIOS)]
        else:
            self._scenario = _scenario_for_seed(self._rng)
        self._step_count = 0
        return _observation(self._scenario, MAX_STEPS)

    def step(self, action: Any) -> StepResult:
        self._step_count += 1
        steps_left = max(0, MAX_STEPS - self._step_count)

        burns, commit, agent_reasoning, err = _parse_action(action)
        if err:
            truncated = self._step_count >= MAX_STEPS
            return StepResult(
                observation={
                    "error": err,
                    "steps_remaining": steps_left,
                    "hint": 'Use {"burns":[{"time_s":0,"dv":[0.1,0.0]}],"commit":true}',
                },
                reward=-0.05,
                terminated=truncated,
                truncated=truncated,
                info={
                    "parse_error": err,
                    "step": str(self._step_count),
                    "scenario_id": self._scenario.id,
                    "score": "0",
                },
            )

        if not commit and steps_left > 0:
            return StepResult(
                observation={
                    "status": "draft_saved",
                    "burn_count": len(burns),
                    "steps_remaining": steps_left,
                },
                reward=0.0,
                terminated=False,
                truncated=False,
                info={
                    "step": str(self._step_count),
                    "scenario_id": self._scenario.id,
                    "burns_json": json.dumps([b.model_dump() for b in burns]),
                    "score": "0",
                },
            )

        plan = MissionPlan(
            burns=burns,
            reasoning=agent_reasoning or "Agent submitted burns without explicit reasoning.",
        )
        result = score_mission(self._scenario, plan)
        reward = max(0.0, min(1.0, result.score / 100.0))

        chaser_traj = _downsample_traj(result.trajectory)
        target_traj = _downsample_traj(result.target_trajectory)

        info = {
            "scenario_id": self._scenario.id,
            "scenario_name": self._scenario.name,
            "tier": self._scenario.tier,
            "score": str(result.score),
            "miss_km": str(result.miss_km),
            "fuel_used": str(result.fuel_used),
            "optimal_dv": str(result.optimal_dv),
            "fuel_ratio": str(result.fuel_ratio),
            "hit_score": str(result.hit_score),
            "crashed": str(result.crashed),
            "closest_approach_time_s": str(result.closest_approach_time_s),
            "burns_json": json.dumps([b.model_dump() for b in burns]),
            "agent_reasoning": plan.reasoning,
            "chaser_traj_json": json.dumps(chaser_traj),
            "target_traj_json": json.dumps(target_traj),
            "earth_radius_km": "6371",
            "mu_earth": "398600",
        }

        return StepResult(
            observation={
                "status": "complete",
                "score": result.score,
                "miss_km": result.miss_km,
                "crashed": result.crashed,
            },
            reward=reward,
            terminated=True,
            truncated=False,
            info=info,
        )
