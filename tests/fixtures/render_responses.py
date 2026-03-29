"""Fake Render API responses for contract tests."""

VALID_CONFIG = {"api_key": "rnd_test_key_abc"}

OWNERS_RESPONSE = [{"id": "owner_01", "name": "Test Owner"}]

DEPLOY_RESPONSE = {
    "deploy": {
        "id": "dep_01",
        "status": "created",
        "commit": {"id": "abc123"},
    }
}

RESTART_RESPONSE = {"status": "ok"}

CREATE_SERVICE_RESPONSE = {
    "service": {
        "id": "srv_cron_01",
        "name": "daily-sync",
        "type": "cron_job",
    }
}

UPDATE_SERVICE_RESPONSE = {
    "service": {
        "id": "srv_cron_01",
        "name": "daily-sync",
        "type": "cron_job",
    }
}

DEPLOY_LOGS_RESPONSE = {
    "logs": [
        {"timestamp": "2026-03-29T08:00:00Z", "message": "Build started"},
        {"timestamp": "2026-03-29T08:01:00Z", "message": "Build completed"},
    ]
}

SERVICE_STATUS_RESPONSE = {
    "service": {
        "id": "srv_01",
        "name": "omdt-api",
        "type": "web_service",
        "serviceDetails": {
            "status": "running",
            "url": "https://omdt-api.onrender.com",
        },
    }
}
