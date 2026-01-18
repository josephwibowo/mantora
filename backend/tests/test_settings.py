"""Tests for settings API endpoint."""

from mantora.app import create_app
from mantora.config.settings import Caps, SafetyMode, Settings


def test_get_settings_protective_mode() -> None:
    """Test settings endpoint returns all rules in protective mode."""
    settings = Settings(safety_mode=SafetyMode.protective)
    app = create_app(settings=settings)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/api/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["safety_mode"] == "protective"
    assert len(data["active_rules"]) == 6  # includes always-on + toggle-driven rules

    rule_ids = {rule["id"] for rule in data["active_rules"]}
    assert "unknown_tool_requires_approval" in rule_ids
    assert "block_destructive" in rule_ids
    assert "block_ddl" in rule_ids
    assert "block_dml" in rule_ids
    assert "block_multi_statement" in rule_ids
    assert "block_delete_without_where" in rule_ids


def test_get_settings_transparent_mode() -> None:
    """Test settings endpoint returns empty rules in transparent mode."""
    settings = Settings(safety_mode=SafetyMode.transparent)
    app = create_app(settings=settings)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/api/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["safety_mode"] == "transparent"
    assert len(data["active_rules"]) == 0


def test_settings_includes_limits() -> None:
    """Test settings endpoint includes caps/limits."""
    settings = Settings(
        caps=Caps(max_preview_rows=100, max_preview_payload_bytes=1024, max_columns=50)
    )
    app = create_app(settings=settings)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/api/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["limits"]["max_preview_rows"] == 100
    assert data["limits"]["max_preview_payload_bytes"] == 1024
    assert data["limits"]["max_columns"] == 50


def test_cors_origins_configured() -> None:
    """App uses configured CORS origins."""
    settings = Settings(cors_allow_origins=["http://localhost:3001"])
    app = create_app(settings=settings)

    cors_middleware = [m for m in app.user_middleware if "CORSMiddleware" in str(m.cls)]
    assert cors_middleware
    options = getattr(cors_middleware[0], "options", cors_middleware[0].kwargs)
    assert options["allow_origins"] == ["http://localhost:3001"]
