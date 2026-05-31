"""Mesocosm-style agent reasoning and simulation narratives."""

from __future__ import annotations

import math

from orbital_planner.orbital_motion import enrich_target
from orbital_planner.reward import (
    BUDGET_USE_FACTOR,
    FUEL_PENALTY_CAP,
    SCORE_WEIGHT_BUDGET,
    SCORE_WEIGHT_FUEL,
    SCORE_WEIGHT_PROXIMITY,
)
from orbital_planner.schemas import Burn, MissionPlan, Scenario, ScoreBreakdown
from orbital_planner.vec3 import vec3_mag


def _orbit_plain_description(tg, incl_deg: float, raan_deg: float) -> str:
    if incl_deg > 0.5:
        return (
            f"a tilted {tg.orbit_type} orbit "
            f"({incl_deg:.0f}° inclination — the path is angled above/below the equator)"
        )
    return f"a {tg.orbit_type} orbit around Earth (near the equatorial plane)"


def _burn_plain(b: Burn) -> str:
    dv = b.dv
    mag = vec3_mag(dv)
    dx, dy = dv[0], dv[1]
    dz = dv[2] if len(dv) > 2 else 0.0

    parts: list[str] = []
    if abs(dx) >= abs(dy) and abs(dx) >= abs(dz):
        parts.append("mostly forward" if dx > 0 else "mostly backward")
    elif abs(dy) >= abs(dx) and abs(dy) >= abs(dz):
        parts.append("mostly sideways" if dy > 0 else "mostly sideways (opposite)")
    if abs(dz) > 0.02:
        parts.append(f"{'up' if dz > 0 else 'down'} by {abs(dz):.2f} km/s (out-of-plane)")

    direction = ", ".join(parts) if parts else "small correction"
    return f"{mag:.2f} km/s — {direction}"


def format_mesocosm_reasoning(
    scenario: Scenario,
    plan: MissionPlan,
    *,
    dv1_mag: float | None = None,
    dv2_mag: float | None = None,
    apo_t: float | None = None,
    strategy: str = "coplanar_hohmann",
) -> str:
    """Legacy template for analytical mock burns (prefer Claude + simulation narrative)."""
    tg = enrich_target(scenario.target)
    sc = scenario.spacecraft
    r_sc = vec3_mag(sc.position)
    r_tg = vec3_mag(tg.position)
    v_sc = vec3_mag(sc.velocity)
    fuel_used = sum(vec3_mag(b.dv) for b in plan.burns)
    incl_deg = math.degrees(tg.inclination_rad)
    raan_deg = math.degrees(tg.raan_rad)
    orbit_desc = _orbit_plain_description(tg, incl_deg, raan_deg)
    target_word = "moon" if tg.kind == "moon" else "satellite"
    horizon_min = scenario.time_limit_s / 60.0

    lines = [
        "Turn 1 — What I see",
        f"Mission: {scenario.name} ({scenario.tier} difficulty).",
        f"Goal: fly our spacecraft to a moving {target_word} on {orbit_desc}.",
        "",
        "Starting picture:",
        f"  • Our ship (chaser) is about {r_sc:.0f} km from Earth, moving at {v_sc:.2f} km/s.",
        f"  • The {target_word} is about {r_tg:.0f} km out and keeps moving on its orbit.",
        f"  • We must get within {tg.tolerance_km:.0f} km at closest approach to score well.",
        f"  • Fuel allowance: {scenario.fuel_budget_dv:.2f} km/s total · time limit: {horizon_min:.0f} min.",
        "",
    ]

    if incl_deg > 0.5:
        lines.extend(
            [
                "Important detail — tilted orbit:",
                f"  The target path is inclined {incl_deg:.0f}°. A simple flat transfer may miss "
                "above or below the target unless we also adjust out-of-plane velocity.",
                "",
            ]
        )

    if tg.kind == "moon":
        lines.extend(
            [
                "Important detail — moon gravity:",
                "  The moon is massive enough to pull on us during the final approach, so the "
                "simulation uses full 3D physics (Earth + moon gravity).",
                "",
            ]
        )

    lines.extend(["The plan", ""])

    if strategy == "phasing":
        lines.append(
            "Match the target's orbit, then make a small speed change to catch up in angle."
        )
    elif strategy == "rendezvous":
        lines.append(
            "Raise to the target's altitude, then match the target's speed and direction at rendezvous."
        )
    else:
        lines.append(
            "Two-burn Hohmann transfer: leave our orbit, coast on an ellipse, circularize at target altitude."
        )
        if dv1_mag is not None and dv2_mag is not None:
            lines.append(
                f"  Textbook sizes: first burn ≈{dv1_mag:.2f} km/s, "
                f"second ≈{dv2_mag:.2f} km/s (≈{dv1_mag + dv2_mag:.2f} km/s total)."
            )

    lines.extend(["", "Engine burns (when & how much)", ""])
    if not plan.burns:
        lines.append("  No burns planned — coast only.")
    for i, b in enumerate(plan.burns, 1):
        when = "at mission start" if b.time_s < 1 else f"at T+{b.time_s:.0f} s ({b.time_s / 60:.1f} min)"
        dz = b.dv[2] if len(b.dv) > 2 else 0.0
        lines.append(f"  {i}. {when}: {_burn_plain(b)}")
        lines.append(
            f"     Vector Δv = [{b.dv[0]:+.2f}, {b.dv[1]:+.2f}, {dz:+.2f}] km/s"
        )

    lines.extend(
        [
            "",
            "Decision: commit this plan for simulation.",
            '{"commit": true}',
        ]
    )
    return "\n".join(lines)


