"""CI has to test what the product actually runs on (B-60).

Every defect this week that the local suite missed, CI could have caught — and
one CI caught that the local suite could not. The difference was never the
tests; it was which database, which process and which image they ran against.

So this file holds the workflow against the claims the roadmap makes for it. It
cannot run GitHub Actions, and a test that pretends to would be worse than none:
what it does is fail when somebody quietly drops a leg.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"
REQUIREMENTS_DEV = ROOT / "backend" / "requirements-dev.txt"
SETUP_SH = ROOT / "scripts" / "setup.sh"

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _steps(job: dict) -> str:
    return yaml.safe_dump(job.get("steps", []))


# --------------------------------------------------------------------------- #
# Both databases
# --------------------------------------------------------------------------- #


async def test_the_backend_suite_runs_on_both_databases(workflow):
    """SQLite has no fixed-width integers and no row-level security; Postgres is
    what production runs. Each hides a different class of bug from the other —
    `usage_events.quantity` overflowed int32 on one and passed on the other for
    weeks."""
    matrix = workflow["jobs"]["backend"]["strategy"]["matrix"]["db"]

    assert set(matrix) == {"postgres", "sqlite"}


async def test_a_failing_leg_does_not_hide_the_other(workflow):
    """The point of running both is seeing *which* one disagrees."""
    assert workflow["jobs"]["backend"]["strategy"]["fail-fast"] is False


async def test_the_database_url_actually_changes_per_leg(workflow):
    """A matrix whose legs all use the same connection string runs one thing twice."""
    url = workflow["jobs"]["backend"]["env"]["DATABASE_URL"]

    assert "matrix.db" in url
    assert "sqlite" in url
    assert "postgresql" in url


# --------------------------------------------------------------------------- #
# Migrations go down as well as up
# --------------------------------------------------------------------------- #


async def test_migrations_are_reversed_and_reapplied(workflow):
    """A migration nobody has ever reversed cannot be rolled back at 3 a.m."""
    steps = _steps(workflow["jobs"]["migrations"])

    assert "alembic downgrade base" in steps
    assert "alembic upgrade head" in steps


async def test_drift_is_still_checked(workflow):
    assert "autogenerate" in _steps(workflow["jobs"]["migrations"])


# --------------------------------------------------------------------------- #
# The thing that has never been started
# --------------------------------------------------------------------------- #


async def test_there_is_a_compose_smoke_job(workflow):
    """Production *is* compose. Until this job existed, nothing had ever asserted
    that the stack starts at all."""
    assert "compose-smoke" in workflow["jobs"]


async def test_the_smoke_job_starts_the_stack_and_asks_it_a_question(workflow):
    steps = _steps(workflow["jobs"]["compose-smoke"])

    assert "docker compose up" in steps
    assert "--wait" in steps, "without --wait the health check races the boot"
    assert "/api/health" in steps


async def test_the_smoke_job_runs_the_worker(workflow):
    """The worker is the half with no HTTP surface; `--once` is the only way to
    find out it can reach the database it was given."""
    steps = _steps(workflow["jobs"]["compose-smoke"])

    assert "app.worker --once" in steps


async def test_the_smoke_job_builds_the_frontend_image(workflow):
    """It had never been built in CI, and its NEXT_PUBLIC_* build args are easy
    to break silently (B-62)."""
    assert re.search(r"docker compose build[^\n]*\bweb\b", _steps(workflow["jobs"]["compose-smoke"]))


async def test_the_smoke_job_does_not_pull_ollama(workflow):
    """Nothing in the smoke test needs a model, and the image is gigabytes."""
    steps = _steps(workflow["jobs"]["compose-smoke"])

    assert re.search(r"docker compose up[^\n]*", steps)
    assert not re.search(r"docker compose up[^\n]*\bollama\b", steps)


async def test_the_smoke_job_prints_logs_when_it_fails(workflow):
    """A red job with no output is a job people re-run instead of reading."""
    steps = _steps(workflow["jobs"]["compose-smoke"])

    assert "docker compose logs" in steps
    assert "if: failure()" in steps or "failure()" in steps


async def test_the_smoke_job_tears_down_even_when_it_fails(workflow):
    assert "docker compose down" in _steps(workflow["jobs"]["compose-smoke"])


async def test_the_smoke_job_generates_its_secrets(workflow):
    """A fixed value in a workflow file is a credential in git."""
    steps = _steps(workflow["jobs"]["compose-smoke"])

    assert "openssl rand" in steps
    assert "SECRET_KEY" in steps


# --------------------------------------------------------------------------- #
# One formatter, one version
# --------------------------------------------------------------------------- #


def _pinned_ruff() -> str | None:
    match = re.search(r"^ruff==([0-9][^\s#]*)", REQUIREMENTS_DEV.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


def _pre_commit_ruff() -> str | None:
    text = PRE_COMMIT.read_text(encoding="utf-8")
    match = re.search(r"astral-sh/ruff-pre-commit\s*\n\s*rev:\s*v?([0-9][^\s#]*)", text)
    return match.group(1) if match else None


async def test_ruff_is_pinned_not_floated():
    """`ruff>=0.9` meant the hook, CI and a laptop could each format differently,
    and the one that disagrees is always the one nobody has locally."""
    assert _pinned_ruff() is not None, "requirements-dev.txt must pin ruff exactly"


async def test_the_hook_and_ci_use_the_same_ruff():
    assert _pinned_ruff() == _pre_commit_ruff(), (
        f"requirements-dev.txt has ruff=={_pinned_ruff()} and .pre-commit-config.yaml has "
        f"v{_pre_commit_ruff()}. Bump both or neither."
    )


async def test_lint_runs_once_not_once_per_matrix_leg(workflow):
    assert "lint" in workflow["jobs"]
    assert "ruff" not in _steps(workflow["jobs"]["backend"])


# --------------------------------------------------------------------------- #
# No credentials in the repo
# --------------------------------------------------------------------------- #


async def test_the_setup_script_carries_no_password():
    """It used to hardcode a real one, which put it in every clone and every
    fork — and left it in the history after it was removed."""
    text = SETUP_SH.read_text(encoding="utf-8")

    treffer = re.findall(r"postgresql://[^:\s\"']+:([^@\s\"']+)@", text)
    echte = [t for t in treffer if "$" not in t and t not in ("CHANGE_ME", "")]

    assert echte == [], f"a literal password in scripts/setup.sh: {echte}"
