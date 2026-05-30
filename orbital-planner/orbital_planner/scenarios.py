"""~15 authored scenarios across difficulty tiers."""

from __future__ import annotations

import math
from typing import Literal

from orbital_planner.constants import MU_EARTH_KM3_S2
from orbital_planner.kepler2d import OrbitElements, mean_motion, state_from_elements
from orbital_planner.schemas import Scenario, SpacecraftState, TargetSpec


def _state_on_kepler_ellipse(
    semi_major_km: float,
    eccentricity: float,
    true_anomaly_rad: float,
    argument_of_periapsis_rad: float = 0.0,
) -> tuple[tuple[float, float], tuple[float, float]]:
    n = mean_motion(semi_major_km)
    el = OrbitElements(
        semi_major_axis_km=semi_major_km,
        eccentricity=eccentricity,
        argument_of_periapsis_rad=argument_of_periapsis_rad,
        true_anomaly_at_t0_rad=true_anomaly_rad,
        mean_motion_rad_s=n,
        period_s=2.0 * math.pi / n,
        periapsis_km=semi_major_km * (1.0 - eccentricity),
        apoapsis_km=semi_major_km * (1.0 + eccentricity),
        specific_angular_momentum=math.sqrt(MU_EARTH_KM3_S2 * semi_major_km * (1.0 - eccentricity**2)),
        specific_energy_km2_s2=-MU_EARTH_KM3_S2 / (2.0 * semi_major_km),
    )
    return state_from_elements(el, true_anomaly_rad)


def _elliptical_state(
    semi_major_km: float,
    eccentricity: float,
    true_anomaly_rad: float,
    argument_of_periapsis_rad: float = 0.0,
) -> SpacecraftState:
    pos, vel = _state_on_kepler_ellipse(
        semi_major_km, eccentricity, true_anomaly_rad, argument_of_periapsis_rad
    )
    return SpacecraftState(position=pos, velocity=vel)


def _target_elliptical(
    semi_major_km: float,
    eccentricity: float,
    true_anomaly_rad: float,
    tolerance_km: float,
    *,
    argument_of_periapsis_rad: float = 0.0,
    kind: Literal["satellite", "moon"] = "satellite",
    spin_rad_s: float = 0.12,
) -> TargetSpec:
    pos, vel = _state_on_kepler_ellipse(
        semi_major_km, eccentricity, true_anomaly_rad, argument_of_periapsis_rad
    )
    return TargetSpec(
        position=pos,
        velocity=vel,
        tolerance_km=tolerance_km,
        kind=kind,
        semi_major_axis_km=semi_major_km,
        eccentricity=eccentricity,
        argument_of_periapsis_rad=argument_of_periapsis_rad,
        true_anomaly_at_t0_rad=true_anomaly_rad,
        spin_rad_s=spin_rad_s,
    )


def _circular_state(radius_km: float, angle_rad: float) -> SpacecraftState:
    """Circular orbit: position on circle, prograde velocity."""
    x = radius_km * math.cos(angle_rad)
    y = radius_km * math.sin(angle_rad)
    speed = math.sqrt(MU_EARTH_KM3_S2 / radius_km)
    vx = -speed * math.sin(angle_rad)
    vy = speed * math.cos(angle_rad)
    return SpacecraftState(position=(x, y), velocity=(vx, vy))


def _target_on_radius(
    radius_km: float,
    angle_rad: float,
    tolerance_km: float,
    *,
    kind: Literal["satellite", "moon"] = "satellite",
    spin_rad_s: float = 0.12,
) -> TargetSpec:
    return TargetSpec(
        position=(radius_km * math.cos(angle_rad), radius_km * math.sin(angle_rad)),
        tolerance_km=tolerance_km,
        kind=kind,
        orbit_radius_km=radius_km,
        initial_angle_rad=angle_rad,
        spin_rad_s=spin_rad_s,
    )


# Easy — small radius change, generous fuel
RAISE_EASY = Scenario(
    id="raise-easy-01",
    name="Gentle orbit raise",
    tier="easy",
    spacecraft=_circular_state(6800.0, -math.pi / 2),
    target=_target_on_radius(7500.0, math.pi / 2, 80.0),
    fuel_budget_dv=2.5,
    time_limit_s=6000.0,
)

STATION_EASY = Scenario(
    id="station-easy-02",
    name="Station-keeping hop",
    tier="easy",
    spacecraft=_circular_state(7000.0, 0.0),
    target=_target_on_radius(7200.0, math.pi / 3, 100.0),
    fuel_budget_dv=2.0,
    time_limit_s=5400.0,
)

# Medium
INTERCEPT_01 = Scenario(
    id="intercept-01",
    name="Intercept derelict satellite",
    tier="medium",
    spacecraft=_elliptical_state(7600.0, 0.12, -math.pi / 2, 0.0),
    target=_target_elliptical(
        10_000.0,
        0.14,
        math.pi / 2,
        50.0,
        argument_of_periapsis_rad=0.25,
        kind="moon",
        spin_rad_s=0.06,
    ),
    fuel_budget_dv=2.0,
    time_limit_s=7200.0,
)

