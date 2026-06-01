"""Build showcase replay.json with one local episode per scenario (seeds 0..13).

Uses the Hohmann baseline from test_env so the Pages demo lists all 14 scenarios
with trajectories. Replace via `mesocosm run export` when a gallery run completes.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env import OrbitalPlannerEnv
from orbital_planner.scenarios import ALL_SCENARIOS
from test_env import _hohmann_action

OUT = ROOT / "showcase" / "data" / "replay.json"
JS_OUT = ROOT / "showcase" / "data" / "replay.js"


def _str_info(info: dict) -> dict[str, str]:
    return {k: str(v) for k, v in info.items()}


def main() -> None:
    base = {}
    if OUT.is_file():
        base = json.loads(OUT.read_text(encoding="utf-8"))

    episodes = []
    replay: dict[str, list] = {}
    now = datetime.now(timezone.utc).isoformat()

    for seed, scenario in enumerate(ALL_SCENARIOS):
        env = OrbitalPlannerEnv()
        obs = env.reset(seed=seed)
        action = _hohmann_action(scenario.id, seed)
        result = env.step(action)
        eid = str(uuid.uuid4())
        info = _str_info(result.info)

        turn = {
            "step": 1,
            "timestamp": now,
            "board_before": obs,
            "observation": obs,
            "reasoning": info.get("agent_reasoning", "Hohmann transfer baseline (local demo)."),
            "model": "local/hohmann-baseline",
            "action": action,
            "reward": result.reward,
            "terminated": result.terminated,
            "truncated": result.truncated,
            "info": info,
            "board_after": result.observation,
            "episode_end": {
                "score": float(info.get("score", 0)),
                "miss_km": float(info.get("miss_km", 0)),
                "crashed": info.get("crashed", "False") == "True",
            },
        }
        replay[eid] = [turn]
        episodes.append(
            {
                "id": eid,
                "run_id": base.get("run", {}).get("id", "local-demo"),
                "seed": seed,
                "status": "completed",
                "started_at": now,
                "ended_at": now,
                "steps": 1,
                "total_reward": result.reward,
                "terminal_info": {
                    "scenario_id": scenario.id,
                    "score": float(info.get("score", 0)),
                    "miss_km": float(info.get("miss_km", 0)),
                    "crashed": info.get("crashed", "False") == "True",
                },
            }
        )

    payload = {
        "schema_version": "1",
        "exported_at": now,
        "visibility": "gallery_public",
        "domain_id": base.get("domain_id", "local"),
        "domain_name": base.get("domain_name", "Orbital Planner"),
        "binding_vow_version": base.get("binding_vow_version", "1.0.0"),
        "run": {
            **(base.get("run") or {}),
            "config": {
                **((base.get("run") or {}).get("config") or {}),
                "num_episodes": len(ALL_SCENARIOS),
                "agent_config": {
                    "model": "local/hohmann-baseline (all 14 scenarios)",
                    "temperature": 0.0,
                },
            },
            "status": "completed",
            "scores": {
                "pass_rate": sum(1 for e in episodes if e["total_reward"] > 0) / len(episodes),
                "mean_reward": sum(e["total_reward"] for e in episodes) / len(episodes),
            },
        },
        "episodes": episodes,
        "replay": replay,
    }

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    JS_OUT.write_text("window.REPLAY = " + json.dumps(payload) + ";\n", encoding="utf-8")
    print(f"Wrote {len(episodes)} episodes -> {OUT}")


if __name__ == "__main__":
    main()
