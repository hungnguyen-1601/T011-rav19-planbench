# Importing an algorithm bundle: what runs, where, with what rights

This is the threat model for the algorithm import path — the door that
lets somebody upload a `.zip` containing Python and have the platform run
it as a navigation candidate. It exists because that door cannot be
opened honestly without writing down what it costs.

Read it before changing anything under `algorithms/plugins`, and copy its
§4 wording into the UI rather than paraphrasing it.

---

## 1. What actually happens to an uploaded bundle

1. The archive is stored. Nothing is extracted.
2. Its **table of contents** is read — member names, sizes — and its
   `plugin.json` is parsed. This is metadata parsing, not extraction and
   not import: no member is written to disk and no Python is executed.
3. If, and only if, the manifest parses and preflight says the plugin can
   run here, the archive is extracted into a per-bundle directory.
4. The conformance suite runs the plugin **in a subprocess**. This is the
   first moment the uploader's code executes.
5. A benchmark that names the plugin starts a subprocess per episode
   segment and drives it over a JSON line protocol.

Steps 1–3 are refusable. Step 4 is the point of no return, and the
ordering exists so that it can be refused.

## 2. The privileges that code has

The subprocess lane gives **crash and interpreter isolation**:

- a plugin that hangs is killed at the deployment's control period;
- a plugin that crashes exits a process rather than unwinding an
  exception through the simulator;
- a plugin that corrupts its own state cannot corrupt the host's.

It does **not** give a security boundary. The worker:

- inherits the API process's environment variables, including any
  secrets that live there;
- receives a `PYTHONPATH` that includes this repository;
- holds the same filesystem and network rights as the operating-system
  user running the API;
- takes its entry point on a command line visible in any process listing.

A plugin that means harm is limited by none of that. Running genuinely
untrusted code needs a container with dropped privileges, a scrubbed
environment and no network — which this platform does not yet provide.

**Do not call this a sandbox.** `services/simulator/planbench_simulator/host/runtimes/subprocess_lane.py`
says the same thing in its module docstring, and the author guide says it
in §10. Three places agreeing is deliberate: this is the claim most
likely to soften as it gets retold.

## 3. Why this is nevertheless acceptable today

The platform already runs uploaded code with fewer protections than
this, and has since the model registry shipped:

- `_build_ppo` (`packages/benchmark/planbench_benchmark/registry.py`)
  calls Stable-Baselines3's `PPO.load()` on an uploaded `.zip`.
  Deserialising a checkpoint unpickles it, and unpickling executes
  arbitrary code chosen by whoever produced the file.
- Benchmarks run in a `ThreadPoolExecutor` **inside the API process**
  (`apps/api/planbench_api/worker.py`), so that code runs there.

So the honest comparison is not "safe today versus unsafe tomorrow". It
is: an uploaded PPO checkpoint runs in the API process with no isolation
at all, and an uploaded plugin runs in a child process that can be
killed. The new door is the better-defended of the two.

What this does change is *who* can plausibly reach it: a checkpoint is a
file most people cannot author, while a Python file is not. That is why
§5 restricts the door rather than leaving it open to every member.

`ValidationStatus`'s docstring currently claims deserialising an upload
"never happens inside the API process". That was aspirational when it was
written and it is not true. Fixing the claim — or the code — is tracked
separately; this document does not pretend otherwise.

## 4. The wording the UI must show

Displayed **above the upload control**, not in a tooltip, not behind a
disclosure triangle:

> Uploading an algorithm runs your code on this server. It runs in a
> separate process, so a crash or a hang cannot take the platform down —
> but it is not a sandbox: it can read the files and reach the network
> that this server can. Only upload code you wrote or have read.

Shortening this is a product decision that needs a person to make it, not
a copy edit. The three claims that must survive any rewrite: *your code
runs*, *a crash is contained*, *nothing else is*.

## 5. Who may import

**Administrators only**, checked as `user.is_admin`.

Admin is granted by deployment configuration (`PLANBENCH_ADMIN_NICKNAMES`
/ `PLANBENCH_ADMIN_EMAILS`), never by anything a user can type — see
`account_service.apply_admin_policy`. So "who may upload code" is a
question the deployment answers, not one the sign-up form answers.

This is the interim rule. A finer grant — a per-user capability, or a
review queue — is expected later; the check is one call in one place so
that replacing it does not mean finding it.

Every other read path stays open: seeing an imported algorithm, and
seeing why it cannot run, needs no privilege. Only creating one does.

## 6. Ceilings

Deliberately generous for now, and expected to come down once real
bundles have been measured. All are settings, none are constants:

| Setting | Default | Guards against |
|---|---|---|
| `PLANBENCH_MAX_PLUGIN_UPLOAD_MB` | 50 | one request filling the disk |
| `PLANBENCH_MAX_PLUGIN_MEMBERS` | 500 | an archive with a million tiny files |
| `PLANBENCH_MAX_PLUGIN_EXTRACTED_MB` | 200 | a zip bomb: 50 MB compressed is not 50 MB written |
| `PLANBENCH_MAX_PLUGIN_MANIFEST_KB` | 64 | a manifest large enough to be a denial of service by itself |

The extracted ceiling is the one that matters and the one that is easy to
forget: the compressed size says nothing about what extraction writes.

## 7. Refusals that are structural, not configurable

- **A manifest declaring the in-process lane is refused.** The host never
  falls back between lanes, so a plugin that says in-process and gets run
  in a subprocess would be measured in a lane it did not declare. The
  refusal names the lane.
- **Archives with unsafe member paths are refused** — absolute paths,
  `..` segments, backslashes, symlinks. Checked when the table of
  contents is read *and* again when members are written, because those
  are two different moments and only the second one can actually escape.
- **Extraction never happens before preflight passes.**
- **A stored "runnable" verdict is never trusted.** Registration state is
  recomputed on every read: a deployment can gain or lose a provider, and
  yesterday's answer is not evidence about today.
- **Nothing is deleted.** A plugin is what a benchmark *ran*; removing it
  turns those measurements into records of nothing. Disabling is the
  retirement path, exactly as it is for models.

## 8. Roles accepted in v1

`local` and `monolithic` only.

Not a policy judgement — a capability one. `SubprocessPlugin` implements
`reset` and `step` and has no `plan`, so the subprocess lane cannot drive
a `global` plugin at all. A manifest declaring `role: "global"` is refused
with that reason rather than with a vaguer one, and widening this is a
single constant plus the lane work it names.
