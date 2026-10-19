"""Deployment trust boundaries, exercised without a database or live services."""

import pytest
from fastapi.testclient import TestClient

from app.main import app, settings


@pytest.mark.parametrize("origin", [
    "https://unrelated-learner-site.vercel.app",
    "https://unrelated-service.onrender.com",
])
def test_credentialed_cors_rejects_unconfigured_hosted_origins(origin):
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.options("/v1/auth/me", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_configured_frontend_origin_remains_allowed():
    origin = settings.cors_origin_list[0]
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.options("/v1/auth/me", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_postgres_user_table_is_protected_only_by_its_existing_owner():
    from unittest.mock import Mock
    from app.db.migrate_columns import protect_owned_user_table

    connection = Mock()
    connection.dialect.name = "postgresql"
    connection.execute.return_value.scalar.return_value = True
    protect_owned_user_table(connection)
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert any("ENABLE ROW LEVEL SECURITY" in statement for statement in statements)
    assert any("REVOKE ALL" in statement and "anon, authenticated" in statement for statement in statements)
    assert not any("GRANT" in statement or "SET ROLE" in statement for statement in statements)

    connection.reset_mock()
    connection.execute.return_value.scalar.return_value = False
    protect_owned_user_table(connection)
    assert connection.execute.call_count == 1  # Metadata only for a non-owner.


def test_sqlite_user_table_protection_does_not_execute_postgres_ddl():
    from unittest.mock import Mock
    from app.db.migrate_columns import protect_owned_user_table

    connection = Mock()
    connection.dialect.name = "sqlite"
    protect_owned_user_table(connection)
    connection.execute.assert_not_called()
