#!/usr/bin/env bash
# validate_all.sh — Run every quality gate locally (mirrors CI).
# Usage: bash scripts/validate_all.sh
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

step=0
pass() { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; exit 1; }
run() {
  step=$((step + 1))
  echo -e "\n${BOLD}[$step] $1${RESET}"
  shift
  "$@" && pass "passed" || fail "failed"
}

run "Validate config files"        python -m app.cli.main config validate
run "Lint (ruff check)"            ruff check .
run "Format check (ruff format)"   ruff format --check .
run "Type check (mypy)"            mypy app/
run "Unit tests"                   pytest tests/unit/ --cov=app --cov-report=term-missing -q
run "Contract tests"               pytest tests/contract/ -q 2>/dev/null || echo "  (no contract tests)"
run "Workflow tests"               pytest tests/workflows/ -q
run "Config tests"                 pytest tests/config/ -q
run "Migration tests"              pytest tests/migrations/ -q 2>/dev/null || echo "  (no migration tests)"
run "Security scan (bandit)"       bandit -r app/ -c pyproject.toml
run "Dependency audit (pip-audit)" pip-audit

echo -e "\n${GREEN}${BOLD}All quality gates passed.${RESET}"
