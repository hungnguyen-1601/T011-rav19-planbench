"""Unit tests for BenchmarkJobRow and RefreshTokenRow database models."""

from planbench_api.db.models import BenchmarkJobRow, RefreshTokenRow


def test_benchmark_job_row_attributes():
    """Verify BenchmarkJobRow fields."""
    row = BenchmarkJobRow(
        id="job_123",
        kind="benchmark_run",
        state="queued",
        progress=0,
        total=10,
        message="Queued job",
        error=None,
        created_at="2026-08-08T10:00:00Z",
    )
    assert row.id == "job_123"
    assert row.kind == "benchmark_run"
    assert row.state == "queued"
    assert row.total == 10


def test_refresh_token_row_attributes():
    """Verify RefreshTokenRow fields."""
    row = RefreshTokenRow(
        id="rt_123",
        user_id="usr_456",
        token_hash="hash_abc",
        expires_at="2026-08-15T10:00:00Z",
        revoked=False,
        created_at="2026-08-08T10:00:00Z",
    )
    assert row.id == "rt_123"
    assert row.user_id == "usr_456"
    assert row.revoked is False
