"""Check that a configured LLM provider actually answers.

Run this right after pasting an API key. It reports which providers are
ready, then makes **one** real request to the selected one and shows
what came back — including whether the structured-output path works,
since mission parsing depends on it.

    PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:services/tracking:\
services/agent_service:ml:apps/api" \
      .venv/bin/python scripts/check_agent_provider.py [provider] [model]

With no arguments it uses PLANBENCH_AGENT_PROVIDER / PLANBENCH_AGENT_MODEL
(falling back to `auto`). Nothing here writes to the database or runs a
benchmark: it is a connectivity and credentials check, nothing more.
"""

from __future__ import annotations

import os
import sys

from planbench_agent.factory import build_provider, provider_status
from planbench_agent.provider import (
    LLMMessage,
    LLMRequest,
    ProviderError,
    ProviderUnavailable,
)
from planbench_agent.specs import mission_schema, parse_structured, validate_draft

PROBE = "Reply with exactly: PLANBENCH OK"
MISSION = "Benchmark A*+DWA on the doorway scenario with seeds 1 and 2."


def show_status() -> None:
    print("Provider readiness")
    print(f"  {'provider':<12} {'ready':<6} {'key env':<22} what is missing")
    for status in provider_status():
        mark = "yes" if status.ready else "no"
        print(
            f"  {status.name:<12} {mark:<6} {status.api_key_env or '(none)':<22} {status.missing}"
        )
    print()


def main(argv: list[str]) -> int:
    kind = argv[0] if argv else os.environ.get("PLANBENCH_AGENT_PROVIDER", "auto")
    model = argv[1] if len(argv) > 1 else os.environ.get("PLANBENCH_AGENT_MODEL") or None

    show_status()

    try:
        provider = build_provider(kind, model=model)
    except (ValueError, ProviderUnavailable) as exc:
        print(f"FAILED to build provider {kind!r}: {exc}")
        return 2

    print(f"Selected  : {provider.name} ({provider.model})")
    print(f"Determinist: {provider.deterministic}")
    if provider.deterministic:
        print(
            "\nThis is the offline keyword-matching provider, not a model.\n"
            "Set PLANBENCH_AGENT_PROVIDER and the matching API key, then "
            "re-run to test a real one."
        )
        return 0

    print("\n1. Plain completion")
    try:
        response = provider.complete(
            LLMRequest(
                system="You are a connectivity probe. Answer in as few words as possible.",
                messages=(LLMMessage.user(PROBE),),
                max_tokens=256,
            )
        )
    except (ProviderError, ProviderUnavailable) as exc:
        print(f"   FAILED: {exc}")
        return 1
    print(f"   stop_reason : {response.stop_reason.value}")
    print(f"   text        : {response.text.strip()[:200]!r}")
    print(f"   tokens      : in={response.input_tokens} out={response.output_tokens}")

    print("\n2. Structured output (mission parsing depends on this)")
    try:
        structured = provider.complete(
            LLMRequest(
                system=(
                    "Translate the request into a benchmark specification. "
                    "Use only values allowed by the schema."
                ),
                messages=(LLMMessage.user(MISSION),),
                output_schema=mission_schema(),
                max_tokens=1024,
            )
        )
    except (ProviderError, ProviderUnavailable) as exc:
        print(f"   FAILED: {exc}")
        return 1

    if structured.structured is None:
        print("   FAILED: no JSON object came back")
        print(f"   raw text: {structured.text.strip()[:300]!r}")
        print(
            "\n   The provider does not honour json_schema output, or the model "
            "ignored it. Mission parsing will refuse rather than guess, which is "
            "safe but not useful. Try a model that supports structured output."
        )
        return 1

    draft, errors = parse_structured(structured.structured)
    if draft is None:
        print(f"   returned JSON, but it does not match the schema: {list(errors)}")
        return 1
    errors = validate_draft(draft)
    if errors:
        print(f"   schema-valid, but rejected by the registry check: {list(errors)}")
        print("   (this is the guard working; the model chose something unavailable)")
        return 1

    print(f"   draft       : scenario={draft.scenario} algorithms={list(draft.algorithms)}")
    print(f"   seeds       : {list(draft.seeds)}")
    print("\nProvider is usable for the agent endpoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
