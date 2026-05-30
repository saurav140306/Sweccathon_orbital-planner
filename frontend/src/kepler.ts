/** 2D Kepler propagation (matches backend kepler2d.py). */

const MU = 398600;

export interface OrbitElements {
  semi_major_axis_km: number;
  eccentricity: number;
  argument_of_periapsis_rad: number;
  true_anomaly_at_t0_rad: number;
  mean_motion_rad_s: number;
}

function meanMotion(a: number): number {
  return Math.sqrt(MU / (Math.max(a, 1) ** 3));
}

function solveKepler(M: number, e: number): number {
  const m = M % (2 * Math.PI);
  if (e < 1e-10) return m;
  let E = e < 0.8 ? m : Math.PI;
  for (let i = 0; i < 50; i++) {
    const d = (E - e * Math.sin(E) - m) / (1 - e * Math.cos(E));
    E -= d;
    if (Math.abs(d) < 1e-11) break;
  }
  return E;
}

function trueAnomalyFromMean(M: number, e: number): number {
  const E = solveKepler(M, e);
  const sinE = Math.sin(E);
  const cosE = Math.cos(E);
  const denom = 1 - e * cosE;
  return Math.atan2((Math.sqrt(1 - e * e) * sinE) / denom, (cosE - e) / denom);
}

function trueAnomalyToMean(nu: number, e: number): number {
  if (e < 1e-10) return nu;
  const tanHalf = Math.tan(nu / 2);
  const E =
    2 *
    Math.atan2(
      Math.sqrt(1 + e) * tanHalf,
      Math.sqrt(1 - e),
    );
  return E - e * Math.sin(E);
}

function stateFromElements(el: OrbitElements, nu: number): [number, number] {
  const { semi_major_axis_km: a, eccentricity: e, argument_of_periapsis_rad: argp } = el;
  const p = a * (1 - e * e);
  const r = p / (1 + e * Math.cos(nu));
  const ang = argp + nu;
  return [r * Math.cos(ang), r * Math.sin(ang)];
}

export function elementsFromState(
  position: [number, number],
  velocity: [number, number],
): OrbitElements {
  const [rx, ry] = position;
  const [vx, vy] = velocity;
  const r = Math.hypot(rx, ry);
  const v2 = vx * vx + vy * vy;
  const h = rx * vy - ry * vx;
  const eps = 0.5 * v2 - MU / Math.max(r, 1);
  const a = -MU / (2 * eps);
  const e = Math.sqrt(Math.max(0, 1 - (h * h) / (a * MU)));
  const ex = (vy * h) / MU - rx / r;
  const ey = (-vx * h) / MU - ry / r;
  const argp = Math.atan2(ey, ex);
  const nu0 =
    e < 1e-9
      ? Math.atan2(ry, rx) - argp
      : Math.atan2(ex * ry - ey * rx, ex * rx + ey * ry);
  return {
    semi_major_axis_km: a,
    eccentricity: e,
    argument_of_periapsis_rad: argp,
    true_anomaly_at_t0_rad: nu0,
    mean_motion_rad_s: meanMotion(a),
  };
}

export function propagateElements(
  el: OrbitElements,
  t_s: number,
): [number, number] {
  const m0 = trueAnomalyToMean(el.true_anomaly_at_t0_rad, el.eccentricity);
  const m = m0 + el.mean_motion_rad_s * t_s;
  const nu = trueAnomalyFromMean(m, el.eccentricity);
  return stateFromElements(el, nu);
}

export function sampleOrbitPath(
  el: OrbitElements,
  n = 90,
): [number, number][] {
  const pts: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const nu = -Math.PI + (2 * Math.PI * i) / n;
    pts.push(stateFromElements(el, nu));
  }
  return pts;
}
