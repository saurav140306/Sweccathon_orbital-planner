import type { Scenario, TargetSpec, TrajectoryPoint } from "./types";
import { elementsFromState, propagateElements, sampleOrbitPath } from "./kepler";

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
}

function targetElements(target: TargetSpec): ReturnType<typeof elementsFromState> | null {
  if (target.velocity) {
    return elementsFromState(target.position, target.velocity);
  }
  if (target.orbit_elements) {
    const o = target.orbit_elements;
    return {
      semi_major_axis_km: o.semi_major_axis_km,
      eccentricity: o.eccentricity,
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
    const nu0 =
      target.true_anomaly_at_t0_rad ?? Math.atan2(y, x) - argp;
    return {
      semi_major_axis_km: a,
      eccentricity: e,
      argument_of_periapsis_rad: argp,
      true_anomaly_at_t0_rad: nu0,
      mean_motion_rad_s: Math.sqrt(MU / (a * a * a)),
    };
  }
  return null;
}

export function getTargetMotion(target: TargetSpec): TargetMotion {
  const x = target.position[0];
  const y = target.position[1];
  const el = targetElements(target);
  const r = target.orbit_radius_km ?? Math.hypot(x, y);
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
    orbit_type: (target.orbit_type as "circular" | "elliptical") ?? (el && el.eccentricity > 1e-4 ? "elliptical" : "circular"),
    semi_major_axis_km: el?.semi_major_axis_km ?? r,
    eccentricity: el?.eccentricity ?? 0,
  };
}

export function targetOrbitPath(target: TargetSpec): [number, number][] {
  const el = targetElements(target);
  if (el) return sampleOrbitPath(el);
  const m = getTargetMotion(target);
  const pts: [number, number][] = [];
  for (let i = 0; i <= 90; i++) {
    const theta = m.initial_angle_rad + (2 * Math.PI * i) / 90;
    pts.push([m.orbit_radius_km * Math.cos(theta), m.orbit_radius_km * Math.sin(theta)]);
  }
  return pts;
}

export function targetPositionAt(target: TargetSpec, t_s: number): [number, number] {
  const el = targetElements(target);
  if (el) return propagateElements(el, t_s);
  const m = getTargetMotion(target);
  const theta = m.initial_angle_rad + m.angular_velocity_rad_s * t_s;
  return [m.orbit_radius_km * Math.cos(theta), m.orbit_radius_km * Math.sin(theta)];
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
): [number, number] {
  if (scoreTargetTraj?.length) {
    const nearest = scoreTargetTraj.reduce((best, p) =>
      Math.abs(p.t_s - t_s) < Math.abs(best.t_s - t_s) ? p : best,
    );
    return nearest.position;
  }
  return targetPositionAt(target, t_s);
}

export function chaserCoastPath(scenario: Scenario): [number, number][] {
  return sampleOrbitPath(
    elementsFromState(scenario.spacecraft.position, scenario.spacecraft.velocity),
  );
}
