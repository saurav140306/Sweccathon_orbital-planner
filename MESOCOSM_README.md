# Orbital Planner — Mesocosm Environment

Plan impulsive burns to rendezvous with a **moving satellite or moon** in 2D Earth orbit. Physics: RK4 gravity (Earth + optional moon third-body), Keplerian target motion, Lambert optimal baseline.

**Gallery:** https://saurav140306.github.io/Sweccathon_orbital-planner/

## Repo layout (Mesocosm pipeline)

All sandbox entrypoints at the **repository root** (platform clones the repo and runs `adapter.py` from root):

```
benchanything.json   manifest
env.py               OrbitalPlannerEnv (BaseEnv)
adapter.py           HTTP adapter (sandbox entrypoint)
orbital_planner/     physics engine
showcase/            interactive replay UI (GitHub Pages)
test_env.py          determinism + smart vs dumb policy tests
.github/workflows/pages.yml   deploy showcase/
```

## Local dev

```powershell
pip install swecc-mesocosm
pip install -r requirements.txt
py -3.13 -m pytest test_env.py -q
mesocosm validate benchanything.json
python adapter.py
```

## Submit & run (platform)

```powershell
Remove-Item Env:MESOCOSM_LOCAL -ErrorAction SilentlyContinue
mesocosm auth login
mesocosm env submit --name "Orbital Planner" --github-url https://github.com/saurav140306/Sweccathon_orbital-planner --solo
mesocosm env list
mesocosm run create --domain DOMAIN_ID --vow-version 1.0.0 --model gemini/gemini-3.1-flash-lite --episodes 8 --visibility gallery_public --solo
mesocosm run export RUN_ID -o showcase/data/replay.json
# regenerate replay.js for file:// and Pages:
# python -c "import json; from pathlib import Path; p=json.loads(Path('showcase/data/replay.json').read_text()); Path('showcase/data/replay.js').write_text('window.REPLAY = '+json.dumps(p)+';\\n')"
```

## Agent action format

```json
{"burns":[{"time_s":0,"dv":[0.05,0.02]}],"reasoning":"Mesocosm trace…","commit":true}
```

Units: km, km/s, seconds. Max 5 steps per episode (parse retries allowed; `max_steps` ≤ 35 in manifest).
