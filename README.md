# Sweccathon_orbital-planner

**Orbital Planner** — SWEccathon AGI & real-world modeling. Claude plans impulsive burns; Python simulates 2D gravity (RK4) and scores against a Lambert optimal baseline.

**Repository:** https://github.com/saurav140306/Sweccathon_orbital-planner

## Monorepo

```
backend/              FastAPI + NumPy physics + Anthropic agent
frontend/             React + Vite + Canvas viewport
env.py, adapter.py    Mesocosm sandbox entrypoints (repo root)
benchanything.json    Mesocosm manifest (repo root)
showcase/             GitHub Pages gallery replay
orbital_planner/      Env implementation package
```

## Mesocosm

Mesocosm files live at the **repo root** (`env.py`, `adapter.py`, `benchanything.json`, `showcase/`).

```powershell
mesocosm validate benchanything.json
python adapter.py
```

Submit with `--github-url https://github.com/Dirac3011/Sweccathon_orbital-planner`

Showcase (GitHub Pages): `showcase/index.html` → https://dirac3011.github.io/Sweccathon_orbital-planner/

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

Open http://localhost:5173 — API proxied to :8000.

### Live Claude (optional)

```powershell
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...

# frontend/.env
VITE_ANTHROPIC_LIVE=1
```

Without `VITE_ANTHROPIC_LIVE`, the UI uses the analytical Hohmann mock planner (no API key).

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scenarios` | List ~14 scenarios by tier |
| POST | `/api/run` | Plan + score (`scenario_id`, `use_mock`) |
| POST | `/api/run/stream` | SSE: reasoning chunks + complete |
| POST | `/api/run-all?use_mock=true` | Benchmark all scenarios |

## Physics & scoring

- Central body: Earth, μ = 398600 km³/s², R = 6371 km  
- RK4 @ 10 s, impulsive Δv  
- `optimal_dv`: Lambert grid search (`lamberthub`), Hohmann fallback when collinear  
- Score: proximity + fuel + budget blend (varies per scenario)
- Moon targets: third-body gravity (μ☾ ≈ 4903 km³/s²)
- Moving elliptical targets via Kepler propagation

## Tests

```powershell
cd backend && py -3.13 -m pytest -v
```

Hohmann sanity on `intercept-01` expects score ≥ 95.
