# Orbital Planner

**Orbital Planner** — SWEccathon AGI & real-world modeling. Plan impulsive burns to rendezvous with moving satellites or moons in 3D Earth orbit; the **Mesocosm AI** agent explains strategy and outcomes; a deterministic physics engine scores every flight.

**Repository:** https://github.com/saurav140306/Sweccathon_orbital-planner

## Monorepo

```
backend/          FastAPI · 3D RK4 physics · Mesocosm AI agent · scoring
frontend/         React · Vite · Three.js viewport · calculations panel
orbital-planner/  Mesocosm bench package (env.py, adapter.py, showcase/)
```

## How a mission run works

1. **Turn 1 — Mesocosm AI planning**  
   The agent reads the scenario (chaser state, target orbit, fuel budget, time limit) and returns a JSON plan: burn schedule + plain-English reasoning with orbital calculations.

2. **Physics simulation**  
   Burns are applied as instant Δv kicks; the chaser is integrated forward in 3D with RK4. Scores come **only** from this simulation — the AI does not invent miss distance or points.

3. **Turn 2 — Mesocosm AI outcome**  
   The agent receives the simulation results and score breakdown and explains what happened, how the score was calculated, and what could improve.

4. **UI**  
   The orbital viewport, **Orbital calculations** panel (live formulae + numbers), **Mesocosm reasoning**, and **Score breakdown** update together. Previous runs are remembered per scenario when you switch missions.

---

## Quick start

### Backend

