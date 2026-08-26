"""Settings that only misbehave outside a developer checkout.

These are regression tests from the first real ``docker compose up``
(Đợt 0.2). Both failures were invisible on a workstation, where the
current directory happens to be writable and every default path happens
to be right.
"""

from __future__ import annotations

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
