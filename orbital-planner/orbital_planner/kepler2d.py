"""2D Keplerian orbits: elements, propagation, vis-viva."""

from __future__ import annotations

import math
from dataclasses import dataclass

from orbital_planner.constants import MU_EARTH_KM3_S2


@dataclass(frozen=True)
class OrbitElements:
    """Planar Keplerian elements around Earth."""

    semi_major_axis_km: float
    eccentricity: float
    argument_of_periapsis_rad: float
    true_anomaly_at_t0_rad: float
    mean_motion_rad_s: float
    period_s: float
    periapsis_km: float
    apoapsis_km: float
    specific_angular_momentum: float
    specific_energy_km2_s2: float

    @property
    def is_circular(self) -> bool:
        return self.eccentricity < 1e-6


def mean_motion(semi_major_axis_km: float, mu: float = MU_EARTH_KM3_S2) -> float:
    a = max(semi_major_axis_km, 1.0)
    return math.sqrt(mu / a**3)


def elements_from_state(
    position: tuple[float, float],
    velocity: tuple[float, float],
    *,
    mu: float = MU_EARTH_KM3_S2,
) -> OrbitElements:
    """Recover osculating Kepler elements from inertial r, v (bounded orbit)."""
    rx, ry = position
    vx, vy = velocity
    r = math.hypot(rx, ry)
    v2 = vx * vx + vy * vy
    h = rx * vy - ry * vx
    eps = 0.5 * v2 - mu / max(r, 1.0)
    if eps >= -1e-12:
        raise ValueError("Hyperbolic/escape state not supported for elliptical target")
    a = -mu / (2.0 * eps)
    e2 = max(0.0, 1.0 - (h * h) / (a * mu))
    e = math.sqrt(e2)
    p = a * (1.0 - e * e)

    ex = (vy * h) / mu - rx / r
    ey = (-vx * h) / mu - ry / r
    argp = math.atan2(ey, ex)
    if e < 1e-9:
        nu0 = math.atan2(ry, rx) - argp
    else:
        nu0 = math.atan2(ex * ry - ey * rx, ex * rx + ey * ry)

    n = mean_motion(a, mu)
    return OrbitElements(
        semi_major_axis_km=a,
        eccentricity=e,
        argument_of_periapsis_rad=argp,
        true_anomaly_at_t0_rad=nu0,
        mean_motion_rad_s=n,
        period_s=2.0 * math.pi / n,
        periapsis_km=a * (1.0 - e),
        apoapsis_km=a * (1.0 + e),
        specific_angular_momentum=h,
        specific_energy_km2_s2=eps,
    )


def _solve_kepler(mean_anomaly_rad: float, eccentricity: float, max_iter: int = 50) -> float:
    """Eccentric anomaly E from mean anomaly M (rad)."""
    e = eccentricity
    m = mean_anomaly_rad % (2.0 * math.pi)
    if e < 1e-10:
        return m
    e_anom = m if e < 0.8 else math.pi
    for _ in range(max_iter):
        delta = (e_anom - e * math.sin(e_anom) - m) / (1.0 - e * math.cos(e_anom))
        e_anom -= delta
        if abs(delta) < 1e-11:
            break
    return e_anom


def true_anomaly_from_mean(mean_anomaly_rad: float, eccentricity: float) -> float:
    e = eccentricity
    e_anom = _solve_kepler(mean_anomaly_rad, e)
    sin_e = math.sin(e_anom)
    cos_e = math.cos(e_anom)
    denom = 1.0 - e * cos_e
    sin_nu = (math.sqrt(1.0 - e * e) * sin_e) / denom
    cos_nu = (cos_e - e) / denom
    return math.atan2(sin_nu, cos_nu)


def state_from_elements(
    elements: OrbitElements,
    true_anomaly_rad: float,
    *,
    mu: float = MU_EARTH_KM3_S2,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Inertial position and velocity at true anomaly ν."""
    a = elements.semi_major_axis_km
    e = elements.eccentricity
    argp = elements.argument_of_periapsis_rad
    nu = true_anomaly_rad
    p = a * (1.0 - e * e)
    r = p / (1.0 + e * math.cos(nu))
    # Polar v_r, v_theta in orbit frame
    sqrt_mu_p = math.sqrt(mu / p)
    vr = sqrt_mu_p * e * math.sin(nu)
    vtheta = sqrt_mu_p * (1.0 + e * math.cos(nu))
    # Rotate by argp + nu
    px = r * math.cos(argp + nu)
    py = r * math.sin(argp + nu)
    # Velocity: vr * r_hat + vtheta * t_hat
    rhat_x = math.cos(argp + nu)
    rhat_y = math.sin(argp + nu)
    that_x = -math.sin(argp + nu)
    that_y = math.cos(argp + nu)
    vx = vr * rhat_x + vtheta * that_x
    vy = vr * rhat_y + vtheta * that_y
    return (px, py), (vx, vy)


def propagate_elements(
    elements: OrbitElements,
    t_s: float,
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Return (position, velocity, true_anomaly) at time t from t=0."""
    m0 = _true_anomaly_to_mean(elements.true_anomaly_at_t0_rad, elements.eccentricity)
    m = m0 + elements.mean_motion_rad_s * t_s
    nu = true_anomaly_from_mean(m, elements.eccentricity)
    pos, vel = state_from_elements(elements, nu)
    return pos, vel, nu


def _true_anomaly_to_mean(nu: float, e: float) -> float:
    if e < 1e-10:
        return nu
    tan_half = math.tan(nu / 2.0)
    e_anom = 2.0 * math.atan2(math.sqrt(1.0 + e) * tan_half, math.sqrt(1.0 - e))
    return e_anom - e * math.sin(e_anom)


def sample_orbit_positions(
    elements: OrbitElements,
    *,
    n_points: int = 120,
) -> list[tuple[float, float]]:
    """Sample one full revolution for drawing the ellipse."""
    pts: list[tuple[float, float]] = []
    for i in range(n_points + 1):
        nu = -math.pi + (2.0 * math.pi * i) / n_points
        pos, _ = state_from_elements(elements, nu)
        pts.append(pos)
    return pts
