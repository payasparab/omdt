"""Fake GitHub API responses for contract tests."""

VALID_CONFIG = {
    "token": "ghp_test_token",
    "owner": "testorg",
    "repo": "omdt",
}

RATE_LIMIT_RESPONSE = {
    "rate": {"limit": 5000, "remaining": 4999, "reset": 1711700000}
}

CREATE_ISSUE_RESPONSE = {
    "number": 42,
    "html_url": "https://github.com/testorg/omdt/issues/42",
    "state": "open",
    "title": "Test issue",
}

UPDATE_ISSUE_RESPONSE = {
    "number": 42,
    "html_url": "https://github.com/testorg/omdt/issues/42",
    "state": "closed",
    "title": "Test issue (updated)",
}

PR_STATUS_RESPONSE = {
    "number": 10,
    "state": "open",
    "merged": False,
    "mergeable": True,
    "title": "feat: add adapter framework",
    "html_url": "https://github.com/testorg/omdt/pull/10",
    "head": {"sha": "abc123def456"},
}

WORKFLOW_STATUS_RESPONSE = {
    "id": 999,
    "status": "completed",
    "conclusion": "success",
    "name": "CI",
    "html_url": "https://github.com/testorg/omdt/actions/runs/999",
    "head_sha": "abc123def456",
}

TRIGGER_WORKFLOW_RESPONSE = {"status": "ok"}  # 204 no content

COMMIT_RESPONSE = {
    "sha": "abc123def456",
    "commit": {
        "message": "feat: initial commit",
        "author": {"name": "Payas Parab"},
    },
    "html_url": "https://github.com/testorg/omdt/commit/abc123def456",
}
