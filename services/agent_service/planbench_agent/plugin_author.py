"""Read a paper into a plugin bundle the Algorithm Host can accept.

The candidate extractor (:mod:`paper`) maps a paper onto a stack this
platform already has, and refuses when there is none. This module is the
other half: when the paper's method is *new*, the way in is An's
Algorithm Host, and the host accepts exactly one shape — a bundle of
``plugin.json`` manifest plus code exporting the declared entry point
(`tongduyan_cau-truc-plugin-algorithm-host.md`).

**The mentor's rule is the design rule: the LLM's output must be in that
shape, or the system does not take it.** So the model is boxed twice.
Its structured-output schema pins every enum the manifest documents —
role, runtime lanes, action types, capability URIs — and a deterministic
validator re-checks the result against the documented manifest rules,
line by line. A draft that fails validation comes back *rejected with
the named errors*, never quietly repaired: repairing it here would teach
the caller that malformed output works.

The validator implements the documented rules, not a guess at them:

- ``production_lane`` must be one of ``supported_lanes`` (§5.1);
- every supported lane needs a profile, and every profile an
  ``entry_point`` of the form ``package:Class`` (§5.1);
- a requirement URI that is neither a known capability nor declared in
  the bundle's own ``capability_schemas`` is an invalid manifest, with a
  near-match suggestion — a typo must die at parse time, not surface
  later as "missing provider" (§5.2, rule 2);
- a ``global`` plugin must offer ``global-path@1``; ``local`` and
  ``monolithic`` drive through ``continuous-velocity@1``, the one action
  type the MVP host executes (§5.5–5.6).

An's SDK parser is not on this branch yet. When it lands, it replaces
:func:`validate_manifest` as the authority; the schema and scaffolding
stay. Nothing here is stored and nothing is imported or executed — the
generated code is text for a person to read, finish and test.
"""

from __future__ import annotations

import difflib
import json
import keyword
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from planbench_agent.provider import LLMMessage, LLMProvider, LLMRequest

__all__ = [
    "KNOWN_CAPABILITIES",
    "PLUGIN_API",
    "PluginDraft",
    "author_plugin",
    "plugin_schema",
    "validate_manifest",
]

#: The protocol version the host documents (`plugin_api` in every example).
PLUGIN_API = "1.1.0"

#: Every capability URI the host's documentation names. A requirement
#: outside this list must carry its own schema declaration or the
#: manifest is invalid — the closed list is what turns a typo into a
#: parse error instead of a phantom "missing provider".
KNOWN_CAPABILITIES: tuple[str, ...] = (
    "planbench://channel/global-path@1",
    "planbench://channel/human-state-estimates@1",
    "planbench://channel/lidar-2d@1",
    "planbench://channel/planning-grid@1",
    "planbench://channel/robot-state@1",
)

_ROLES = ("global", "local", "monolithic")
_LANES = ("python_in_process", "subprocess")
_ACTION_TYPES = ("global-path@1", "continuous-velocity@1")
_DYNAMICS = ("differential-drive@1",)
_EXECUTION_MODELS = ("synchronous-step@1",)

#: Thinking models spend output budget before writing a token of JSON.
AUTHOR_MAX_TOKENS = 32768

AUTHOR_SYSTEM = """You are turning a robotics paper into a PlanBench \
Algorithm Host plugin draft.

The host accepts exactly one shape: a plugin.json manifest plus Python \
code exporting the declared entry point. Your output is validated \
mechanically against the manifest rules; anything out of shape is \
rejected, not repaired.

Rules you must follow:
- `role`: "global" if the paper's method plans a path from start to \
goal; "local" if it produces velocity commands each control tick from a \
global path; "monolithic" if it produces velocity commands with no \
global path at all.
- `entry_point` is "package:ClassName". The class in `code` must have \
that exact name, with `plan(self, request)` for global, or \
`reset(...)` and `step(...)` for local and monolithic.
- Declare in `requirements.all_of` only channels the algorithm truly \
needs, from the allowed list.
- `config_schema.properties` holds the tunable parameters the paper \
states, with defaults taken from the paper where given. Parameters the \
paper does not state get sensible defaults and a mention in `notes`.
- `notes` lists what you assumed, what the paper left unstated, and any \
part of the method the code skeleton does not implement.
- The code is a faithful skeleton: real signatures, the algorithm's \
core steps as code or as clearly marked TODOs. Never pretend a step is \
implemented when it is not.
- If the text is not a paper about a planning or control algorithm, \
set `refused` to a one-line reason and leave everything else empty."""


