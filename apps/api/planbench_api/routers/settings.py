"""Deployment settings a person may change without a restart.

Today that is one thing: which model answers, and the key that reaches
it. It exists because the alternative was asking somebody to find
`.env` on disk, paste a key into the right one of two places it is
declared, and restart the server — three steps, each of which fails
quietly, to change a setting the product asks for on first use.

Two properties hold the design together.

**The key is never read back.** A saved key leaves in one direction. The
response says whether one is present and shows its last four characters,
which is enough to answer "is the key I pasted the one in use?" and not
enough to be worth intercepting.

**Saving takes effect now.** `get_agent_service` reads
`app.state.agent_provider` per request, so rebuilding the provider and
assigning it there changes the next answer — including the decision
advisor's, which shares the same instance. Writing `.env` as well is
what makes it survive a restart; neither alone is enough.

The model list is one entry on purpose. `o4-mini` is the model this
deployment has actually been run and scored against
(`docs/journal/antongduy/notes/2026-08-24/`), and offering a picker of models
nobody has evaluated would be offering a choice the evidence cannot
support. Later versions add entries; the shape here already carries a
list so that adding one is data, not a redesign.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from planbench_agent.factory import build_provider, provider_status
from planbench_api.auth import ActiveUser, Forbidden
from planbench_api.config import write_env_values

router = APIRouter(prefix="/settings", tags=["settings"])

logger = logging.getLogger("planbench.api")

#: The provider and model this version wires up. Fixed rather than
#: configurable: see the module docstring.
AGENT_PROVIDER = "openai"
AGENT_MODEL = "o4-mini"
API_KEY_ENV = "OPENAI_API_KEY"

#: Offered in the UI. One entry today, a list so that the second one is
#: an edit to this tuple rather than a change of shape.
AVAILABLE_MODELS: tuple[str, ...] = (AGENT_MODEL,)


def _mask(value: str) -> str:
    """The last four characters, and nothing else.

    Enough to recognise a key you pasted; not enough to use. A key
    shorter than eight characters is not shown at all — at that length
    the tail is most of it.
    """
    if not value:
        return ""
    if len(value) < 8:
        return "••••"
    return f"••••{value[-4:]}"


class AgentSettings(BaseModel):
    """What the settings page shows. Never a key, only whether one is set."""

    provider: str
    model: str
    models: tuple[str, ...]
    api_key_env: str
    key_present: bool
    key_hint: str = ""
    #: True when the provider is configured *and* its SDK is installed.
    ready: bool = False
    #: What is still missing, phrased for the person who can fix it.
    missing: str = ""
    #: The provider actually answering right now. When this is the mock,
    #: the page says so instead of letting a reader assume a saved key
    #: took effect.
    active_provider: str = ""
    active_model: str = ""
    active_deterministic: bool = True


class AgentSettingsUpdate(BaseModel):
    """A key to save. The model is not a parameter yet — see the docstring."""

    api_key: str = Field(min_length=8, max_length=512)


def _describe(request: Request) -> AgentSettings:
    key = os.environ.get(API_KEY_ENV, "")
    status = next((s for s in provider_status() if s.name == AGENT_PROVIDER), None)
    live = getattr(request.app.state, "agent_provider", None)
    return AgentSettings(
        provider=AGENT_PROVIDER,
        model=AGENT_MODEL,
        models=AVAILABLE_MODELS,
        api_key_env=API_KEY_ENV,
        key_present=bool(key),
        key_hint=_mask(key),
        ready=bool(status and status.ready),
        missing=status.missing if status else "",
        active_provider=getattr(live, "name", ""),
        active_model=getattr(live, "model", ""),
        active_deterministic=bool(getattr(live, "deterministic", True)),
    )


@router.get("/agent", response_model=AgentSettings)
def read_agent_settings(request: Request, _: ActiveUser) -> AgentSettings:
    """The current provider, and whether a key is in place.

    Readable by anyone signed in: "is the assistant answering from a
    model or from the offline responder?" is a question about the answers
    on screen, not a privileged one.
    """
    return _describe(request)


@router.put("/agent", response_model=AgentSettings)
def save_agent_settings(
    request: Request,
    update: AgentSettingsUpdate,
    user: ActiveUser,
) -> AgentSettings:
    """Save the API key and switch the live provider onto it.

    Administrators only. The key pays for every model call this
    deployment makes and is shared by every signed-in reader, so setting
    it is a deployment decision rather than a personal preference — the
    same reasoning that limits importing an algorithm
    (`docs/reference/plugin_import_security.md` §5).

    The environment is set directly rather than through
    :func:`load_provider_keys`, which by design refuses to overwrite a
    variable already present: it exists to stop a file from quietly
    replacing a key exported for one run, and that rule would here stop
    the save from having any effect at all.

    The provider is named explicitly rather than left as `auto`. `auto`
    walks a list and falls to the offline responder when nothing is
    ready, which turns a bad key into a subtly different answer instead
    of an error — this way a bad key raises where it is pasted.
    """
    if not user.is_admin:
        raise Forbidden(
            "the API key is shared by everyone using this deployment, so setting it is "
            "limited to administrators"
        )

    key = update.api_key.strip()
    os.environ[API_KEY_ENV] = key
    written = write_env_values(
        {
            API_KEY_ENV: key,
            "PLANBENCH_AGENT_PROVIDER": AGENT_PROVIDER,
            "PLANBENCH_AGENT_MODEL": AGENT_MODEL,
        }
    )
    # Names only. The value is the one thing this module must never log.
    logger.info("settings saved by %s: %s", user.nickname, ", ".join(written))

    request.app.state.agent_provider = build_provider(AGENT_PROVIDER, model=AGENT_MODEL)
    return _describe(request)
