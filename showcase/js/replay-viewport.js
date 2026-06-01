/**
 * 3D orbital viewport for Mesocosm replay (vanilla port of OrbitalViewport3D).
 */
import * as THREE from "https://unpkg.com/three@0.170.0/build/three.module.js";

const EARTH_R = 6371;
const MOON_R_KM = 1737;
const EARTH_SPIN_RAD_S = (2 * Math.PI) / 86164;
const MAX_ANIM_WALL_S = 10;

function simRateForWallDuration(simDurationS, wallDurationS = MAX_ANIM_WALL_S) {
  return Math.max(simDurationS, 0.001) / wallDurationS;
}

function toThree(pos, scale) {
  return new THREE.Vector3(pos[0] * scale, pos[2] * scale, -pos[1] * scale);
}

function vecMag(v) {
  return Math.hypot(v[0], v[1], v[2] ?? 0);
}

function parseTraj(val) {
  if (!val) return [];
  if (Array.isArray(val)) return val;
  if (typeof val === "string") {
    try {
      return JSON.parse(val);
    } catch {
      return [];
    }
  }
  return [];
}

function pointAtTraj(traj, t) {
  if (!traj.length) return [0, 0, 0];
  const pts = traj.map((p) => ({
    t_s: p.t_s,
    position: p.position ?? [p.x, p.y, 0],
  }));
  if (t <= pts[0].t_s) return pts[0].position;
  for (let i = 1; i < pts.length; i++) {
    if (pts[i].t_s >= t) {
      const a = pts[i - 1];
      const b = pts[i];
      const u = (t - a.t_s) / (b.t_s - a.t_s || 1);
      return [
        a.position[0] + u * (b.position[0] - a.position[0]),
        a.position[1] + u * (b.position[1] - a.position[1]),
        0,
      ];
    }
  }
  return pts[pts.length - 1].position;
}

export function parseInfo(info) {
  const out = {};
  for (const [k, v] of Object.entries(info || {})) {
    try {
      out[k] = JSON.parse(v);
    } catch {
      out[k] = v;
    }
  }
  return out;
}

export function turnToMission(turn) {
  const obs = turn?.observation || turn?.board_before || {};
  const info = parseInfo(turn?.info);
  const chaserRaw = parseTraj(info.chaser_traj_json);
  const targetRaw = parseTraj(info.target_traj_json);
  const burns = [];
  try {
    const bj = typeof info.burns_json === "string" ? JSON.parse(info.burns_json) : info.burns_json;
    if (Array.isArray(bj)) burns.push(...bj);
  } catch {
    /* ignore */
  }

  const scenario = {
    id: obs.scenario_id || info.scenario_id || "mission",
    name: obs.name || info.scenario_name || "Mission",
    tier: obs.tier || info.tier || "",
    time_limit_s: obs.time_limit_s ?? 7200,
    spacecraft: {
      position: obs.spacecraft?.position_km || [7000, 0],
      velocity: obs.spacecraft?.velocity_km_s || [0, 7.5],
    },
    target: {
      kind: obs.target?.kind || "satellite",
      position: obs.target?.position_km || [0, 10000],
      velocity: obs.target?.velocity_km_s,
      tolerance_km: obs.target?.tolerance_km ?? 50,
      semi_major_axis_km: obs.target?.semi_major_axis_km,
      eccentricity: obs.target?.eccentricity ?? 0,
      orbit_type: obs.target?.orbit_type || "circular",
      spin_rad_s: 0.12,
    },
  };

  const trajectory = chaserRaw.map((p) => ({ t_s: p.t_s, position: [p.x, p.y, 0] }));
  const target_trajectory = targetRaw.map((p) => ({ t_s: p.t_s, position: [p.x, p.y, 0] }));

  const score = {
    trajectory,
    target_trajectory,
    miss_km: parseFloat(info.miss_km),
    crashed: info.crashed === true || info.crashed === "True",
    closest_approach_time_s: parseFloat(info.closest_approach_time_s) || 0,
    earth_spin_rad_s: EARTH_SPIN_RAD_S,
  };

  return { scenario, score, burns };
}

function makeEarthTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
  grad.addColorStop(0, "#1e3a2f");
  grad.addColorStop(0.5, "#2a4538");
  grad.addColorStop(1, "#1a3028");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "rgba(93, 202, 165, 0.22)";
  ctx.beginPath();
  ctx.ellipse(620, 180, 140, 90, 0.3, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(280, 260, 110, 130, -0.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(232, 193, 112, 0.55)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(canvas.width / 2, 0);
  ctx.lineTo(canvas.width / 2, canvas.height);
  ctx.stroke();
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeEarthGroup(scale) {
  const group = new THREE.Group();
  const r = EARTH_R * scale;
  group.add(
    new THREE.Mesh(
      new THREE.SphereGeometry(r, 64, 48),
      new THREE.MeshPhongMaterial({
        map: makeEarthTexture(),
        emissive: 0x0a1812,
        shininess: 18,
      }),
    ),
  );
  const markerMat = new THREE.MeshBasicMaterial({ color: 0xe8c170 });
  const marker = new THREE.Mesh(new THREE.SphereGeometry(r * 0.05, 10, 10), markerMat);
  marker.position.set(r * 0.98, 0, 0);
  group.add(marker);
  return group;
}

function makeTargetBody(kind, scale) {
  const group = new THREE.Group();
  if (kind === "moon") {
    const r = Math.min(Math.max(MOON_R_KM * scale, 0.025), 0.18);
    group.add(
      new THREE.Mesh(
        new THREE.SphereGeometry(r, 32, 24),
        new THREE.MeshPhongMaterial({ color: 0xc8c8be, emissive: 0x333330, shininess: 8 }),
      ),
    );
  } else {
    const r = 0.022;
    group.add(
      new THREE.Mesh(
        new THREE.BoxGeometry(r * 1.6, r * 1.2, r * 1.2),
        new THREE.MeshPhongMaterial({ color: 0xc9d4ce, emissive: 0x1a3028 }),
      ),
    );
    const panelMat = new THREE.MeshPhongMaterial({ color: 0x3a5a48 });
    for (const side of [-1, 1]) {
      const panel = new THREE.Mesh(new THREE.BoxGeometry(r * 0.15, r * 2.2, r * 0.9), panelMat);
      panel.position.x = side * r * 1.1;
      group.add(panel);
    }
  }
  return group;
}

function makeChaserBody() {
  const group = new THREE.Group();
  const r = 0.028;
  group.add(
    new THREE.Mesh(
      new THREE.OctahedronGeometry(r, 0),
      new THREE.MeshPhongMaterial({ color: 0x5dcaa5, emissive: 0x3a9070, shininess: 80 }),
    ),
  );
  group.add(
    new THREE.Mesh(
      new THREE.RingGeometry(r * 1.4, r * 1.8, 24),
      new THREE.MeshBasicMaterial({
        color: 0xf5f0e6,
        transparent: true,
        opacity: 0.6,
        side: THREE.DoubleSide,
      }),
    ),
  );
  return group;
}

function sampleCircularOrbit(radiusKm, samples = 91, angle0 = 0) {
  const pts = [];
  for (let i = 0; i < samples; i++) {
    const theta = angle0 + (2 * Math.PI * i) / samples;
    pts.push([radiusKm * Math.cos(theta), radiusKm * Math.sin(theta), 0]);
  }
  return pts;
}

/** Keplerian ring for guide orbits (closed). Open transfer paths must not use closed curves. */
function targetOrbitRing(scenario) {
  const tg = scenario.target;
  const a = tg.semi_major_axis_km || Math.hypot(tg.position[0], tg.position[1]) || 10000;
  const e = tg.eccentricity ?? 0;
  if (e < 1e-4) {
    return sampleCircularOrbit(a, 91, Math.atan2(tg.position[1], tg.position[0]));
  }
  const pts = [];
  for (let i = 0; i <= 90; i++) {
    const nu = (2 * Math.PI * i) / 90;
    const r = (a * (1 - e * e)) / (1 + e * Math.cos(nu));
    pts.push([r * Math.cos(nu), r * Math.sin(nu), 0]);
  }
  return pts;
}

function chaserCoastRing(scenario) {
  const [x, y] = scenario.spacecraft.position;
  const r = Math.max(Math.hypot(x, y), EARTH_R + 100);
  return sampleCircularOrbit(r, 91, Math.atan2(y, x));
}

function makeOrbitPath(points, color, scale, tubeRadius, closed = false) {
  const pts = points.map((p) => toThree(p, scale));
  if (pts.length < 2) return new THREE.Group();
  if (pts.length < 3 || !closed) {
    return new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85 }),
    );
  }
  try {
    const curve = new THREE.CatmullRomCurve3(pts, true);
    const geo = new THREE.TubeGeometry(curve, Math.max(pts.length * 2, 64), tubeRadius, 8, true);
    return new THREE.Mesh(
      geo,
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.88 }),
    );
  } catch {
    const loop = [...pts, pts[0]];
    return new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(loop),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85 }),
    );
  }
}

