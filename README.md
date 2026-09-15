# Sol-Window Planner

**Mars Hackathon · PhysicsX × GirlsWhoML · Track: Vehicles & Mobility (crosses into Life Support)**

Time-aware Mars route finder that plans the fastest safe traverse from a rover's
current position to the nearest viable **water deposit**. Fuses MOLA elevation,
AI4Mars terrain classes, MARCI dust opacity forecasts, and a water-deposit
catalog into a single spacetime cost, wrapped by an LLM that narrates the plan.

## The one ML decision
Predict **time-to-water (sols)** for every reachable deposit under safety +
energy constraints, and pick the route that minimises it.

## Quickstart
```bash
pip install -r requirements.txt
python -m sol_window.demo --start 10,10 --horizon-sols 20
```

## Data layers
| Layer | Source | Role |
|---|---|---|
| Elevation / slope | MOLA DEM (fallback: HiRISE DTM) | Geometric cost |
| Terrain class | AI4Mars labelled tiles | Traversability × energy multiplier |
| Atmospheric opacity τ | MARCI daily + climatology | Time-varying solar generation, storm windows |
| Water deposits | SWIM / neutron spectrometer catalog | Goal set |

## Repo layout
```
sol-window-planner/
├── data/                 # cached rasters, deposit CSV, tau time series
├── src/sol_window/
│   ├── data_io.py        # loaders for MOLA / AI4Mars / MARCI / deposits
│   ├── cost_map.py       # slope + terrain-class → per-cell cost
│   ├── power_model.py    # τ(t) → solar W/m² → drive-hours per sol
│   ├── planner.py        # A*-in-spacetime (x, y, sol)
│   ├── llm_agent.py      # LLM tool-caller (router as a tool)
│   ├── viz.py            # matplotlib animation of route + τ
│   └── demo.py           # end-to-end CLI
├── notebooks/            # scratch exploration
├── demo/                 # rendered gifs / stills for the pitch
└── tests/                # tiny sanity tests
```

## Milestones (hard)
- **18:35 · Scope locked.** Repo up, one MOLA tile + one AI4Mars tile + 1 week τ downloaded, 3 hard-coded deposits.
- **19:15 · Skeleton up.** Static cost map + straight-line baseline ETA rendered.
- **20:00 · Core working.** A*-in-spacetime returns a route + sol ETA; LLM narrates.
- **20:25 · Freeze-ready.** README pinned, demo GIF exported, commits staged.
- **20:35 · Push.**

## Demo money shot
Animated route on a MOLA/AI4Mars tile, τ heatmap sliding in time, rover pausing
through a sol-8 dust storm, ETA counter ticking down.