def plugin_schema() -> dict[str, Any]:
    """The structured-output contract, enums pinned to the host's vocabulary.

    Everything the manifest documentation closes is closed here too, so
    the model cannot wander even before validation. `additionalProperties`
    is false at every level: an extra field is the first symptom of a
    model inventing its own manifest dialect.
    """
    return {
        "type": "object",
        "properties": {
            "refused": {"type": "string", "maxLength": 300},
            "plugin_id": {
                "type": "string",
                "description": "Dot-namespaced id, e.g. org.paper.theta-star",
                "maxLength": 80,
            },
            "role": {"type": "string", "enum": list(_ROLES)},
            "class_name": {"type": "string", "maxLength": 80},
            "summary": {"type": "string", "maxLength": 400},
            "requirements": {
                "type": "array",
                "items": {"type": "string", "enum": list(KNOWN_CAPABILITIES)},
                "maxItems": len(KNOWN_CAPABILITIES),
            },
            "parameters": {
                "type": "array",
                "maxItems": 24,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "maxLength": 60},
                        "type": {"type": "string", "enum": ["number", "integer", "boolean"]},
                        "default": {
                            "type": ["number", "boolean", "string"],
                            "description": "In SI units where applicable.",
                        },
                        "description": {"type": "string", "maxLength": 200},
                        "stated_by_paper": {"type": "boolean"},
                    },
                    "required": ["name", "type", "default", "stated_by_paper"],
                    "additionalProperties": False,
                },
            },
            "code": {"type": "string", "description": "Contents of planner.py"},
            "notes": {"type": "array", "items": {"type": "string", "maxLength": 300}},
        },
        "required": [
            "refused",
            "plugin_id",
            "role",
            "class_name",
            "requirements",
            "parameters",
            "code",
            "notes",
        ],
        "additionalProperties": False,
    }


class _Parameter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    default: Any = None
    description: str = ""
    stated_by_paper: bool = False


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refused: str = ""
    plugin_id: str = ""
    role: str = ""
    class_name: str = ""
    summary: str = ""
    requirements: tuple[str, ...] = ()
    parameters: tuple[_Parameter, ...] = ()
    code: str = ""
    notes: tuple[str, ...] = ()


class PluginDraft(BaseModel):
    """A plugin bundle proposal, and the verdict on its shape.

    ``accepted`` is the validator's word, not the model's: it is true
    exactly when the manifest passed every documented rule and the code
    carries the declared entry point. A rejected draft still returns in
    full, because the errors name what to fix and hiding the draft would
    hide what they refer to.
    """

    model_config = ConfigDict(frozen=True)

    manifest: dict[str, Any] = {}
    #: Relative path -> file content, ready to be written as a bundle.
    files: dict[str, str] = {}
    errors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    summary: str = ""
    refused: str = ""
    provider: str = ""
    model: str = ""
    deterministic: bool = True

    @property
    def accepted(self) -> bool:
        return not self.errors and not self.refused and bool(self.manifest)


_ENTRY_POINT = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*):([A-Za-z_][A-Za-z0-9_]*)$"
)
_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$")
_URI = re.compile(r"^[a-z][a-z0-9.-]*://channel/[a-z][a-z0-9-]*@\d+$")


