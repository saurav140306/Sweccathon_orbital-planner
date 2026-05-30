import { useEffect, useRef, type MutableRefObject } from "react";
import type { Scenario, ScoreBreakdown } from "../types";
import type { Vec3 } from "../kepler3d";
import { elementsFromState, propagateElements } from "../kepler3d";
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
import styles from "./OrbitalCanvas.module.css";

const EARTH_R = 6371;

interface Props {
  scenario: Scenario | null;
  score: ScoreBreakdown | null;
  simTRef: MutableRefObject<number>;
}

function chaserPosAt(scenario: Scenario, score: ScoreBreakdown | null, simT: number): Vec3 {
  const traj = score?.trajectory ?? [];
  const visible = traj.filter((p) => p.t_s <= simT + 1e-6);
  if (visible.length > 0) return visible[visible.length - 1].position;
  const el = elementsFromState(scenario.spacecraft.position, scenario.spacecraft.velocity);
  return propagateElements(el, simT).pos;
}

function drawEarth2D(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale: number,
  spinRad: number,
) {
  const r = EARTH_R * scale;
  const grad = ctx.createRadialGradient(cx, cy, r * 0.1, cx, cy, r);
  grad.addColorStop(0, "#2a4538");
  grad.addColorStop(0.75, "#243d30");
  grad.addColorStop(1, "#8FB89B");

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-spinRad);
  ctx.translate(-cx, -cy);
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = "rgba(232, 193, 112, 0.6)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx, cy - r);
  ctx.lineTo(cx, cy + r);
  ctx.stroke();

  ctx.strokeStyle = "rgba(143, 184, 155, 0.35)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * r * 0.9, cy + Math.sin(a) * r * 0.9);
    ctx.stroke();
  }
  ctx.restore();
}

