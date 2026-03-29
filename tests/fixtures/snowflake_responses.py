"""Fake Snowflake adapter responses for contract tests."""

VALID_CONFIG = {
    "account": "test_account",
    "user": "test_user",
    "password": "secret_pass",
    "warehouse": "COMPUTE_WH",
}

TEST_CONNECTION_RESPONSE = {
    "connected": True,
    "account": "test_account",
    "user": "test_user",
}

RUN_QUERY_RESPONSE = {
    "query": "SELECT 1",
    "warehouse": "COMPUTE_WH",
    "rows": [],
    "row_count": 0,
    "status": "executed",
}

LIST_DATABASES_RESPONSE = {"databases": [], "status": "ok"}

LIST_ROLES_RESPONSE = {"roles": [], "status": "ok"}

CREATE_USER_RESPONSE = {"username": "new_user", "created": True, "status": "ok"}

GRANT_ROLE_RESPONSE = {
    "username": "new_user",
    "role": "ANALYST",
    "granted": True,
    "status": "ok",
}

REVOKE_ROLE_RESPONSE = {
    "username": "old_user",
    "role": "ANALYST",
    "revoked": True,
    "status": "ok",
}

DESCRIBE_SCHEMA_RESPONSE = {
    "database": "ANALYTICS",
    "schema": "PUBLIC",
    "tables": [],
    "views": [],
    "status": "ok",
}

WAREHOUSE_USAGE_RESPONSE = {
    "warehouse": "COMPUTE_WH",
    "credits_used": 0.0,
    "queries_executed": 0,
    "status": "ok",
}
