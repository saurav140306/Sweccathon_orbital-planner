"""HTTP adapter for Orbital Planner Mesocosm env."""

from __future__ import annotations

import argparse

from bench_common.env_sdk import serve

from env import OrbitalPlannerEnv

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print(f"OrbitalPlannerEnv adapter -> http://{args.host}:{args.port}")
    serve(OrbitalPlannerEnv, host=args.host, port=args.port)
