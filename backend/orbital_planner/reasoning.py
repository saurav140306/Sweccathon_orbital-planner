"""Mesocosm-style agent reasoning text for mission plans."""

from __future__ import annotations

import math

from orbital_planner.orbital_motion import enrich_target
from orbital_planner.schemas import Burn, MissionPlan, Scenario
from orbital_planner.vec3 import vec3_mag


def format_mesocosm_reasoning(
    scenario: Scenario,
    plan: MissionPlan,
    *,
    dv1_mag: float | None = None,
    dv2_mag: float | None = None,
    apo_t: float | None = None,
    strategy: str = "coplanar_hohmann",
) -> str:
    tg = enrich_target(scenario.target)
    sc = scenario.spacecraft
    r_sc = vec3_mag(sc.position)
    r_tg = vec3_mag(tg.position)
    v_sc = vec3_mag(sc.velocity)
    fuel_used = sum(vec3_mag(b.dv) for b in plan.burns)

    incl_deg = math.degrees(tg.inclination_rad)
    raan_deg = math.degrees(tg.raan_rad)
    orbit_desc = f"{tg.orbit_type} Kepler orbit"
    if incl_deg > 0.5:
        orbit_desc = f"{orbit_desc} (i={incl_deg:.1f}°, Ω={raan_deg:.1f}°)"

    lines = [
        "Turn 1 — reading the observation.",
        f"Scenario «{scenario.name}» ({scenario.tier}): rendezvous with a {tg.kind} on a {orbit_desc}.",
        f"Chaser: r≈{r_sc:.0f} km, |v|≈{v_sc:.3f} km/s. Target at t₀: r≈{r_tg:.0f} km, tolerance {tg.tolerance_km:.0f} km.",
        f"Budget {scenario.fuel_budget_dv:.2f} km/s · horizon {scenario.time_limit_s:.0f} s.",
        "",
    ]

    if incl_deg > 0.5:
        lines.append(
            f"The target orbit is tilted {incl_deg:.1f}° from the equatorial plane — "
            "a coplanar Hohmann alone leaves cross-track separation; plane-change Δv may be needed for tight intercept."
        )
        lines.append("")

    if tg.kind == "moon":
        lines.append(
            "The target is a massive moon — third-body gravity (μ☾≈4903 km³/s²) perturbs the coast arc in full 3D when we get close."
        )
    else:
        lines.append("Satellite target — Earth gravity only; target position evolves on its inclined ellipse in ECI.")

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
        dv = vec3_mag(b.dv)
        dz = b.dv[2] if len(b.dv) > 2 else 0.0
        lines.append(
            f"  {i}. t={b.time_s:.0f} s · Δv=[{b.dv[0]:+.3f}, {b.dv[1]:+.3f}, {dz:+.3f}] km/s (|Δv|={dv:.3f})"
        )
    if apo_t is not None:
        lines.append(f"Apoapsis coast time ≈{apo_t:.0f} s (simulated under 3D RK4 + gravity).")

    lines.extend(
        [
            "",
            "Commit check:",
            f"Planned fuel {fuel_used:.3f} km/s vs budget {scenario.fuel_budget_dv:.2f} km/s — "
            + ("within budget." if fuel_used <= scenario.fuel_budget_dv else "OVER BUDGET (penalty)."),
            "Scoring model: 50% proximity (3D miss + 0.15× cross-track offset / miss_scale), "
            "30% fuel vs Lambert/Hohmann baseline, 20% budget headroom; "
            "miss_scale = tolerance × 20 × (1 + 0.15·sin i).",
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
