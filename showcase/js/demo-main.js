import { ReplayViewport3D, MAX_ANIM_WALL_S, parseInfo, turnToMission } from "./replay-viewport.js";
import { BirdEyeViewport } from "./birdeye-viewport.js";

export async function startDemo({ data, scenarios }) {
  let DATA = data;
  const SCENARIOS = scenarios;
  let epId = null;
  let turnIdx = 0;
  let scrubT = 0;
  let playing = false;

  const viewport = new ReplayViewport3D(document.getElementById("viewportMount"));
  const birdeye = new BirdEyeViewport(document.getElementById("birdEyeCanvas"));
  birdeye.startLoop(() => scrubT);

  function turns() {
    return (DATA.replay && epId && DATA.replay[epId]) || [];
  }

  function currentTurn() {
    return turns()[turnIdx] || null;
  }

  function updateHudPanels() {
    const t = currentTurn();
    if (!t) return;
    const info = parseInfo(t.info);
    const { scenario, score } = turnToMission(t);
    const maxT = viewport.maxT;

    document.getElementById("timeLabel").textContent =
      `T+${scrubT.toFixed(0)} s / ${maxT.toFixed(0)} s · ≤${MAX_ANIM_WALL_S}s @1×`;
    document.getElementById("scrub").max = String(maxT);
    document.getElementById("scrub").value = String(scrubT);

    document.getElementById("scoreVal").textContent = info.score ?? "—";
    const tgtInc = scenario.target?.inclination_rad ?? 0;
    const incLine =
      tgtInc > 1e-4
        ? `<div><strong>Target i</strong> ${((tgtInc * 180) / Math.PI).toFixed(0)}°</div>`
        : "";
    document.getElementById("metrics").innerHTML = `
      <div><strong>Scenario</strong> ${scenario.name}</div>
      <div><strong>Tier</strong> ${scenario.tier || "—"}</div>
      ${incLine}
      <div><strong>Reward</strong> ${Number(t.reward).toFixed(3)}</div>
      <div><strong>Miss</strong> ${info.miss_km ?? "—"} km</div>
      <div><strong>Fuel</strong> ${info.fuel_used ?? "—"} km/s</div>
    `;
    let reasoningText = info.agent_reasoning || t.reasoning || "—";
    if (typeof reasoningText === "string" && reasoningText.trim().startsWith("{")) {
      try {
        const j = JSON.parse(reasoningText);
        if (j.reasoning) reasoningText = j.reasoning;
      } catch {
        /* keep */
      }
    }
    document.getElementById("reasoning").textContent = reasoningText;
    document.getElementById("action").textContent =
      typeof t.action === "string" ? t.action : JSON.stringify(t.action, null, 2);

    const badge = document.getElementById("missBadge");
    if (score && Number.isFinite(score.miss_km) && !score.crashed) {
      badge.hidden = false;
      document.getElementById("missVal").textContent = `Miss ${score.miss_km.toFixed(1)} km`;
      document.getElementById("caVal").textContent =
        `closest T+${score.closest_approach_time_s.toFixed(0)} s`;
    } else if (score?.crashed) {
      badge.hidden = false;
      document.getElementById("missVal").textContent = "Crashed";
      document.getElementById("caVal").textContent = "no intercept";
    } else {
      badge.hidden = true;
    }
  }

  function applyTurn() {
    const t = currentTurn();
    if (!t) return;
    viewport.setMission(t);
    birdeye.setMission(t);
    scrubT = 0;
    viewport.setScrub(0);
    updateHudPanels();
  }

  function setEpisode(id) {
    if (!id || !DATA.replay[id]) return;
    epId = id;
    turnIdx = 0;
    stopPlay();
    document.querySelectorAll(".ep-btn").forEach((b) =>
      b.classList.toggle("active", b.dataset.episodeId === id),
    );
    applyTurn();
  }

  function stopPlay() {
    playing = false;
    viewport.setPlaying(false);
    document.getElementById("btnPlay").textContent = "Play";
  }

  window.__demoApp = { setEpisode };

  viewport.onScrub = (t) => {
    scrubT = t;
    updateHudPanels();
  };
  viewport.onPlayingChange = (p) => {
    playing = p;
    document.getElementById("btnPlay").textContent = p ? "Pause" : "Play";
  };

  document.getElementById("btnPlay").onclick = () => {
    if (playing) stopPlay();
    else {
      viewport.speedFactor = Number(document.getElementById("speed").value);
      if (scrubT >= viewport.maxT - 1) {
        scrubT = 0;
        viewport.setScrub(0);
      }
      playing = true;
      viewport.setPlaying(true);
      document.getElementById("btnPlay").textContent = "Pause";
    }
  };

  document.getElementById("btnPrev").onclick = () => {
    stopPlay();
    scrubT = Math.max(0, scrubT - Math.max(60, viewport.maxT / 80));
    viewport.setScrub(scrubT);
    updateHudPanels();
  };

  document.getElementById("btnNext").onclick = () => {
    stopPlay();
    scrubT = Math.min(viewport.maxT, scrubT + Math.max(60, viewport.maxT / 80));
    viewport.setScrub(scrubT);
    updateHudPanels();
  };

  document.getElementById("scrub").oninput = (e) => {
    stopPlay();
    scrubT = Number(e.target.value);
    viewport.setScrub(scrubT);
    updateHudPanels();
  };

  document.addEventListener("keydown", (e) => {
    if (e.code === "Space") {
      e.preventDefault();
      document.getElementById("btnPlay").click();
    }
    if (e.code === "ArrowLeft") document.getElementById("btnPrev").click();
    if (e.code === "ArrowRight") document.getElementById("btnNext").click();
  });

  const pending = window.__pendingEpisodeId;
  if (pending && DATA.replay[pending]) setEpisode(pending);
}
