# PlanBench — Working Conventions

Agentic AI PlanBench: simulator and benchmark platform for AMR/AGV
path/motion planning. Simulation only — never controls real robots.
No Gazebo; the 2D/2.5D simulator is built in-house.

## Workflow rules

- Work proceeds in approved phases. Do NOT start the next phase, commit,
  or push without explicit user approval.
- Never fabricate run results, metrics, or test output. Report real
  command output only.
- No global package installs, no sudo. Use `.venv` in the repo root.
- Show planned commands (installs, migrations, docker, ROS2) and wait
  for approval before running them.

## Architecture principles

- **Core-first**: `packages/` and `services/simulator/` are pure Python
  libraries — no FastAPI, ROS2, or frontend imports. API/ROS/Gym layers
  are thin adapters over this core.
- **Contract-first**: Pydantic models in `packages/schemas/` are the
  single source of truth for domain types.
- **Determinism-first**: every component takes explicit seeds/config;
  no global mutable state; same input ⇒ same output.

## Technical conventions

- SI units: metres, seconds, radians. Angles normalized to **(-π, π]**
  via `planbench_schemas.geometry.normalize_angle`.
- Shared float tolerance: `EPS = 1e-9` (import from
  `planbench_schemas.geometry`; do not redefine).
- Boundary contact counts as collision (`clearance <= EPS`).
- Occupancy cell values follow ROS convention: FREE=0, OCCUPIED=100,
  UNKNOWN=-1. Grids are row-major, index = `row * width + col`; rows
  grow along world +y, columns along +x.
- Rotated map origins are NOT supported yet: `MapData` rejects
  `origin.theta != 0` (within EPS).
- Kinematics uses explicit Euler exactly as specified:
  `x += v·cosθ·dt; y += v·sinθ·dt; θ = normalize(θ + ω·dt)`.
  Order: clamp velocity → apply acceleration limit → integrate.
- Only OCCUPIED cells are inflation sources; UNKNOWN cells stay UNKNOWN
  unless covered by an occupied cell's inflation disk.

## Commands

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
PYTHONPATH= .venv/bin/pytest tests/ -v --cov=planbench_schemas --cov=planbench_simulator --cov-report=term-missing
```

Run pytest with `PYTHONPATH=` (empty): the user's shell sources ROS2
Jazzy, whose site-packages register a `launch_testing` pytest plugin
that fails to import inside the venv.

Packages are imported from source via pytest `pythonpath` (see
pyproject.toml) — no editable installs yet.

## Current status

Phase 1A complete: schemas, occupancy grid, kinematics, collision.
Next (needs approval): Phase 1B — LiDAR, A*, pure-pursuit (temporary
adapter only, not a benchmark algorithm), SimulationEngine, metrics.
Later benchmarks compare stacks (A*+DWA vs A*+PPO), never a global
planner against a local planner directly.
