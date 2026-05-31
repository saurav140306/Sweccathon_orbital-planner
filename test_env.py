"""Determinism + score discrimination for Orbital Planner Mesocosm env."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env import OrbitalPlannerEnv
from orbital_planner.transfer import build_coplanar_hohmann_plan


def _run_episode(seed: int, action: str) -> tuple[float, str]:
    env = OrbitalPlannerEnv()
    env.reset(seed=seed)
    result = env.step(action)
    return result.reward, result.info.get("score", "0")


def _hohmann_action(scenario_id: str, seed: int) -> str:
    env = OrbitalPlannerEnv()
    env.reset(seed=seed, scenario_id=scenario_id)
    sc = env._scenario
    try:
        plan = build_coplanar_hohmann_plan(
            sc.spacecraft.position,
            sc.spacecraft.velocity,
            sc.target.position,
            time_limit_s=sc.time_limit_s,
            target=sc.target,
        )
    except RuntimeError:
        plan = build_coplanar_hohmann_plan(
            sc.spacecraft.position,
            sc.spacecraft.velocity,
            sc.target.position,
            time_limit_s=sc.time_limit_s,
            target=None,
        )
    return json.dumps({"burns": [b.model_dump() for b in plan.burns], "commit": True})


def test_deterministic_replay():
    action = json.dumps({"burns": [], "commit": True})
    for seed in (1, 7, 42):
        r1, s1 = _run_episode(seed, action)
        r2, s2 = _run_episode(seed, action)
        assert r1 == r2
        assert s1 == s2


def test_smart_beats_dumb():
    scenario_id = "raise-easy-01"
    seed = 11
    dumb = json.dumps({"burns": [{"time_s": 0, "dv": [-0.8, 0.0]}], "commit": True})
    smart = _hohmann_action(scenario_id, seed)

    env = OrbitalPlannerEnv()
    env.reset(seed=seed, scenario_id=scenario_id)
    dumb_r = env.step(dumb)

    env2 = OrbitalPlannerEnv()
    env2.reset(seed=seed, scenario_id=scenario_id)
    smart_r = env2.step(smart)

    assert float(smart_r.info["score"]) != float(dumb_r.info["score"])
    assert float(smart_r.info["score"]) >= float(dumb_r.info["score"])


def test_parse_error_then_commit():
    env = OrbitalPlannerEnv()
    env.reset(seed=3, scenario_id="station-easy-02")
    bad = env.step("not json")
    assert not bad.terminated
    good = env.step(json.dumps({"burns": [{"time_s": 0, "dv": [0.05, 0.05]}], "commit": True}))
    assert good.terminated
    assert float(good.info["score"]) >= 0
