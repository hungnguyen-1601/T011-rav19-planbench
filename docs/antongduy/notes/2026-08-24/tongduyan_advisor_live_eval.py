"""Run the advisor against a real model on three stored runs.

Three runs of deliberately different shapes (gated / carded / tied) x two
advice kinds x N models. Every call is scored on the things the advisor's
own constitution promises, plus the leaks the offline probes found.
"""

import sys, pathlib, json, re, time, os

ROOT = pathlib.Path(r"E:/VinAI/RoboMind_project/P-011")
for p in ["packages/schemas", "packages/planning", "packages/metrics", "packages/benchmark",
          "packages/decision", "packages/explanation", "packages/plugin_sdk",
          "services/simulator", "services/agent_service", "ml", "apps/api", "."]:
    sys.path.insert(0, str(ROOT / p))

# .env by hand: the app loads it through settings, this script does not.
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line.strip())
    if m and m.group(2):
        os.environ[m.group(1)] = m.group(2)

import yaml
from planbench_agent.advisor import MAX_MODEL_ADVICE, advise_with_model
from planbench_agent.factory import build_provider
from planbench_decision.gate_advice import build_diagnosis, gate_advice
from planbench_benchmark.outcome import build_outcome, outcome_advice


# ---- local patch, NOT a repo change -------------------------------------
# `_schema_is_strict` only inspects the top-level object, so the nested
# `additions.items` object is sent under strict:true while omitting
# `do_not` from its `required` list. OpenAI rejects that with a 400 and
# the advisor degrades to rules on every single call. Patch it here so
# the run measures the model rather than the bug.
import planbench_agent.advisor as _adv
_orig_schema = _adv.advisor_schema
def _fixed_schema():
    schema = _orig_schema()
    items = schema["properties"]["additions"]["items"]
    items["required"] = list(items["properties"].keys())
    return schema
if os.environ.get("ADVISOR_SCHEMA_FIX") == "1":
    _adv.advisor_schema = _fixed_schema
    print("[patched advisor_schema: additions.items.required now lists every property]")
# ADVISOR_MAX_TOKENS = 32768 exceeds gpt-4o-mini's 16384 completion cap, which
# is a second independent 400. Clamp it locally for the same reason.
_cap = os.environ.get("ADVISOR_MAX_TOKENS_CAP")
if _cap:
    _adv.ADVISOR_MAX_TOKENS = int(_cap)
    print(f"[clamped ADVISOR_MAX_TOKENS to {_cap}]")
# -------------------------------------------------------------------------

RUNS = ROOT / "artifacts/runs"
CASES = {
    "gated": RUNS / "2026-08-11/open_hall_v2_global_planner_selection_ce26fe87/comparison_report.json",
    "carded": RUNS / "2026-08-11/open_hall_v2_local_controller_selection_3edf8fe6/comparison_report.json",
    "tied": RUNS / "2026-08-12/open_hall_2_global_planner_selection_ce26fe87/comparison_report.json",
}
MODELS = (os.environ.get("ADVISOR_MODELS") or "gpt-4o-mini,o4-mini").split(",")
SEVERITY = {"blocking": 0, "material": 1, "disclosure": 2}

# The system prompt forbids these outright.
FORBIDDEN = (r"\bsafe\b", r"cost of ownership", r"\btotal cost\b")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def profile_for(report):
    pid = (report.get("identity") or {}).get("task_profile_id", "")
    for base in (ROOT / "profiles", RUNS / "profiles"):
        f = base / f"{pid}.yaml"
        if f.exists():
            return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return {}


def numbers(text):
    """Numeric tokens a reader would take as a measurement."""
    return {n for n in re.findall(r"\d+(?:[.,]\d+)?", text or "") if len(n) > 1 or n not in "0123456789"}


def source_numbers(source):
    return numbers(json.dumps(source, default=str))


class Recording:
    """Wrap a provider so the token counts survive advise_with_model."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def complete(self, request):
        t0 = time.time()
        response = self.inner.complete(request)
        self.calls.append({
            "seconds": round(time.time() - t0, 1),
            "in": response.input_tokens,
            "out": response.output_tokens,
            "stop": str(response.stop_reason),
        })
        return response


def score(kind, case, model, source, rules, result, usage):
    rule_items = [a for a in result.advice if a.source == "rule"]
    model_items = [a for a in result.advice if a.source == "model"]
    rule_codes = {a.code for a in rules}
    kept = {a.code for a in rule_items}

    order = [SEVERITY.get(a.severity, 9) for a in rule_items]
    demoted = any(order[i] > order[i + 1] for i in range(len(order) - 1))

    src_nums = source_numbers(source)
    invented = set()
    for a in model_items:
        invented |= numbers(a.claim) - src_nums
    summary_invented = numbers(result.summary) - src_nums

    banned = [p for p in FORBIDDEN if re.search(p, result.summary, re.I)]
    blocking_no_donot = [a.code for a in model_items if a.severity == "blocking" and not a.do_not]

    return {
        "case": case, "kind": kind, "model": model,
        "rules_in": len(rule_codes), "rules_kept": len(kept),
        "floor_intact": kept == rule_codes,
        "additions": len(model_items),
        "over_cap": len(model_items) > MAX_MODEL_ADVICE,
        "fabricated": result.fabricated,
        "severity_demoted": demoted,
        "blocking_without_donot": blocking_no_donot,
        "invented_numbers_in_claims": sorted(invented),
        "invented_numbers_in_summary": sorted(summary_invented),
        "banned_words_in_summary": banned,
        "refused": result.refused,
        "summary": result.summary,
        "model_claims": [f"[{a.severity}] {a.claim}  <- {a.field_path}" for a in model_items],
        "usage": usage,
    }


def main():
    rows = []
    for model in MODELS:
        provider = Recording(build_provider("openai", model=model))
        for case, path in CASES.items():
            report = load(path)
            prof = profile_for(report)
            for kind, build, rule_fn in (
                ("diagnosis", build_diagnosis, gate_advice),
                ("outcome", build_outcome, outcome_advice),
            ):
                source = build(report, prof)
                rules = tuple(rule_fn(source))
                before = len(provider.calls)
                try:
                    result = advise_with_model("diagnosis", source, rules, provider)
                except Exception as exc:
                    rows.append({"case": case, "kind": kind, "model": model,
                                 "crashed": f"{type(exc).__name__}: {exc}"})
                    print(f"  !! {model} {case}/{kind}: {type(exc).__name__}: {exc}")
                    continue
                usage = provider.calls[before:] or [{}]
                row = score(kind, case, model, source, rules, result, usage[-1])
                rows.append(row)
                flag = "REFUSED" if result.refused else "ok"
                print(f"  {model:12} {case:7} {kind:10} rules={row['rules_kept']}/{row['rules_in']} "
                      f"add={row['additions']} fab={row['fabricated']} {flag} "
                      f"{usage[-1].get('out', 0)}tok {usage[-1].get('seconds', 0)}s")
    tag = "_patched" if os.environ.get("ADVISOR_SCHEMA_FIX") == "1" else ""
    out = ROOT / f"docs/antongduy/notes/2026-08-24/tongduyan_advisor_live_results{tag}{os.environ.get("RUN_TAG","")}.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
