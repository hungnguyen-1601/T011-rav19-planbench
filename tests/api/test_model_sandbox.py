"""Unit tests for Model Sandbox execution and resource isolation."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from planbench_api.sandbox import (
    ModelSandbox,
    ModelSandboxConfig,
    SandboxExecutionError,
)


def test_sandbox_config_defaults():
    """Verify default sandbox security boundaries: network disabled, RAM <= 1GB, CPU <= 1.0."""
    config = ModelSandboxConfig()
    assert config.network_disabled is True
    assert config.memory_limit == "1g"
    assert config.cpu_quota == 1.0


def test_sandbox_execute_with_docker_mock():
    """Test sandbox execution using mock docker client."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b'{"success": true, "reward": 150.0}'
    mock_client.containers.run.return_value = mock_container

    with patch("docker.from_env", return_value=mock_client):
        sandbox = ModelSandbox(config=ModelSandboxConfig())
        result = sandbox.run_evaluation(
            model_path=Path("/tmp/fake_model.zip"),
            scenario_spec={"name": "doorway"},
        )

        assert result.get("success") is True
        assert result.get("reward") == 150.0
        assert mock_client.containers.run.called
        call_kwargs = mock_client.containers.run.call_args[1]
        assert call_kwargs.get("network_mode") == "none"
        assert call_kwargs.get("mem_limit") == "1g"


def test_sandbox_execute_docker_error_handling():
    """Test that container crash or non-zero exit raises SandboxExecutionError."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 1}
    mock_container.logs.return_value = b"Container memory limit exceeded"
    mock_client.containers.run.return_value = mock_container

    with patch("docker.from_env", return_value=mock_client):
        sandbox = ModelSandbox(config=ModelSandboxConfig())
        with pytest.raises(SandboxExecutionError) as exc_info:
            sandbox.run_evaluation(
                model_path=Path("/tmp/fake_model.zip"),
                scenario_spec={"name": "doorway"},
            )
        assert "sandbox execution failed" in str(exc_info.value).lower()
