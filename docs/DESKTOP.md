# PlanBench as a Windows desktop application

One installer, one machine, one person. No Docker, no Node, no Python to
install first — the build carries its own interpreter.

This document is for two readers: somebody who has been handed
`PlanBench-Setup-x.y.z.exe`, and somebody who has to build the next one.

---

## For the person running it

### Installing

Run `PlanBench-Setup-x.y.z.exe`. It installs under
`%LOCALAPPDATA%\Programs\PlanBench` and asks for no administrator
rights. Windows SmartScreen will warn that the publisher is unknown —
the installer is not code-signed (see [What is not done yet](#what-is-not-done-yet));
choose **More info → Run anyway**.

### First launch

The app creates `%LOCALAPPDATA%\PlanBench` and writes a `.env` there
holding a generated password for the local account. Sign in with the
nickname `admin` and that password; both are printed in
`%LOCALAPPDATA%\PlanBench\logs\planbench.log` on the first run and stored
in `.env` beside it.

The `admin` account is created **once**, and it is the only account that
may import an algorithm or set the API key — `PLANBENCH_ADMIN_NICKNAMES`
is read when an account is created and never again, so editing it later
has no effect on an account that already exists.

### Connecting a model

Open **Settings** in the sidebar, paste an OpenAI API key, and save. The
key takes effect immediately — no restart — and is written to
`%LOCALAPPDATA%\PlanBench\.env` so it survives one. This version is
wired to `o4-mini`; the model list exists to grow, and today it has one
entry.

Without a key the assistant answers from an offline keyword responder,
and the Settings page says so rather than letting a green tick imply a
model is answering.

### Where your data lives

Everything you create is under `%LOCALAPPDATA%\PlanBench`:

| | |
|---|---|
| `planbench.db` | deployments, comparison runs, decision cards, approvals |
| `artifacts\` | trajectories, traces, imported algorithms, uploaded models |
| `maps\`, `profiles\` | stock copies plus anything you edit or draw |
| `.env` | the local account, the session secret, the API key |
| `logs\planbench.log` | what to send when something goes wrong |

Upgrades never touch this directory. Uninstall **asks** before deleting
it and the default answer is No — a comparison run costs machine-hours
to reproduce. Back it up as one unit: the database stores artifacts by
path, so a database restored without its `artifacts\` has rows that
point at nothing.

### Updates

On launch the app asks GitHub whether a newer desktop release exists. If
one does, it offers it once; declining is a real answer and it will ask
again next time. Accepting downloads the installer, **verifies it
against the hash the release publishes**, closes the app, installs, and
reopens it.

The repository is private, so the check needs a read-only GitHub token
in `%LOCALAPPDATA%\PlanBench\.env`:

```
PLANBENCH_UPDATE_TOKEN=github_pat_...
```

A fine-grained token scoped to this repository with **Contents:
read-only** is enough. Without one the app never checks and says so once
in the log — which is the right behaviour for a machine deliberately
kept off the network.

### When it does not open

Read `%LOCALAPPDATA%\PlanBench\logs\planbench.log`. The launcher writes
there before anything else can fail, because the app runs under
`pythonw.exe` and has no console to print to.

---

## For the person building it

### What the build machine needs

* **CPython 3.12** reachable as `py -3.12`. The same minor version the
  installer ships, and not a detail: pip builds C extensions for the
  interpreter it is running on, so 3.13 here produces a numpy the
  shipped 3.12 cannot import — and the error names the module, not the
  cause.
* **Node 22** for the web export.
* **Inno Setup 6** (`iscc`) for the installer.

### Building

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
```

The interpreter is already pinned (3.12.10 — the last 3.12 that
publishes an embeddable zip; `.11` and `.12` are source-only). If you
ever change that version, `installer\python-embed.json` must get a new
`sha256` and the build **refuses to run without one**: an unpinned
download is a supply chain owned by whoever can answer for the host, and
a hash the build computed for itself would pin nothing at all. The
current value was established by matching the archive against the MD5
python.org publishes on its release page.

`py -3.12` is tried first for the pip step but is not required — the
script also searches the launcher's inventory and uv's interpreters, so
a 3.12 installed by `uv python install 3.12` is found even though the py
launcher never learns about it.

Useful switches: `-SkipWeb` reuses an existing export, `-SkipInstaller`
stops after the smoke gate and leaves a runnable stage in `build\stage`.

### Releasing

```powershell
# bump apps\desktop\planbench_desktop\VERSION first
git tag desktop-v0.2.0
git push origin desktop-v0.2.0
```

`.github/workflows/desktop-release.yml` builds on `windows-latest`, runs
the same script (and therefore the same gate), writes `latest.json` with
the installer's hash, and publishes both as release assets. It refuses
to build if the tag and the `VERSION` file disagree — otherwise the
release is named one thing, the installed app reports another, and the
updater offers the same update forever.

### How it is put together

```
%LOCALAPPDATA%\Programs\PlanBench\
  runtime\     embedded CPython + python312._pth + site-packages
  app\         the source tree, directories intact
  web\         the exported UI, served by the API
  planbench.ico
```

Four decisions carry the design, and each answers something that broke
or would have:

**No freezer.** PyInstaller would have broken the plugin subprocess lane
in two places at once: it spawns `sys.executable`, which in a frozen app
is the app itself rather than a Python, and `candidates.py` calls
`inspect.getsource` to compute a controller version, which needs `.py`
files a freezer strips. An embedded interpreter beside the real source
tree keeps both working, and Alembic's dynamically imported revisions
with them.

**The path file is generated, never written by hand.** An embeddable
Python resolves imports from `python312._pth` and nothing else.
`scripts/desktop/make_runtime_paths.py` builds it from the source-root
list in `pyproject.toml` — the same list pytest and `dev_stack.sh` read.
Three hand-maintained copies of that list already exist and one of them
drifted; a fourth would be a fourth chance at the same bug.

**`sitecustomize.py` hands `PYTHONPATH` back.** A `._pth` interpreter
ignores that variable, and `subprocess_lane._environment` uses it to
tell a worker where an imported algorithm lives. Without this the worker
starts, cannot import the plugin, and the host reads that as an
algorithm that stops the robot — a path problem wearing a robotics
costume.

**The API serves the web UI.** One origin, so there is no CORS to
configure, no second port to find free, and no API URL baked into the
JavaScript at build time. Deep links into `/decisions/<id>` and the two
other record routes are served the exported shell for that route, which
reads the real id after it hydrates.

### The gate

`scripts/desktop/smoke_stage.py` runs **between** assembling the stage
and packaging it, using the staged interpreter, and a failure stops the
release. Everything it checks is invisible to the test suite, because
the suite runs on a normal CPython from a checkout where none of these
mechanisms exist:

1. every declared source root imports,
2. a child process still sees `PYTHONPATH`,
3. a real plugin runs out of process through the lane,
4. the launcher provisions, migrates, serves and stops,
5. the exported UI answers, including a deep link.

It has already earned its place: it caught the launcher writing
`PLANBENCH_DATABASE_URL` to `.env` without exporting it, which the unit
test had masked by setting the variable itself. That build would have
installed cleanly and failed on the first migration.

The cheap half of the same coverage lives in
`tests/desktop/test_desktop_packaging.py` and runs with every other
test: that the path file names every root, that the shortcut points at a
launcher that exists, that the interpreter is pinned.

### What is not done yet

Code signing (hence the SmartScreen warning) · delta updates, so each
update downloads the whole installer · a tray icon · OAuth sign-in, since
dev login is what a single-user machine needs · torch/PPO, MLflow and
PostgreSQL, which degrade cleanly by design · macOS and Linux.

One limit is not a gap to close: decision runs are queued **one at a
time**, because HĐ-7.4 forbids two evaluation runs on one machine at
once — both pin the same cores and each becomes the other's background
load. That is a measurement contract, not a performance setting.
