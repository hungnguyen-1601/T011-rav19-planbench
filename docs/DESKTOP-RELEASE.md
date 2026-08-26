# Releasing the desktop app — the runbook

**Read this before shipping a version of the Windows desktop build.**
[DESKTOP.md](DESKTOP.md) explains what the app is and how it is put
together; this file is the operating procedure, and it exists because
seven of the eight releases so far each failed for a different reason
that nothing in the code told anyone about in advance.

Written for whoever does the next release — a person, or an agent
picking this project up in a fresh session with no memory of the last
one.

---

## The short version

Run this in the **private** repository. The release appears in the
public one — see [Two repositories](#two-repositories-where-you-tag-and-where-the-release-appears).

```powershell
# 1. Bump the stamp. The tag and this file MUST agree or CI refuses.
#    apps\desktop\planbench_desktop\VERSION   ->  0.1.9

git add apps/desktop/planbench_desktop/VERSION
git commit -m "TongDuyAn - <one English line saying what ships>"
git push origin main

git tag -a desktop-v0.1.9 -m "PlanBench desktop 0.1.9 — <what changed>"
git push origin desktop-v0.1.9
```

That is the whole release. CI builds on `windows-latest`, runs the smoke
gate, and publishes the installer plus `latest.json`. Nothing else to
do; nothing to upload by hand.

Watch it **at one-minute intervals or slower** — see [Rate limit](#the-rate-limit-is-shared-with-the-running-app).

---

## Two repositories: where you tag, and where the release appears

Development lives in the **private organisation repository**
`AI20K-Build-Phase-Cohort-3/P-011`. Releases are published to the
**public repository** `hungnguyen-1601/T011-rav19-planbench`, which no
longer receives code.

| | Repository |
|---|---|
| You push the tag here | `AI20K-Build-Phase-Cohort-3/P-011` (private) |
| CI builds here | same — it is where the source is |
| The release appears here | `hungnguyen-1601/T011-rav19-planbench` (public) |
| People download from here | the public one |

**Why the split is this way round, and not the other.** The permanent
download link *is* the public repository's path, and that same path is
compiled into every installed copy of the app as `updater.REPOSITORY` —
a constant that is deliberately not configurable. Publishing somewhere
else would break the link people were already sent, and would leave
every existing install checking a repository that had stopped
publishing, silently, forever. Distribution cannot move. Source can, and
did.

**What makes it work:** one guard and one secret.

- `.github/workflows/desktop-release.yml` carries
  `if: github.repository == 'AI20K-Build-Phase-Cohort-3/P-011'`. The
  file exists in both repositories — it arrived in the public one with
  the copied history — and the guard is what stops a tag pushed there
  from building a second installer off a frozen tree and publishing it
  over the real one. One file with a guard rather than two files,
  because two copies drift and the drift surfaces at a release.
- `secrets.PUBLISH_TOKEN` in the private repository: a fine-grained PAT
  with `contents: write` on the public repository and nothing else. The
  automatic `github.token` cannot be used — it is scoped to the
  repository the job runs in.

**Two consequences worth knowing before you go looking for them:**

1. The tag in the public repository is created by `gh release create
   --target main`, so it points at that repository's frozen `main`, not
   at the commit that built the installer. Provenance is the identically
   named tag in the private repository, and the SHA the installer stamps
   into its System page — which will not resolve in the public
   repository.
2. The release body is a fixed sentence, not `--generate-notes`.
   Generated notes summarise commits of the repository the build ran in,
   which is the private one. Publishing its commit subjects on a public
   release page is a leak with no upside.

---

## What makes this project's deployment unusual

Six things differ from an ordinary web deployment, and each one has bitten:

### The version lives in three places that must agree

| Where | What it is |
|---|---|
| `apps/desktop/planbench_desktop/VERSION` | the source of truth |
| the git tag `desktop-v<X.Y.Z>` | what triggers the build |
| `latest.json` in the release | what installed apps compare against |

The workflow **fails on purpose** when the tag and the stamp disagree.
Without that check the release is named one thing, the installed app
reports another, and the updater — which compares the tag against the
running `VERSION` — offers the same update forever.

### The download link is permanent, so the asset name must never change

**https://github.com/hungnguyen-1601/T011-rav19-planbench/releases/latest/download/PlanBench-Setup.exe**

That URL resolves only while every release publishes an asset under
exactly that name. Putting the version back into the file name
(`PlanBench-Setup-0.1.9.exe`) silently invalidates every copy of the
link that has been sent out, and the person who finds out is whoever
clicks it. `installer/planbench.iss` sets `OutputBaseFilename=PlanBench-Setup`
and a test pins it.

The version is not in the file name for that reason. It is reported on
the **System** page instead, from the stamp the launcher publishes.

### An updater bug cannot ship its own fix

Every installed copy runs the updater it was built with. When the bug
*is* in the updater, the fix cannot arrive through it — the thing that
would have to fetch the patch is the thing that is broken. This has
happened twice.

When it happens: publish the fix, then tell people to install once by
hand from the permanent link. From that build onward updates flow
again. There is no way around it, and pretending otherwise costs a
round trip.

### A release build carries no `.git`

The installation is a copied source tree. `resolve_git_sha` in
`packages/decision/planbench_decision/card.py` refuses to write a
manifest saying `unknown` — correctly: a manifest that looks complete
and rebuilds nothing is worse than an error.

`scripts/build_desktop.ps1` therefore stamps the commit into
`apps/desktop/planbench_desktop/COMMIT`, and the launcher publishes it
as `PLANBENCH_GIT_SHA` before anything reads configuration. **Do not
weaken the refusal to make a card write.** If a card cannot name its
commit, the stamp is missing — fix the stamp.

### Migrations run on the user's machine, unattended

The launcher runs `alembic upgrade head` on every launch and copies the
database to `planbench.db.bak` first. A migration that fails leaves the
app unable to open, with nobody watching a terminal — so a release that
adds a migration deserves a real check that it applies to an *existing*
database, not only to a fresh one.

### The rate limit is shared with the running app

GitHub's anonymous API allows **60 requests per hour, per IP address**,
and the installed app used the same allowance from the same machine.
Polling a build every 30 seconds exhausts it and the app starts
answering `403` to its own update check. That happened, and it looked
like a bug in the updater.

It happened a second time with nothing polling at all — ordinary use of
git and the API from a developer's machine was enough. 0.1.13 shipped
and the 0.1.12 beside it went on saying it was current, because its
check got a 403 and a failed check is silent by design.

**From 0.1.14 the app's check no longer touches the API.** It reads
`releases/latest/download/latest.json`, which the release CDN serves
without any rate limit, and falls back to the API only when that
manifest is unusable. An update now costs zero API calls end to end.
Older installs still use the API and can still be starved; a token in
their `.env` is the only fix for those, and installing 0.1.14 by hand is
the better one.

When watching a build **from this machine**, still poll at 60-second
intervals or slower, and prefer that same manifest over `/actions/runs`
— or authenticate, which moves you to a separate 5000-an-hour budget
and leaves the anonymous one for anything that cannot.

---

## Building locally

Only needed to reproduce a CI failure or to test a change to the
packaging itself. A normal release does not need it.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
# -SkipWeb        reuse an existing export
# -SkipInstaller  stop after the smoke gate, leave build\stage runnable
```

**On this machine specifically** (An's laptop, where every release so
far was built):

* Inno Setup is installed but **not on PATH** — the script falls back to
  `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`, which is where it is.
* CPython 3.12 exists only as a **uv-managed interpreter**, which the
  `py` launcher does not know about. `py -3.12` answers "No suitable
  Python runtime found"; the script also searches uv's directory. The
  repo `.venv` is 3.13 and is **not** usable for the pip step — pip
  builds C extensions for the interpreter it runs on, and a 3.13 numpy
  cannot be imported by the shipped 3.12.
* `dist\` may still hold an installer from an older build. The workflow
  publishes `dist\PlanBench-Setup.exe` by name for that reason.

Leaving `dist/` and `build/` around is fine — both are gitignored.

---

## The smoke gate is the release gate

`scripts/desktop/smoke_stage.py` runs **between** assembling the stage
and packaging it, **using the staged interpreter**, and a failure stops
the release. It checks what the test suite structurally cannot, because
the suite runs on a normal CPython from a checkout where none of these
mechanisms exist:

1. every declared source root imports;
2. a child process still sees `PYTHONPATH` (an embeddable Python with a
   `._pth` ignores it, and the plugin subprocess lane passes an imported
   algorithm's location through it);
3. a real plugin runs out of process through the lane;
4. the launcher provisions, migrates, serves and stops;
5. a decision card could name the commit that produced it;
6. the exported UI answers, including a deep link.

It has already caught three bugs that every unit test passed over. When
it fails, read what it says before changing anything — it names the
mechanism, not a symptom.

---

## Verifying a release actually landed

Three checks, in order of how much they prove:

```bash
# 1. The permanent link points at the new tag.
curl -sI ".../releases/latest/download/PlanBench-Setup.exe" | grep -i location

# 2. The manifest says the version you shipped.
curl -sL ".../releases/latest/download/latest.json"

# 3. The strongest: download through the link and match the hash the
#    manifest declares — the same check the updater makes before it
#    will run anything.
```

On a machine with the app installed, the evidence is on disk:

| File | What it answers |
|---|---|
| `%LOCALAPPDATA%\PlanBench\logs\planbench.log` | which version started, what the update check found |
| `%LOCALAPPDATA%\PlanBench\updates\apply-update.cmd` | the exact commands the update ran |
| `%LOCALAPPDATA%\PlanBench\updates\apply-update.txt` | the installer's exit code |
| `%LOCALAPPDATA%\PlanBench\updates\installer.log` | Inno's own log |

Those last three exist from 0.1.6 onward. Before diagnosing an update
that "did nothing", read them — every update failure so far was
explained by one of them, and none was explained by guessing.

---

## Local state on the machine that has been testing

Facts that will confuse a fresh session otherwise:

* The app is installed at **`F:\PlanBench`**, not the default
  `%LOCALAPPDATA%\Programs\PlanBench` — chosen during a manual install.
  Find it from the registry rather than assuming:
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall` → `PlanBench`.
* Data lives at `%LOCALAPPDATA%\PlanBench` regardless, and survives both
  upgrade and uninstall (uninstall asks, default No).
* Sign in with **`admin` / `admin`**. Temporary and deliberate — see
  DESKTOP.md. `.env` is written once, but the password is now reconciled
  with `PLANBENCH_SEED_USERS` on every launch, so editing that line and
  reopening does change it.

---

## Known-red things that are not your fault

Do not chase these when a release goes out; none of them blocks the
desktop build, and the `desktop release` workflow is independent of CI.

* **CI on `main` is red**, and was before this work: `ruff format --check`
  wants 26 files reformatted, and `tests/test_trace_review.py` imports
  `pandas`, which is declared in no requirements file — pytest dies at
  collection. Both predate the desktop work and both belong to whoever
  owns those files.
* **12 golden tests fail** (`test_host_parity_golden`,
  `test_dwa_core_refactor`, `test_decision_export_golden`). Never
  classified as pre-existing or not. Deferred deliberately.
* **8 errors in `test_outcome.py`** — `UnicodeDecodeError` on cp1252,
  the Windows encoding debt the repo already records.
* **The plugin tests are flaky.** `test_a_re_import_of_the_same_version_is_refused`
  and `test_the_same_archive_cannot_be_imported_twice` failed once in a
  combined run and passed on every rerun, individually and together.
  Suspected shared plugin-extraction directory. Not diagnosed.

---

## Rules this project follows

* Commit messages: `TongDuyAn - ` then **one line, English**. Detail
  goes in a report under `docs/antongduy/reports/<date>/`, not in the
  message.
* Never commit `vfh_plus_import/`, `vfh_plus_iterated/`, or
  `planbench.db.bak-*`.
* Do not run the full test suite as a matter of course — test what
  changed. The full suite takes about 48 minutes.
* `docs/antongduy/` is committed on purpose in this repository, unlike
  the default for those folders.
