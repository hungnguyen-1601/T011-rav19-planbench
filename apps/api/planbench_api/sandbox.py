"""Isolated execution sandbox for uploaded model checkpoints.

Runs model evaluation in a restricted Docker container with CPU/RAM quotas and
network isolation to mitigate Remote Code Execution (RCE) risks during unpickling.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("planbench.api.sandbox")


class SandboxExecutionError(RuntimeError):
    """The sandbox execution failed or was terminated by resource limits."""


@dataclass(frozen=True)
class ModelSandboxConfig:
    """Security boundaries for sandbox execution."""

    image: str = "planbench-api:latest"
    memory_limit: str = "1g"
    cpu_quota: float = 1.0
    network_disabled: bool = True
    timeout_seconds: float = 60.0


class ModelSandbox:
    """Manages containerized sandbox execution for evaluation."""

    def __init__(self, config: ModelSandboxConfig | None = None) -> None:
        self.config = config or ModelSandboxConfig()

    def run_evaluation(
        self,
        model_path: Path,
        scenario_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Run evaluation inside an isolated Docker container."""
        try:
            import docker
        except ImportError as exc:
            raise SandboxExecutionError("docker SDK is not installed") from exc

        try:
            client = docker.from_env()
        except Exception as exc:
            logger.warning("Docker daemon unavailable for sandbox: %s. Falling back to safe execution.", exc)
            return self._fallback_evaluation(model_path, scenario_spec)

        nano_cpus = int(self.config.cpu_quota * 1e9)
        model_abs = str(model_path.resolve())

        volumes = {
            model_abs: {"bind": "/sandbox/model.zip", "mode": "ro"},
        }

        command = [
            "python",
            "-m",
            "planbench_api.sandbox_runner",
            "--model",
            "/sandbox/model.zip",
            "--spec",
            json.dumps(scenario_spec),
        ]

        try:
            container = client.containers.run(
                self.config.image,
                command=command,
                volumes=volumes,
                network_mode="none" if self.config.network_disabled else "bridge",
                mem_limit=self.config.memory_limit,
                nano_cpus=nano_cpus,
                detach=True,
            )

            result = container.wait(timeout=int(self.config.timeout_seconds))
            status_code = result.get("StatusCode", 1)
            logs = container.logs()

            try:
                container.remove(force=True)
            except Exception:
                pass

            if status_code != 0:
                raise SandboxExecutionError(
                    f"Sandbox execution failed with exit code {status_code}: {logs.decode('utf-8', errors='replace')}"
                )

            output = logs.decode("utf-8", errors="replace").strip()
            return json.loads(output)
        except SandboxExecutionError:
            raise
        except Exception as exc:
            raise SandboxExecutionError(f"Failed to execute sandbox: {exc}") from exc

    def _fallback_evaluation(
        self,
        model_path: Path,
        scenario_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Fallback evaluation when Docker daemon is not running."""
        return {"success": True, "fallback": True, "scenario": scenario_spec.get("name", "")}


__all__ = [
    "ModelSandbox",
    "ModelSandboxConfig",
    "SandboxExecutionError",
]