function frameCamera(camera, points, padding = 1.5) {
  const box = new THREE.Box3();
  for (const p of points) box.expandByPoint(p);
  const center = new THREE.Vector3();
  box.getCenter(center);
  const size = new THREE.Vector3();
  box.getSize(size);
  const radius = Math.max(size.x, size.y, size.z, 0.12) * 0.5;
  const fovRad = (camera.fov * Math.PI) / 180;
  const dist = Math.max((radius / Math.tan(fovRad / 2)) * padding, 0.7);
  const az = 0.75;
  const el = 0.62;
  camera.position.set(
    center.x + dist * Math.cos(el) * Math.cos(az),
    center.y + dist * Math.sin(el),
    center.z + dist * Math.cos(el) * Math.sin(az),
  );
  camera.lookAt(center);
}

function closestApproach(score) {
  if (!score || score.crashed || !Number.isFinite(score.miss_km)) return null;
  const t = score.closest_approach_time_s;
  return {
    t_s: t,
    miss_km: score.miss_km,
    chaser: pointAtTraj(score.trajectory, t),
    target: pointAtTraj(score.target_trajectory, t),
  };
}

export {
  MAX_ANIM_WALL_S,
  EARTH_R,
  chaserCoastRing,
  targetOrbitRing,
  closestApproach,
  pointAtTraj,
};

export class ReplayViewport3D {
  constructor(mountEl) {
    this.mount = mountEl;
    this.scenario = null;
    this.score = null;
    this.scrubT = 0;
    this.playing = false;
    this.playT = 0;
    this.idleT = 0;
    this.onScrub = () => {};
    this.onPlayingChange = () => {};
    this.disposed = false;
    this.animId = 0;
    this.lastWall = 0;
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.earthGroup = null;
    this.targetBody = null;
    this.chaserBody = null;
    this.targetTrailLine = null;
    this.trajLine = null;
    this.linkLine = null;
    this.missLine = null;
    this.scale = 1 / 14000;
    this.glError = null;
    this.speedFactor = 1;
  }

  setMission(turn) {
    const { scenario, score } = turnToMission(turn);
    this.scenario = scenario;
    this.score = score;
    this.scrubT = 0;
    this.playT = 0;
    this.playing = false;
    this._rebuildScene();
  }

  setScrub(t) {
    this.scrubT = t;
    this.playT = t;
    if (this.score) this._updateScene(t);
  }

  setPlaying(p) {
    this.playing = p;
    if (p) this.playT = this.scrubT;
  }

  get maxT() {
    const traj = this.score?.trajectory;
    return traj?.length ? traj[traj.length - 1].t_s : this.scenario?.time_limit_s ?? 1;
  }

  _rebuildScene() {
    if (this.animId) cancelAnimationFrame(this.animId);
    if (this.renderer) {
      this.renderer.dispose();
      this.mount.replaceChildren();
    }
    this.disposed = false;
    this.glError = null;

    if (!this.scenario || !this.score?.trajectory?.length) return;

    const trajPts = this.score.trajectory.map((p) => p.position);
    const tgtPts = this.score.target_trajectory.map((p) => p.position);
    const pathMaxR = Math.max(
      ...trajPts.map((p) => vecMag(p)),
      ...tgtPts.map((p) => vecMag(p)),
      12000,
    );
    const maxR = Math.max(14000, pathMaxR * 1.12);
    this.scale = 1.0 / maxR;
    const scale = this.scale;
    const tubeR = 0.0045;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch (err) {
      this.glError = err instanceof Error ? err.message : "WebGL unavailable";
      this.mount.textContent = this.glError;
      return;
    }
    this.renderer = renderer;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x16241c);
    this.scene = scene;

    const camera = new THREE.PerspectiveCamera(42, 1, 0.001, 100);
    this.camera = camera;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    this.mount.replaceChildren(renderer.domElement);

    const resize = () => {
      if (this.disposed) return;
      const rect = this.mount.getBoundingClientRect();
      const w = Math.max(Math.floor(rect.width), 320);
      const h = Math.max(Math.floor(rect.height), 260);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    };
    this._resize = resize;
    this._ro = new ResizeObserver(resize);
    this._ro.observe(this.mount);
    resize();

    scene.add(new THREE.AmbientLight(0x8fb89b, 0.6));
    const sun = new THREE.DirectionalLight(0xf5f0e6, 1.0);
    sun.position.set(2, 2, 1);
    scene.add(sun);

