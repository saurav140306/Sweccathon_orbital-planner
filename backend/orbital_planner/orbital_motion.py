"""Moving targets: 3D Kepler orbits (inclination + RAAN), Earth spin."""

from __future__ import annotations

import math

from orbital_planner.constants import (
    EARTH_SPIN_RAD_S,
    MOON_RADIUS_KM,
    MU_EARTH_KM3_S2,
    MU_MOON_KM3_S2,
)
from orbital_planner.kepler3d import (
    OrbitElements3D,
    elements_from_elements_2d,
    elements_from_state,
    propagate_elements,
    sample_orbit_positions,
    state_from_elements,
)
from orbital_planner.schemas import OrbitElementsOut, TargetSpec, TrajectoryPoint
from orbital_planner.vec3 import to_vec3, vec3_mag

Vec3 = tuple[float, float, float]


def circular_mean_motion(radius_km: float, mu: float = MU_EARTH_KM3_S2) -> float:
    r = max(radius_km, 1.0)
    return math.sqrt(mu / r**3)


def _elements_out_to_3d(out: OrbitElementsOut) -> OrbitElements3D:
    return OrbitElements3D(
        semi_major_axis_km=out.semi_major_axis_km,
        eccentricity=out.eccentricity,
        inclination_rad=out.inclination_rad,
        raan_rad=out.raan_rad,
        argument_of_periapsis_rad=out.argument_of_periapsis_rad,
        true_anomaly_at_t0_rad=out.true_anomaly_at_t0_rad,
        mean_motion_rad_s=out.mean_motion_rad_s,
        period_s=out.period_s,
        periapsis_km=out.periapsis_km,
        apoapsis_km=out.apoapsis_km,
        specific_angular_momentum=out.specific_angular_momentum,
        specific_energy_km2_s2=out.specific_energy_km2_s2,
    )


def _elements_to_out(el: OrbitElements3D) -> OrbitElementsOut:
    return OrbitElementsOut(
        semi_major_axis_km=el.semi_major_axis_km,
        eccentricity=el.eccentricity,
        argument_of_periapsis_rad=el.argument_of_periapsis_rad,
        true_anomaly_at_t0_rad=el.true_anomaly_at_t0_rad,
        mean_motion_rad_s=el.mean_motion_rad_s,
        period_s=el.period_s,
        periapsis_km=el.periapsis_km,
        apoapsis_km=el.apoapsis_km,
        specific_angular_momentum=el.specific_angular_momentum,
        specific_energy_km2_s2=el.specific_energy_km2_s2,
        inclination_rad=el.inclination_rad,
        raan_rad=el.raan_rad,
    )


def target_elements(target: TargetSpec) -> OrbitElements3D:
    tg = enrich_target(target)
    if tg.orbit_elements is None:
        raise RuntimeError("Target orbit elements not resolved")
    return _elements_out_to_3d(tg.orbit_elements)


def target_body_mu(target: TargetSpec) -> float:
    if target.gravitational_parameter_km3_s2 is not None:
        return target.gravitational_parameter_km3_s2
    if target.kind == "moon":
        return MU_MOON_KM3_S2
    return 0.0


def target_body_radius_km(target: TargetSpec) -> float:
    if target.body_radius_km is not None:
        return target.body_radius_km
    if target.kind == "moon":
        return MOON_RADIUS_KM
    return 0.0


