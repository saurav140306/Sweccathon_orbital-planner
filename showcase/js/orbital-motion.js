import {
  elementsFromElements2d,
  elementsFromState,
  propagateElements,
  sampleOrbitPath,
  toVec3,
  vecMag,
} from "./kepler3d.js";

const MU = 398600;

function targetElements(target) {
  if (target.orbit_elements) {
    const o = target.orbit_elements;
    return {
      semi_major_axis_km: o.semi_major_axis_km,
      eccentricity: o.eccentricity,
      inclination_rad: o.inclination_rad ?? target.inclination_rad ?? 0,
      raan_rad: o.raan_rad ?? target.raan_rad ?? 0,
      argument_of_periapsis_rad: o.argument_of_periapsis_rad,
      true_anomaly_at_t0_rad: o.true_anomaly_at_t0_rad,
      mean_motion_rad_s: o.mean_motion_rad_s,
    };
  }
  if (target.velocity) {
    return elementsFromState(target.position, target.velocity);
  }
  if (target.semi_major_axis_km != null) {
    const a = target.semi_major_axis_km;
    const e = target.eccentricity ?? 0;
    const argp = target.argument_of_periapsis_rad ?? 0;
    const [x, y] = toVec3(target.position);
    const nu0 = target.true_anomaly_at_t0_rad ?? Math.atan2(y, x) - argp;
    return elementsFromElements2d(a, e, argp, nu0, {
      inclination_rad: target.inclination_rad ?? 0,
      raan_rad: target.raan_rad ?? 0,
    });
  }
  return null;
}

export function targetOrbitPath(target) {
  const el = targetElements(target);
  if (el) return sampleOrbitPath(el);
  const [x, y] = toVec3(target.position);
  const r = target.orbit_radius_km ?? Math.hypot(x, y) ?? 10000;
  const pts = [];
  for (let i = 0; i <= 90; i++) {
    const theta = (2 * Math.PI * i) / 90;
    pts.push([r * Math.cos(theta), r * Math.sin(theta), 0]);
  }
  return pts;
}

export function chaserCoastPath(scenario) {
  const el = elementsFromState(scenario.spacecraft.position, scenario.spacecraft.velocity);
  return sampleOrbitPath(el);
}

export function targetPositionAt(target, t_s) {
  const el = targetElements(target);
  if (el) return propagateElements(el, t_s).pos;
  const [x, y] = toVec3(target.position);
  const r = target.orbit_radius_km ?? Math.hypot(x, y);
  const omega = target.angular_velocity_rad_s ?? Math.sqrt(MU / (r * r * r));
  const theta = (target.initial_angle_rad ?? Math.atan2(y, x)) + omega * t_s;
  return [r * Math.cos(theta), r * Math.sin(theta), 0];
}

export function targetPointAtTime(scoreTargetTraj, target, t_s) {
  if (scoreTargetTraj?.length) {
    const nearest = scoreTargetTraj.reduce((best, p) =>
      Math.abs(p.t_s - t_s) < Math.abs(best.t_s - t_s) ? p : best,
    );
    return toVec3(nearest.position);
  }
  return targetPositionAt(target, t_s);
}

export function getTargetMotion(target) {
  const el = targetElements(target);
  const [x, y] = toVec3(target.position);
  const r = target.orbit_radius_km ?? vecMag(toVec3(target.position));
  const omega = el?.mean_motion_rad_s ?? target.angular_velocity_rad_s ?? Math.sqrt(MU / (r * r * r));
  return {
    orbit_radius_km: r,
    kind: target.kind ?? "satellite",
    eccentricity: el?.eccentricity ?? target.eccentricity ?? 0,
    inclination_rad: el?.inclination_rad ?? target.inclination_rad ?? 0,
    orbit_type: target.orbit_type || "circular",
  };
}
