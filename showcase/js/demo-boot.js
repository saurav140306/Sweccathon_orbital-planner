/**
 * Non-module bootstrap: load replay + scenarios, fill the rail, then load 3D modules.
 */
(function () {
  const TIER_ORDER = ["easy", "medium", "hard", "expert"];

  function showError(msg) {
    const rail = document.getElementById("episodeRail");
    if (rail) {
      rail.innerHTML = `<p class="tier-label" style="color:#e8a070">${msg}</p>`;
    }
    const hud = document.getElementById("runHud");
    if (hud) hud.textContent = "Failed to load demo";
  }

  function parseInfo(info) {
    const out = {};
    for (const [k, v] of Object.entries(info || {})) {
      if (typeof v === "string") {
        try {
          out[k] = JSON.parse(v);
        } catch {
          out[k] = v;
        }
      } else {
        out[k] = v;
      }
    }
    return out;
  }

  function scenarioIdFromEpisode(data, ep) {
    if (ep?.terminal_info?.scenario_id) return ep.terminal_info.scenario_id;
    const turn = data.replay?.[ep.id]?.[0];
    return (
      turn?.board_before?.scenario_id ||
      turn?.observation?.scenario_id ||
      parseInfo(turn?.info)?.scenario_id
    );
  }

  function findEpisodeForScenario(data, scenarios, scenarioId) {
    const order = (scenarios.all || []).map((s) => s.id);
    const wantIdx = order.indexOf(scenarioId);

    for (const ep of data.episodes || []) {
      if (scenarioIdFromEpisode(data, ep) === scenarioId) return ep.id;
      if (ep?.terminal_info?.scenario_id === scenarioId) return ep.id;
    }
    for (const [eid, tlist] of Object.entries(data.replay || {})) {
      const t = tlist[0];
      const sid =
        t?.board_before?.scenario_id ||
        t?.observation?.scenario_id ||
        parseInfo(t?.info)?.scenario_id;
      if (sid === scenarioId) return eid;
    }
    if (wantIdx >= 0) {
      for (const ep of data.episodes || []) {
        const seed = ep?.seed;
        if (seed != null && Number(seed) % order.length === wantIdx) return ep.id;
      }
    }
    return null;
  }

  function episodeScoreForScenario(data, scenarios, scenarioId) {
    const eid = findEpisodeForScenario(data, scenarios, scenarioId);
    if (!eid) return null;
    const ep = data.episodes.find((e) => e.id === eid);
    const ti = ep?.terminal_info;
    if (ti?.score != null) return ti.score;
    if (ep?.total_reward != null) return (ep.total_reward * 100).toFixed(1);
    return null;
  }

  function updateRunHud(data) {
    const nEp = data.episodes?.length ?? 0;
    const model = data.run?.config?.agent_config?.model ?? "—";
    const ms = data.run?.scores?.mission_score ?? data.run?.scores?.mean_reward;
    document.getElementById("runHud").textContent =
      `${nEp} episodes · ${model}` + (ms != null ? ` · score ${Number(ms).toFixed(1)}` : "");
  }

  function buildRail(data, scenarios) {
    const rail = document.getElementById("episodeRail");
    rail.innerHTML = "";
    let firstId = null;

    for (const tier of TIER_ORDER) {
      const group = scenarios.tiers?.[tier] || [];
      if (!group.length) continue;
      const tierEl = document.createElement("p");
      tierEl.className = "tier-label";
      tierEl.textContent = tier;
      rail.appendChild(tierEl);

      for (const sc of group) {
        const eid = findEpisodeForScenario(data, scenarios, sc.id);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ep-btn" + (eid ? "" : " missing");
        btn.dataset.scenarioId = sc.id;
        btn.dataset.episodeId = eid || "";
        const score = episodeScoreForScenario(data, scenarios, sc.id);
        btn.innerHTML =
          score != null
            ? `${sc.name}<br><span class="ep-score">score ${score}</span>`
            : `${sc.name}<br><span class="ep-score">no run</span>`;
        if (eid) {
          btn.addEventListener("click", () => {
            document.querySelectorAll(".ep-btn").forEach((b) =>
              b.classList.toggle("active", b.dataset.episodeId === eid),
            );
            if (window.__demoApp) window.__demoApp.setEpisode(eid);
            else window.__pendingEpisodeId = eid;
          });
          if (!firstId) firstId = eid;
        }
        rail.appendChild(btn);
      }
    }

    if (firstId) {
      window.__pendingEpisodeId = firstId;
      const firstBtn = rail.querySelector(`[data-episode-id="${firstId}"]`);
      if (firstBtn) firstBtn.classList.add("active");
    }
    return firstId;
  }

  function loadReplayScript() {
    return new Promise((resolve, reject) => {
      if (window.REPLAY) {
        resolve(window.REPLAY);
        return;
      }
      const s = document.createElement("script");
      s.src = `data/replay.js?ts=${Date.now()}`;
      s.onload = () => resolve(window.REPLAY);
      s.onerror = () => reject(new Error("replay.js failed"));
      document.head.appendChild(s);
    });
  }

  async function loadJson(url) {
    const res = await fetch(`${url}?ts=${Date.now()}`);
    if (!res.ok) throw new Error(`${url} HTTP ${res.status}`);
    return res.json();
  }

  async function main() {
    let scenarios;
    try {
      scenarios = await loadJson("data/scenarios.json");
    } catch (err) {
      console.warn("scenarios fetch", err);
      const embedded = document.getElementById("scenarios-json");
      if (embedded) scenarios = JSON.parse(embedded.textContent);
      else {
        showError("Could not load scenarios.json");
        return;
      }
    }

    let data;
    try {
      data = await loadJson("data/replay.json");
    } catch (err) {
      console.warn("replay fetch", err);
      try {
        data = await loadReplayScript();
      } catch (e2) {
        showError("Could not load replay data.");
        return;
      }
    }

    if (!data?.episodes?.length) {
      showError("Replay has no episodes.");
      return;
    }

    buildRail(data, scenarios);
    updateRunHud(data);

    try {
      const catRes = await fetch(`data/orbit-catalog.json?ts=${Date.now()}`);
      if (catRes.ok) {
        globalThis.__ORBIT_CATALOG = await catRes.json();
      }
    } catch (err) {
      console.warn("orbit-catalog load failed", err);
    }

    try {
      const { startDemo } = await import("./demo-main.js");
      await startDemo({ data, scenarios });
    } catch (err) {
      console.error("demo-main load failed", err);
      const mount = document.getElementById("viewportMount");
      if (mount) {
        mount.textContent = `3D view failed to load (${err.message}). Scenario list above should still work after refresh.`;
      }
      document.getElementById("runHud").textContent += " · 3D unavailable";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => main().catch(console.error));
  } else {
    main().catch(console.error);
  }
})();
