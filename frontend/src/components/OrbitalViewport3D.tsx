import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import type { Burn, Scenario, ScoreBreakdown } from "../types";
import {
  bodySpinAngle,
  chaserCoastPath,
  closestApproachState,
  earthSpinAngle,
  getTargetMotion,
  separationAt,
  targetOrbitPath,
  targetPointAtTime,
} from "../orbitalMotion";
import { eciToScene, elementsFromState, propagateElements, type Vec3, vecMag } from "../kepler3d";
import { OrbitalBirdEye } from "./OrbitalBirdEye";
import styles from "./OrbitalCanvas.module.css";

const EARTH_R = 6371;
const MOON_R_KM = 1737;
const MAX_ANIM_WALL_S = 10;

function simRateForWallDuration(simDurationS: number, wallDurationS = MAX_ANIM_WALL_S): number {
  return Math.max(simDurationS, 0.001) / wallDurationS;
}

interface Props {
  scenario: Scenario | null;
  score: ScoreBreakdown | null;
  burns: Burn[];
  scrubT: number;
  playing: boolean;
  onScrub: (t: number) => void;
  onPlayingChange: (p: boolean) => void;
}

function toThree(v: Vec3, scale: number): THREE.Vector3 {
  const [x, y, z] = eciToScene(v);
  return new THREE.Vector3(x * scale, y * scale, z * scale);
}

function makeEarthTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 512;
  const ctx = canvas.getContext("2d")!;

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

  ctx.strokeStyle = "rgba(245, 240, 230, 0.12)";
  ctx.lineWidth = 1;
  for (let i = 1; i < 8; i++) {
    const y = (canvas.height * i) / 8;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeEarthGroup(scale: number): THREE.Group {
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

  const pin = new THREE.Mesh(new THREE.ConeGeometry(r * 0.045, r * 0.15, 8), markerMat);
  pin.position.set(r * 1.03, 0, 0);
  pin.rotation.z = -Math.PI / 2;
  group.add(pin);

  return group;
}

function makeMoonTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 256;
  const ctx = canvas.getContext("2d")!;

  const grad = ctx.createRadialGradient(256, 128, 20, 256, 128, 280);
  grad.addColorStop(0, "#dcd8d0");
  grad.addColorStop(0.55, "#b8b4ac");
  grad.addColorStop(1, "#8a8680");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = "rgba(70, 68, 64, 0.45)";
  const craters: [number, number, number][] = [
    [120, 90, 28], [340, 70, 22], [420, 140, 18], [180, 160, 35],
    [280, 200, 14], [90, 180, 12], [460, 200, 20], [220, 110, 16],
  ];
  for (const [cx, cy, rad] of craters) {
    ctx.beginPath();
    ctx.arc(cx, cy, rad, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(50, 48, 45, 0.3)";
    ctx.beginPath();
    ctx.arc(cx - rad * 0.2, cy - rad * 0.2, rad * 0.65, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(70, 68, 64, 0.45)";
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeTargetBody(
  kind: "satellite" | "moon",
  scale: number,
  bodyRadiusKm?: number | null,
): THREE.Group {
  const group = new THREE.Group();

  if (kind === "moon") {
    const r = Math.min(Math.max((bodyRadiusKm ?? MOON_R_KM) * scale, 0.025), 0.18);

    group.add(
      new THREE.Mesh(
        new THREE.SphereGeometry(r, 32, 24),
        new THREE.MeshPhongMaterial({
          map: makeMoonTexture(),
          color: 0xffffff,
          emissive: 0x333330,
          shininess: 8,
        }),
      ),
    );

    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(r * 1.15, 16, 12),
      new THREE.MeshBasicMaterial({
        color: 0xe8e4dc,
        transparent: true,
        opacity: 0.15,
        depthWrite: false,
      }),
    );
    group.add(halo);

    const spinPin = new THREE.Mesh(
      new THREE.ConeGeometry(r * 0.1, r * 0.3, 8),
      new THREE.MeshBasicMaterial({ color: 0xf5f0e6 }),
    );
    spinPin.position.set(r * 1.05, 0, 0);
    spinPin.rotation.z = -Math.PI / 2;
    group.add(spinPin);
  } else {
    const r = 0.022;
    group.add(
      new THREE.Mesh(
        new THREE.BoxGeometry(r * 1.6, r * 1.2, r * 1.2),
        new THREE.MeshPhongMaterial({ color: 0xc9d4ce, emissive: 0x1a3028, shininess: 40 }),
      ),
    );
    const panelMat = new THREE.MeshPhongMaterial({ color: 0x3a5a48, emissive: 0x0a1812, shininess: 60 });
    for (const side of [-1, 1]) {
      const panel = new THREE.Mesh(new THREE.BoxGeometry(r * 0.15, r * 2.2, r * 0.9), panelMat);
      panel.position.x = side * r * 1.1;
      group.add(panel);
    }
    group.add(
      new THREE.Mesh(
        new THREE.SphereGeometry(r * 1.8, 12, 10),
        new THREE.MeshBasicMaterial({ color: 0x5dcaa5, transparent: true, opacity: 0.2, depthWrite: false }),
      ),
    );
  }

  return group;
}

function makeChaserBody(): THREE.Group {
  const group = new THREE.Group();
  const r = 0.028;

  group.add(
    new THREE.Mesh(
      new THREE.SphereGeometry(r * 2, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0x5dcaa5, transparent: true, opacity: 0.22, depthWrite: false }),
    ),
  );

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
        depthWrite: false,
      }),
    ),
  );

  return group;
}

