"""Unit tests for DB startup retry logic and connection resilience."""

from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.exc import OperationalError

from planbench_api.db.session import DatabaseUnavailable, create_db_engine


def test_create_db_engine_postgresql_retry_success():
    """Test that create_db_engine retries on OperationalError and succeeds if DB becomes available."""
    mock_connect = MagicMock()
    # Fail twice with OperationalError, then succeed (return mock connection context manager)
    mock_conn = MagicMock()
    mock_connect.side_effect = [
        OperationalError("connection refused", params=None, orig=Exception("refused")),
        OperationalError("connection refused", params=None, orig=Exception("refused")),
        mock_conn,
    ]

    with patch("planbench_api.db.session.create_engine") as mock_sqlalchemy_create_engine, patch("time.sleep") as mock_sleep:
        mock_engine = MagicMock()
        mock_engine.connect = mock_connect
        mock_sqlalchemy_create_engine.return_value = mock_engine

        # We pass a fake postgresql URL and max_retries=3, backoff_factor=0.01 for fast test
        engine = create_db_engine(
            "postgresql://user:pass@localhost:5432/planbench",
            max_retries=3,
            backoff_factor=0.01,
        )

        assert engine is mock_engine
        assert mock_connect.call_count == 3
        assert mock_sleep.call_count == 2


def test_create_db_engine_postgresql_retry_exhausted():
    """Test that create_db_engine raises DatabaseUnavailable after max_retries attempts."""
    mock_connect = MagicMock()
    mock_connect.side_effect = OperationalError("connection refused", params=None, orig=Exception("refused"))

    with patch("planbench_api.db.session.create_engine") as mock_sqlalchemy_create_engine, patch("time.sleep") as mock_sleep:
        mock_engine = MagicMock()
        mock_engine.connect = mock_connect
        mock_sqlalchemy_create_engine.return_value = mock_engine

        with pytest.raises(DatabaseUnavailable) as exc_info:
            create_db_engine(
                "postgresql://user:pass@localhost:5432/planbench",
                max_retries=3,
                backoff_factor=0.01,
            )

        assert "could not connect to postgresql" in str(exc_info.value).lower()
        assert mock_connect.call_count == 3
        assert mock_sleep.call_count == 2