PHASE_MEDIUM = Scenario(
    id="phase-medium-02",
    name="Phasing rendezvous",
    tier="medium",
    spacecraft=_circular_state(8000.0, math.pi * 0.15),
    target=_target_on_radius(8000.0, math.pi * 0.85, 60.0),
    fuel_budget_dv=1.8,
    time_limit_s=8000.0,
)

TRANSFER_MED = Scenario(
    id="transfer-medium-03",
    name="Elliptic transfer slot",
    tier="medium",
    spacecraft=_elliptical_state(6800.0, 0.12, -math.pi / 2),
    target=_target_elliptical(9800.0, 0.18, math.pi / 2, 55.0, kind="satellite"),
    fuel_budget_dv=2.2,
    time_limit_s=7200.0,
)

# Hard
RESCUE_HARD = Scenario(
    id="rescue-hard-01",
    name="Rescue capsule intercept",
    tier="hard",
    spacecraft=_circular_state(6500.0, 0.4),
    target=_target_on_radius(10500.0, 2.1, 45.0),
    fuel_budget_dv=2.0,
    time_limit_s=7200.0,
)

DEBRIS_HARD = Scenario(
    id="debris-hard-02",
    name="Debris avoidance slot",
    tier="hard",
    spacecraft=_circular_state(7200.0, -0.8),
    target=_target_on_radius(11000.0, 2.6, 40.0),
    fuel_budget_dv=1.9,
    time_limit_s=6800.0,
)

SYNC_HARD = Scenario(
    id="sync-hard-03",
    name="GEO slot sync (scaled)",
    tier="hard",
    spacecraft=_circular_state(8000.0, 1.2),
    target=_target_on_radius(12000.0, 3.5, 35.0),
    fuel_budget_dv=1.8,
    time_limit_s=9000.0,
)

TIGHT_HARD = Scenario(
    id="tight-hard-04",
    name="Tight tolerance flyby",
    tier="hard",
    spacecraft=_circular_state(7500.0, -1.1),
    target=_target_on_radius(10000.0, 0.9, 25.0),
    fuel_budget_dv=1.7,
    time_limit_s=6500.0,
)

# Expert
COMPOUND_EX = Scenario(
    id="compound-expert-01",
    name="Compound plane change",
    tier="expert",
    spacecraft=_circular_state(6800.0, 0.2),
    target=_target_on_radius(11500.0, 2.8, 30.0),
    fuel_budget_dv=1.6,
    time_limit_s=8000.0,
)

MIN_FUEL_EX = Scenario(
    id="minfuel-expert-02",
    name="Minimum-fuel intercept",
    tier="expert",
    spacecraft=_circular_state(7100.0, -0.3),
    target=_target_on_radius(10800.0, 2.4, 20.0),
    fuel_budget_dv=1.5,
    time_limit_s=7200.0,
)

LONG_ARC_EX = Scenario(
    id="longarc-expert-03",
    name="Long-arc reposition",
    tier="expert",
    spacecraft=_circular_state(6600.0, 1.7),
    target=_target_on_radius(12500.0, 4.2, 28.0),
    fuel_budget_dv=1.55,
    time_limit_s=9500.0,
)

EDGE_EX = Scenario(
    id="edge-expert-04",
    name="Edge-of-budget sprint",
    tier="expert",
    spacecraft=_circular_state(7000.0, 0.6),
    target=_target_on_radius(11200.0, 3.9, 22.0),
    fuel_budget_dv=1.45,
    time_limit_s=7000.0,
)

ORIGINAL_LEO = Scenario(
    id="leo-classic-01",
    name="Classic LEO [7000,0] → [0,10000]",
    tier="hard",
    spacecraft=SpacecraftState(position=(7000.0, 0.0), velocity=(0.0, 7.546)),
    target=TargetSpec(position=(0.0, 10000.0), tolerance_km=50.0),
    fuel_budget_dv=2.2,
    time_limit_s=7200.0,
)

ALL_SCENARIOS: list[Scenario] = [
    RAISE_EASY,
    STATION_EASY,
    INTERCEPT_01,
    PHASE_MEDIUM,
    TRANSFER_MED,
    RESCUE_HARD,
    DEBRIS_HARD,
    SYNC_HARD,
    TIGHT_HARD,
    COMPOUND_EX,
    MIN_FUEL_EX,
    LONG_ARC_EX,
    EDGE_EX,
    ORIGINAL_LEO,
]

SCENARIOS: dict[str, Scenario] = {s.id: s for s in ALL_SCENARIOS}

TIER_ORDER = ("easy", "medium", "hard", "expert")
