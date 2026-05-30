"""Build calculation snapshots for the frontend panel."""



from __future__ import annotations



import math



from orbital_planner.constants import EARTH_RADIUS_KM, MU_EARTH_KM3_S2

from orbital_planner.kepler2d import elements_from_state, propagate_elements

from orbital_planner.orbital_motion import (

    earth_spin_angle,

    enrich_target,

    target_elements,

    target_position_at,

    target_true_anomaly_at,

    target_velocity_at,

)

from orbital_planner.physics import gravity_breakdown_at

from orbital_planner.schemas import CalculationSnapshot, Scenario, ScoreBreakdown





def _vec_mag(v: tuple[float, float]) -> float:

    return math.hypot(v[0], v[1])





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

    tr = _vec_mag(tpos)

    tv = _vec_mag(tvel)



    sc_el = elements_from_state(scenario.spacecraft.position, scenario.spacecraft.velocity)

    sc_pos, sc_vel, sc_nu = propagate_elements(sc_el, t_s)



    if score is not None and score.trajectory:

        nearest = min(score.trajectory, key=lambda p: abs(p.t_s - t_s))

        chaser_pos = nearest.position

        chaser_vel = nearest.velocity

    else:

        chaser_pos = sc_pos

        chaser_vel = sc_vel



    grav = gravity_breakdown_at(chaser_pos, t_s, tg if tg.kind == "moon" else None)



    miss_scale = tg.tolerance_km * 20.0



    score_block: dict | None = None

    if score is not None:

        score_block = {

            "miss_km": score.miss_km,

            "fuel_used": score.fuel_used,

            "optimal_dv": score.optimal_dv,

            "fuel_ratio": score.fuel_ratio,

            "hit_score": score.hit_score,

            "fuel_penalty": score.fuel_penalty,

            "final_score": score.score,

            "hit_formula": "proximity = 1 / (1 + miss / miss_scale)",

            "miss_scale_km": miss_scale,

            "score_formula": "100×(0.5·proximity + 0.3·fuel + 0.2·budget) − penalty",

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

            "periapsis_km": el.periapsis_km,

            "apoapsis_km": el.apoapsis_km,

            "period_min": el.period_s / 60.0,

            "mean_motion_deg_s": math.degrees(el.mean_motion_rad_s),

            "specific_energy": el.specific_energy_km2_s2,

            "angular_momentum": el.specific_angular_momentum,

            "vis_viva_energy": tv * tv / 2.0 - MU_EARTH_KM3_S2 / max(tr, 1.0),

            "orbit_equation": "r = a(1−e²) / (1 + e cos ν)",

            "mu_body_km3_s2": tg.gravitational_parameter_km3_s2 or 0.0,

            "body_radius_km": tg.body_radius_km or 0.0,

        },

        chaser={

            "position_km": list(chaser_pos),

            "velocity_km_s": list(chaser_vel),

            "radius_km": _vec_mag(chaser_pos),

            "speed_km_s": _vec_mag(chaser_vel),

            "true_anomaly_deg": math.degrees(sc_nu),

            "semi_major_axis_km": sc_el.semi_major_axis_km,

            "eccentricity": sc_el.eccentricity,

            "periapsis_km": sc_el.periapsis_km,

            "apoapsis_km": sc_el.apoapsis_km,

            "period_min": sc_el.period_s / 60.0,

            "specific_energy": sc_el.specific_energy_km2_s2,

            "free_orbit": (

                "RK4: Earth + moon gravity"

                if tg.kind == "moon"

                else "RK4: Earth gravity only"

            ),

        },

        gravity={

            **grav,

            "earth_formula": "a⊕ = −μ⊕ r / |r|³",

            "moon_formula": "a☾ = μ☾ (r_moon − r) / |r_moon − r|³",

            "model": "restricted 3-body (moon on fixed Kepler orbit)",

        },

        score=score_block,

    )


