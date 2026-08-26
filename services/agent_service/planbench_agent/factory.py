"""Provider selection across vendors.

One rule: a missing API key degrades the agent, it never breaks the
platform. With nothing configured the deterministic mock takes over, the
whole M8 surface stays available, and every response records which
provider produced it — so nobody mistakes a keyword-matched answer for a
model-written one.

Selecting a provider explicitly that is not usable raises instead of
silently downgrading. An explicit choice should fail loudly; only
``auto`` is allowed to fall back.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass

from planbench_agent.openai_provider import PRESETS, OpenAICompatibleProvider
from planbench_agent.provider import LLMProvider, MockProvider, ProviderUnavailable

logger = logging.getLogger("planbench.agent.factory")

MOCK = "mock"
ANTHROPIC = "anthropic"
AUTO = "auto"

#: Every provider that can be named in ``PLANBENCH_AGENT_PROVIDER``.
PROVIDERS: tuple[str, ...] = (AUTO, MOCK, ANTHROPIC, *sorted(PRESETS))

#: Order ``auto`` tries. Anthropic first because its adapter is the one
#: written against first-party documentation; the rest follow the shared
#: OpenAI-compatible wire format. ``local`` is last and only picked when
#: named explicitly — an unreachable localhost port should not silently
#: become the configured provider.
AUTO_ORDER: tuple[str, ...] = (
    ANTHROPIC,
    "openai",
    "gemini",
    "openrouter",
    "groq",
    "deepseek",
    "xai",
)


@dataclass(frozen=True)
class ProviderStatus:
    """Whether one provider is ready, and what is missing if not."""

    name: str
    api_key_env: str
    key_present: bool
    sdk_installed: bool
    sdk_package: str

    @property
    def ready(self) -> bool:
        return self.key_present and self.sdk_installed

    @property
    def missing(self) -> str:
        if self.ready:
            return ""
        gaps = []
        if not self.key_present and self.api_key_env:
            gaps.append(f"set {self.api_key_env}")
        if not self.sdk_installed:
            gaps.append(f"pip install {self.sdk_package}")
        return "; ".join(gaps)


def _anthropic_key_env() -> str:
    from planbench_agent.anthropic_provider import API_KEY_ENV

    return API_KEY_ENV


def provider_status() -> tuple[ProviderStatus, ...]:
    """Readiness of every configurable provider, for diagnostics.

    Surfaced through ``GET /agent/capabilities`` so "why is it still
    using the mock?" is answerable without reading the logs.
    """
    key_env = _anthropic_key_env()
    statuses = [
        ProviderStatus(
            name=ANTHROPIC,
            api_key_env=key_env,
            key_present=bool(os.environ.get(key_env)),
            sdk_installed=_can_import("anthropic"),
            sdk_package="anthropic",
        )
    ]
    for kind in sorted(PRESETS):
        preset = PRESETS[kind]
        statuses.append(
            ProviderStatus(
                name=kind,
                api_key_env=preset.api_key_env,
                key_present=(not preset.requires_key) or bool(os.environ.get(preset.api_key_env)),
                sdk_installed=_can_import("openai"),
                sdk_package="openai",
            )
        )
    return tuple(statuses)


def _can_import(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def build_provider(
    kind: str = AUTO,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMProvider:
    """Return a provider for ``kind``.

    ``model`` is required for the OpenAI-compatible providers: model ids
    there change often enough that a hardcoded default would eventually
    404, and guessing one is worse than asking. The Anthropic adapter
    carries its own documented default.
    """
    kind = (kind or AUTO).strip().lower()
    if kind not in PROVIDERS:
        raise ValueError(f"unknown provider {kind!r}; expected one of {PROVIDERS}")

    if kind == MOCK:
        return MockProvider()
    if kind == AUTO:
        return _auto(model=model, api_key=api_key, base_url=base_url)
    return _named(kind, model=model, api_key=api_key, base_url=base_url)


def _named(
    kind: str, *, model: str | None, api_key: str | None, base_url: str | None
) -> LLMProvider:
    if kind == ANTHROPIC:
        from planbench_agent.anthropic_provider import DEFAULT_MODEL, AnthropicProvider

        return AnthropicProvider(model=model or DEFAULT_MODEL, api_key=api_key)
    return OpenAICompatibleProvider.for_provider(
        kind, model_id=model or "", api_key=api_key, base_url=base_url
    )


def _auto(*, model: str | None, api_key: str | None, base_url: str | None) -> LLMProvider:
    for kind in AUTO_ORDER:
        if not _auto_ready(kind):
            continue
        if kind != ANTHROPIC and not model:
            # A key alone is not enough for these: without a model id the
            # first request would fail. Say so and keep looking.
            logger.warning("provider %r has a key but no PLANBENCH_AGENT_MODEL; skipping it", kind)
            continue
        provider = _named(kind, model=model, api_key=api_key, base_url=base_url)
        logger.info("agent provider: %s (%s)", provider.name, provider.model)
        return provider

    logger.info(
        "agent provider: deterministic mock (no provider key found); answers are "
        "keyword-matched, not model-generated. Configure one with "
        "PLANBENCH_AGENT_PROVIDER + the matching API key."
    )
    return MockProvider()


def _auto_ready(kind: str) -> bool:
    if kind == ANTHROPIC:
        from planbench_agent.anthropic_provider import AnthropicProvider

        return AnthropicProvider.available()
    return OpenAICompatibleProvider.available(kind)


def describe_unavailable(kind: str) -> str:
    """Human-readable reason a named provider cannot be used, or ''."""
    for status in provider_status():
        if status.name == kind:
            return status.missing
    return f"unknown provider {kind!r}"


def require_provider(kind: str, *, model: str | None = None) -> LLMProvider:
    """Build a named provider, raising with the fix if it is not ready."""
    reason = describe_unavailable(kind)
    if reason:
        raise ProviderUnavailable(f"provider {kind!r} is not usable: {reason}")
    return build_provider(kind, model=model)


__all__ = [
    "ANTHROPIC",
    "AUTO",
    "AUTO_ORDER",
    "MOCK",
    "PROVIDERS",
    "ProviderStatus",
    "build_provider",
    "describe_unavailable",
    "provider_status",
    "require_provider",
]