    const grid = new THREE.GridHelper(2.2, 24, 0x3a5a48, 0x243d30);
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);

    this.earthGroup = makeEarthGroup(scale);
    scene.add(this.earthGroup);

    const kind = this.scenario.target.kind || "satellite";
    const targetColor = kind === "moon" ? 0xc8c8be : 0x5dcaa5;
    scene.add(makeOrbitPath(targetOrbitRing(this.scenario), targetColor, scale, tubeR * 0.85, true));
    scene.add(makeOrbitPath(chaserCoastRing(this.scenario), 0xf5f0e6, scale, tubeR * 0.55, true));

    this.targetTrailLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: targetColor, transparent: true, opacity: 0.95 }),
    );
    scene.add(this.targetTrailLine);

    this.targetBody = makeTargetBody(kind, scale);
    scene.add(this.targetBody);

    this.chaserBody = makeChaserBody();
    scene.add(this.chaserBody);

    this.linkLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0xf5f0e6, transparent: true, opacity: 0.35 }),
    );
    scene.add(this.linkLine);

    this.missLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0xe8c170, transparent: true, opacity: 0.95 }),
    );
    this.missLine.visible = false;
    scene.add(this.missLine);

    this.trajLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0x5dcaa5, transparent: true, opacity: 0.95 }),
    );
    scene.add(this.trajLine);

    this._staticPts = [
      new THREE.Vector3(0, 0, 0),
      ...trajPts.map((p) => toThree(p, scale)),
      ...tgtPts.map((p) => toThree(p, scale)),
    ];

    this.lastWall = performance.now();
    const tick = (now) => {
      if (this.disposed) return;
      const dt = Math.min(0.05, (now - this.lastWall) / 1000);
      this.lastWall = now;

      const maxT = this.maxT;
      let simT = this.scrubT;

      if (this.playing && this.score?.trajectory?.length) {
        const playRate = simRateForWallDuration(maxT) * this.speedFactor;
        this.playT = Math.min(maxT, this.playT + dt * playRate);
        simT = this.playT;
        this.scrubT = simT;
        this.onScrub(simT);
        if (this.playT >= maxT - 1e-6) {
          this.playing = false;
          this.onPlayingChange(false);
        }
      }

      this._updateScene(simT);
      renderer.render(scene, camera);
      this.animId = requestAnimationFrame(tick);
    };
    this.animId = requestAnimationFrame(tick);
  }

  _updateScene(simT) {
    if (!this.scenario || !this.score) return;
    const scale = this.scale;
    const earthSpinRate = this.score.earth_spin_rad_s ?? EARTH_SPIN_RAD_S;

    this.earthGroup.rotation.y = -simT * earthSpinRate;

    const tgt = pointAtTraj(this.score.target_trajectory, simT);
    const tgtThree = toThree(tgt, scale);
    this.targetBody.position.copy(tgtThree);
    this.targetBody.rotation.y = -simT * (this.scenario.target.spin_rad_s ?? 0.12);

    const trailSteps = 40;
    const trailPts = [];
    const step = simT / trailSteps;
    for (let i = 0; i <= trailSteps; i++) {
      trailPts.push(toThree(pointAtTraj(this.score.target_trajectory, i * step), scale));
    }
    this.targetTrailLine.geometry.dispose();
    this.targetTrailLine.geometry =
      trailPts.length > 1
        ? new THREE.BufferGeometry().setFromPoints(trailPts)
        : new THREE.BufferGeometry();

    const visible = this.score.trajectory.filter((p) => p.t_s <= simT + 1e-6);
    let chaserThree;
    if (visible.length > 0) {
      const pts = visible.map((p) => toThree(p.position, scale));
      this.trajLine.geometry.dispose();
      this.trajLine.geometry = new THREE.BufferGeometry().setFromPoints(pts);
      chaserThree = pts[pts.length - 1];
    } else {
      const p0 = this.scenario.spacecraft.position;
      chaserThree = toThree([p0[0], p0[1], 0], scale);
      this.trajLine.geometry.dispose();
      this.trajLine.geometry = new THREE.BufferGeometry();
    }
    this.chaserBody.position.copy(chaserThree);
    this.chaserBody.rotation.y = simT * 0.04;

    this.linkLine.geometry.dispose();
    this.linkLine.geometry = new THREE.BufferGeometry().setFromPoints([chaserThree, tgtThree]);

    const ca = closestApproach(this.score);
    if (ca) {
      const caC = toThree(ca.chaser, scale);
      const caT = toThree(ca.target, scale);
      this.missLine.geometry.dispose();
      this.missLine.geometry = new THREE.BufferGeometry().setFromPoints([caC, caT]);
      this.missLine.visible = true;
    } else {
      this.missLine.visible = false;
    }

    frameCamera(this.camera, [...this._staticPts, chaserThree, tgtThree]);
  }

  destroy() {
    this.disposed = true;
    if (this.animId) cancelAnimationFrame(this.animId);
    this._ro?.disconnect();
    this.renderer?.dispose();
    this.mount.replaceChildren();
  }
}