def validate_manifest(manifest: dict[str, Any]) -> tuple[str, ...]:
    """Every documented manifest rule, as a list of named violations.

    Empty means the host's discovery would register this bundle. The
    checks mirror the documentation's own wording so that when An's SDK
    parser replaces this function, a drift between the two reads as a
    diff in error strings rather than as a silent behaviour change.
    """
    errors: list[str] = []

    if manifest.get("plugin_api") != PLUGIN_API:
        errors.append(f"plugin_api must be {PLUGIN_API!r}, got {manifest.get('plugin_api')!r}")
    if not _PLUGIN_ID.match(str(manifest.get("id") or "")):
        errors.append(
            f"id {manifest.get('id')!r} is not dot-namespaced lowercase (e.g. org.paper.theta-star)"
        )
    if not re.match(r"^\d+\.\d+\.\d+$", str(manifest.get("version") or "")):
        errors.append(f"version {manifest.get('version')!r} is not semver")
    role = manifest.get("role")
    if role not in _ROLES:
        errors.append(f"role {role!r} is not one of {_ROLES}")

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("runtime block is missing")
        runtime = {}
    lanes = runtime.get("supported_lanes") or []
    unknown_lanes = [lane for lane in lanes if lane not in _LANES]
    if not lanes:
        errors.append("runtime.supported_lanes is empty")
    if unknown_lanes:
        errors.append(f"unknown runtime lane(s) {unknown_lanes}; host offers {list(_LANES)}")
    production = runtime.get("production_lane")
    if production not in lanes:
        # The rule the documentation states verbatim: "validator: phải
        # thuộc supported_lanes".
        errors.append(f"production_lane {production!r} is not in supported_lanes {lanes}")
    profiles = runtime.get("profiles") or {}
    for lane in lanes:
        profile = profiles.get(lane)
        if not isinstance(profile, dict):
            errors.append(f"lane {lane!r} has no runtime profile")
            continue
        if not profile.get("protocol"):
            errors.append(f"profile for {lane!r} names no protocol")
        entry = str(profile.get("entry_point") or "")
        match = _ENTRY_POINT.match(entry)
        if not match:
            errors.append(f"entry_point {entry!r} is not of the form package:ClassName")
        elif any(keyword.iskeyword(part) for part in entry.replace(":", ".").split(".")):
            errors.append(f"entry_point {entry!r} uses a Python keyword")

    requirements = (manifest.get("requirements") or {}).get("all_of") or []
    declared = {
        str(item.get("uri"))
        for item in manifest.get("capability_schemas") or []
        if isinstance(item, dict)
    }
    for uri in requirements:
        uri = str(uri)
        if uri in KNOWN_CAPABILITIES or uri in declared:
            continue
        if not _URI.match(uri):
            errors.append(f"requirement {uri!r} is not a capability URI")
            continue
        # Documented rule §5.2: an unregistered URI with no bundled
        # schema dies at parse time, with a near-match suggestion —
        # "typo" and "missing infrastructure" are different diagnoses.
        near = difflib.get_close_matches(uri, KNOWN_CAPABILITIES, n=1)
        hint = f" (did you mean {near[0]!r}?)" if near else ""
        errors.append(f"requirement {uri!r} is not a known capability and declares no schema{hint}")

    supports = manifest.get("supports") or {}
    actions = supports.get("action_types") or []
    if role == "global" and "global-path@1" not in actions:
        errors.append("a global plugin must support action type global-path@1")
    if role in ("local", "monolithic") and "continuous-velocity@1" not in actions:
        errors.append(f"a {role} plugin must support continuous-velocity@1 (the MVP action type)")
    for action in actions:
        if action not in _ACTION_TYPES:
            errors.append(f"action type {action!r} is not hosted; MVP offers {list(_ACTION_TYPES)}")
    if role == "monolithic" and manifest.get("requires_global_path") is not False:
        errors.append("a monolithic plugin must declare requires_global_path: false")

    schema = manifest.get("config_schema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        errors.append("config_schema must be a JSON schema of type object")
    else:
        for name in schema.get("properties") or {}:
            if not str(name).isidentifier():
                errors.append(f"config_schema property {name!r} is not a valid identifier")

    return tuple(errors)


def _package_name(plugin_id: str) -> str:
    """A Python package name from the manifest id's last segment."""
    tail = plugin_id.rsplit(".", 1)[-1].replace("-", "_")
    return tail if tail.isidentifier() and not keyword.iskeyword(tail) else "paper_plugin"


def _build_manifest(payload: _Payload) -> dict[str, Any]:
    """Assemble the manifest deterministically from the model's answer.

    The model chooses the *content* — id, role, requirements, tunables —
    and this function owns the *shape*, so a well-behaved answer cannot
    be let down by a mis-nested block. Validation still runs on the
    result: the shape being ours does not exempt the content.
    """
    package = _package_name(payload.plugin_id)
    properties: dict[str, Any] = {}
    for param in payload.parameters:
        if not param.name.isidentifier():
            continue
        entry: dict[str, Any] = {"type": param.type}
        if param.default is not None:
            entry["default"] = param.default
        if param.description:
            entry["description"] = param.description
        properties[param.name] = entry

    manifest: dict[str, Any] = {
        "plugin_api": PLUGIN_API,
        "id": payload.plugin_id,
        "version": "0.1.0",
        "role": payload.role,
        "runtime": {
            "supported_lanes": ["python_in_process"],
            "production_lane": "python_in_process",
            "profiles": {
                "python_in_process": {
                    "protocol": "planbench-inproc/v1",
                    "codec": "python-object/v1",
                    "deadline_policy": "control-period",
                    "entry_point": f"{package}:{payload.class_name}",
                }
            },
        },
        "requirements": {"all_of": sorted(set(payload.requirements))},
        "supports": {
            "action_types": ["global-path@1"]
            if payload.role == "global"
            else ["continuous-velocity@1"],
            "robot_dynamics": list(_DYNAMICS),
            "execution_models": list(_EXECUTION_MODELS),
        },
        "config_schema": {"type": "object", "properties": properties},
    }
    if payload.role == "monolithic":
        manifest["requires_global_path"] = False
    return manifest


def _check_code(payload: _Payload) -> tuple[str, ...]:
    """The code is text, never imported — but its shape is checkable.

    A manifest naming an entry point the code does not define would
    register cleanly and then fail at the first episode, which is the
    late failure this whole module exists to move earlier.
    """
    errors: list[str] = []
    if not payload.code.strip():
        errors.append("code is empty")
        return tuple(errors)
    if not re.search(rf"^class\s+{re.escape(payload.class_name)}\b", payload.code, re.M):
        errors.append(f"code does not define class {payload.class_name!r}")
    needed = ("def plan(",) if payload.role == "global" else ("def reset(", "def step(")
    for method in needed:
        if method not in payload.code:
            errors.append(f"a {payload.role} plugin's code must define {method}...)")
    return tuple(errors)


def author_plugin(text: str, provider: LLMProvider) -> PluginDraft:
    """A paper in, a validated plugin bundle draft out. Never raises."""
    meta = {
        "provider": provider.name,
        "model": provider.model,
        "deterministic": provider.deterministic,
    }
    if not text.strip():
        return PluginDraft(refused="no text to read", **meta)

    request = LLMRequest(
        system=AUTHOR_SYSTEM,
        messages=(LLMMessage.user(text),),
        output_schema=plugin_schema(),
        max_tokens=AUTHOR_MAX_TOKENS,
    )
    try:
        response = provider.complete(request)
    except Exception as exc:  # a provider failure is a refusal, not a crash
        return PluginDraft(refused=f"provider failed: {exc}", **meta)
    if not isinstance(response.structured, dict):
        return PluginDraft(refused="provider returned no structured output", **meta)
    try:
        payload = _Payload.model_validate(response.structured)
    except ValidationError as exc:
        return PluginDraft(
            refused=f"structured output did not validate: {exc.error_count()} error(s)", **meta
        )
    if payload.refused:
        return PluginDraft(refused=payload.refused, **meta)

    manifest = _build_manifest(payload)
    errors = validate_manifest(manifest) + _check_code(payload)

    package = _package_name(payload.plugin_id)
    files = {
        f"{package}/.planbench-plugin/plugin.json": json.dumps(manifest, indent=2) + "\n",
        f"{package}/planner.py": payload.code
        if payload.code.endswith("\n")
        else payload.code + "\n",
        f"{package}/__init__.py": (
            f'"""Generated from a paper; review before running."""\n\n'
            f"from {package}.planner import {payload.class_name}\n\n"
            f'__all__ = ["{payload.class_name}"]\n'
        ),
    }
    return PluginDraft(
        manifest=manifest,
        files=files,
        errors=errors,
        notes=payload.notes,
        summary=payload.summary,
        **meta,
    )
