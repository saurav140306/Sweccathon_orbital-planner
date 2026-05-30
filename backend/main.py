"""FastAPI backend for Orbital Planner."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from orbital_planner.agent import plan_mission_with_retry
from orbital_planner.calculations import build_calculation_snapshot
from orbital_planner.reward import score_mission
from orbital_planner.scenarios import ALL_SCENARIOS, SCENARIOS, TIER_ORDER
from orbital_planner.kepler2d import elements_from_state, sample_orbit_positions
from orbital_planner.orbital_motion import enrich_target, target_orbit_path
from orbital_planner.transfer import build_coplanar_hohmann_plan

load_dotenv()

app = FastAPI(title="Orbital Planner", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    scenario_id: str
    use_mock: bool = False


class RunResponse(BaseModel):
    scenario_id: str
    plan: dict[str, Any]
    score: dict[str, Any]
    raw_response: str | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/calculations")
def get_calculations(
    scenario_id: str,
    t_s: float = Query(0.0, ge=0.0),
) -> dict[str, Any]:
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(404, f"Unknown scenario {scenario_id!r}")
    snap = build_calculation_snapshot(scenario, t_s)
    path = [{"x": p[0], "y": p[1]} for p in target_orbit_path(enrich_target(scenario.target))]
    chaser_el = elements_from_state(scenario.spacecraft.position, scenario.spacecraft.velocity)
    chaser_path = [{"x": p[0], "y": p[1]} for p in sample_orbit_positions(chaser_el, n_points=90)]
    payload = snap.model_dump()
    payload["target_orbit_path"] = path
    payload["chaser_orbit_path"] = chaser_path
    return payload


@app.get("/api/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    ordered = sorted(ALL_SCENARIOS, key=lambda s: (TIER_ORDER.index(s.tier), s.id))
    out = []
    for s in ordered:
        payload = s.model_dump()
        payload["target"] = enrich_target(s.target).model_dump()
        out.append(payload)
    return out


@app.post("/api/run", response_model=RunResponse)
async def run_mission(body: RunRequest) -> RunResponse:
    scenario = SCENARIOS.get(body.scenario_id)
    if not scenario:
        raise HTTPException(404, f"Unknown scenario {body.scenario_id!r}")

    raw: str | None = None
    if body.use_mock or not os.environ.get("ANTHROPIC_API_KEY"):
        plan = build_coplanar_hohmann_plan(
            scenario.spacecraft.position,
            scenario.spacecraft.velocity,
            scenario.target.position,
            time_limit_s=scenario.time_limit_s,
            target=scenario.target,
            scenario=scenario,
        )
        raw = plan.reasoning
    else:
        plan, raw = await asyncio.to_thread(plan_mission_with_retry, scenario)

    breakdown = score_mission(scenario, plan)
    return RunResponse(
        scenario_id=scenario.id,
        plan=plan.model_dump(),
        score=_score_payload(breakdown),
        raw_response=raw,
    )


@app.post("/api/run/stream")
async def run_mission_stream(body: RunRequest) -> StreamingResponse:
    scenario = SCENARIOS.get(body.scenario_id)
    if not scenario:
        raise HTTPException(404, f"Unknown scenario {body.scenario_id!r}")

    async def event_stream() -> AsyncGenerator[str, None]:
        yield _sse("status", {"phase": "thinking"})
        try:
            if body.use_mock or not os.environ.get("ANTHROPIC_API_KEY"):
                plan = build_coplanar_hohmann_plan(
                    scenario.spacecraft.position,
                    scenario.spacecraft.velocity,
                    scenario.target.position,
                    time_limit_s=scenario.time_limit_s,
                    target=scenario.target,
                )
                reasoning = plan.reasoning
                for i in range(0, len(reasoning), 12):
                    yield _sse("reasoning", {"text": reasoning[i : i + 12]})
                    await asyncio.sleep(0.02)
                raw = reasoning
            else:
                plan, raw = await asyncio.to_thread(plan_mission_with_retry, scenario)
                reasoning = plan.reasoning or raw or ""
                for i in range(0, len(reasoning), 14):
                    yield _sse("reasoning", {"text": reasoning[i : i + 14]})
                    await asyncio.sleep(0.018)

            yield _sse("status", {"phase": "scoring"})
            breakdown = score_mission(scenario, plan)
            yield _sse(
                "complete",
                {
                    "scenario_id": scenario.id,
                    "plan": plan.model_dump(),
                    "score": _score_payload(breakdown),
                    "raw_response": raw,
                },
            )
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/run-all")
async def run_all(use_mock: bool = Query(True)) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scenario in ALL_SCENARIOS:
        resp = await run_mission(RunRequest(scenario_id=scenario.id, use_mock=use_mock))
        results.append(
            {
                "scenario_id": scenario.id,
                "tier": scenario.tier,
                "name": scenario.name,
                "score": resp.score["score"],
                "miss_km": resp.score["miss_km"],
                "fuel_used": resp.score["fuel_used"],
            }
        )
    return results


def _score_payload(breakdown) -> dict[str, Any]:
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
        "trajectory": [p.model_dump() for p in breakdown.trajectory],
        "target_trajectory": [p.model_dump() for p in breakdown.target_trajectory],
        "earth_spin_rad_s": breakdown.earth_spin_rad_s,
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