def format_simulation_outcome(scenario: Scenario, breakdown: ScoreBreakdown) -> str:
    """Turn 2 — computed narrative from the physics simulation (not per-scenario hardcoding)."""
    tg = enrich_target(scenario.target)
    w_p = SCORE_WEIGHT_PROXIMITY * 100
    w_f = SCORE_WEIGHT_FUEL * 100
    w_b = SCORE_WEIGHT_BUDGET * 100

    lines = [
        "Turn 2 — Simulation results",
        "The environment integrated your burns with 3D orbital mechanics and scored the flight.",
        "",
    ]

    if breakdown.crashed:
        lines.append("Outcome: the spacecraft crashed into Earth. Score: 0 / 100.")
        return "\n".join(lines)

    prox_pts = breakdown.hit_score * SCORE_WEIGHT_PROXIMITY * 100
    fuel_pts = min(1.0, breakdown.fuel_ratio) * SCORE_WEIGHT_FUEL * 100
    budget_pts = max(0.0, 1.0 - BUDGET_USE_FACTOR * breakdown.fuel_used / scenario.fuel_budget_dv) * SCORE_WEIGHT_BUDGET * 100
    pen_pts = breakdown.fuel_penalty * 100
    within_tol = breakdown.miss_km <= tg.tolerance_km

    lines.extend(
        [
            f"Final score: {breakdown.score:.1f} / 100.",
            (
                f"Closest approach: {breakdown.miss_km:.1f} km at T+{breakdown.closest_approach_time_s:.0f} s "
                f"({'inside' if within_tol else 'outside'} the {tg.tolerance_km:.0f} km tolerance)."
            ),
        ]
    )
    if breakdown.plane_offset_km > 0.01:
        lines.append(
            f"Cross-track separation at closest approach: {breakdown.plane_offset_km:.1f} km."
        )

    lines.extend(
        [
            "",
            "How the score was calculated:",
            f"  • Reach target ({w_p:.0f}%): {prox_pts:.1f} pts — proximity {breakdown.hit_score * 100:.1f}%",
            f"  • Fuel efficiency ({w_f:.0f}%): {fuel_pts:.1f} pts — {breakdown.fuel_ratio * 100:.0f}% vs ideal transfer",
            f"  • Budget headroom ({w_b:.0f}%): {budget_pts:.1f} pts — used {breakdown.fuel_used:.2f} / {scenario.fuel_budget_dv:.2f} km/s",
        ]
    )
    if pen_pts > 0:
        lines.append(
            f"  • Over-budget penalty: −{pen_pts:.1f} pts (capped at {FUEL_PENALTY_CAP * 100:.0f} total)"
        )

    return "\n".join(lines)
