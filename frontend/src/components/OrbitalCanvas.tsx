import { useEffect, useRef } from "react";
import type { Burn, Scenario, ScoreBreakdown } from "../types";
import {
  bodySpinAngle,
  chaserCoastPath,
  earthSpinAngle,
  getTargetMotion,
  targetOrbitPath,
  targetPointAtTime,
} from "../orbitalMotion";
import styles from "./OrbitalCanvas.module.css";

const EARTH_R = 6371;

interface Props {
  scenario: Scenario | null;
  score: ScoreBreakdown | null;
  burns: Burn[];
  scrubT: number;
  playing: boolean;
  onScrub: (t: number) => void;
  onPlayingChange: (p: boolean) => void;
}

function drawEarth(
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

  // Surface markings (rotate with Earth)
  ctx.strokeStyle = "rgba(143, 184, 155, 0.35)";
  ctx.lineWidth = 1.2;
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * r * 0.92, cy + Math.sin(a) * r * 0.92);
    ctx.stroke();
  }
  ctx.fillStyle = "rgba(93, 202, 165, 0.25)";
  ctx.beginPath();
  ctx.ellipse(cx + r * 0.25, cy - r * 0.15, r * 0.35, r * 0.2, 0.4, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();

  // Spin indicator (fixed frame arrow showing rotation direction)
  ctx.strokeStyle = "rgba(245, 240, 230, 0.25)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, r + 6, -spinRad - 0.4, -spinRad + 0.4);
  ctx.stroke();
}