function makeOrbitPath(
  points: Vec3[],
  color: number,
  scale: number,
  tubeRadius: number,
): THREE.Object3D {
  const pts = points.map((p) => toThree(p, scale));
  if (pts.length < 3) return new THREE.Group();

  try {
    const curve = new THREE.CatmullRomCurve3(pts, true);
    const geo = new THREE.TubeGeometry(curve, Math.max(pts.length * 2, 64), tubeRadius, 8, true);
    return new THREE.Mesh(
      geo,
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.88 }),
    );
  } catch {
    const closed = [...pts, pts[0]!];
    return new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(closed),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85 }),
    );
  }
}

function makeMissLine(points: THREE.Vector3[]): THREE.Line {
  const geo = points.length >= 2
    ? new THREE.BufferGeometry().setFromPoints(points)
    : new THREE.BufferGeometry();
  return new THREE.Line(
    geo,
    new THREE.LineBasicMaterial({ color: 0xe8c170, transparent: true, opacity: 0.95 }),
  );
}

function makeTrailLine(points: THREE.Vector3[], color: number): THREE.Line {
  const geo = points.length > 0 ? new THREE.BufferGeometry().setFromPoints(points) : new THREE.BufferGeometry();
  return new THREE.Line(
    geo,
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95 }),
  );
}

function sampleTargetTrail(
  scenario: Scenario,
  scoreTargetTraj: ScoreBreakdown["target_trajectory"],
  simT: number,
  steps = 40,
): Vec3[] {
  if (simT <= 0) return [];
  const pts: Vec3[] = [];
  const step = simT / steps;
  for (let i = 0; i <= steps; i++) {
    pts.push(targetPointAtTime(scoreTargetTraj, scenario.target, i * step));
  }
  return pts;
}

function chaserCoastAt(scenario: Scenario, t: number): Vec3 {
  const el = elementsFromState(scenario.spacecraft.position, scenario.spacecraft.velocity);
  return propagateElements(el, t).pos;
}

