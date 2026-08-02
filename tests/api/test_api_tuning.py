"""API tests: P01 tuning-results endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from planbench_benchmark import SEARCH_SPACES


class TestTuningResults:
    def test_unauthenticated_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/v1/tuning").status_code == 401

    def test_returns_a_dict_shaped_response(self, client: TestClient, alice_headers) -> None:
        """Doesn't require scripts/tune_hyperparameters.py to have been
        run — an empty dict is a valid "not yet tuned" answer. If the
        checked-in cache is present, its entries must be sane."""
        response = client.get("/api/v1/tuning", headers=alice_headers)
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)
        for algorithm_id, result in body.items():
            assert algorithm_id in SEARCH_SPACES
            assert result["algorithm"] == algorithm_id
            assert 0.0 <= result["best_value"] <= 1.0
            assert len(result["trials"]) == result["n_trials"]
