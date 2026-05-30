"""3D Keplerian orbits: inclination, RAAN, propagation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from orbital_planner.constants import MU_EARTH_KM3_S2

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class OrbitElements3D:
    semi_major_axis_km: float
    eccentricity: float
    inclination_rad: float
    raan_rad: float
    argument_of_periapsis_rad: float
    true_anomaly_at_t0_rad: float
    mean_motion_rad_s: float
    period_s: float
    periapsis_km: float
    apoapsis_km: float
    specific_angular_momentum: float
    specific_energy_km2_s2: float


def mean_motion(semi_major_axis_km: float, mu: float = MU_EARTH_KM3_S2) -> float:
    a = max(semi_major_axis_km, 1.0)
    return math.sqrt(mu / a**3)


def _rot_z(angle: float) -> list[list[float]]:
    c, s = math.cos(angle), math.sin(angle)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def _rot_x(angle: float) -> list[list[float]]:
    c, s = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def _mat_vec(m: list[list[float]], v: Vec3) -> Vec3:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    out = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            out[i][j] = sum(a[i][k] * b[k][j] for k in range(3))
    return out


def _perifocal_to_inertial(v: Vec3, raan: float, inc: float, argp: float) -> Vec3:
    r = _mat_mul(_rot_z(-raan), _mat_mul(_rot_x(-inc), _rot_z(-argp)))
    return _mat_vec(r, v)


def _solve_kepler(mean_anomaly_rad: float, eccentricity: float) -> float:
    e = eccentricity
    m = mean_anomaly_rad % (2.0 * math.pi)
    if e < 1e-10:
        return m
    e_anom = m if e < 0.8 else math.pi
    for _ in range(50):
        delta = (e_anom - e * math.sin(e_anom) - m) / (1.0 - e * math.cos(e_anom))
        e_anom -= delta
        if abs(delta) < 1e-11:
            break
    return e_anom


def _true_anomaly_from_mean(mean_anomaly_rad: float, eccentricity: float) -> float:
    e_anom = _solve_kepler(mean_anomaly_rad, eccentricity)
    sin_e = math.sin(e_anom)
    cos_e = math.cos(e_anom)
    denom = 1.0 - eccentricity * cos_e
    return math.atan2(
        math.sqrt(1.0 - eccentricity**2) * sin_e / denom,
        (cos_e - eccentricity) / denom,
    )


def _true_anomaly_to_mean(nu: float, e: float) -> float:
    if e < 1e-10:
        return nu
    tan_half = math.tan(nu / 2.0)
    e_anom = 2.0 * math.atan2(math.sqrt(1.0 + e) * tan_half, math.sqrt(1.0 - e))
    return e_anom - e * math.sin(e_anom)


def elements_from_elements_2d(
    semi_major_km: float,
    eccentricity: float,
    argp: float,
    nu0: float,
    *,
    inclination_rad: float = 0.0,
    raan_rad: float = 0.0,
    mu: float = MU_EARTH_KM3_S2,
) -> OrbitElements3D:
    a = semi_major_km
    n = mean_motion(a, mu)
    h = math.sqrt(mu * a * (1.0 - eccentricity**2))
    return OrbitElements3D(
        semi_major_axis_km=a,
        eccentricity=eccentricity,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
        argument_of_periapsis_rad=argp,
        true_anomaly_at_t0_rad=nu0,
        mean_motion_rad_s=n,
        period_s=2.0 * math.pi / n,
        periapsis_km=a * (1.0 - eccentricity),
        apoapsis_km=a * (1.0 + eccentricity),
        specific_angular_momentum=h,
        specific_energy_km2_s2=-mu / (2.0 * a),
    )


def elements_from_state(
    position: Vec3,
    velocity: Vec3,
    *,
    mu: float = MU_EARTH_KM3_S2,
) -> OrbitElements3D:
    rx, ry, rz = position
    vx, vy, vz = velocity
    r = math.sqrt(rx * rx + ry * ry + rz * rz)
    v2 = vx * vx + vy * vy + vz * vz
    hx = ry * vz - rz * vy
    hy = rz * vx - rx * vz
    hz = rx * vy - ry * vx
    h = math.sqrt(hx * hx + hy * hy + hz * hz)
    eps = 0.5 * v2 - mu / max(r, 1.0)
    if eps >= -1e-12:
        raise ValueError("Escape/hyperbolic state not supported")
    a = -mu / (2.0 * eps)
    e = math.sqrt(max(0.0, 1.0 - (h * h) / (a * mu)))
    inc = math.acos(max(-1.0, min(1.0, hz / max(h, 1e-12))))
    nx, ny = -hy, hx
    n_mag = math.hypot(nx, ny)
    if n_mag < 1e-12:
        raan = 0.0
    else:
        raan = math.atan2(ny, nx) % (2.0 * math.pi)
    if n_mag < 1e-12:
        argp = math.atan2(ry, rx) if inc < 1e-6 else 0.0
    else:
        argp = math.atan2(
            hz * (nx * rx + ny * ry) - h * (nx * vx + ny * vy),
            h * (nx * vy - ny * vx) - hz * (nx * rx + ny * ry),
        )
    px = (vy * hz - vz * hy) / mu - rx / r
    py = (vz * hx - vx * hz) / mu - ry / r
    pz = (vx * hy - vy * hx) / mu - rz / r
    nu = math.atan2(
        (py * rz - pz * ry) if e > 1e-9 else ry,
        (px * rx + py * ry + pz * rz) if e > 1e-9 else rx,
    )
    n = mean_motion(a, mu)
    return OrbitElements3D(
        semi_major_axis_km=a,
        eccentricity=e,
        inclination_rad=inc,
        raan_rad=raan,
        argument_of_periapsis_rad=argp,
        true_anomaly_at_t0_rad=nu,
        mean_motion_rad_s=n,
        period_s=2.0 * math.pi / n,
        periapsis_km=a * (1.0 - e),
        apoapsis_km=a * (1.0 + e),
        specific_angular_momentum=h,
        specific_energy_km2_s2=eps,
    )


def state_from_elements(el: OrbitElements3D, true_anomaly_rad: float, *, mu: float = MU_EARTH_KM3_S2) -> tuple[Vec3, Vec3]:
    a, e, argp, inc, raan = (
        el.semi_major_axis_km,
        el.eccentricity,
        el.argument_of_periapsis_rad,
        el.inclination_rad,
        el.raan_rad,
    )
    nu = true_anomaly_rad
    p = a * (1.0 - e * e)
    r = p / (1.0 + e * math.cos(nu))
    sqrt_mu_p = math.sqrt(mu / p)
    vr = sqrt_mu_p * e * math.sin(nu)
    vtheta = sqrt_mu_p * (1.0 + e * math.cos(nu))
    pos_p: Vec3 = (r * math.cos(nu), r * math.sin(nu), 0.0)
    vel_p: Vec3 = (vr * math.cos(nu) - vtheta * math.sin(nu), vr * math.sin(nu) + vtheta * math.cos(nu), 0.0)
    pos = _perifocal_to_inertial(pos_p, raan, inc, argp)
    vel = _perifocal_to_inertial(vel_p, raan, inc, argp)
    return pos, vel


def propagate_elements(el: OrbitElements3D, t_s: float) -> tuple[Vec3, Vec3, float]:
    m0 = _true_anomaly_to_mean(el.true_anomaly_at_t0_rad, el.eccentricity)
    m = m0 + el.mean_motion_rad_s * t_s
    nu = _true_anomaly_from_mean(m, el.eccentricity)
    pos, vel = state_from_elements(el, nu)
    return pos, vel, nu


def sample_orbit_positions(el: OrbitElements3D, *, n_points: int = 120) -> list[Vec3]:
    pts: list[Vec3] = []
    for i in range(n_points + 1):
        nu = -math.pi + (2.0 * math.pi * i) / n_points
        pos, _ = state_from_elements(el, nu)
        pts.append(pos)
    return pts