function frameCamera(camera: THREE.PerspectiveCamera, points: THREE.Vector3[], padding = 1.5) {
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

function readMountSize(mount: HTMLElement): { w: number; h: number } {
  const rect = mount.getBoundingClientRect();
  return {
    w: Math.max(Math.floor(rect.width), 320),
    h: Math.max(Math.floor(rect.height), 260),
  };
}

export function OrbitalViewport3D({
  scenario,
  score,
  burns: _burns,
  scrubT,
  playing,
  onScrub,
  onPlayingChange,
}: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const animRef = useRef(0);
  const playTRef = useRef(0);
  const idleTRef = useRef(0);
  const simTRef = useRef(scrubT);
  const scrubTRef = useRef(scrubT);
  const playingRef = useRef(playing);
  const scoreRef = useRef(score);
  const onScrubRef = useRef(onScrub);
  const onPlayingChangeRef = useRef(onPlayingChange);
  const [glError, setGlError] = useState<string | null>(null);
  const [timelineT, setTimelineT] = useState(scrubT);

  scrubTRef.current = scrubT;
  playingRef.current = playing;
  scoreRef.current = score;
  onScrubRef.current = onScrub;
  onPlayingChangeRef.current = onPlayingChange;

  useEffect(() => {
    if (!playing) {
      playTRef.current = scrubT;
      simTRef.current = scrubT;
      setTimelineT(scrubT);
    }
  }, [scrubT, playing]);

  useEffect(() => {
    if (playing) {
      playTRef.current = scrubT;
      simTRef.current = scrubT;
      setTimelineT(scrubT);
    }
  }, [playing]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !scenario) return;

    let disposed = false;
    setGlError(null);

    const motion = getTargetMotion(scenario.target);
    const earthSpinRate = scoreRef.current?.earth_spin_rad_s ?? (2 * Math.PI) / 86164;
    const targetPath = targetOrbitPath(scenario.target);
    const chaserPath = chaserCoastPath(scenario);
    const pathMaxR = Math.max(
      ...targetPath.map(vecMag),
      ...chaserPath.map(vecMag),
      motion.orbit_radius_km,
    );
    const maxR = Math.max(14000, pathMaxR * 1.12);
    const scale = 1.0 / maxR;
    const tubeR = 0.0045;

    const staticFramePts = [
      new THREE.Vector3(0, 0, 0),
      ...chaserPath.map((p) => toThree(p, scale)),
      ...targetPath.map((p) => toThree(p, scale)),
    ];

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch (err) {
      setGlError(err instanceof Error ? err.message : "WebGL unavailable");
      return;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x16241c);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.001, 100);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    mount.replaceChildren(renderer.domElement);

    const resize = () => {
      if (disposed) return;
      const { w, h } = readMountSize(mount);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    };

    const ro = new ResizeObserver(() => resize());
    ro.observe(mount);
    resize();

    scene.add(new THREE.AmbientLight(0x8fb89b, 0.6));
    const sun = new THREE.DirectionalLight(0xf5f0e6, 1.0);
    sun.position.set(2, 2, 1);
    scene.add(sun);

    const grid = new THREE.GridHelper(2.2, 24, 0x3a5a48, 0x243d30);
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);

    const earthGroup = makeEarthGroup(scale);
    scene.add(earthGroup);

    scene.add(makeOrbitPath(chaserPath, 0xf5f0e6, scale, tubeR));

    const targetColor = motion.kind === "moon" ? 0xc8c8be : 0x5dcaa5;
    scene.add(makeOrbitPath(targetPath, targetColor, scale, tubeR));

    const targetTrailLine = makeTrailLine([], targetColor);
    scene.add(targetTrailLine);

    const targetBody = makeTargetBody(motion.kind, scale, scenario.target.body_radius_km);
    scene.add(targetBody);

    const chaserBody = makeChaserBody();
    scene.add(chaserBody);

    const linkLine = makeTrailLine([], 0xf5f0e6);
    (linkLine.material as THREE.LineBasicMaterial).opacity = 0.35;
    scene.add(linkLine);

    const missLine = makeMissLine([]);
    missLine.visible = false;
    scene.add(missLine);

    const caMarkerChaser = new THREE.Mesh(
      new THREE.SphereGeometry(0.012, 10, 8),
      new THREE.MeshBasicMaterial({ color: 0xe8c170 }),
    );
    caMarkerChaser.visible = false;
    scene.add(caMarkerChaser);

    const caMarkerTarget = new THREE.Mesh(
      new THREE.SphereGeometry(0.012, 10, 8),
      new THREE.MeshBasicMaterial({ color: 0xe8c170 }),
    );
    caMarkerTarget.visible = false;
    scene.add(caMarkerTarget);

    const trajLine = makeTrailLine([], 0x5dcaa5);
    scene.add(trajLine);

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let lastWall = performance.now();
    let lastScrubEmit = 0;

    const updateScene = (simT: number) => {
      const liveScore = scoreRef.current;
      earthGroup.rotation.y = -earthSpinAngle(simT, earthSpinRate);

      const tgtEci = targetPointAtTime(liveScore?.target_trajectory, scenario.target, simT);
      const tgtThree = toThree(tgtEci, scale);
      targetBody.position.copy(tgtThree);
      targetBody.rotation.y = -bodySpinAngle(scenario.target, simT);

      const trailPts = sampleTargetTrail(scenario, liveScore?.target_trajectory, simT).map((p) =>
        toThree(p, scale),
      );
      targetTrailLine.geometry.dispose();
      targetTrailLine.geometry =
        trailPts.length > 1
          ? new THREE.BufferGeometry().setFromPoints(trailPts)
          : new THREE.BufferGeometry();

      const traj = liveScore?.trajectory ?? [];
      const visible = traj.filter((p) => p.t_s <= simT + 1e-6);
      let chaserThree: THREE.Vector3;
      if (visible.length > 0) {
        const pts = visible.map((p) => toThree(p.position, scale));
        trajLine.geometry.dispose();
        trajLine.geometry = new THREE.BufferGeometry().setFromPoints(pts);
        chaserThree = pts[pts.length - 1]!;
      } else {
        chaserThree = toThree(chaserCoastAt(scenario, simT), scale);
        trajLine.geometry.dispose();
        trajLine.geometry = new THREE.BufferGeometry();
      }
      chaserBody.position.copy(chaserThree);
      chaserBody.rotation.y = simT * 0.04;

      linkLine.geometry.dispose();
      linkLine.geometry = new THREE.BufferGeometry().setFromPoints([chaserThree, tgtThree]);

      const ca = closestApproachState(liveScore, scenario);
      if (ca) {
        const caChaser = toThree(ca.chaser, scale);
        const caTarget = toThree(ca.target, scale);
        missLine.geometry.dispose();
        missLine.geometry = new THREE.BufferGeometry().setFromPoints([caChaser, caTarget]);
        missLine.visible = true;
        caMarkerChaser.position.copy(caChaser);
        caMarkerChaser.visible = true;
        caMarkerTarget.position.copy(caTarget);
        caMarkerTarget.visible = true;
      } else {
        missLine.visible = false;
        caMarkerChaser.visible = false;
        caMarkerTarget.visible = false;
      }

      frameCamera(camera, [...staticFramePts, chaserThree, tgtThree]);
    };

    const tick = (now: number) => {
      if (disposed) return;
      const dt = Math.min(0.05, (now - lastWall) / 1000);
      lastWall = now;

      const liveScore = scoreRef.current;
      const maxT = liveScore?.trajectory?.at(-1)?.t_s ?? scenario.time_limit_s;

      if (!liveScore && !reducedMotion) {
        const idleRate = simRateForWallDuration(scenario.time_limit_s);
        idleTRef.current = (idleTRef.current + dt * idleRate) % scenario.time_limit_s;
      }

      let simT = scrubTRef.current;
      if (playingRef.current && !reducedMotion && liveScore?.trajectory?.length) {
        const playRate = simRateForWallDuration(maxT);
        playTRef.current = Math.min(maxT, playTRef.current + dt * playRate);
        simT = playTRef.current;
        if (now - lastScrubEmit > 80) {
          setTimelineT(simT);
          onScrubRef.current(simT);
          lastScrubEmit = now;
        }
        if (playTRef.current >= maxT - 1e-6) {
          playTRef.current = maxT;
          simT = maxT;
          setTimelineT(maxT);
          onScrubRef.current(maxT);
          onPlayingChangeRef.current(false);
        }
      } else if (!liveScore && !playingRef.current && !reducedMotion) {
        simT = idleTRef.current;
      }

      simTRef.current = simT;

      try {
        updateScene(simT);
        renderer.render(scene, camera);
      } catch (err) {
        console.error("Orbital 3D render error:", err);
        setGlError(err instanceof Error ? err.message : "Render error");
      }
      animRef.current = requestAnimationFrame(tick);
    };

    const boot = () => {
      if (disposed) return;
      resize();
      simTRef.current = scrubTRef.current;
      updateScene(scrubTRef.current);
      renderer.render(scene, camera);
      animRef.current = requestAnimationFrame(tick);
    };

    requestAnimationFrame(boot);

    return () => {
      disposed = true;
      cancelAnimationFrame(animRef.current);
      ro.disconnect();
      renderer.dispose();
      mount.replaceChildren();
    };
  }, [scenario?.id]);

  const maxT = score?.trajectory?.at(-1)?.t_s ?? scenario?.time_limit_s ?? 1;
  const sliderT = playing ? timelineT : scrubT;
  const motion = scenario ? getTargetMotion(scenario.target) : null;
  const ca = scenario && score ? closestApproachState(score, scenario) : null;
  const liveSep = scenario && score ? separationAt(score, scenario, scrubT) : null;

  return (
    <div className={styles.wrap}>
      <div className={styles.dualViewport}>
        <div className={styles.main3d}>
          <p className={styles.viewLabel}>3D — auto-tracked</p>
          <div className={styles.viewportShell}>
            <div ref={mountRef} className={styles.canvasMount} aria-label="3D orbital viewport">
              {glError && <p className={styles.glError}>{glError}</p>}
            </div>
            {scenario && (
              <div className={styles.legend}>
                <span className={styles.legendItem}>
                  <span className={styles.swatchChaser} /> Chaser
                </span>
                <span className={styles.legendItem}>
                  <span className={styles.swatchTarget} /> Target
                </span>
                <span className={styles.legendItem}>
                  <span className={styles.swatchEarth} /> Earth spin
                </span>
                {ca && (
                  <span className={styles.legendItem}>
                    <span className={styles.swatchMiss} /> Miss {ca.miss_km.toFixed(1)} km
                  </span>
                )}
                {motion && (
                  <span className={styles.legendMeta}>
                    {motion.orbit_type === "elliptical"
                      ? `e=${motion.eccentricity.toFixed(2)} · i=${((motion.inclination_rad * 180) / Math.PI).toFixed(0)}°`
                      : `r=${motion.orbit_radius_km.toFixed(0)} km`}
                  </span>
                )}
              </div>
            )}
            {ca && (
              <div className={styles.missBadge}>
                <strong>Miss {ca.miss_km.toFixed(1)} km</strong>
                <span>closest approach T+{ca.t_s.toFixed(0)} s</span>
                {liveSep != null && (
                  <span>now {liveSep.toFixed(1)} km apart</span>
                )}
              </div>
            )}
            {score?.crashed && (
              <div className={`${styles.missBadge} ${styles.missBad}`}>Crashed — no intercept</div>
            )}
          </div>
        </div>

        <OrbitalBirdEye scenario={scenario} score={score} simTRef={simTRef} />
      </div>

      <div className={styles.controls}>
        <button
          type="button"
          className={styles.btn}
          onClick={() => {
            playTRef.current = 0;
            simTRef.current = 0;
            setTimelineT(0);
            onScrub(0);
            onPlayingChange(!playing);
          }}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <input
          type="range"
          min={0}
          max={maxT}
          step={10}
          value={sliderT}
          onChange={(e) => {
            const t = Number(e.target.value);
            playTRef.current = t;
            simTRef.current = t;
            setTimelineT(t);
            onScrub(t);
            onPlayingChange(false);
          }}
          className={styles.scrub}
          aria-label="Trajectory timeline"
        />
        <span className={styles.timeLabel}>
          T+{sliderT.toFixed(0)} s / {maxT.toFixed(0)} s
        </span>
      </div>
    </div>
  );
}
