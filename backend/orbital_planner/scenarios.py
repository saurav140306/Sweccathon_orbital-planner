"""~15 authored scenarios across difficulty tiers."""

from __future__ import annotations

import math
from typing import Literal

from orbital_planner.kepler3d import elements_from_elements_2d, state_from_elements
from orbital_planner.schemas import Scenario, SpacecraftState, TargetSpec
from orbital_planner.vec3 import Vec3


def _state_on_inclined_ellipse(
    semi_major_km: float,
    eccentricity: float,
    true_anomaly_rad: float,
    *,
    argument_of_periapsis_rad: float = 0.0,
    inclination_rad: float = 0.0,
    raan_rad: float = 0.0,
) -> tuple[Vec3, Vec3]:
    el = elements_from_elements_2d(
        semi_major_km,
        eccentricity,
        argument_of_periapsis_rad,
        true_anomaly_rad,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
    )
    return state_from_elements(el, true_anomaly_rad)


def _elliptical_state(
    semi_major_km: float,
    eccentricity: float,
    true_anomaly_rad: float,
    argument_of_periapsis_rad: float = 0.0,
    *,
    inclination_rad: float = 0.0,
    raan_rad: float = 0.0,
) -> SpacecraftState:
    pos, vel = _state_on_inclined_ellipse(
        semi_major_km,
        eccentricity,
        true_anomaly_rad,
        argument_of_periapsis_rad=argument_of_periapsis_rad,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
    )
    return SpacecraftState(position=pos, velocity=vel)


def _target_elliptical_tilted(
    semi_major_km: float,
    eccentricity: float,
    true_anomaly_rad: float,
    tolerance_km: float,
    *,
    argument_of_periapsis_rad: float = 0.0,
    inclination_rad: float = 0.0,
    raan_rad: float = 0.0,
    kind: Literal["satellite", "moon"] = "satellite",
    spin_rad_s: float = 0.12,
) -> TargetSpec:
    pos, vel = _state_on_inclined_ellipse(
        semi_major_km,
        eccentricity,
        true_anomaly_rad,
        argument_of_periapsis_rad=argument_of_periapsis_rad,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
    )
    return TargetSpec(
        position=pos,
        velocity=vel,
        tolerance_km=tolerance_km,
        kind=kind,
        semi_major_axis_km=semi_major_km,
        eccentricity=eccentricity,
        argument_of_periapsis_rad=argument_of_periapsis_rad,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
        true_anomaly_at_t0_rad=true_anomaly_rad,
        spin_rad_s=spin_rad_s,
    )


def _circular_state(radius_km: float, angle_rad: float) -> SpacecraftState:
    pos, vel = _state_on_inclined_ellipse(radius_km, 0.0, 0.0, argument_of_periapsis_rad=angle_rad)
    return SpacecraftState(position=pos, velocity=vel)


def _target_on_radius(
    radius_km: float,
    angle_rad: float,
    tolerance_km: float,
    *,
    kind: Literal["satellite", "moon"] = "satellite",
    spin_rad_s: float = 0.12,
    inclination_rad: float = 0.0,
    raan_rad: float = 0.0,
) -> TargetSpec:
    pos, vel = _state_on_inclined_ellipse(
        radius_km,
        0.0,
        0.0,
        argument_of_periapsis_rad=angle_rad,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
    )
    return TargetSpec(
        position=pos,
        velocity=vel,
        tolerance_km=tolerance_km,
        kind=kind,
        orbit_radius_km=radius_km,
        initial_angle_rad=angle_rad,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
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

# Medium — moon on inclined elliptical orbit
INTERCEPT_01 = Scenario(
    id="intercept-01",
    name="Intercept derelict satellite",
    tier="medium",
    spacecraft=_elliptical_state(7600.0, 0.12, -math.pi / 2, 0.0),
    target=_target_elliptical_tilted(
        10_000.0,
        0.14,
        math.pi / 2,
        50.0,
        argument_of_periapsis_rad=0.25,
        inclination_rad=math.radians(22.0),
        raan_rad=math.radians(48.0),
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
    target=_target_elliptical_tilted(
        9800.0,
        0.18,
        math.pi / 2,
        55.0,
        inclination_rad=math.radians(18.0),
        raan_rad=math.radians(72.0),
        kind="satellite",
    ),
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

# Expert — plane-change style rendezvous
COMPOUND_EX = Scenario(
    id="compound-expert-01",
    name="Compound plane change",
    tier="expert",
    spacecraft=_circular_state(6800.0, 0.2),
    target=_target_elliptical_tilted(
        11_500.0,
        0.10,
        2.8,
        30.0,
        inclination_rad=math.radians(28.0),
        raan_rad=math.radians(115.0),
        kind="satellite",
    ),
    fuel_budget_dv=1.6,
    time_limit_s=8000.0,
)

MIN_FUEL_EX = Scenario(
    id="minfuel-expert-02",
    name="Minimum-fuel intercept",
    tier="expert",
    spacecraft=_circular_state(7100.0, -0.3),
    target=_target_elliptical_tilted(
        10_800.0,
        0.08,
        2.4,
        20.0,
        inclination_rad=math.radians(24.0),
        raan_rad=math.radians(95.0),
    ),
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
    target=_target_elliptical_tilted(
        11_200.0,
        0.12,
        3.9,
        22.0,
        inclination_rad=math.radians(20.0),
        raan_rad=math.radians(130.0),
    ),
    fuel_budget_dv=1.45,
    time_limit_s=7000.0,
)

ORIGINAL_LEO = Scenario(
    id="leo-classic-01",
    name="Classic LEO [7000,0] → [0,10000]",
    tier="hard",
    spacecraft=SpacecraftState(position=(7000.0, 0.0, 0.0), velocity=(0.0, 7.546, 0.0)),
    target=TargetSpec(position=(0.0, 10000.0, 0.0), tolerance_km=50.0),
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
