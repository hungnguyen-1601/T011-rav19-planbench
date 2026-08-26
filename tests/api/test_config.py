"""Settings that only misbehave outside a developer checkout.

These are regression tests from the first real ``docker compose up``
(Đợt 0.2). Both failures were invisible on a workstation, where the
current directory happens to be writable and every default path happens
to be right.
"""

from __future__ import annotations

import os
from pathlib import Path

from planbench_api.config import Settings


class TestModelDirFollowsArtifactDir:
    """``model_dir`` must not drift away from the artifact root.

    In the API image the process runs as an unprivileged user under a
    root-owned ``WORKDIR /app``. A default of ``"artifacts/models"``
    therefore made ``LocalModelStorage.__init__`` raise ``PermissionError``
    while ``create_app()`` was still importing — the container never
    reached the first request, even though compose had set
    ``PLANBENCH_ARTIFACT_DIR=/data/artifacts`` correctly.
    """

    def test_it_defaults_under_the_configured_artifact_dir(self) -> None:
        settings = Settings(artifact_dir="/data/artifacts", model_dir="")
        assert Path(settings.model_dir) == Path("/data/artifacts/models")

    def test_moving_the_artifact_root_moves_the_models(self) -> None:
        settings = Settings(artifact_dir="/srv/planbench", model_dir="")
        assert Path(settings.model_dir).parent == Path("/srv/planbench")

    def test_an_explicit_model_dir_still_wins(self) -> None:
        """Deployments that split the two must keep being able to."""
        settings = Settings(artifact_dir="/data/artifacts", model_dir="/mnt/checkpoints")
        assert settings.model_dir == "/mnt/checkpoints"

    def test_the_developer_default_is_unchanged(self) -> None:
        """A plain checkout still writes to ./artifacts/models."""
        settings = Settings(artifact_dir="artifacts", model_dir="")
        assert Path(settings.model_dir) == Path("artifacts/models")


class TestProviderKeysReachTheProvider:
    """The keys live in `.env`; the factory reads `os.environ`.

    Those two facts were each documented and never met. The symptom was
    a complete configuration that still answered from the offline
    keyword responder, and nothing in the UI or the settings said why.
    """

    def _env_file(self, tmp_path, body: str):
        path = tmp_path / ".env"
        path.write_text(body, encoding="utf-8")
        return path

    def test_a_key_in_the_file_reaches_the_environment(self, tmp_path, monkeypatch):
        from planbench_api.config import load_provider_keys

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        env_file = self._env_file(tmp_path, "OPENAI_API_KEY=sk-from-the-file\n")
        assert "OPENAI_API_KEY" in load_provider_keys(env_file)
        assert os.environ["OPENAI_API_KEY"] == "sk-from-the-file"

    def test_the_shell_wins_over_the_file(self, tmp_path, monkeypatch):
        """A key exported for one run is the more deliberate of the two."""
        from planbench_api.config import load_provider_keys

        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-the-shell")
        env_file = self._env_file(tmp_path, "OPENAI_API_KEY=sk-from-the-file\n")
        assert load_provider_keys(env_file) == ()
        assert os.environ["OPENAI_API_KEY"] == "sk-from-the-shell"

    def test_only_provider_keys_are_copied(self, tmp_path, monkeypatch):
        """A `.env` may not reach in and set an arbitrary process
        variable; the allowlist is the names the factory publishes."""
        from planbench_api.config import load_provider_keys

        monkeypatch.delenv("PATH_TO_SOMETHING", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        env_file = self._env_file(
            tmp_path, "GROQ_API_KEY=gsk-real\nPATH_TO_SOMETHING=/etc/passwd\n"
        )
        assert load_provider_keys(env_file) == ("GROQ_API_KEY",)
        assert "PATH_TO_SOMETHING" not in os.environ

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        from planbench_api.config import load_provider_keys

        assert load_provider_keys(tmp_path / "nope.env") == ()

    def test_an_empty_value_is_not_a_key(self, tmp_path, monkeypatch):
        """The shipped `.env` lists every provider with the unused ones
        blank; copying those would set a variable to the empty string,
        which reads as configured and is not."""
        from planbench_api.config import load_provider_keys

        monkeypatch.delenv("XAI_API_KEY", raising=False)
        env_file = self._env_file(tmp_path, "XAI_API_KEY=\n")
        assert load_provider_keys(env_file) == ()
        assert "XAI_API_KEY" not in os.environ
