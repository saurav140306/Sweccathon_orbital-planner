#!/usr/bin/env python3
"""Full Orbital Planner API demo — prints results for showcase."""

from __future__ import annotations

import json
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "http://127.0.0.1:8000"


def safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")


def get(path: str) -> dict | list:
    with urllib.request.urlopen(f"{API}{path}", timeout=120) as resp:
        return json.loads(resp.read().decode())


def post(path: str, body: dict) -> dict | list:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    print("=" * 60)
    print("  ORBITAL PLANNER — FULL DEMO")
    print("=" * 60)

    health = get("/api/health")
    print(f"\n[1] Health: {health['status']}")

    scenarios = get("/api/scenarios")
    print(f"\n[2] Scenarios loaded: {len(scenarios)}")
    by_tier: dict[str, list] = {}
    for s in scenarios:
        by_tier.setdefault(s["tier"], []).append(s["name"])
    for tier in ("easy", "medium", "hard", "expert"):
        names = by_tier.get(tier, [])
        if names:
            preview = ", ".join(safe(n) for n in names[:2])
            suffix = "..." if len(names) > 2 else ""
            print(f"    {tier:8} ({len(names)}): {preview}{suffix}")

    print("\n[3] Hero run — intercept-01 (Hohmann mock planner)")
    print("-" * 60)
    hero = post("/api/run", {"scenario_id": "intercept-01", "use_mock": True})
    sc = hero["score"]
    plan = hero["plan"]
    print(f"    Strategy: {safe(plan.get('reasoning', '')[:72])}...")
    print(f"    Burns: {len(plan['burns'])}")
    for b in plan["burns"]:
        print(f"      t={b['time_s']:6.0f}s  dv=[{b['dv'][0]:+.3f}, {b['dv'][1]:+.3f}] km/s")
    print(f"    Score:        {sc['score']}/100")
    print(f"    Miss:         {sc['miss_km']:.2f} km (tol 50 km)")
    print(f"    Fuel used:    {sc['fuel_used']:.3f} km/s")
    print(f"    Optimal dv:   {sc['optimal_dv']:.3f} km/s (Lambert/Hohmann)")
    print(f"    Efficiency:   {sc['fuel_ratio']*100:.0f}% of optimal")
    print(f"    Crashed:      {sc['crashed']}")
    print(f"    Trajectory:   {len(sc['trajectory'])} sampled points")

    print("\n[4] Benchmark — all scenarios (mock planner)")
    print("-" * 60)
    req = urllib.request.Request(
        f"{API}/api/run-all?use_mock=true",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        bench = json.loads(resp.read().decode())

    print(f"    {'Scenario':<28} {'Tier':<8} {'Score':>6}  {'Miss km':>8}  {'Fuel':>6}")
    print("    " + "-" * 54)
    for row in sorted(bench, key=lambda r: r["score"], reverse=True):
        print(
            f"    {safe(row['scenario_id']):<28} {row['tier']:<8} "
            f"{row['score']:>6.1f}  {row['miss_km']:>8.1f}  {row['fuel_used']:>6.2f}"
        )

    scores = [r["score"] for r in bench]
    print(f"\n    Mean score: {sum(scores)/len(scores):.1f}  |  "
          f"Best: {max(scores):.1f}  |  Worst: {min(scores):.1f}")

    print("\n[5] UI")
    print(f"    Frontend: http://localhost:5173")
    print(f"    API docs: {API}/docs")
    print("\n" + "=" * 60)
    print("  Demo complete.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"ERROR: API not reachable at {API}", file=sys.stderr)
        print("Start backend: cd backend && py -3.13 -m uvicorn main:app --port 8000", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