```powershell
cd backend
py -3.13 -m pip install -r requirements.txt
py -3.13 -m pytest -q
py -3.13 -m uvicorn main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — API at http://127.0.0.1:8000.

### Mesocosm AI (Ollama)

Planning and reasoning use an OpenAI-compatible endpoint (default: local Ollama).

```powershell
ollama pull llama3.2
ollama serve
```

Copy `.env.example` to `backend/.env`:

```env
MESOCOSM_MODEL=ollama/llama3.2
MESOCOSM_API_BASE=http://localhost:11434/v1
MESOCOSM_API_KEY=mesocosm
```

`GET /api/config` reports whether Mesocosm AI is reachable. Without Ollama, runs fail unless you pass `use_mock=true` (analytical Hohmann baseline only, no LLM).

---

## Orbital calculations (formulae)

All missions use an **Earth-centered inertial (ECI)** frame. Units: km, km/s, seconds.

### Constants

| Symbol | Value | Meaning |
|--------|-------|---------|
| μ⊕ | 398600 km³/s² | Earth gravitational parameter |
| R⊕ | 6371 km | Earth radius — impact if chaser radius &lt; R⊕ → **crash**, score 0 |

### Target orbit (Keplerian)

The target moves on a conic in 3D (circular or elliptical, optionally inclined):

**Orbit equation (in the orbital plane):**

\[
r = \frac{a(1 - e^2)}{1 + e \cos\nu}
\]

| Symbol | Meaning |
|--------|---------|
| \(a\) | Semi-major axis (km) |
| \(e\) | Eccentricity (0 = circle) |
| \(\nu\) | True anomaly (angle along orbit, deg in UI) |
| \(i\) | Inclination — tilt above equator |
| \(\Omega\) | RAAN — rotation of the orbit plane |

**Energy and momentum:**

\[
\varepsilon = \frac{v^2}{2} - \frac{\mu}{r}, \qquad \mathbf{h} = \mathbf{r} \times \mathbf{v}
\]

**Periapsis / apoapsis:** \(r_p = a(1-e)\), \(r_a = a(1+e)\).

The calculations panel shows the target’s **instantaneous** radius \(r\), speed \(|v|\), and \(\nu\) at the scrub time **T+t**.

### Chaser propagation

- **Before a plan:** chaser coasts on its initial ellipse.
- **After a plan:** positions come from the simulated trajectory at **T+t**.

**Impulsive burns:**

\[
\mathbf{v} \rightarrow \mathbf{v} + \Delta\mathbf{v}
\]

applied at scheduled `time_s`. Total fuel used:

\[
\Delta v_{\text{used}} = \sum_i \|\Delta\mathbf{v}_i\|
\]

### Gravity model

**Earth (always):**

\[
\mathbf{a}_\oplus = -\mu_\oplus \frac{\mathbf{r}}{|\mathbf{r}|^3}
\]

**Moon targets (restricted 3-body):** moon on a fixed Kepler orbit; chaser feels Earth + moon:

\[
\mathbf{a}_\moon = \mu_\moon \frac{\mathbf{r}_\moon - \mathbf{r}}{|\mathbf{r}_\moon - \mathbf{r}|^3}
\]

**Integration:** 4th-order Runge–Kutta (RK4), step **Δt = 10 s**, up to the scenario time limit.

### Rendezvous metrics (from simulation)

| Metric | Definition |
|--------|------------|
| **Miss (3D)** | Minimum distance between chaser and target positions over the trajectory (km) |
| **Closest approach time** | Mission time \(t\) when miss is smallest |
| **Plane offset** | Cross-track separation at closest approach (km) — important for inclined orbits |
| **Optimal Δv** | Lambert / Hohmann baseline for comparison (`lamberthub` with Hohmann fallback) |

---

## Mesocosm reasoning

Reasoning is produced by **Mesocosm AI** (`backend/orbital_planner/mesocosm_agent.py`), not hardcoded per scenario.

### Turn 1 — Planning

The model returns JSON:

```json
{
  "burns": [{"time_s": 0, "dv": [dx, dy, dz]}],
  "reasoning": "Plain-English mission trace with calculations…",
  "commit": true
}
```

Expected content in `reasoning`:

1. What the mission is (goal, target type, constraints)  
2. Risks in simple terms (inclination, fuel, time)  
3. Transfer strategy  
4. Burn schedule (when, how much Δv, direction)  
5. Fuel budget check  
6. Commit decision  

The AI must **not** invent post-simulation scores in Turn 1.

### Turn 2 — Outcome

After `score_mission()` runs, Mesocosm AI receives authoritative numbers (miss, fuel, components, orbital snapshot at closest approach) and writes a short narrative:

- Did we meet the tolerance?  
- How proximity / fuel / budget produced the final score  
- One suggestion to improve  

If the LLM is unavailable, a computed template (`format_simulation_outcome`) is used instead.

### Offline mock (`use_mock=true`)

Analytical **Hohmann** burns only — no Mesocosm AI. Useful for tests and CI. Reasoning is a short baseline note; scoring still uses the full physics engine.

---

## Reward and score breakdown

Scoring is **deterministic** (`backend/orbital_planner/reward.py`). Same plan → same score.

### Weights (must sum to 100% of the blend)

| Component | Weight | What it measures |
|-----------|--------|------------------|
| **Reach target** | **75%** | 3D proximity to the moving target |
| **Fuel efficiency** | **10%** | Used Δv vs optimal transfer Δv |
| **Budget headroom** | **15%** | How much of the fuel allowance remains |

### Proximity (main score driver)

Define a scale (more forgiving on easy tiers):

\[
\text{miss\_scale} = \text{tolerance} \times 58 \times \text{tier\_mult} \times (1 + 0.12 \sin i)
\]

Tier multipliers: easy **1.65**, medium **1.35**, hard **1.05**, expert **0.95**.

\[
\text{miss\_ratio} = \frac{\text{miss}}{\text{miss\_scale}}, \quad
\text{plane\_ratio} = \frac{\text{plane\_offset}}{\text{miss\_scale}}
\]

\[
\text{proximity} = \frac{1}{1 + \text{miss\_ratio}^{0.52} + 0.07 \cdot \text{plane\_ratio}^{0.52}}
\]

**Tolerance bonuses** (floor on proximity):

- If miss ≤ tolerance: proximity ≥ \(0.90 + 0.10(1 - \text{miss}/\text{tolerance})\)  
- If miss ≤ 5× tolerance: additional floor ramps from 0.50 to 0.90  

`hit_score` in the API is this proximity value (0–1).

### Fuel and budget terms

\[
\text{fuel\_score} = \min\left(1,\ \frac{\Delta v_{\text{optimal}}}{\Delta v_{\text{used}}}\right)
\]

\[
\text{budget\_score} = \max\left(0,\ 1 - 0.65 \cdot \frac{\Delta v_{\text{used}}}{\text{fuel\_budget}}\right)
\]

Only **65%** of used fuel counts against the budget term (slightly lenient).

### Final score

\[
\text{raw} = 100 \times (0.75 \cdot \text{proximity} + 0.10 \cdot \text{fuel\_score} + 0.15 \cdot \text{budget\_score})
\]

**Over-budget penalty** (subtracted from raw):

\[
\text{penalty} = \min\left(0.10,\ \max(0,\ \Delta v_{\text{used}} - \text{fuel\_budget}) \times 0.10\right)
\]

\[
\text{score} = \max(0,\ \text{raw} - 100 \times \text{penalty})
\]

**Crash** (radius &lt; 6371 km): score **0**, miss = ∞.

### Reading the Score breakdown panel

| UI label | Meaning |
|----------|---------|
| **Reach target** | Proximity × 100% |
| **Miss (3D)** | Closest approach distance (km) |
| **Plane offset** | Cross-track miss at closest approach |
| **Closest approach** | Time of minimum miss (s) |
| **Fuel used** | Sum of \|Δv\| (km/s) |
| **vs optimal** | fuel_ratio × 100% |
| **75% / 10% / 15% rows** | Point contribution from each component |
| **Over-budget penalty** | Points deducted if over fuel cap |
| **Large number** | Final score / 100 |

The **Orbital calculations** panel shows the same formulae as strings when a run has completed.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Mesocosm AI availability, model name |
| GET | `/api/scenarios` | List scenarios by tier |
| GET | `/api/calculations` | Orbital snapshot at `t_s` |
| POST | `/api/calculations` | Snapshot with score payload after a run |
| POST | `/api/run` | Plan + simulate + score |
| POST | `/api/run/stream` | SSE: `reasoning`, `score_reasoning`, `complete` |
| POST | `/api/run-all?use_mock=` | Benchmark all scenarios |

**Run body:** `{ "scenario_id": "raise-easy-01", "use_mock": false }`

---

## Mesocosm bench package

The `orbital-planner/` folder is the [Mesocosm](https://mesocosm.swecc.org) environment for platform benchmarking (separate from the local web UI).

```powershell
cd orbital-planner
mesocosm validate benchanything.json
python adapter.py
```

Platform runs use the model you choose in `mesocosm run create` (e.g. Gemini on SWECC). Local dev uses Ollama via `mesocosm run local`. Showcase replay: `orbital-planner/showcase/index.html`.

---

## Tests

```powershell
cd backend
py -3.13 -m pytest -v
```

Covers Hohmann sanity, Lambert baseline, moon gravity, and env determinism.

---

## Summary

| Layer | Role |
|-------|------|
| **Mesocosm AI** | Turn 1 planning + reasoning; Turn 2 score narrative |
| **Physics (RK4)** | Truth for trajectories, miss, crash |
| **reward.py** | Truth for all numeric scores |
| **Calculations panel** | Live orbital math at scrub time |
| **Mock planner** | Optional Hohmann-only path (`use_mock=true`) |

For a walkthrough of each calculations row in the UI, see the in-app **Orbital calculations** panel while scrubbing the timeline before and after a run.
