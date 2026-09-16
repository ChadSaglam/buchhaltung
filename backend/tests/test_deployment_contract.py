"""What compose promises and what the app expects have to be the same thing
(B-62, and the Settings ↔ `.env.example` half of B-60).

Nothing here runs a container — there is no daemon in CI's unit job, and a test
that needs one is a test that gets skipped. What it does instead is hold the
three files that have to agree against each other: the frontend Dockerfile,
`docker-compose.yml`, and the two `.env.example`s.

The failure this exists for is quiet by construction. `NEXT_PUBLIC_*` is inlined
by Next at **build** time, so putting one in a service's `environment:` block
does exactly nothing — no error, no warning, and the feature it controls simply
never appears. That is how the Apps switcher went missing from the compose image.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
FRONTEND_DOCKERFILE = ROOT / "frontend" / "Dockerfile"
ENV_EXAMPLES = (ROOT / ".env.example", ROOT / "backend" / ".env.example")

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return FRONTEND_DOCKERFILE.read_text(encoding="utf-8")


def _documented() -> set[str]:
    names: set[str] = set()
    for path in ENV_EXAMPLES:
        names |= set(re.findall(r"^#?\s*([A-Z0-9_]+)=", path.read_text(encoding="utf-8"), re.M))
    return names


# --------------------------------------------------------------------------- #
# The frontend image (B-62)
# --------------------------------------------------------------------------- #


async def test_every_public_var_the_image_takes_is_passed_by_compose(compose, dockerfile):
    args = set(re.findall(r"^ARG\s+(NEXT_PUBLIC_[A-Z0-9_]+)", dockerfile, re.M))
    passed = set(compose["services"]["web"]["build"]["args"])

    assert args, "the frontend image declares no NEXT_PUBLIC_* build args"
    assert args <= passed, f"compose does not pass: {sorted(args - passed)}"


async def test_compose_passes_nothing_the_image_does_not_take(compose, dockerfile):
    """A renamed ARG would otherwise leave compose passing a value into nothing."""
    args = set(re.findall(r"^ARG\s+([A-Z0-9_]+)", dockerfile, re.M))
    passed = set(compose["services"]["web"]["build"]["args"])

    assert passed <= args, f"the image does not declare: {sorted(passed - args)}"


async def test_the_public_vars_are_set_before_the_build_runs(dockerfile):
    """`ARG` after `RUN npm run build` compiles fine and inlines nothing."""
    env_line = dockerfile.index("ENV NEXT_PUBLIC_API_URL")
    build_line = dockerfile.index("RUN npm run build")

    assert env_line < build_line


async def test_no_public_var_is_passed_as_runtime_environment(compose):
    """The silent one. `NEXT_PUBLIC_*` is inlined at build time, so a runtime
    value is ignored with no error — which is exactly how the Apps switcher
    stopped rendering in the compose image."""
    falsch: list[str] = []
    for name, service in compose["services"].items():
        umgebung = service.get("environment") or []
        eintraege = umgebung if isinstance(umgebung, list) else [f"{k}={v}" for k, v in umgebung.items()]
        falsch += [f"{name}: {e}" for e in eintraege if str(e).startswith("NEXT_PUBLIC_")]

    assert falsch == [], f"these do nothing at runtime; they belong in build.args: {falsch}"


async def test_the_image_installs_from_the_lockfile(dockerfile):
    """`npm install` may resolve a different tree than the one that was tested."""
    assert "npm ci" in dockerfile
    assert not re.search(r"^RUN npm install\b", dockerfile, re.M)


async def test_the_base_image_is_pinned_to_a_major(dockerfile):
    assert re.search(r"^FROM node:\d+", dockerfile, re.M), "node:latest is not a version"


async def test_the_build_context_excludes_what_must_not_be_copied():
    ignored = (FRONTEND_DOCKERFILE.parent / ".dockerignore").read_text(encoding="utf-8").split()

    for eintrag in ("node_modules/", ".next/", ".env.local"):
        assert eintrag in ignored, f"{eintrag} would be copied into the image"


# --------------------------------------------------------------------------- #
# Compose ↔ .env.example
# --------------------------------------------------------------------------- #


async def test_every_variable_compose_needs_is_documented():
    referenziert = set(re.findall(r"\$\{([A-Z0-9_]+)[:}?-]", COMPOSE.read_text(encoding="utf-8")))

    fehlend = sorted(referenziert - _documented())

    assert fehlend == [], f"compose reads these and no .env.example mentions them: {fehlend}"


async def test_the_worker_gets_time_to_shut_down(compose):
    """B-57: docker's default is 10 s, which is not enough for a retrain to
    unwind and hand its job back to the queue."""
    assert "stop_grace_period" in compose["services"]["worker"]


async def test_the_api_has_a_healthcheck_the_worker_waits_for(compose):
    """B-61: the readiness probe is what keeps the worker from booting against a
    database that is not there yet."""
    assert "healthcheck" in compose["services"]["api"]
    assert compose["services"]["worker"]["depends_on"]["api"]["condition"] == "service_healthy"


# --------------------------------------------------------------------------- #
# Settings ↔ .env.example (the B-60 half that needs no CI)
# --------------------------------------------------------------------------- #

#: Settings that are deliberately not in any `.env.example`, with the reason.
#: Anything else that ends up here is a setting nobody can discover.
NICHT_DOKUMENTIERT: dict[str, str] = {
    "ALGORITHM": "the JWT algorithm is a contract with billing, not a deployment knob",
    "APP_VERSION": "shipped with the code; overriding it would make /api/health lie",
    "ENV": "a read-only alias for ENVIRONMENT, kept for older tooling that sets it",
}


async def test_every_setting_is_either_documented_or_explained():
    fehlend = sorted(set(Settings.model_fields) - _documented() - set(NICHT_DOKUMENTIERT))

    assert fehlend == [], (
        f"these settings exist and no .env.example mentions them: {fehlend}. "
        "Document them, or add them to NICHT_DOKUMENTIERT with a reason."
    )


async def test_the_exception_list_does_not_outlive_its_settings():
    """An entry for a setting that no longer exists is a comment pretending to be a rule."""
    verwaist = sorted(set(NICHT_DOKUMENTIERT) - set(Settings.model_fields))

    assert verwaist == [], f"NICHT_DOKUMENTIERT names settings that are gone: {verwaist}"


async def test_the_migration_url_is_documented_because_production_refuses_without_it():
    """B-24 makes this one load-bearing: an empty value, or one equal to
    DATABASE_URL, stops production from booting at all."""
    assert "MIGRATION_DATABASE_URL" in _documented()
