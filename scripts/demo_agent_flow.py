"""End-to-end demo of the M8 agent flow over real HTTP.

Prints the whole gated sequence — mission, refusal cases, the approval
gate, evidence, cited report — using the in-process test client so it
runs without a server.

    PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:services/tracking:\
services/agent_service:ml:apps/api" .venv/bin/python scripts/demo_agent_flow.py

With no ANTHROPIC_API_KEY the deterministic provider answers, and the
output says so. The point of the demo is the platform's behaviour — the
gates and the citation checks — not the prose.
"""

from __future__ import annotations

import json
import os
import tempfile

from fastapi.testclient import TestClient

from planbench_api.config import get_settings
from planbench_api.main import create_app

OPERATOR = ("op-alice", "operator-password")
REVIEWER = ("rev-carol", "reviewer-password")


def headers(client: TestClient, credentials: tuple[str, str]) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": credentials[0], "password": credentials[1]},
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def section(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def main() -> int:
    os.environ["PLANBENCH_SEED_USERS"] = ",".join(
        [
            f"{OPERATOR[0]}:operator:{OPERATOR[1]}",
            f"{REVIEWER[0]}:reviewer:{REVIEWER[1]}",
        ]
    )
    os.environ.setdefault("PLANBENCH_JWT_SECRET", "demo-secret-not-for-production")
    get_settings.cache_clear()

    with tempfile.TemporaryDirectory() as artifacts:
        client = TestClient(create_app(artifact_dir=artifacts))
        operator = headers(client, OPERATOR)
        reviewer = headers(client, REVIEWER)

        section("capabilities")
        capabilities = client.get("/api/v1/agent/capabilities", headers=operator).json()
        print(f"provider     : {capabilities['provider']} ({capabilities['model']})")
        print(f"deterministic: {capabilities['deterministic']}")
        print(f"tools        : {', '.join(capabilities['tools'])}")
        print(f"forbidden    : {', '.join(capabilities['forbidden'])}")

        section("mission the agent cannot parse -> refusal, nothing created")
        refused = client.post(
            "/api/v1/agent/missions",
            json={"mission": "make the robot go faster", "submit": True},
            headers=operator,
        ).json()
        print(f"draft   : {refused['draft']}")
        print(f"refusal : {refused['refusal']['reason']}")
        print(f"created : {len(client.get('/api/v1/benchmarks', headers=operator).json())}")

        section("mission naming a stack that needs a checkpoint -> refusal")
        ppo = client.post(
            "/api/v1/agent/missions",
            json={"mission": "Compare DWA and PPO on open_space", "submit": True},
            headers=operator,
        ).json()
        for error in ppo["refusal"]["errors"]:
            print(f"error   : {error}")

        section("valid mission -> draft, submitted, waiting on a human")
        mission = client.post(
            "/api/v1/agent/missions",
            json={
                "mission": "Benchmark DWA on the open_space scenario with seeds 1 2",
                "submit": True,
            },
            headers=operator,
        ).json()
        benchmark = mission["benchmark"]
        print(f"draft     : {json.dumps(mission['draft'])}")
        print(f"benchmark : {benchmark['id']} state={benchmark['state']}")
        print(f"next step : {mission['next_step']}")

        section("agent tries to run before approval")
        blocked = client.post(f"/api/v1/agent/benchmarks/{benchmark['id']}/run", headers=operator)
        print(f"HTTP {blocked.status_code}: {blocked.json()['error']['message']}")

        section("operator tries to approve their own benchmark")
        self_approve = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/approve", json={}, headers=operator
        )
        print(f"HTTP {self_approve.status_code}: {self_approve.json()['error']['message']}")

        section("reviewer approves (human gate 1), then the agent runs it")
        approved = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/approve", json={}, headers=reviewer
        ).json()
        print(f"state after approve: {approved['state']}")
        finished = client.post(
            f"/api/v1/agent/benchmarks/{benchmark['id']}/run", headers=operator
        ).json()
        print(f"state after run    : {finished['state']}  (gate 2 still ahead)")
        print(f"conditions_checksum: {finished['conditions_checksum']}")

        section("evidence collected from storage")
        evidence = client.get(
            f"/api/v1/agent/benchmarks/{benchmark['id']}/evidence", headers=operator
        ).json()
        print(f"{len(evidence['items'])} items")
        for item in evidence["items"][:6]:
            citation = item["citation"]
            print(f"  [{citation['kind']}:{citation['locator']}] {item['statement']}")

        section("generated report")
        report = client.post(
            f"/api/v1/agent/benchmarks/{benchmark['id']}/report",
            json={"question": "How did A*+DWA perform?"},
            headers=operator,
        ).json()
        print(f"refused    : {report['refused']}")
        print(f"provisional: {report['provisional']}")
        print(f"citations  : {len(report['citations'])} (all verified against the bundle)")
        print("---")
        print(report["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
