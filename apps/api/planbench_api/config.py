"""Application settings from environment variables (PLANBENCH_*)."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLANBENCH_",
        env_file=".env",
        extra="ignore",
        # OAuth credentials are conventionally named GOOGLE_CLIENT_ID and
        # so on; those fields carry an explicit alias, and populate_by_name
        # keeps the prefixed spelling working for everything else.
        populate_by_name=True,
    )

    app_name: str = "PlanBench API"
    version: str = "0.1.0"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]
    # Upper bound for WebSocket playback pacing (messages per second).
    ws_max_rate_hz: float = 60.0

    # Auth. An empty secret means "generate a random one per process":
    # fine for development, and no secret ever lives in the repository.
    # Production must set AUTH_SECRET (see docs/DEPLOYMENT.md).
    jwt_secret: str = ""
    jwt_ttl_minutes: int = 60
    # "name:password" entries, comma separated (a legacy third ":role"
    # field is accepted and ignored — everyone is a member now). Only
    # usable when dev login is enabled.
    seed_users: str = ""
    # Username/password sign-in. Off unless explicitly enabled, so a
    # deployment cannot accidentally expose a password login next to
    # OAuth — the login page hides it based on the same flag.
    enable_dev_login: bool = False

    # OAuth. These four are the provider's, and the fifth signs our own
    # tokens; all five are named without the PLANBENCH_ prefix because
    # that is what the provider consoles and every deployment guide call
    # them. Empty values are not an error: the corresponding button is
    # simply not offered.
    google_client_id: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    github_client_id: str = Field(default="", validation_alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="", validation_alias="GITHUB_CLIENT_SECRET")
    #: Signs JWTs and the OAuth state cookie. Falls back to
    #: PLANBENCH_JWT_SECRET, then to a per-process random value.
    auth_secret: str = Field(default="", validation_alias="AUTH_SECRET")

    # Where the two halves of the app are reachable. The redirect URI
    # registered with Google and GitHub is derived from api_public_url,
    # so it cannot drift from what the callback route actually is.
    api_public_url: str = "http://localhost:8000"
    web_app_url: str = "http://localhost:3000"

    # Admin is granted by configuration, never by anything a user can
    # type: a nickname is chosen by its owner, so only a nickname the
    # deployment already trusts counts. Comma-separated, case-insensitive.
    # Emails are matched only when the provider verified them.
    admin_nicknames: str = ""
    admin_emails: str = ""

    # Artifact storage root for trajectories and reports.
    artifact_dir: str = "artifacts"

    # Uploaded model files. Kept out of the source tree and out of Git —
    # a checkpoint is data, not code, and a repository is not a CDN.
    #
    # Empty means "<artifact_dir>/models", so moving the artifact root
    # moves the checkpoints with it. A fixed default here would keep
    # pointing at ./artifacts/models after a deployment set
    # PLANBENCH_ARTIFACT_DIR elsewhere — in the container that path is
    # under a root-owned WORKDIR and the API cannot create it, which is
    # a crash at import time rather than a wrong path at upload time.
    model_dir: str = ""
    # Upload ceilings, in megabytes. A trained PPO checkpoint is
    # typically a few MB; 200 leaves room for a large policy without
    # letting one request fill the disk.
    max_model_upload_mb: int = 200
    max_document_upload_mb: int = 20

    # Imported algorithm bundles. Deliberately generous for now and
    # expected to come down once real bundles have been measured — see
    # docs/plugin_import_security.md §6.
    #
    # `max_plugin_extracted_mb` is the one that matters and the one that
    # is easy to leave out: a compressed size says nothing about what
    # extraction writes, so the upload ceiling alone does not bound the
    # disk a zip bomb can claim.
    max_plugin_upload_mb: int = 50
    max_plugin_members: int = 500
    max_plugin_extracted_mb: int = 200
    max_plugin_manifest_kb: int = 64
    # Where bundles are unpacked to be run. Empty means
    # "<artifact_dir>/plugins", for the same reason `model_dir` defaults
    # that way: moving the artifact root has to move this with it.
    plugin_dir: str = ""

    # Persistence (M10). Empty keeps everything in memory, which is what
    # development and the test suite use. A URL switches to SQL:
    #   postgresql://user:pass@host:5432/planbench   (production)
    #   sqlite:///./planbench.db                     (single process only)
    # The schema is applied with Alembic, never on startup; db_create_all
    # exists for throwaway SQLite. See docs/DEPLOYMENT.md.
    database_url: str = ""
    db_echo: bool = False
    db_create_all: bool = False

    # Background worker: hard cap on concurrent benchmark jobs so a few
    # large runs cannot starve the API process.
    worker_concurrency: int = 2

    # Experiment tracking. Empty URI -> tracking disabled (null tracker).
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "planbench"

    # Agentic AI (M8). "auto" picks the first configured provider and
    # falls back to the deterministic mock, so the agent endpoints work
    # in every environment. Named providers: anthropic, openai, gemini,
    # openrouter, groq, deepseek, xai, local, mock.
    #
    # API keys are read from each provider's own environment variable
    # (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, ...) — never a
    # PlanBench setting, never stored in a config file in the repository.
    agent_provider: str = "auto"
    # Required for every provider except anthropic: model ids there
    # change often enough that a hardcoded default would eventually 404.
    agent_model: str = ""
    # Override the provider endpoint (self-hosted or proxy). Empty uses
    # the preset for the selected provider.
    agent_base_url: str = ""
    # Directories indexed for retrieval, comma separated, relative to the
    # repository root. Empty disables retrieval.
    # Ceiling on episodes the agent may propose in one benchmark.
    agent_max_episodes: int = 60

    # -- episode analyst (plan 2026-08-27) -----------------------------
    #
    # Whether a model may be asked why one episode went the way it did,
    # and who may read the answer. **Off by default and off in every
    # deployment that has not said otherwise**: the deterministic
    # verdict and the model-free floor are served either way, and they
    # are what the panel is built on. The model is the layer on top.
    #
    #   off               the route answers 404
    #   shadow            the round runs and is written to an artifact;
    #                     nothing model-written reaches the response
    #   internal_preview  administrators read it; requires
    #                     `episode_analyst_report_ref`
    #   production        refused in this build — the mode exists so
    #                     that granting it later is a grant and not a
    #                     redesign
    episode_analyst_mode: str = "off"
    # The exploratory report the preview was opened on. A mode that
    # turned on with nothing behind it would be a decision nobody
    # recorded.
    episode_analyst_report_ref: str = ""
    # Per caller per day. Both, because a call returning a long answer
    # and one returning a short answer cost differently, and a cap on
    # one of them is a cap on neither.
    episode_analyst_max_calls_per_day: int = 20
    episode_analyst_max_tokens_per_day: int = 400_000
    # Where a shadow round's artifact is written.
    episode_analyst_artifact_root: str = "artifacts/analyst-episode"

    # -- decision layer (Phase 6.2) ------------------------------------
    #
    # Where a task profile's relative paths resolve. Every profile names
    # its map as `maps/<name>.pgm` relative to the repository root, and
    # storing the profile in a database did not move the `.pgm` — so the
    # API needs to be told where those files are, not guess.
    map_root: str = "."

    # The built web UI, served by this process when set.
    #
    # Empty means "serve the API alone", which is what every deployment
    # with a separate web container does and what the dev stack does.
    # The desktop build sets it: one process, one origin, and therefore
    # no CORS to configure, no second port to find free, and no API URL
    # baked into the JavaScript at build time.
    web_dir: str = ""

    # Trace and run roots for selections started through the API.
    #
    # **Empty means "follow the artifact root", and it is left empty on
    # purpose.** `model_dir` above is defaulted in the validator below;
    # these two are not, and the difference is load-bearing:
    # `create_app(artifact_dir=...)` overrides the artifact root for a
    # single application — a test giving itself a temporary root, most
    # often — and it can only tell "the operator chose a trace directory"
    # from "nobody chose one" if the unset case is still visibly unset by
    # the time it looks.
    #
    # Filling them in here made the setting dead: `main.py` computed its
    # own path from `artifact_dir` and never consulted these, because
    # consulting them would have overridden every test's isolation. So
    # `PLANBENCH_DECISION_TRACE_DIR` could be set and had no effect at
    # all, which is worse than not existing — somebody sets it and
    # believes it. Resolved in `main.py`, which is the only place that
    # knows both this and the per-application override.
    decision_trace_dir: str = ""
    decision_run_dir: str = ""

    @model_validator(mode="after")
    def _default_model_dir_under_artifacts(self) -> Settings:
        if not self.model_dir:
            # object.__setattr__ is not needed (Settings is mutable), but
            # assigning through the field keeps validation in play.
            self.model_dir = str(Path(self.artifact_dir) / "models")
        # decision_trace_dir / decision_run_dir are deliberately NOT
        # defaulted here — see the comment on their declaration.
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def oauth_redirect_uri(settings: Settings, provider: str) -> str:
    """The callback URL to register with the provider.

    Derived rather than configured: a mismatch between what is registered
    and what the app actually serves is the single most common OAuth
    setup failure, and there is no reason for two sources of truth.
    """
    return f"{settings.api_public_url.rstrip('/')}/api/v1/auth/oauth/{provider}/callback"


def load_provider_keys(env_file: str | Path = ".env") -> tuple[str, ...]:
    """Put provider API keys from ``.env`` into the process environment.

    Two rules were each right on their own and did not meet. Keys are
    **never PlanBench settings** — that is why they are absent from
    :class:`Settings`, and it keeps them out of every settings dump and
    every log line that prints one. And ``.env`` is where the project
    documents pasting them, next to ``PLANBENCH_AGENT_MODEL``.

    The gap between the two was silent and total: pydantic-settings reads
    ``.env`` into the *settings object*, while
    :func:`~planbench_agent.factory.build_provider` reads
    ``os.environ`` directly. So the model id arrived and the key never
    did, `auto` found no provider ready, and the assistant answered from
    the offline keyword responder — which is a legible sentence in the
    UI and, to anyone who had just pasted a key, the wrong one.

    This copies **only** the provider key variables, by the names the
    factory itself publishes, so a ``.env`` cannot reach in and set an
    arbitrary process variable. A value already in the environment wins:
    the shell is the more deliberate of the two, and a key exported for
    one run should not be overridden by a file.

    Returns the names actually filled in, for the startup log.
    """
    import os

    from dotenv import dotenv_values

    from planbench_agent.factory import provider_status

    path = Path(env_file)
    if not path.exists():
        return ()
    values = dotenv_values(path)
    wanted = {status.api_key_env for status in provider_status() if status.api_key_env}
    filled: list[str] = []
    for name in sorted(wanted):
        if os.environ.get(name):
            continue
        value = values.get(name)
        if value:
            os.environ[name] = value
            filled.append(name)
    return tuple(filled)


#: The only variables the settings endpoint may write into ``.env``.
#: An allowlist rather than a filter: the file also holds the database
#: URL and the session secret, and a request body that could name any
#: variable would be a way to rewrite those over HTTP.
WRITABLE_ENV_KEYS: frozenset[str] = frozenset(
    {
        "OPENAI_API_KEY",
        "PLANBENCH_AGENT_PROVIDER",
        "PLANBENCH_AGENT_MODEL",
    }
)


def write_env_values(
    values: Mapping[str, str],
    env_file: str | Path = ".env",
) -> tuple[str, ...]:
    """Persist ``values`` into ``.env``, leaving every other line as it was.

    Three properties this has to hold, and each one comes from a way the
    obvious implementation goes wrong:

    **Every occurrence is updated, not the first.** ``.env`` in this
    repository declares ``OPENAI_API_KEY`` twice — once in a header
    block, once among the provider keys — and ``dotenv_values`` takes the
    *last* one. Rewriting only the first would leave a stale key winning,
    and the caller would see the value they just saved having no effect.
    Writing the same value to all of them makes which-one-wins stop
    mattering.

    **The rest of the file survives byte for byte.** Comments in this
    file are the documentation for pasting keys; a writer that re-emitted
    a parsed dictionary would delete them the first time anyone saved.

    **The replace is atomic.** A crash mid-write would otherwise leave a
    truncated ``.env``, which takes the database URL and the session
    secret with it — losing the key would be the least of it.

    Returns the names written, for the caller's log. Values are never
    returned and never logged.
    """
    import os

    unknown = sorted(set(values) - WRITABLE_ENV_KEYS)
    if unknown:
        raise ValueError(f"not writable through this endpoint: {', '.join(unknown)}")
    for name, value in values.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"{name} may not contain a line break")

    path = Path(env_file)
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    seen: set[str] = set()

    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if name in values:
            lines[index] = f"{name}={values[name]}"
            seen.add(name)

    appended = sorted(set(values) - seen)
    if appended:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Written by the settings page.")
        lines.extend(f"{name}={values[name]}" for name in appended)

    body = "\n".join(lines) + "\n"
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)
    return tuple(sorted(values))
