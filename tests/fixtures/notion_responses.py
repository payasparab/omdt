"""Fake Notion API responses for contract tests."""

VALID_CONFIG = {"api_key": "ntn_test_secret_abc123"}

USER_ME_RESPONSE = {
    "object": "user",
    "id": "bot_01",
    "name": "OMDT Bot",
    "type": "bot",
}

CREATE_PAGE_RESPONSE = {
    "id": "page_01",
    "url": "https://www.notion.so/page_01",
    "object": "page",
    "created_time": "2026-03-29T00:00:00Z",
    "last_edited_time": "2026-03-29T00:00:00Z",
    "properties": {
        "title": {"title": [{"text": {"content": "Test PRD"}}]},
    },
}

UPDATE_PAGE_RESPONSE = {
    "id": "page_01",
    "url": "https://www.notion.so/page_01",
    "object": "page",
    "properties": {
        "Status": {"select": {"name": "In Review"}},
    },
}

GET_PAGE_RESPONSE = {
    "id": "page_01",
    "url": "https://www.notion.so/page_01",
    "object": "page",
    "created_time": "2026-03-29T00:00:00Z",
    "last_edited_time": "2026-03-29T12:00:00Z",
    "properties": {
        "title": {"title": [{"text": {"content": "Test PRD"}}]},
        "Status": {"select": {"name": "Draft"}},
    },
}
