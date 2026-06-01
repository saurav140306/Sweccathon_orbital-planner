/**
 * Equatorial bird's-eye canvas (port of OrbitalBirdEye.tsx).
 */
import {
  EARTH_R,
  chaserCoastRing,
  closestApproach,
  pointAtTraj,
  targetOrbitRing,
  turnToMission,
} from "./replay-viewport.js";

const EARTH_SPIN_RAD_S = (2 * Math.PI) / 86164;

function drawEarth2D(ctx, cx, cy, scale, spinRad) {
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
  ctx.restore();
}

function drawChaser2D(ctx, sx, sy) {
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
}

function drawSatellite2D(ctx, sx, sy, spinRad) {
  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(-spinRad);
  ctx.fillStyle = "#c9d4ce";
  ctx.fillRect(-5, -4, 10, 8);
  ctx.fillStyle = "#3a5a48";
  ctx.fillRect(-14, -2, 8, 4);
  ctx.fillRect(6, -2, 8, 4);
  ctx.restore();
}

function drawMoon2D(ctx, sx, sy, radiusPx, spinRad) {
  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(-spinRad);
  const grad = ctx.createRadialGradient(-radiusPx * 0.2, -radiusPx * 0.2, 1, 0, 0, radiusPx);
  grad.addColorStop(0, "#ece8e0");
  grad.addColorStop(1, "#7a7872");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(0, 0, radiusPx, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawOrbitPath2D(ctx, path, toScreen, color, width = 1.5) {
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

export class BirdEyeViewport {
  constructor(canvasEl) {
    this.canvas = canvasEl;
    this.scenario = null;
    this.score = null;
    this.simT = 0;
    this.animId = 0;
    this.disposed = false;
  }

  setMission(turn) {
    const { scenario, score } = turnToMission(turn);
    this.scenario = scenario;
    this.score = score;
    this.simT = 0;
  }

  setSimT(t) {
    this.simT = t;
    this.draw();
  }

  startLoop(getSimT) {
    const tick = () => {
      if (this.disposed) return;
      this.simT = getSimT();
      this.draw();
      this.animId = requestAnimationFrame(tick);
    };
    this.animId = requestAnimationFrame(tick);
  }

  draw() {
    const canvas = this.canvas;
    if (!canvas || !this.scenario || !this.score) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(canvas.clientWidth, 200);
    const h = Math.max(canvas.clientHeight, 200);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const chaserRing = chaserCoastRing(this.scenario);
    const targetRing = targetOrbitRing(this.scenario);
    const maxR = Math.max(
      14000,
      ...chaserRing.map((p) => Math.hypot(p[0], p[1])),
      ...targetRing.map((p) => Math.hypot(p[0], p[1])),
      12000,
    );
    const scale = (Math.min(w, h) * 0.44) / maxR;
    const cx = w / 2;
    const cy = h / 2;
    const toScreen = (x, y) => ({ sx: cx + x * scale, sy: cy - y * scale });
    const simT = this.simT;
    const kind = this.scenario.target.kind || "satellite";

    ctx.fillStyle = "#16241c";
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(143, 184, 155, 0.1)";
    ctx.lineWidth = 1;
    for (const ring of [8000, 10000, 12000]) {
      ctx.beginPath();
      ctx.arc(cx, cy, ring * scale, 0, Math.PI * 2);
      ctx.stroke();
    }

    drawOrbitPath2D(ctx, chaserRing, toScreen, "rgba(245, 240, 230, 0.55)", 2);
    drawOrbitPath2D(
      ctx,
      targetRing,
      toScreen,
      kind === "moon" ? "rgba(200, 200, 190, 0.65)" : "rgba(93, 202, 165, 0.65)",
      2,
    );

    drawEarth2D(ctx, cx, cy, scale, simT * EARTH_SPIN_RAD_S);

    const ca = closestApproach(this.score);
    if (ca) {
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = "rgba(232, 193, 112, 0.95)";
      ctx.lineWidth = 2.5;
      const c0 = toScreen(ca.chaser[0], ca.chaser[1]);
      const c1 = toScreen(ca.target[0], ca.target[1]);
      ctx.beginPath();
      ctx.moveTo(c0.sx, c0.sy);
      ctx.lineTo(c1.sx, c1.sy);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (simT > 0) {
      const trailSteps = 40;
      ctx.strokeStyle = kind === "moon" ? "rgba(200, 200, 190, 0.5)" : "rgba(93, 202, 165, 0.5)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i <= trailSteps; i++) {
        const tt = (simT * i) / trailSteps;
        const tgt = pointAtTraj(this.score.target_trajectory, tt);
        const p = toScreen(tgt[0], tgt[1]);
        if (i === 0) ctx.moveTo(p.sx, p.sy);
        else ctx.lineTo(p.sx, p.sy);
      }
      ctx.stroke();
    }

    const visible = this.score.trajectory.filter((p) => p.t_s <= simT + 1e-6);
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

    const tgt = pointAtTraj(this.score.target_trajectory, simT);
    const tp = toScreen(tgt[0], tgt[1]);
    ctx.strokeStyle = "rgba(93, 202, 165, 0.35)";
    ctx.beginPath();
    ctx.arc(tp.sx, tp.sy, (this.scenario.target.tolerance_km || 50) * scale, 0, Math.PI * 2);
    ctx.stroke();

    if (kind === "moon") {
      drawMoon2D(ctx, tp.sx, tp.sy, Math.max(10, 1737 * scale), simT * 0.12);
    } else {
      drawSatellite2D(ctx, tp.sx, tp.sy, simT * 0.12);
    }

    const ch = pointAtTraj(this.score.trajectory, simT);
    const cp = toScreen(ch[0], ch[1]);
    drawChaser2D(ctx, cp.sx, cp.sy);

    ctx.setLineDash([3, 4]);
    ctx.strokeStyle = "rgba(245, 240, 230, 0.35)";
    ctx.beginPath();
    ctx.moveTo(tp.sx, tp.sy);
    ctx.lineTo(cp.sx, cp.sy);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.font = "10px 'Source Sans 3', sans-serif";
    ctx.fillStyle = "rgba(245, 240, 230, 0.5)";
    ctx.fillText("Equatorial · looking −Z", 8, 14);
    if (ca) {
      ctx.fillStyle = "#e8c170";
      ctx.fillText(`Miss ${ca.miss_km.toFixed(1)} km · CA T+${ca.t_s.toFixed(0)} s`, 8, 28);
    }
  }

  destroy() {
    this.disposed = true;
    if (this.animId) cancelAnimationFrame(this.animId);
  }
}
