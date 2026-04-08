"""
測試用量統計查詢端點

驗收標準:
- GET /api/v1/usage 回傳正確的累計統計
- 無任何呼叫時回傳零值
- Swagger 文檔包含 usage 端點說明
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.database import get_db


def _make_mock_db(total_calls=0, total_pages=0, total_cost=0.0):
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.count.return_value = total_calls
    mock_query.with_entities.return_value.first.return_value = (total_pages, total_cost)
    return mock_db


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestUsageEndpoint:
    """測試用量統計查詢"""

    def test_usage_returns_200(self, client):
        """GET /api/v1/usage 應回傳 200"""
        from app.main import app
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/usage")
        assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_usage_zero_values(self, client):
        """無呼叫時應回傳零值"""
        from app.main import app
        mock_db = _make_mock_db(0, 0, 0.0)
        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/usage")
        data = response.json()

        assert data["total_calls"] == 0
        assert data["total_pages"] == 0
        assert data["total_llm_cost"] == 0.0

        app.dependency_overrides.clear()

    def test_usage_has_period_field(self, client):
        """回應應包含 period 欄位"""
        from app.main import app
        mock_db = _make_mock_db(5, 15, 0.12)
        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/usage")
        data = response.json()

        assert "period" in data
        assert data["period"] == "all_time"

        app.dependency_overrides.clear()

    def test_usage_aggregated_values(self, client):
        """應回傳正確的累計數據"""
        from app.main import app
        mock_db = _make_mock_db(10, 42, 1.56)
        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/usage")
        data = response.json()

        assert data["total_calls"] == 10
        assert data["total_pages"] == 42
        assert data["total_llm_cost"] == 1.56

        app.dependency_overrides.clear()


class TestUsageInSwagger:
    """測試 Swagger 文檔"""

    def test_usage_endpoint_in_openapi(self, client):
        """usage 端點應出現在 OpenAPI 文檔中"""
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert "/api/v1/usage" in paths
        assert "get" in paths["/api/v1/usage"]
