"""Mesocosm-style agent reasoning text for mission plans."""

from __future__ import annotations

import math

from orbital_planner.orbital_motion import enrich_target
from orbital_planner.schemas import Burn, MissionPlan, Scenario


def format_mesocosm_reasoning(
    scenario: Scenario,
    plan: MissionPlan,
    *,
    dv1_mag: float | None = None,
    dv2_mag: float | None = None,
    apo_t: float | None = None,
    strategy: str = "coplanar_hohmann",
) -> str:
    """Build a multi-paragraph agent trace like a Mesocosm replay turn."""
    tg = enrich_target(scenario.target)
    sc = scenario.spacecraft
    r_sc = math.hypot(sc.position[0], sc.position[1])
    r_tg = math.hypot(tg.position[0], tg.position[1])
    v_sc = math.hypot(sc.velocity[0], sc.velocity[1])
    fuel_used = sum(math.hypot(b.dv[0], b.dv[1]) for b in plan.burns)

    lines = [
        "Turn 1 — reading the observation.",
        f"Scenario «{scenario.name}» ({scenario.tier}): rendezvous with a {tg.kind} on a {tg.orbit_type} Kepler orbit.",
        f"Chaser: r≈{r_sc:.0f} km, |v|≈{v_sc:.3f} km/s. Target at t₀: r≈{r_tg:.0f} km, tolerance {tg.tolerance_km:.0f} km.",
        f"Budget {scenario.fuel_budget_dv:.2f} km/s · horizon {scenario.time_limit_s:.0f} s.",
        "",
    ]

    if tg.kind == "moon":
        lines.append(
            "The target is a massive moon — third-body gravity (μ☾≈4903 km³/s²) will perturb the coast arc when we get close."
        )
    else:
        lines.append("Satellite target — Earth gravity only; target position evolves on its ellipse.")

    lines.extend(["", "Strategy:"])

    if strategy == "phasing":
        lines.append(
            "Co-orbit phasing: small prograde/retrograde burn to adjust mean anomaly and close angular separation."
        )
    elif strategy == "rendezvous":
        lines.append(
            "Hohmann raise to target altitude, then match target inertial velocity at apoapsis for a moving rendezvous."
        )
    else:
        lines.append(
            "Two-impulse coplanar Hohmann: burn prograde at periapsis onto the transfer ellipse, "
            "coast to apoapsis, then circularize at the target radius."
        )
        if dv1_mag is not None and dv2_mag is not None:
            lines.append(
                f"Textbook Δv₁≈{dv1_mag:.3f} km/s and Δv₂≈{dv2_mag:.3f} km/s "
                f"(total {dv1_mag + dv2_mag:.3f} km/s)."
            )

    lines.extend(["", "Burn schedule:"])
    if not plan.burns:
        lines.append("No burns — pure coast (likely poor intercept on a moving target).")
    for i, b in enumerate(plan.burns, 1):
        dv = math.hypot(b.dv[0], b.dv[1])
        lines.append(
            f"  {i}. t={b.time_s:.0f} s · Δv=[{b.dv[0]:+.3f}, {b.dv[1]:+.3f}] km/s (|Δv|={dv:.3f})"
        )
    if apo_t is not None:
        lines.append(f"Apoapsis coast time ≈{apo_t:.0f} s (simulated under RK4 + gravity).")

    lines.extend(
        [
            "",
            "Commit check:",
            f"Planned fuel {fuel_used:.3f} km/s vs budget {scenario.fuel_budget_dv:.2f} km/s — "
            + ("within budget." if fuel_used <= scenario.fuel_budget_dv else "OVER BUDGET (penalty)."),
            "",
            '{"commit": true}',
        ]
    )

    if plan.reasoning and plan.reasoning not in lines:
        extra = plan.reasoning.strip()
        if extra and not extra.startswith("Turn 1"):
            lines.insert(-1, "")
            lines.insert(-1, extra)

    return "\n".join(lines)