def enrich_target(target: TargetSpec) -> TargetSpec:
    pos = to_vec3(target.position)
    r0 = vec3_mag(pos)
    x, y, _z = pos

    elements: OrbitElements3D | None = None

    if target.velocity is not None:
        elements = elements_from_state(pos, to_vec3(target.velocity))

    if elements is None and target.semi_major_axis_km is not None:
        a = target.semi_major_axis_km
        e = max(0.0, min(target.eccentricity, 0.95))
        argp = target.argument_of_periapsis_rad
        nu0 = (
            target.true_anomaly_at_t0_rad
            if target.true_anomaly_at_t0_rad is not None
            else math.atan2(y, x) - argp
        )
        elements = elements_from_elements_2d(
            a,
            e,
            argp,
            nu0,
            inclination_rad=target.inclination_rad,
            raan_rad=target.raan_rad,
        )

    if elements is None:
        omega = target.angular_velocity_rad_s or circular_mean_motion(r0)
        angle = target.initial_angle_rad or math.atan2(y, x)
        elements = elements_from_elements_2d(
            r0,
            0.0,
            angle,
            0.0,
            inclination_rad=target.inclination_rad,
            raan_rad=target.raan_rad,
        )
        elements = OrbitElements3D(
            semi_major_axis_km=elements.semi_major_axis_km,
            eccentricity=0.0,
            inclination_rad=elements.inclination_rad,
            raan_rad=elements.raan_rad,
            argument_of_periapsis_rad=angle,
            true_anomaly_at_t0_rad=0.0,
            mean_motion_rad_s=omega,
            period_s=2.0 * math.pi / omega,
            periapsis_km=r0,
            apoapsis_km=r0,
            specific_angular_momentum=math.sqrt(MU_EARTH_KM3_S2 * r0),
            specific_energy_km2_s2=-MU_EARTH_KM3_S2 / (2.0 * r0),
        )

    out = _elements_to_out(elements)
    orbit_type = "circular" if elements.eccentricity < 1e-4 else "elliptical"
    return target.model_copy(
        update={
            "position": pos,
            "velocity": target.velocity,
            "orbit_type": orbit_type,
            "orbit_elements": out,
            "semi_major_axis_km": elements.semi_major_axis_km,
            "eccentricity": elements.eccentricity,
            "argument_of_periapsis_rad": elements.argument_of_periapsis_rad,
            "true_anomaly_at_t0_rad": elements.true_anomaly_at_t0_rad,
            "inclination_rad": elements.inclination_rad,
            "raan_rad": elements.raan_rad,
            "angular_velocity_rad_s": elements.mean_motion_rad_s,
            "revolution_period_s": elements.period_s,
            "orbit_radius_km": r0,
            "initial_angle_rad": math.atan2(y, x),
            "gravitational_parameter_km3_s2": target_body_mu(target),
            "body_radius_km": target_body_radius_km(target),
        },
    )


def target_position_at(target: TargetSpec, t_s: float) -> Vec3:
    el = target_elements(target)
    pos, _, _ = propagate_elements(el, t_s)
    return pos


def target_velocity_at(target: TargetSpec, t_s: float) -> Vec3:
    el = target_elements(target)
    _, vel, _ = propagate_elements(el, t_s)
    return vel


def target_true_anomaly_at(target: TargetSpec, t_s: float) -> float:
    el = target_elements(target)
    _, _, nu = propagate_elements(el, t_s)
    return nu


def sample_target_trajectory(
    target: TargetSpec,
    time_limit_s: float,
    *,
    sample_every_s: float = 30.0,
) -> list[TrajectoryPoint]:
    points: list[TrajectoryPoint] = []
    t = 0.0
    while t <= time_limit_s + 1e-9:
        pos = target_position_at(target, t)
        vel = target_velocity_at(target, t)
        points.append(TrajectoryPoint(t_s=t, position=pos, velocity=vel))
        t += sample_every_s
    return points


def target_orbit_path(target: TargetSpec, n_points: int = 120) -> list[Vec3]:
    return sample_orbit_positions(target_elements(target), n_points=n_points)


def earth_spin_angle(t_s: float) -> float:
    return EARTH_SPIN_RAD_S * t_s


def body_spin_angle(target: TargetSpec, t_s: float) -> float:
    return target.spin_rad_s * t_s


def spacecraft_elements(
    scenario_spacecraft_position: Vec3,
    scenario_spacecraft_velocity: Vec3,
) -> OrbitElements3D:
    return elements_from_state(
        to_vec3(scenario_spacecraft_position),
        to_vec3(scenario_spacecraft_velocity),
    )
