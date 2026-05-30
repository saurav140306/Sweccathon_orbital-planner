/** 3D Kepler propagation (matches backend kepler3d.py). */

const MU = 398600;

export interface OrbitElements3D {
  semi_major_axis_km: number;
  eccentricity: number;
  inclination_rad: number;
  raan_rad: number;
  argument_of_periapsis_rad: number;
  true_anomaly_at_t0_rad: number;
  mean_motion_rad_s: number;
}

export type Vec3 = [number, number, number];

export function toVec3(v: [number, number] | [number, number, number]): Vec3 {
  return v.length === 3 ? v : [v[0], v[1], 0];
}

function meanMotion(a: number): number {
  return Math.sqrt(MU / Math.max(a, 1) ** 3);
}

function rotZ(a: number): number[][] {
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [
    [c, -s, 0],
    [s, c, 0],
    [0, 0, 1],
  ];
}

function rotX(a: number): number[][] {
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [
    [1, 0, 0],
    [0, c, -s],
    [0, s, c],
  ];
}

function matMul(a: number[][], b: number[][]): number[][] {
  const out = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      out[i][j] = a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j];
    }
  }
  return out;
}

function matVec(m: number[][], v: Vec3): Vec3 {
  return [
    m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
    m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
    m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
  ];
}

function perifocalToInertial(v: Vec3, raan: number, inc: number, argp: number): Vec3 {
  const r = matMul(rotZ(-raan), matMul(rotX(-inc), rotZ(-argp)));
  return matVec(r, v);
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
  const E = 2 * Math.atan2(Math.sqrt(1 + e) * tanHalf, Math.sqrt(1 - e));
  return E - e * Math.sin(E);
}

function stateFromElements(el: OrbitElements3D, nu: number): { pos: Vec3; vel: Vec3 } {
  const { semi_major_axis_km: a, eccentricity: e, argument_of_periapsis_rad: argp, inclination_rad: inc, raan_rad: raan } = el;
  const p = a * (1 - e * e);
  const r = p / (1 + e * Math.cos(nu));
  const sqrtMuP = Math.sqrt(MU / p);
  const vr = sqrtMuP * e * Math.sin(nu);
  const vtheta = sqrtMuP * (1 + e * Math.cos(nu));
  const posP: Vec3 = [r * Math.cos(nu), r * Math.sin(nu), 0];
  const velP: Vec3 = [
    vr * Math.cos(nu) - vtheta * Math.sin(nu),
    vr * Math.sin(nu) + vtheta * Math.cos(nu),
    0,
  ];
  return {
    pos: perifocalToInertial(posP, raan, inc, argp),
    vel: perifocalToInertial(velP, raan, inc, argp),
  };
}

export function elementsFromState(
  position: [number, number] | [number, number, number],
  velocity: [number, number] | [number, number, number],
): OrbitElements3D {
  const [rx, ry, rz] = toVec3(position);
  const [vx, vy, vz] = toVec3(velocity);
  const r = Math.sqrt(rx * rx + ry * ry + rz * rz);
  const v2 = vx * vx + vy * vy + vz * vz;
  const hx = ry * vz - rz * vy;
  const hy = rz * vx - rx * vz;
  const hz = rx * vy - ry * vx;
  const h = Math.sqrt(hx * hx + hy * hy + hz * hz);
  const eps = 0.5 * v2 - MU / Math.max(r, 1);
  const a = -MU / (2 * eps);
  const e = Math.sqrt(Math.max(0, 1 - (h * h) / (a * MU)));
  const inc = Math.acos(Math.max(-1, Math.min(1, hz / Math.max(h, 1e-12))));
  const nx = -hy;
  const ny = hx;
  const nMag = Math.hypot(nx, ny);
  const raan = nMag < 1e-12 ? 0 : Math.atan2(ny, nx);
  let argp = 0;
  if (nMag < 1e-12) {
    argp = inc < 1e-6 ? Math.atan2(ry, rx) : 0;
  } else {
    argp = Math.atan2(
      hz * (nx * rx + ny * ry) - h * (nx * vx + ny * vy),
      h * (nx * vy - ny * vx) - hz * (nx * rx + ny * ry),
    );
  }
  const px = (vy * hz - vz * hy) / MU - rx / r;
  const py = (vz * hx - vx * hz) / MU - ry / r;
  const pz = (vx * hy - vy * hx) / MU - rz / r;
  const nu =
    e > 1e-9
      ? Math.atan2(py * rz - pz * ry, px * rx + py * ry + pz * rz)
      : Math.atan2(ry, rx) - argp;
  return {
    semi_major_axis_km: a,
    eccentricity: e,
    inclination_rad: inc,
    raan_rad: raan,
    argument_of_periapsis_rad: argp,
    true_anomaly_at_t0_rad: nu,
    mean_motion_rad_s: meanMotion(a),
  };
}

export function propagateElements(
  el: OrbitElements3D,
  t_s: number,
): { pos: Vec3; vel: Vec3 } {
  const m0 = trueAnomalyToMean(el.true_anomaly_at_t0_rad, el.eccentricity);
  const m = m0 + el.mean_motion_rad_s * t_s;
  const nu = trueAnomalyFromMean(m, el.eccentricity);
  return stateFromElements(el, nu);
}

export function sampleOrbitPath(el: OrbitElements3D, n = 90): Vec3[] {
  const pts: Vec3[] = [];
  for (let i = 0; i <= n; i++) {
    const nu = -Math.PI + (2 * Math.PI * i) / n;
    pts.push(stateFromElements(el, nu).pos);
  }
  return pts;
}

/** Map ECI (x,y,z) to Three.js Y-up scene coords. */
export function eciToScene([x, y, z]: Vec3): Vec3 {
  return [x, z, -y];
}

export function vecMag(v: Vec3): number {
  return Math.hypot(v[0], v[1], v[2]);
}
