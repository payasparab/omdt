"""Fake Linear API responses for contract tests."""

VALID_CONFIG = {"api_key": "lin_test_key_abc123"}

VIEWER_RESPONSE = {
    "data": {"viewer": {"id": "user_01", "name": "Test User"}}
}

CREATE_ISSUE_RESPONSE = {
    "data": {
        "issueCreate": {
            "success": True,
            "issue": {
                "id": "issue_01",
                "identifier": "DATA-1",
                "title": "Test Issue",
                "state": {"name": "Todo"},
            },
        }
    }
}

UPDATE_ISSUE_RESPONSE = {
    "data": {
        "issueUpdate": {
            "success": True,
            "issue": {
                "id": "issue_01",
                "identifier": "DATA-1",
                "title": "Updated Issue",
                "state": {"name": "In Progress"},
            },
        }
    }
}

CREATE_PROJECT_RESPONSE = {
    "data": {
        "projectCreate": {
            "success": True,
            "project": {"id": "proj_01", "name": "Test Project"},
        }
    }
}

COMMENT_CREATE_RESPONSE = {
    "data": {
        "commentCreate": {
            "success": True,
            "comment": {"id": "comment_01", "body": "A comment"},
        }
    }
}

SEARCH_RESPONSE = {
    "data": {
        "issueSearch": {
            "nodes": [
                {
                    "id": "issue_01",
                    "identifier": "DATA-1",
                    "title": "Test Issue",
                    "state": {"name": "Todo"},
                }
            ]
        }
    }
}

WEBHOOK_ISSUE_CREATE = {
    "action": "create",
    "type": "Issue",
    "data": {
        "id": "issue_webhook_01",
        "identifier": "DATA-5",
        "title": "Webhook created issue",
        "state": {"name": "Backlog"},
    },
}

WEBHOOK_ISSUE_UPDATE = {
    "action": "update",
    "type": "Issue",
    "data": {
        "id": "issue_webhook_01",
        "identifier": "DATA-5",
        "title": "Updated via webhook",
        "state": {"name": "In Progress"},
    },
}