function drawMoon2D(
  ctx: CanvasRenderingContext2D,
  sx: number,
  sy: number,
  radiusPx: number,
  spinRad: number,
) {
  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(-spinRad);

  const grad = ctx.createRadialGradient(-radiusPx * 0.25, -radiusPx * 0.2, 1, 0, 0, radiusPx);
  grad.addColorStop(0, "#ece8e0");
  grad.addColorStop(0.55, "#c8c4bc");
  grad.addColorStop(1, "#7a7872");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(0, 0, radiusPx, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "rgba(55, 53, 50, 0.4)";
  const craters: [number, number, number][] = [
    [-0.35, 0.2, 0.22], [0.3, -0.25, 0.18], [0.1, 0.35, 0.14], [-0.2, -0.3, 0.16],
  ];
  for (const [cx, cy, r] of craters) {
    ctx.beginPath();
    ctx.arc(cx * radiusPx, cy * radiusPx, r * radiusPx, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.strokeStyle = "rgba(245, 240, 230, 0.55)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(radiusPx - 2, 0);
  ctx.stroke();
  ctx.restore();

  ctx.strokeStyle = "rgba(232, 228, 220, 0.35)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(sx, sy, radiusPx + 4, 0, Math.PI * 2);
  ctx.stroke();
}

function drawChaser2D(ctx: CanvasRenderingContext2D, sx: number, sy: number) {
  ctx.fillStyle = "rgba(93, 202, 165, 0.25)";
  ctx.beginPath();
  ctx.arc(sx, sy, 14, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#5dcaa5";
  ctx.strokeStyle = "#f5f0e6";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(sx, sy - 9);
  ctx.lineTo(sx + 8, sy + 6);
  ctx.lineTo(sx - 8, sy + 6);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.strokeStyle = "rgba(245, 240, 230, 0.7)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(sx, sy, 11, 0, Math.PI * 2);
  ctx.stroke();
}

function drawSatellite2D(ctx: CanvasRenderingContext2D, sx: number, sy: number, spinRad: number) {
  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(-spinRad);
  ctx.fillStyle = "rgba(93, 202, 165, 0.2)";
  ctx.beginPath();
  ctx.arc(0, 0, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#c9d4ce";
  ctx.fillRect(-5, -4, 10, 8);
  ctx.fillStyle = "#3a5a48";
  ctx.fillRect(-14, -2, 8, 4);
  ctx.fillRect(6, -2, 8, 4);
  ctx.strokeStyle = "#5dcaa5";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(-5, -4, 10, 8);
  ctx.restore();
}

function drawMiss2D(
  ctx: CanvasRenderingContext2D,
  caChaser: { sx: number; sy: number },
  caTarget: { sx: number; sy: number },
  missKm: number,
  caT: number,
) {
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = "rgba(232, 193, 112, 0.95)";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(caChaser.sx, caChaser.sy);
  ctx.lineTo(caTarget.sx, caTarget.sy);
  ctx.stroke();
  ctx.setLineDash([]);

  for (const p of [caChaser, caTarget]) {
    ctx.fillStyle = "#e8c170";
    ctx.beginPath();
    ctx.arc(p.sx, p.sy, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  const mx = (caChaser.sx + caTarget.sx) / 2;
  const my = (caChaser.sy + caTarget.sy) / 2;
  const label = `${missKm.toFixed(1)} km miss`;
  ctx.font = "bold 11px 'Source Sans 3', sans-serif";
  const tw = ctx.measureText(label).width;
  ctx.fillStyle = "rgba(22, 36, 28, 0.88)";
  ctx.fillRect(mx - tw / 2 - 6, my - 20, tw + 12, 16);
  ctx.fillStyle = "#e8c170";
  ctx.fillText(label, mx - tw / 2, my - 8);

  ctx.font = "9px 'Source Sans 3', sans-serif";
  ctx.fillStyle = "rgba(245, 240, 230, 0.55)";
  const sub = `CA T+${caT.toFixed(0)} s`;
  const sw = ctx.measureText(sub).width;
  ctx.fillText(sub, mx - sw / 2, my + 6);
}

function drawOrbitPath2D(
  ctx: CanvasRenderingContext2D,
  path: Vec3[],
  toScreen: (x: number, y: number) => { sx: number; sy: number },
  color: string,
  width = 1.5,
) {
  if (path.length < 2) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  const p0 = toScreen(path[0][0], path[0][1]);
  ctx.moveTo(p0.sx, p0.sy);
  for (let i = 1; i < path.length; i++) {
    const p = toScreen(path[i][0], path[i][1]);
    ctx.lineTo(p.sx, p.sy);
  }
  ctx.closePath();
  ctx.stroke();
}

export function OrbitalBirdEye({ scenario, score, simTRef }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef(0);
  const scoreRef = useRef(score);

  scoreRef.current = score;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !scenario) return;

    let disposed = false;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const motion = getTargetMotion(scenario.target);
    const targetPath = targetOrbitPath(scenario.target);
    const chaserPath = chaserCoastPath(scenario);
    const maxR = Math.max(
      14000,
      ...targetPath.map((p) => Math.hypot(p[0], p[1])),
      ...chaserPath.map((p) => Math.hypot(p[0], p[1])),
      motion.orbit_radius_km * 1.12,
    );

    let w = 0;
    let h = 0;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      w = Math.max(canvas.clientWidth, 200);
      h = Math.max(canvas.clientHeight, 200);
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const draw = (simT: number) => {
      const liveScore = scoreRef.current;
      const earthSpinRate = liveScore?.earth_spin_rad_s ?? (2 * Math.PI) / 86164;
      const scale = (Math.min(w, h) * 0.44) / maxR;
      const cx = w / 2;
      const cy = h / 2;
      const toScreen = (x: number, y: number) => ({
        sx: cx + x * scale,
        sy: cy - y * scale,
      });

      ctx.fillStyle = "#16241c";
      ctx.fillRect(0, 0, w, h);

      ctx.strokeStyle = "rgba(143, 184, 155, 0.1)";
      ctx.lineWidth = 1;
      for (const ring of [8000, 10000, 12000]) {
        ctx.beginPath();
        ctx.arc(cx, cy, ring * scale, 0, Math.PI * 2);
        ctx.stroke();
      }

      drawOrbitPath2D(ctx, chaserPath, toScreen, "rgba(245, 240, 230, 0.55)", 2);
      drawOrbitPath2D(
        ctx,
        targetPath,
        toScreen,
        motion.kind === "moon" ? "rgba(200, 200, 190, 0.65)" : "rgba(93, 202, 165, 0.65)",
        2,
      );

      drawEarth2D(ctx, cx, cy, scale, earthSpinAngle(simT, earthSpinRate));

      const ca = closestApproachState(liveScore, scenario);
      if (ca) {
        drawMiss2D(
          ctx,
          toScreen(ca.chaser[0], ca.chaser[1]),
          toScreen(ca.target[0], ca.target[1]),
          ca.miss_km,
          ca.t_s,
        );
      }

      const trailSteps = 40;
      if (simT > 0) {
        ctx.strokeStyle =
          motion.kind === "moon" ? "rgba(200, 200, 190, 0.5)" : "rgba(93, 202, 165, 0.5)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i <= trailSteps; i++) {
          const tt = (simT * i) / trailSteps;
          const [tx, ty] = targetPointAtTime(liveScore?.target_trajectory, scenario.target, tt);
          const p = toScreen(tx, ty);
          if (i === 0) ctx.moveTo(p.sx, p.sy);
          else ctx.lineTo(p.sx, p.sy);
        }
        ctx.stroke();
      }

      const traj = liveScore?.trajectory ?? [];
      const visible = traj.filter((p) => p.t_s <= simT + 1e-6);
      if (visible.length > 1) {
        ctx.strokeStyle = "rgba(93, 202, 165, 0.9)";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        const first = toScreen(visible[0].position[0], visible[0].position[1]);
        ctx.moveTo(first.sx, first.sy);
        for (let i = 1; i < visible.length; i++) {
          const p = toScreen(visible[i].position[0], visible[i].position[1]);
          ctx.lineTo(p.sx, p.sy);
        }
        ctx.stroke();
      }

      const [tx, ty, tz] = targetPointAtTime(liveScore?.target_trajectory, scenario.target, simT);
      const tgt = toScreen(tx, ty);
      const moonScale = Math.max((scenario.target.body_radius_km ?? 1737) * scale, 10);

      ctx.strokeStyle = "rgba(93, 202, 165, 0.35)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(tgt.sx, tgt.sy, scenario.target.tolerance_km * scale, 0, Math.PI * 2);
      ctx.stroke();

      if (motion.kind === "moon") {
        drawMoon2D(ctx, tgt.sx, tgt.sy, moonScale, bodySpinAngle(scenario.target, simT));
      } else {
        drawSatellite2D(ctx, tgt.sx, tgt.sy, bodySpinAngle(scenario.target, simT));
      }

      const chaser = chaserPosAt(scenario, liveScore, simT);
      const cp = toScreen(chaser[0], chaser[1]);
      drawChaser2D(ctx, cp.sx, cp.sy);

      ctx.setLineDash([3, 4]);
      ctx.strokeStyle = "rgba(245, 240, 230, 0.35)";
      ctx.beginPath();
      ctx.moveTo(tgt.sx, tgt.sy);
      ctx.lineTo(cp.sx, cp.sy);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.font = "10px 'Source Sans 3', sans-serif";
      ctx.fillStyle = "rgba(245, 240, 230, 0.5)";
      ctx.fillText("Equatorial · looking −Z", 8, 14);

      if (ca) {
        const liveSep = separationAt(liveScore, scenario, simT);
        ctx.fillStyle = "#e8c170";
        ctx.font = "bold 11px 'Source Sans 3', sans-serif";
        ctx.fillText(`Miss ${ca.miss_km.toFixed(1)} km`, 8, 28);
        ctx.font = "10px 'Source Sans 3', sans-serif";
        ctx.fillStyle = "rgba(245, 240, 230, 0.65)";
        if (liveSep != null) {
          ctx.fillText(`Now ${liveSep.toFixed(1)} km apart · CA T+${ca.t_s.toFixed(0)} s`, 8, 42);
        }
      } else if (liveScore?.crashed) {
        ctx.fillStyle = "#e8a070";
        ctx.fillText("Crashed", 8, 28);
      }

      if (Math.abs(tz) > 1 || Math.abs(chaser[2]) > 1) {
        ctx.fillStyle = "rgba(245, 240, 230, 0.5)";
        ctx.fillText(
          `z: tgt ${tz.toFixed(0)} · chsr ${chaser[2].toFixed(0)} km`,
          8,
          ca ? 56 : 26,
        );
      }
    };

    const tick = (_now: number) => {
      if (disposed) return;

      const simT = simTRef.current;
      draw(simT);
      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);

    return () => {
      disposed = true;
      cancelAnimationFrame(animRef.current);
      ro.disconnect();
    };
  }, [scenario?.id]);

  return (
    <div className={styles.birdEyePanel}>
      <p className={styles.birdEyeLabel}>Bird&apos;s eye (equatorial)</p>
      <canvas ref={canvasRef} className={styles.birdEyeCanvas} aria-label="Bird's eye orbital view" />
    </div>
  );
}
