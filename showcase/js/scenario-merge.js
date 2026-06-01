/** Merge authoritative 3D orbit params (from backend scenarios) into replay observations. */

import { propagateElements, toVec3 } from "./kepler3d.js";
import { targetElements } from "./orbital-motion.js";

export function mergeOrbitCatalog(scenario, entry) {
  if (!entry || !scenario) return scenario;

  if (entry.spacecraft) {
    scenario.spacecraft = {
      position: toVec3(entry.spacecraft.position),
      velocity: toVec3(entry.spacecraft.velocity),
    };
  }

  if (entry.target) {
    const t = entry.target;
    scenario.target = {
      ...scenario.target,
      kind: t.kind ?? scenario.target.kind,
      position: toVec3(t.position),
      velocity: t.velocity ? toVec3(t.velocity) : scenario.target.velocity,
      tolerance_km: t.tolerance_km ?? scenario.target.tolerance_km,
      semi_major_axis_km: t.semi_major_axis_km ?? scenario.target.semi_major_axis_km,
      eccentricity: t.eccentricity ?? scenario.target.eccentricity ?? 0,
      argument_of_periapsis_rad: t.argument_of_periapsis_rad ?? scenario.target.argument_of_periapsis_rad ?? 0,
      inclination_rad: t.inclination_rad ?? scenario.target.inclination_rad ?? 0,
      raan_rad: t.raan_rad ?? scenario.target.raan_rad ?? 0,
      true_anomaly_at_t0_rad: t.true_anomaly_at_t0_rad ?? scenario.target.true_anomaly_at_t0_rad,
      orbit_type: t.orbit_type ?? scenario.target.orbit_type,
      spin_rad_s: t.spin_rad_s ?? scenario.target.spin_rad_s,
    };
  }

  return scenario;
}

/** Replace flat target trajectory with 3D Kepler samples when catalog defines tilt. */
export function upliftTargetTrajectory(score, scenario) {
  const el = targetElements(scenario.target);
  if (!el || (el.inclination_rad ?? 0) < 1e-4) return score;

  const traj = score.target_trajectory ?? [];
  const maxT =
    traj.length > 0
      ? traj[traj.length - 1].t_s
      : scenario.time_limit_s ?? 7200;
  const step = Math.max(30, maxT / 80);
  const out = [];
  for (let t = 0; t <= maxT + 1e-6; t += step) {
    out.push({ t_s: t, position: propagateElements(el, t).pos });
  }
  if (traj.length && out[out.length - 1].t_s < traj[traj.length - 1].t_s - 1e-6) {
    const tLast = traj[traj.length - 1].t_s;
    out.push({ t_s: tLast, position: propagateElements(el, tLast).pos });
  }
  score.target_trajectory = out;
  return score;
}