function drawTargetBody(
  ctx: CanvasRenderingContext2D,
  sx: number,
  sy: number,
  kind: "satellite" | "moon",
  bodySpin: number,
) {
  const size = kind === "moon" ? 11 : 8;

  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(-bodySpin);

  if (kind === "moon") {
    const moonGrad = ctx.createRadialGradient(-2, -2, 1, 0, 0, size);
    moonGrad.addColorStop(0, "#e8e4dc");
    moonGrad.addColorStop(0.6, "#b8b4ac");
    moonGrad.addColorStop(1, "#7a7872");
    ctx.fillStyle = moonGrad;
    ctx.beginPath();
    ctx.arc(0, 0, size, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(60, 58, 55, 0.35)";
    ctx.beginPath();
    ctx.arc(-3, 2, 2.5, 0, Math.PI * 2);
    ctx.arc(4, -1, 1.8, 0, Math.PI * 2);
    ctx.fill();
    // Moon spin marker
    ctx.strokeStyle = "rgba(245, 240, 230, 0.5)";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(size - 1, 0);
    ctx.stroke();
  } else {
    ctx.fillStyle = "#5DCAA5";
    ctx.fillRect(-size * 0.6, -1.5, size * 1.2, 3);
    ctx.fillStyle = "#c9d4ce";
    ctx.beginPath();
    ctx.arc(0, 0, size * 0.45, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#e8c170";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-size, 0);
    ctx.lineTo(size, 0);
    ctx.stroke();
  }

  ctx.restore();
}

export function OrbitalCanvas({
  scenario,
  score,
  burns,
  scrubT,
  playing,
  onScrub,
  onPlayingChange,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const playTRef = useRef(0);
  const idleTRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !scenario) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const motion = getTargetMotion(scenario.target);
    const earthSpinRate = score?.earth_spin_rad_s ?? (2 * Math.PI) / 86164;
    const targetPath = targetOrbitPath(scenario.target);
    const chaserPath = chaserCoastPath(scenario);
    const pathMaxR = Math.max(
      ...targetPath.map(([x, y]) => Math.hypot(x, y)),
      ...chaserPath.map(([x, y]) => Math.hypot(x, y)),
      motion.orbit_radius_km,
    );

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const maxR = Math.max(14000, pathMaxR * 1.12);
    const scale = (Math.min(w, h) * 0.42) / maxR;
    const cx = w / 2;
    const cy = h / 2;
    const toScreen = (x: number, y: number) => ({
      sx: cx + x * scale,
      sy: cy - y * scale,
    });

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const draw = (simT: number) => {
      ctx.fillStyle = "#16241c";
      ctx.fillRect(0, 0, w, h);

      // Orbit grid + target revolution path
      ctx.strokeStyle = "rgba(143, 184, 155, 0.12)";
      ctx.lineWidth = 1;
      for (const ring of [8000, 10000, 12000]) {
        ctx.beginPath();
        ctx.arc(cx, cy, ring * scale, 0, Math.PI * 2);
        ctx.stroke();
      }

      const drawOrbitPath = (
        path: [number, number][],
        color: string,
        dash: number[] = [],
      ) => {
        if (path.length < 2) return;
        ctx.strokeStyle = color;
        ctx.setLineDash(dash);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        const p0 = toScreen(path[0][0], path[0][1]);
        ctx.moveTo(p0.sx, p0.sy);
        for (let i = 1; i < path.length; i++) {
          const p = toScreen(path[i][0], path[i][1]);
          ctx.lineTo(p.sx, p.sy);
        }
        ctx.closePath();
        ctx.stroke();
        ctx.setLineDash([]);
      };

      drawOrbitPath(
        chaserPath,
        "rgba(245, 240, 230, 0.12)",
        [4, 10],
      );
      drawOrbitPath(
        targetPath,
        motion.kind === "moon"
          ? "rgba(200, 200, 190, 0.28)"
          : "rgba(93, 202, 165, 0.28)",
        [6, 8],
      );

      drawEarth(ctx, cx, cy, scale, earthSpinAngle(simT, earthSpinRate));

      const targetTraj = score?.target_trajectory;
      const tgtPos = targetPointAtTime(targetTraj, scenario.target, simT);
      const [tx, ty] = tgtPos;
      const tol = scenario.target.tolerance_km;
      const tgt = toScreen(tx, ty);

      // Target trail (revolution arc up to simT)
      const trailSteps = 48;
      const tStep = simT / trailSteps;
      if (tStep > 0) {
        ctx.strokeStyle =
          motion.kind === "moon"
            ? "rgba(200, 200, 190, 0.35)"
            : "rgba(93, 202, 165, 0.35)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let i = 0; i <= trailSteps; i++) {
          const tt = i * tStep;
          const [px, py] = targetPointAtTime(targetTraj, scenario.target, tt);
          const p = toScreen(px, py);
          if (i === 0) ctx.moveTo(p.sx, p.sy);
          else ctx.lineTo(p.sx, p.sy);
        }
        ctx.stroke();
      }

      const pulse = 0.85 + 0.15 * Math.sin(simT * 0.003);
      ctx.strokeStyle = `rgba(93, 202, 165, ${0.3 + 0.2 * pulse})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(tgt.sx, tgt.sy, tol * scale, 0, Math.PI * 2);
      ctx.stroke();

      drawTargetBody(
        ctx,
        tgt.sx,
        tgt.sy,
        motion.kind,
        bodySpinAngle(scenario.target, simT),
      );

      const [sx, sy] = scenario.spacecraft.position;
      const start = toScreen(sx, sy);
      ctx.fillStyle = "#f5f0e6";
      ctx.beginPath();
      ctx.arc(start.sx, start.sy, 6, 0, Math.PI * 2);
      ctx.fill();

      const traj = score?.trajectory ?? [];
      if (traj.length > 1) {
        const visible = traj.filter((p) => p.t_s <= simT + 1e-6);
        if (visible.length > 1) {
          ctx.strokeStyle = "rgba(93, 202, 165, 0.85)";
          ctx.lineWidth = 2.5;
          ctx.shadowColor = "#5DCAA5";
          ctx.shadowBlur = 12;
          ctx.beginPath();
          const first = toScreen(visible[0].position[0], visible[0].position[1]);
          ctx.moveTo(first.sx, first.sy);
          for (let i = 1; i < visible.length; i++) {
            const p = toScreen(visible[i].position[0], visible[i].position[1]);
            ctx.lineTo(p.sx, p.sy);
          }
          ctx.stroke();
          ctx.shadowBlur = 0;

          const last = visible[visible.length - 1];
          const craft = toScreen(last.position[0], last.position[1]);
          ctx.fillStyle = "#5DCAA5";
          ctx.beginPath();
          ctx.arc(craft.sx, craft.sy, 7, 0, Math.PI * 2);
          ctx.fill();
        }

        for (const b of burns) {
          if (b.time_s > simT) continue;
          const near = traj.reduce((best, p) =>
            Math.abs(p.t_s - b.time_s) < Math.abs(best.t_s - b.time_s) ? p : best,
          );
          const bp = toScreen(near.position[0], near.position[1]);
          ctx.fillStyle = "#e8c170";
          ctx.beginPath();
          ctx.arc(bp.sx, bp.sy, 5, 0, Math.PI * 2);
          ctx.fill();
          const dvScale = 800;
          ctx.strokeStyle = "#e8c170";
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(bp.sx, bp.sy);
          ctx.lineTo(bp.sx + b.dv[0] * dvScale, bp.sy - b.dv[1] * dvScale);
          ctx.stroke();
        }

        if (score && !score.crashed && Number.isFinite(score.miss_km)) {
          const caT = score.closest_approach_time_s;
          const ca = traj.reduce((best, p) =>
            Math.abs(p.t_s - caT) < Math.abs(best.t_s - caT) ? p : best,
          );
          const cp = toScreen(ca.position[0], ca.position[1]);
          const [tax, tay] = targetPointAtTime(targetTraj, scenario.target, caT);
          const tap = toScreen(tax, tay);
          ctx.setLineDash([4, 4]);
          ctx.strokeStyle = "rgba(245, 240, 230, 0.55)";
          ctx.beginPath();
          ctx.moveTo(cp.sx, cp.sy);
          ctx.lineTo(tap.sx, tap.sy);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = "#f5f0e6";
          ctx.font = "12px 'Source Sans 3', sans-serif";
          ctx.fillText(
            `${score.miss_km.toFixed(1)} km miss`,
            (cp.sx + tap.sx) / 2,
            (cp.sy + tap.sy) / 2 - 8,
          );
        }
      }

      // Legend
      ctx.font = "11px 'Source Sans 3', sans-serif";
      ctx.fillStyle = "rgba(245, 240, 230, 0.45)";
      const periodMin = ((motion.revolution_period_s ?? 0) / 60).toFixed(1);
      const orbitLabel =
        motion.orbit_type === "elliptical"
          ? `e=${motion.eccentricity.toFixed(2)} a=${motion.semi_major_axis_km.toFixed(0)} km`
          : `r=${motion.orbit_radius_km.toFixed(0)} km`;
      ctx.fillText(
        `Earth spin · ${motion.kind} ${orbitLabel} · T=${periodMin} min`,
        12,
        h - 12,
      );
    };

    const maxT = score?.trajectory?.at(-1)?.t_s ?? scenario.time_limit_s;
    let lastWall = performance.now();

    const tick = (now: number) => {
      const dt = (now - lastWall) / 1000;
      lastWall = now;

      if (!score && !reducedMotion) {
        idleTRef.current = (idleTRef.current + dt * 80) % scenario.time_limit_s;
      }

      let simT = scrubT;
      if (playing && !reducedMotion && score?.trajectory?.length) {
        playTRef.current = Math.min(maxT, playTRef.current + dt * 120);
        simT = playTRef.current;
        onScrub(simT);
        if (playTRef.current >= maxT) onPlayingChange(false);
      } else if (!score && !playing) {
        simT = idleTRef.current;
      }

      draw(simT);
      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current);
  }, [scenario, score, burns, scrubT, playing, onScrub, onPlayingChange]);

  const maxT = score?.trajectory?.at(-1)?.t_s ?? scenario?.time_limit_s ?? 1;

  return (
    <div className={styles.wrap}>
      <canvas ref={canvasRef} className={styles.canvas} />
      <div className={styles.controls}>
        <button
          type="button"
          className={styles.btn}
          onClick={() => {
            playTRef.current = 0;
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
          value={scrubT}
          onChange={(e) => {
            playTRef.current = Number(e.target.value);
            onScrub(playTRef.current);
            onPlayingChange(false);
          }}
          className={styles.scrub}
          aria-label="Trajectory timeline"
        />
        <span className={styles.timeLabel}>
          T+{scrubT.toFixed(0)} s / {maxT.toFixed(0)} s
        </span>
      </div>
    </div>
  );
}
