"""Fake Gamma API responses for contract tests."""

VALID_CONFIG = {
    "api_key": "gamma_test_key",
    "base_url": "https://api.gamma.app",
}

HEALTH_RESPONSE = {"status": "ok"}

SUBMIT_JOB_RESPONSE = {
    "id": "job_01",
    "status": "submitted",
}

POLL_JOB_PENDING_RESPONSE = {
    "id": "job_01",
    "status": "processing",
    "progress": 0.5,
    "error": None,
}

POLL_JOB_COMPLETE_RESPONSE = {
    "id": "job_01",
    "status": "completed",
    "progress": 1.0,
    "error": None,
}

RETRIEVE_OUTPUT_RESPONSE = {
    "url": "https://gamma.app/output/job_01.pdf",
    "format": "pdf",
    "metadata": {"pages": 12, "template": "briefing"},
}
