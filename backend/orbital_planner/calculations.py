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
    miss_scale = tg.tolerance_km * 20.0 * (1.0 + 0.15 * math.sin(incl))

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
            "miss_scale_formula": "miss_scale = tolerance × 20 × (1 + 0.15·sin i)",
            "hit_formula": "proximity = 1 / (1 + miss/miss_scale + 0.15·plane/miss_scale)",
            "miss_scale_km": miss_scale,
            "score_formula": "100×(0.5·proximity + 0.3·fuel + 0.2·budget) − 100×penalty",
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
