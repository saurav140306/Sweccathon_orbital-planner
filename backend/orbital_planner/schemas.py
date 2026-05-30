"""Data contracts for scenarios, plans, and scoring."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from orbital_planner.vec3 import to_vec3


class OrbitElementsOut(BaseModel):
    """Serialized Kepler elements for API + frontend calculations."""

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
    inclination_rad: float = 0.0
    raan_rad: float = 0.0


class SpacecraftState(BaseModel):
    position: tuple[float, float, float] = Field(description="km, inertial ECI")
    velocity: tuple[float, float, float] = Field(description="km/s")

    @field_validator("position", "velocity", mode="before")
    @classmethod
    def coerce_vec3(cls, value: object) -> tuple[float, float, float]:
        return to_vec3(value)


class TargetSpec(BaseModel):
    """Target on a Keplerian orbit (2D equatorial or 3D inclined)."""

    position: tuple[float, float, float] = Field(description="Inertial position at t=0 (km)")
    tolerance_km: float = Field(gt=0)
    kind: Literal["satellite", "moon"] = "satellite"
    velocity: tuple[float, float, float] | None = Field(
        default=None,
        description="Optional; with position defines osculating ellipse at t=0",
    )
    orbit_type: Literal["circular", "elliptical"] = "elliptical"
    semi_major_axis_km: float | None = None
    eccentricity: float = Field(default=0.0, ge=0.0, lt=1.0)
    argument_of_periapsis_rad: float = 0.0
    inclination_rad: float = Field(default=0.0, ge=0.0, le=math.pi)
    raan_rad: float = 0.0
    true_anomaly_at_t0_rad: float | None = None
    orbit_radius_km: float | None = None
    initial_angle_rad: float | None = None
    angular_velocity_rad_s: float | None = None
    spin_rad_s: float = 0.12
    revolution_period_s: float | None = None
    orbit_elements: OrbitElementsOut | None = None
    gravitational_parameter_km3_s2: float | None = Field(
        default=None,
        description="GM for third-body gravity (auto-set for moon kind)",
    )
    body_radius_km: float | None = Field(
        default=None,
        description="Physical radius for moon targets (km)",
    )

    @field_validator("position", "velocity", mode="before")
    @classmethod
    def coerce_position(cls, value: object) -> tuple[float, float, float] | None:
        if value is None:
            return None
        return to_vec3(value)


class Scenario(BaseModel):
    id: str
    name: str
    tier: Literal["easy", "medium", "hard", "expert"]
    spacecraft: SpacecraftState
    target: TargetSpec
    fuel_budget_dv: float = Field(gt=0)
    time_limit_s: float = Field(gt=0)


class Burn(BaseModel):
    time_s: float = Field(ge=0)
    dv: tuple[float, float, float]

    @field_validator("dv", mode="before")
    @classmethod
    def coerce_dv(cls, value: object) -> tuple[float, float, float]:
        return to_vec3(value)


class MissionPlan(BaseModel):
    burns: list[Burn]
    reasoning: str = ""


class TrajectoryPoint(BaseModel):
    t_s: float
    position: tuple[float, float, float]
    velocity: tuple[float, float, float]

    @field_validator("position", "velocity", mode="before")
    @classmethod
    def coerce_traj_vec(cls, value: object) -> tuple[float, float, float]:
        return to_vec3(value)


class ScoreBreakdown(BaseModel):
    miss_km: float
    fuel_used: float
    optimal_dv: float
    fuel_ratio: float
    hit_score: float
    fuel_penalty: float
    score: float
    crashed: bool
    closest_approach_time_s: float
    plane_offset_km: float = 0.0
    trajectory: list[TrajectoryPoint]
    target_trajectory: list[TrajectoryPoint] = Field(default_factory=list)
    earth_spin_rad_s: float = Field(default=7.292e-5)


class CalculationSnapshot(BaseModel):
    """Live orbital mechanics values at simulation time t."""

    t_s: float
    mu_km3_s2: float
    earth_radius_km: float
    earth_spin_deg: float
    target: dict
    chaser: dict
    score: dict | None = None
    gravity: dict | None = None
