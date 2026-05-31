"""Build calculation snapshots for the frontend panel."""

from __future__ import annotations

import math

from orbital_planner.constants import EARTH_RADIUS_KM, MU_EARTH_KM3_S2
from orbital_planner.kepler3d import propagate_elements
from orbital_planner.orbital_motion import (
    earth_spin_angle,
    enrich_target,
    spacecraft_elements,
    target_elements,
    target_position_at,
    target_true_anomaly_at,
    target_velocity_at,
)
from orbital_planner.physics import gravity_breakdown_at
from orbital_planner.reward import (
    BUDGET_USE_FACTOR,
    FUEL_PENALTY_CAP,
    INCL_MISS_SCALE_FACTOR,
    MISS_SCALE_TOLERANCE_MULT,
    PLANE_TERM_WEIGHT,
    PROXIMITY_EXPONENT,
    SCORE_WEIGHT_BUDGET,
    SCORE_WEIGHT_FUEL,
    SCORE_WEIGHT_PROXIMITY,
    TIER_MISS_SCALE,
    miss_scale_km,
)
from orbital_planner.schemas import CalculationSnapshot, Scenario, ScoreBreakdown
from orbital_planner.vec3 import vec3_mag


def build_calculation_snapshot(
    scenario: Scenario,
    t_s: float,
    score: ScoreBreakdown | None = None,
) -> CalculationSnapshot:
    tg = enrich_target(scenario.target)
    el = target_elements(tg)
    tpos = target_position_at(tg, t_s)
    tvel = target_velocity_at(tg, t_s)
    tnu = target_true_anomaly_at(tg, t_s)
    tr = vec3_mag(tpos)
    tv = vec3_mag(tvel)

    sc_el = spacecraft_elements(scenario.spacecraft.position, scenario.spacecraft.velocity)
    sc_pos, sc_vel, sc_nu = propagate_elements(sc_el, t_s)

    if score is not None and score.trajectory:
        nearest = min(score.trajectory, key=lambda p: abs(p.t_s - t_s))
        chaser_pos = nearest.position
        chaser_vel = nearest.velocity
        ch_el = spacecraft_elements(chaser_pos, chaser_vel)
        chaser_nu = ch_el.true_anomaly_at_t0_rad
        chaser_note = "Simulated trajectory (RK4 · post-burn state)"
    else:
        chaser_pos = sc_pos
        chaser_vel = sc_vel
        ch_el = sc_el
        chaser_nu = sc_nu
        chaser_note = (
            "Initial coast ellipse (no plan run yet)"
            if tg.kind == "moon"
            else "Initial coast ellipse (no plan run yet)"
        )

    grav = gravity_breakdown_at(chaser_pos, t_s, tg if tg.kind == "moon" else None)

    incl = el.inclination_rad
    miss_scale = miss_scale_km(scenario, tg)
    tier_mult = TIER_MISS_SCALE.get(scenario.tier, 1.0)

    score_block: dict | None = None
    if score is not None:
        score_block = {
            "miss_km": score.miss_km,
            "plane_offset_km": score.plane_offset_km,
            "fuel_used": score.fuel_used,
            "optimal_dv": score.optimal_dv,
            "fuel_ratio": score.fuel_ratio,
            "hit_score": score.hit_score,
            "fuel_penalty": score.fuel_penalty,
            "score": score.score,
            "miss_scale_formula": (
                f"miss_scale = tolerance × {MISS_SCALE_TOLERANCE_MULT:.0f} × tier({tier_mult:.2f}) "
                f"× (1 + {INCL_MISS_SCALE_FACTOR:.2f}·sin i)"
            ),
            "hit_formula": (
                f"proximity = 1 / (1 + (miss/miss_scale)^{PROXIMITY_EXPONENT:.2f} "
                f"+ {PLANE_TERM_WEIGHT:.2f}·(plane/miss_scale)^{PROXIMITY_EXPONENT:.2f}), "
                f"with tolerance bonus up to 5× tolerance"
            ),
            "miss_scale_km": miss_scale,
            "score_formula": (
                f"100×({SCORE_WEIGHT_PROXIMITY:.0%}·proximity + "
                f"{SCORE_WEIGHT_FUEL:.0%}·fuel + {SCORE_WEIGHT_BUDGET:.0%}·budget) "
                f"− min(100×penalty, {FUEL_PENALTY_CAP * 100:.0f})"
            ),
            "weight_proximity": SCORE_WEIGHT_PROXIMITY,
            "weight_fuel": SCORE_WEIGHT_FUEL,
            "weight_budget": SCORE_WEIGHT_BUDGET,
            "crashed": score.crashed,
            "closest_approach_time_s": score.closest_approach_time_s,
        }

    return CalculationSnapshot(
        t_s=t_s,
        mu_km3_s2=MU_EARTH_KM3_S2,
        earth_radius_km=EARTH_RADIUS_KM,
        earth_spin_deg=math.degrees(earth_spin_angle(t_s)),
        target={
            "kind": tg.kind,
            "orbit_type": tg.orbit_type,
            "position_km": list(tpos),
            "velocity_km_s": list(tvel),
            "radius_km": tr,
            "speed_km_s": tv,
            "true_anomaly_deg": math.degrees(tnu),
            "semi_major_axis_km": el.semi_major_axis_km,
            "eccentricity": el.eccentricity,
            "inclination_deg": math.degrees(el.inclination_rad),
            "raan_deg": math.degrees(el.raan_rad),
            "periapsis_km": el.periapsis_km,
            "apoapsis_km": el.apoapsis_km,
            "period_min": el.period_s / 60.0,
            "mean_motion_deg_s": math.degrees(el.mean_motion_rad_s),
            "specific_energy": el.specific_energy_km2_s2,
            "angular_momentum": el.specific_angular_momentum,
            "vis_viva_energy": tv * tv / 2.0 - MU_EARTH_KM3_S2 / max(tr, 1.0),
            "orbit_equation": "3D Kepler: r = a(1−e²)/(1+e cos ν) in orbital plane",
            "mu_body_km3_s2": tg.gravitational_parameter_km3_s2 or 0.0,
            "body_radius_km": tg.body_radius_km or 0.0,
        },
        chaser={
            "position_km": list(chaser_pos),
            "velocity_km_s": list(chaser_vel),
            "radius_km": vec3_mag(chaser_pos),
            "speed_km_s": vec3_mag(chaser_vel),
            "true_anomaly_deg": math.degrees(chaser_nu),
            "semi_major_axis_km": ch_el.semi_major_axis_km,
            "eccentricity": ch_el.eccentricity,
            "inclination_deg": math.degrees(ch_el.inclination_rad),
            "periapsis_km": ch_el.periapsis_km,
            "apoapsis_km": ch_el.apoapsis_km,
            "period_min": ch_el.period_s / 60.0,
            "specific_energy": ch_el.specific_energy_km2_s2,
            "free_orbit": chaser_note,
        },
        gravity={
            **grav,
            "earth_formula": "a⊕ = −μ⊕ r / |r|³",
            "moon_formula": "a☾ = μ☾ (r_moon − r) / |r_moon − r|³",
            "model": "restricted 3-body · full 3D ECI state",
        },
        score=score_block,
    )
