# Writing a PlanBench algorithm plugin

For someone outside this repository who wants their planner benchmarked
here. You need one dependency — `planbench_plugin_sdk` — and you never
edit the simulation loop.

Three roles: **global** (produces a path), **local** (produces velocity
commands, follows a path), **monolithic** (produces velocity commands,
has no path). Pick by what your algorithm *is*, not by what is easiest
to declare — the role decides what the platform may conclude about it.

---

## 1. The shape of a bundle

```text
my_planner/
  __init__.py
  planner.py
  .planbench-plugin/
    plugin.json          <- the manifest; read without importing anything
```

The manifest is read as text. **Your code is not imported during
discovery**, which is why a bundle with a broken dependency still shows
up in the roster with a reason instead of taking discovery down.

## 2. The manifest

```json
{
  "plugin_api": "1.1.0",
  "id": "org.yourlab.my-planner",
  "version": "0.1.0",
  "role": "local",
  "runtime": {
    "supported_lanes": ["python_in_process"],
    "production_lane": "python_in_process",
    "profiles": {
      "python_in_process": {
        "protocol": "planbench-inproc/v1",
        "codec": "python-object/v1",
        "deadline_policy": "control-period",
        "entry_point": "my_planner:MyPlanner",
        "python_dependencies": ["numpy"]
      }
    }
  },
  "requirements": {
    "all_of": ["planbench://channel/legacy-observation@1"],
    "any_of": [],
    "optional": []
  },
  "supports": {
    "action_types": ["continuous-velocity@1"],
    "robot_dynamics": ["differential-drive@1"],
    "execution_models": ["synchronous-step@1"]
  },
  "config_schema": {"type": "object", "properties": {}},
  "requires_global_path": true
}
```

Fields worth understanding rather than copying:

**`production_lane`** is part of your candidate's identity. It is the
lane you are measured in, and the host will not silently fall back to
another one — measuring a subprocess plugin in-process would compare
your transport with somebody else's.

**`python_dependencies`** are checked with `find_spec`, which locates a
module without running it. A missing one leaves you *registered and not
runnable*, with the module named. That is the difference between "your
plugin is broken" and "this machine has not got torch".

**`requirements`** are capabilities, not a wish list. Anything in
`all_of` must be granted or you do not run; anything in `optional` you
must genuinely work without — the conformance suite checks that by
withholding each one, because the host believes the label.

**Requirement spellings are canonicalised.** `lidar_2d` and
`planbench://channel/lidar-2d@1` are the same capability and produce the
same candidate id; write either.

## 3. The object

### Local / monolithic

```python
class MyPlanner:
    def __init__(self, gain: float = 1.0):     # keys of config_schema
        self._gain = gain

    @property
    def name(self) -> str:                      # appears in every trace
        return "my_planner"

    @property
    def control_period(self) -> float | None:   # None = every sim step
        return None

    def reset(self, request) -> None:
        """New episode segment. request.global_path, request.robot,
        request.declared."""

    def step(self, request):
        """One control tick. request.state, request.channels."""
        return {"linear_velocity": 0.4, "angular_velocity": 0.0}
```

**What `step` returns depends on your lane, and getting it wrong is
silent.** In the **subprocess** lane return a plain mapping, as above:
the worker converts it, and importing anything from the platform would
defeat the point of a process that holds only your code. In the
**in-process** lane the host requires a `LocalPlanResult`:

```python
def step(self, request):
    from planbench_planning.common.local_base import LocalPlanResult
    from planbench_schemas.robot import SimAction

    return LocalPlanResult(action=SimAction(linear_velocity=0.4, angular_velocity=0.0))
```

A mapping returned in-process is not an error. The host records an
invalid output and substitutes a **safe stop**, so the episode runs to
its end with a robot that never moves and nothing raises anywhere. If
your controller is mysteriously stationary, this is the first thing to
check.

So the in-process lane costs you a second dependency — `planbench_planning`
for `LocalPlanResult`, `planbench_schemas` for `SimAction`. The "one
dependency" promise at the top of this guide holds for the subprocess
lane, which is the lane an imported bundle runs in.

A monolithic plugin is identical except that `requires_global_path` is
`false` and `request.global_path` is empty — the platform does not hand
you a path you said you do not use.

### Global

```python
from planbench_plugin_sdk import GlobalPlanResponse

class MyGlobalPlanner:
    @property
    def name(self) -> str:
        return "my_global"

    def plan(self, request):
        """request.start, request.goal, request.robot, request.channels."""
        return GlobalPlanResponse(success=True, path=((1.0, 2.0), (3.0, 4.0)))
```

