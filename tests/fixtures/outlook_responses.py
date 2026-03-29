"""Fake Outlook/Graph API responses for contract tests."""

VALID_CONFIG = {
    "tenant_id": "tenant_abc",
    "client_id": "client_abc",
    "client_secret": "secret_abc",
    "shared_mailbox": "data-team@example.com",
}

TOKEN_RESPONSE = {"access_token": "fake_token_xyz", "expires_in": 3600}

LIST_MESSAGES_RESPONSE = {
    "value": [
        {
            "id": "msg_01",
            "conversationId": "conv_01",
            "internetMessageId": "<abc@mail.com>",
            "subject": "Data request",
            "from": {"emailAddress": {"address": "user@example.com"}},
            "receivedDateTime": "2026-03-29T08:00:00Z",
            "bodyPreview": "Please help with dashboard",
            "hasAttachments": False,
            "isRead": False,
        },
        {
            "id": "msg_02",
            "conversationId": "conv_01",
            "internetMessageId": "<def@mail.com>",
            "subject": "Re: Data request",
            "from": {"emailAddress": {"address": "analyst@example.com"}},
            "receivedDateTime": "2026-03-29T09:00:00Z",
            "bodyPreview": "Sure, will look into it",
            "hasAttachments": True,
            "isRead": True,
        },
    ]
}

SEND_MAIL_RESPONSE = {"status": "ok"}  # 202 accepted, no body

REPLY_RESPONSE = {"status": "ok"}  # 202 accepted, no body
