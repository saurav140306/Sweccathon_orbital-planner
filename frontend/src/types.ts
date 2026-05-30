export type Tier = "easy" | "medium" | "hard" | "expert";
export type TargetKind = "satellite" | "moon";
export type OrbitType = "circular" | "elliptical";

export interface OrbitElementsOut {
  semi_major_axis_km: number;
  eccentricity: number;
  argument_of_periapsis_rad: number;
  true_anomaly_at_t0_rad: number;
  mean_motion_rad_s: number;
  period_s: number;
  periapsis_km: number;
  apoapsis_km: number;
  specific_angular_momentum: number;
  specific_energy_km2_s2: number;
}

export interface TargetSpec {
  position: [number, number];
  velocity?: [number, number] | null;
  tolerance_km: number;
  kind?: TargetKind;
  orbit_type?: OrbitType;
  semi_major_axis_km?: number;
  eccentricity?: number;
  argument_of_periapsis_rad?: number;
  true_anomaly_at_t0_rad?: number;
  orbit_radius_km?: number;
  initial_angle_rad?: number;
  angular_velocity_rad_s?: number;
  spin_rad_s?: number;
  revolution_period_s?: number | null;
  orbit_elements?: OrbitElementsOut | null;
  gravitational_parameter_km3_s2?: number | null;
  body_radius_km?: number | null;
}

export interface Scenario {
  id: string;
  name: string;
  tier: Tier;
  spacecraft: { position: [number, number]; velocity: [number, number] };
  target: TargetSpec;
  fuel_budget_dv: number;
  time_limit_s: number;
}

export interface Burn {
  time_s: number;
  dv: [number, number];
}

export interface MissionPlan {
  burns: Burn[];
  reasoning: string;
}

export interface TrajectoryPoint {
  t_s: number;
  position: [number, number];
  velocity: [number, number];
}

export interface ScoreBreakdown {
  miss_km: number;
  fuel_used: number;
  optimal_dv: number;
  fuel_ratio: number;
  hit_score: number;
  fuel_penalty: number;
  score: number;
  crashed: boolean;
  closest_approach_time_s: number;
  trajectory: TrajectoryPoint[];
  target_trajectory?: TrajectoryPoint[];
  earth_spin_rad_s?: number;
}

export interface RunResult {
  scenario_id: string;
  plan: MissionPlan;
  score: ScoreBreakdown;
  raw_response?: string;
}

export interface BenchmarkRow {
  scenario_id: string;
  tier: Tier;
  name: string;
  score: number;
  miss_km: number;
  fuel_used: number;
}

export interface CalculationSnapshot {
  t_s: number;
  mu_km3_s2: number;
  earth_radius_km: number;
  earth_spin_deg: number;
  target: Record<string, number | string | number[]>;
  chaser: Record<string, number | string | number[]>;
  score?: Record<string, number | string | boolean> | null;
  gravity?: Record<string, number | string> | null;
  target_orbit_path?: { x: number; y: number }[];
  chaser_orbit_path?: { x: number; y: number }[];
}