`GlobalPlanResponse` comes from the SDK, so this stays true to "one
dependency" — the host converts it into its own internal result type on
the other side of the boundary. It carries no path length on purpose:
that is a property of the geometry you returned, and a plugin reporting
one could report a number the path does not have.

Return `success=False` with a `failure_reason` when there is no route.
That is a result the platform counts (G1), not an error — raising
instead loses the distinction between "no path exists" and "the planner
broke".

## 4. Reading channels

You get exactly what you declared and were granted. Nothing else is
reachable:

```python
def _payload(request, capability):
    for envelope in request.channels:
        if envelope.capability == capability:
            return envelope.payload
    raise LookupError(f"{capability} was not granted")
```

Each envelope carries `capability`, `cadence`, `produced_at`,
`revision`, `frame_id`, `provenance` and `payload_encoding`. Two of
those repay attention:

**`produced_at` is the truth about age.** When a channel arrives late
and the deployment's freshness policy reuses the previous value, you get
the *previous envelope unmodified* — the timestamp is the real one, so
an age you compute is real. Nothing is ever re-stamped to look current.

**`provenance`** says whether a channel came from the deployment, from
your own bundled provider, or from an oracle. A run fed any oracle
channel produces oracle-class evidence: it can measure an upper bound
and can never be a production recommendation.

## 5. Determinism is not optional

Identical inputs must give identical commands (HĐ-4). Every paired
comparison this platform makes assumes it, and nothing at runtime can
detect its absence — a plugin that consults the clock or an unseeded
generator does not fail, it makes the statistics measure noise.

Draw randomness from something addressable. `reset` hands you
`request.episode_seed`; derive every draw from it plus the thing being
drawn, never from a generator whose state depends on how many times you
were called:

```python
def reset(self, request) -> None:
    self._seed = request.episode_seed

def _draw(self, tick: int, index: int) -> float:
    rng = random.Random((self._seed, tick, index))
    return rng.random()
```

## 6. Check it before anyone runs it

```python
from planbench_plugin_sdk import check_local_plugin, check_global_plugin

report = check_local_plugin(manifest, lambda: MyPlanner(), step_request)
assert report.passed, report.render()

# A global plugin has no step(); it has its own entry point.
report = check_global_plugin(manifest, lambda: MyGlobalPlanner(), plan_request)
```

It checks the role's methods, determinism from two fresh instances, that
your optional channels really are optional — **individually and all at
once**, because "either A or B" is not the same promise as "neither is
required" — that you work with exactly the channels you declared and no
more, and that you do not write into the request the host also hands to
other consumers.

Every finding is returned, never raised: a constructor that throws
becomes a finding too, so you get the whole list in one run.

## 7. See whether the platform can run it

The repository is not installed as a package yet, so the interpreter
needs to be told where the code is. From the repository root:

```sh
# Linux/macOS
export PYTHONPATH=services/simulator:packages/schemas:packages/planning:packages/benchmark:packages/decision:packages/metrics:packages/plugin_sdk

python -m planbench_simulator.host.cli --bundles /path/to/plugins list
python -m planbench_simulator.host.cli --bundles /path/to/plugins check org.yourlab.my-planner
```

`--bundles` belongs to the top-level command, so it comes **before** the
subcommand. (`... cli list --bundles X` is an argparse error, not a
different spelling of the same thing.)

`check` prints the registration state, the resolved provider graph, the
runtime lane, the evidence class, and — when something is wrong — every
blocker at once rather than the first. Exit code 1 means it cannot run,
so it works in CI.

## 8. Worked examples

Three complete bundles live in [`examples/plugins/`](../../examples/plugins):

| Bundle | Shows |
|---|---|
| `corridor_planner` | a **global** plugin outside the registry, planning on the granted costmap channel |
| `social_nav` | a **local** plugin requiring `human_state_estimates` — and therefore oracle-class evidence in this MVP |
| `remote_wanderer` | a plugin in the **subprocess lane**, importing nothing from the platform |

## 9. What the platform will not do for you

- **It will not guess a capability you did not declare.** An undeclared
  read raises; it does not return an empty measurement.
- **It will not pick between two providers of one capability.** A tracker
  and ground truth are different experiments, so an unresolved tie is a
  refusal rather than a choice.
- **It will not fall back to another runtime lane.**
- **It will not treat a crash as a result.** A crash or a missed deadline
  becomes a safe stop recorded in the trace, so the episode says what
  happened instead of ending.

## 10. Isolation, stated plainly

The in-process lane is a **trust policy**, not a boundary: your code can
reach anything the host process can. The subprocess lane adds **crash
and interpreter isolation** — a hang or a crash cannot take the
simulator down — but it is *not* a security sandbox: the worker
inherits the host's environment and its filesystem and network rights.
Running genuinely untrusted code needs a container with dropped
privileges, which this platform does not yet provide.
