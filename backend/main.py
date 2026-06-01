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

from orbital_planner.calculations import build_calculation_snapshot
from orbital_planner.mesocosm_agent import mesocosm_available, mesocosm_model_name
from orbital_planner.run_pipeline import (
    plan_for_scenario,
    planner_mode,
    score_breakdown,
    score_narrative_for_run,
    score_payload,
)
from orbital_planner.schemas import ScoreBreakdown
from orbital_planner.scenarios import ALL_SCENARIOS, SCENARIOS, TIER_ORDER
from orbital_planner.kepler3d import sample_orbit_positions
from orbital_planner.orbital_motion import enrich_target, spacecraft_elements, target_orbit_path

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


class CalculationsRequest(BaseModel):
    scenario_id: str
    t_s: float = 0.0
    score: dict[str, Any] | None = None


class RunResponse(BaseModel):
    scenario_id: str
    plan: dict[str, Any]
    score: dict[str, Any]
    score_narrative: str
    planner_mode: str
    raw_response: str | None = None


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    ready = mesocosm_available()
    return {
        "planner_mode": "mesocosm" if ready else "offline",
        "ai_available": ready,
        "model": mesocosm_model_name(),
        "score_source": "mesocosm_physics_simulation",
        "reasoning_source": "mesocosm_ai",
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/calculations")
def get_calculations(
    scenario_id: str,
    t_s: float = Query(0.0, ge=0.0),
) -> dict[str, Any]:
    return _calculations_payload(scenario_id, t_s, score=None)


@app.post("/api/calculations")
def post_calculations(body: CalculationsRequest) -> dict[str, Any]:
    score = ScoreBreakdown.model_validate(body.score) if body.score else None
    return _calculations_payload(body.scenario_id, body.t_s, score=score)


def _calculations_payload(
    scenario_id: str,
    t_s: float,
    *,
    score: ScoreBreakdown | None,
) -> dict[str, Any]:
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(404, f"Unknown scenario {scenario_id!r}")
    snap = build_calculation_snapshot(scenario, t_s, score=score)
    path = [{"x": p[0], "y": p[1], "z": p[2]} for p in target_orbit_path(enrich_target(scenario.target))]
    chaser_el = spacecraft_elements(scenario.spacecraft.position, scenario.spacecraft.velocity)
    chaser_path = [{"x": p[0], "y": p[1], "z": p[2]} for p in sample_orbit_positions(chaser_el, n_points=90)]
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

    plan, reasoning, mode = await plan_for_scenario(scenario, use_mock=body.use_mock)
    breakdown = score_breakdown(scenario, plan)
    narrative = await score_narrative_for_run(scenario, plan, breakdown, mode=mode)

    return RunResponse(
        scenario_id=scenario.id,
        plan=plan.model_dump(),
        score=score_payload(breakdown),
        score_narrative=narrative,
        planner_mode=mode,
        raw_response=reasoning if mode == "mesocosm" else None,
    )


@app.post("/api/run/stream")
async def run_mission_stream(body: RunRequest) -> StreamingResponse:
    scenario = SCENARIOS.get(body.scenario_id)
    if not scenario:
        raise HTTPException(404, f"Unknown scenario {body.scenario_id!r}")

    async def event_stream() -> AsyncGenerator[str, None]:
        yield _sse("status", {"phase": "thinking"})
        try:
            plan_task = asyncio.create_task(plan_for_scenario(scenario, use_mock=body.use_mock))
            waited = 0.0
            while not plan_task.done():
                try:
                    plan, reasoning, mode = await asyncio.wait_for(asyncio.shield(plan_task), timeout=2.0)
                    break
                except asyncio.TimeoutError:
                    waited += 2.0
                    yield _sse(
                        "status",
                        {
                            "phase": "thinking",
                            "message": f"Mesocosm AI planning… ({int(waited)}s)",
                        },
                    )
            else:
                plan, reasoning, mode = plan_task.result()

            chunk = 14 if mode == "mesocosm" else 12
            for i in range(0, len(reasoning), chunk):
                yield _sse("reasoning", {"text": reasoning[i : i + chunk]})
                await asyncio.sleep(0.018 if mode == "mesocosm" else 0.02)

            yield _sse("status", {"phase": "scoring"})
            breakdown = await asyncio.to_thread(score_breakdown, scenario, plan)
            narrative = await score_narrative_for_run(scenario, plan, breakdown, mode=mode)

            yield _sse("status", {"phase": "outcome"})
            for i in range(0, len(narrative), chunk):
                yield _sse("score_reasoning", {"text": narrative[i : i + chunk]})
                await asyncio.sleep(0.018)

            yield _sse(
                "complete",
                {
                    "scenario_id": scenario.id,
                    "plan": plan.model_dump(),
                    "score": score_payload(breakdown),
                    "score_narrative": narrative,
                    "planner_mode": mode,
                    "raw_response": reasoning if mode == "mesocosm" else None,
                },
            )
        except asyncio.TimeoutError:
            yield _sse(
                "error",
                {
                    "message": (
                        "Mesocosm AI planner timed out. "
                        "Retry or pass use_mock=true for the offline baseline."
                    ),
                },
            )
        except HTTPException as exc:
            yield _sse("error", {"message": exc.detail})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/run-all")
async def run_all(use_mock: bool = Query(False)) -> list[dict[str, Any]]:
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
    return score_payload(breakdown)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
