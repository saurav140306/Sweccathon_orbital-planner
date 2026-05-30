import type { Scenario, ScoreBreakdown, TargetSpec, TrajectoryPoint } from "./types";
import {
  type OrbitElements3D,
  type Vec3,
  elementsFromState,
  propagateElements,
  sampleOrbitPath,
  toVec3,
  vecMag,
} from "./kepler3d";

const MU = 398600;
const EARTH_SPIN_RAD_S = (2 * Math.PI) / 86164;

export interface TargetMotion {
  orbit_radius_km: number;
  initial_angle_rad: number;
  angular_velocity_rad_s: number;
  spin_rad_s: number;
  kind: "satellite" | "moon";
  revolution_period_s?: number | null;
  orbit_type: "circular" | "elliptical";
  semi_major_axis_km: number;
  eccentricity: number;
  inclination_rad: number;
  raan_rad: number;
}

function targetElements(target: TargetSpec): OrbitElements3D | null {
  if (target.velocity) {
    return elementsFromState(target.position, target.velocity);
  }
  if (target.orbit_elements) {
    const o = target.orbit_elements;
    return {
      semi_major_axis_km: o.semi_major_axis_km,
      eccentricity: o.eccentricity,
      inclination_rad: o.inclination_rad ?? 0,
      raan_rad: o.raan_rad ?? 0,
      argument_of_periapsis_rad: o.argument_of_periapsis_rad,
      true_anomaly_at_t0_rad: o.true_anomaly_at_t0_rad,
      mean_motion_rad_s: o.mean_motion_rad_s,
    };
  }
  if (target.semi_major_axis_km != null) {
    const a = target.semi_major_axis_km;
    const e = target.eccentricity ?? 0;
    const argp = target.argument_of_periapsis_rad ?? 0;
    const [x, y] = target.position;
    const nu0 = target.true_anomaly_at_t0_rad ?? Math.atan2(y, x) - argp;
    return {
      semi_major_axis_km: a,
      eccentricity: e,
      inclination_rad: target.inclination_rad ?? 0,
      raan_rad: target.raan_rad ?? 0,
      argument_of_periapsis_rad: argp,
      true_anomaly_at_t0_rad: nu0,
      mean_motion_rad_s: Math.sqrt(MU / (a * a * a)),
    };
  }
  return null;
}

export function getTargetMotion(target: TargetSpec): TargetMotion {
  const [x, y] = target.position;
  const el = targetElements(target);
  const r = target.orbit_radius_km ?? vecMag(toVec3(target.position));
  const omega =
    el?.mean_motion_rad_s ??
    target.angular_velocity_rad_s ??
    Math.sqrt(MU / (r * r * r));
  return {
    orbit_radius_km: r,
    initial_angle_rad: target.initial_angle_rad ?? Math.atan2(y, x),
    angular_velocity_rad_s: omega,
    spin_rad_s: target.spin_rad_s ?? 0.12,
    kind: target.kind ?? "satellite",
    revolution_period_s: target.revolution_period_s ?? (2 * Math.PI) / omega,
    orbit_type:
      (target.orbit_type as "circular" | "elliptical") ??
      (el && el.eccentricity > 1e-4 ? "elliptical" : "circular"),
    semi_major_axis_km: el?.semi_major_axis_km ?? r,
    eccentricity: el?.eccentricity ?? 0,
    inclination_rad: el?.inclination_rad ?? target.inclination_rad ?? 0,
    raan_rad: el?.raan_rad ?? target.raan_rad ?? 0,
  };
}

export function targetOrbitPath(target: TargetSpec): Vec3[] {
  const el = targetElements(target);
  if (el) return sampleOrbitPath(el);
  const m = getTargetMotion(target);
  const pts: Vec3[] = [];
  for (let i = 0; i <= 90; i++) {
    const theta = m.initial_angle_rad + (2 * Math.PI * i) / 90;
    pts.push([
      m.orbit_radius_km * Math.cos(theta),
      m.orbit_radius_km * Math.sin(theta),
      0,
    ]);
  }
  return pts;
}

export function targetPositionAt(target: TargetSpec, t_s: number): Vec3 {
  const el = targetElements(target);
  if (el) return propagateElements(el, t_s).pos;
  const m = getTargetMotion(target);
  const theta = m.initial_angle_rad + m.angular_velocity_rad_s * t_s;
  return [m.orbit_radius_km * Math.cos(theta), m.orbit_radius_km * Math.sin(theta), 0];
}

export function earthSpinAngle(t_s: number, earthSpinRadS?: number): number {
  return (earthSpinRadS ?? EARTH_SPIN_RAD_S) * t_s;
}

export function bodySpinAngle(target: TargetSpec, t_s: number): number {
  return getTargetMotion(target).spin_rad_s * t_s;
}

export function targetPointAtTime(
  scoreTargetTraj: TrajectoryPoint[] | undefined,
  target: TargetSpec,
  t_s: number,
): Vec3 {
  if (scoreTargetTraj?.length) {
    const nearest = scoreTargetTraj.reduce((best, p) =>
      Math.abs(p.t_s - t_s) < Math.abs(best.t_s - t_s) ? p : best,
    );
    return toVec3(nearest.position);
  }
  return targetPositionAt(target, t_s);
}

export function chaserCoastPath(scenario: Scenario): Vec3[] {
  return sampleOrbitPath(
    elementsFromState(scenario.spacecraft.position, scenario.spacecraft.velocity),
  );
}

export interface ClosestApproachState {
  chaser: Vec3;
  target: Vec3;
  miss_km: number;
  t_s: number;
}

/** Positions at closest approach from a scored simulation. */
export function closestApproachState(
  score: ScoreBreakdown | null | undefined,
  scenario: Scenario,
): ClosestApproachState | null {
  if (!score?.trajectory?.length || score.crashed || !Number.isFinite(score.miss_km)) {
    return null;
  }
  const caT = score.closest_approach_time_s;
  const chaserPt = score.trajectory.reduce((best, p) =>
    Math.abs(p.t_s - caT) < Math.abs(best.t_s - caT) ? p : best,
  );
  const target = targetPointAtTime(score.target_trajectory, scenario.target, caT);
  return {
    chaser: toVec3(chaserPt.position),
    target,
    miss_km: score.miss_km,
    t_s: caT,
  };
}

/** Instantaneous 3D separation at simulation time t (km). */
export function separationAt(
  score: ScoreBreakdown | null | undefined,
  scenario: Scenario,
  t_s: number,
): number | null {
  const traj = score?.trajectory;
  if (!traj?.length) return null;
  const chaserPt = traj.reduce((best, p) =>
    Math.abs(p.t_s - t_s) < Math.abs(best.t_s - t_s) ? p : best,
  );
  const tgt = targetPointAtTime(score?.target_trajectory, scenario.target, t_s);
  const c = toVec3(chaserPt.position);
  return vecMag([c[0] - tgt[0], c[1] - tgt[1], c[2] - tgt[2]]);
}
