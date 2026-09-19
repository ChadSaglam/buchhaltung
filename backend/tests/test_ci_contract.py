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


# --------------------------------------------------------------------------- #
# What the smoke job has to do now that the image is standalone (B-80)
# --------------------------------------------------------------------------- #


async def test_the_smoke_job_starts_the_frontend_image_it_just_built(workflow):
    """Building the image proved it compiles. It did not prove it runs — and
    `output: "standalone"` moved the runtime from `next start` to a bundle that
    is assembled by two separate COPY lines."""
    steps = _steps(workflow["jobs"]["compose-smoke"])
    starten = re.search(r"docker compose up[^\n]*", steps)

    assert starten, "the smoke job never starts the stack"
    assert re.search(r"\bweb\b", starten.group(0)), f"the web image is built and never run: {starten.group(0)}"


async def test_the_smoke_job_fetches_an_asset_not_only_a_page(workflow):
    """A runtime stage that forgets `.next/static` boots, answers 200 on /login,
    and renders it without a single stylesheet. Only asking for the asset the
    page references tells the two apart."""
    steps = _steps(workflow["jobs"]["compose-smoke"])

    assert "/_next/static/" in steps, "nothing in the smoke job would notice an unstyled page"


async def test_the_e2e_server_is_the_one_production_runs(workflow):
    """Next refuses to support `next start` with output: "standalone" — it warns
    and serves anyway today. CI running on that warning is a failure waiting for
    a Next upgrade, so playwright.config.ts starts the standalone bundle."""
    konfiguration = (ROOT / "frontend" / "playwright.config.ts").read_text(encoding="utf-8")

    assert "serve-standalone.sh" in konfiguration
    assert "npm run start" not in konfiguration


async def test_the_serve_script_copies_what_the_dockerfile_copies():
    """Two places assemble the same bundle. If they drift, CI passes against a
    layout the image does not have."""
    skript = (ROOT / "scripts" / "serve-standalone.sh").read_text(encoding="utf-8")
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    for teil in ("standalone", "static"):
        assert teil in skript, f"the serve script does not place {teil}"
        assert teil in dockerfile, f"the image does not copy {teil}"


# --------------------------------------------------------------------------- #
# The runtime lockfile (B-81)
# --------------------------------------------------------------------------- #

REQUIREMENTS_IN = ROOT / "backend" / "requirements.in"
REQUIREMENTS_TXT = ROOT / "backend" / "requirements.txt"


def _verteilungen(text: str) -> set[str]:
    """The distribution names a requirements file asks for, normalised (PEP 503)."""
    namen: set[str] = set()
    for zeile in text.splitlines():
        zeile = zeile.split("#")[0].strip()
        if not zeile or zeile.startswith("-"):
            continue
        name = re.split(r"[\[<>=!~;\s]", zeile, maxsplit=1)[0]
        if name:
            namen.add(re.sub(r"[-_.]+", "-", name).lower())
    return namen


async def test_the_input_and_the_lock_are_two_different_files():
    """`>=` is a decision about what we accept; the lock is what actually got
    installed. One file cannot be both."""
    assert REQUIREMENTS_IN.exists(), "backend/requirements.in is the input and must exist"
    assert REQUIREMENTS_TXT.exists(), "backend/requirements.txt is the compiled tree (run: make lock)"


async def test_the_lock_says_it_is_generated():
    """Dependabot finds a pip-compile output by this header, and so does the next
    person tempted to edit the file by hand."""
    kopf = REQUIREMENTS_TXT.read_text(encoding="utf-8")[:400]

    assert "autogenerated by pip-compile" in kopf, "requirements.txt is not a compiled file (run: make lock)"
    assert "requirements.in" in kopf, "the header does not name its input"


async def test_the_lock_was_compiled_for_the_python_ci_runs():
    """pip-compile resolves for the interpreter it runs on. On 3.11 this file
    pins numpy 2.4.6; on 3.13, 2.5.3. The wrong one installs a tree the image
    never runs, and nothing downstream would say so."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ci_version = re.search(r'PYTHON_VERSION:\s*"?([\d.]+)"?', workflow)
    kopf = REQUIREMENTS_TXT.read_text(encoding="utf-8")[:400]

    assert ci_version, "the workflow no longer declares PYTHON_VERSION"
    assert f"with Python {ci_version.group(1)}" in kopf, (
        f"the lock was not compiled with Python {ci_version.group(1)} — see the header, and run: make lock"
    )


async def test_nothing_we_require_is_missing_from_the_lock():
    """The failure this exists for: a line is added to requirements.in and
    `make lock` is not run. Everything keeps working locally, and the image
    ships without the package."""
    gewuenscht = _verteilungen(REQUIREMENTS_IN.read_text(encoding="utf-8"))
    gepinnt = {
        re.sub(r"[-_.]+", "-", m).lower()
        for m in re.findall(
            r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==", REQUIREMENTS_TXT.read_text("utf-8"), re.M
        )
    }

    fehlend = sorted(gewuenscht - gepinnt)

    assert fehlend == [], f"in requirements.in and not in the lock: {fehlend}. Run: make lock"


async def test_every_line_of_the_lock_is_pinned():
    """One `>=` in here and two installs a month apart are different installs
    again — which is the whole of B-81."""
    lose = [
        zeile
        for zeile in REQUIREMENTS_TXT.read_text(encoding="utf-8").splitlines()
        if zeile[:1].isalnum() and "==" not in zeile
    ]

    assert lose == [], f"these are not pinned: {lose}"


async def test_make_lock_refuses_on_the_wrong_python():
    """The guard is the feature. Without it the command is a foot-gun that
    reports success."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ziel = makefile[makefile.index("\nlock:") :].split("\n\n")[0]

    assert "PYTHON_VERSION" in ziel, "`make lock` does not check which Python it is resolving for"
    assert "exit 1" in ziel, "`make lock` warns about the wrong Python instead of refusing"


async def test_the_image_and_ci_install_the_lock_not_the_ranges():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "requirements.in" not in dockerfile, "the image installs the ranges instead of the lock"
    assert "requirements.txt" in dockerfile
    assert "requirements.in" not in workflow, "a CI job installs the ranges instead of the lock"


async def test_the_audit_reads_the_lock():
    """`fastapi>=0.115.6` says nothing about which fastapi is installed, so an
    audit of the input file is an audit of nothing."""
    security = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    pruefung = next(line for line in security.splitlines() if "pip-audit" in line and "-r" in line)

    assert "requirements.txt" in pruefung, f"pip-audit does not read the lock: {pruefung}"


async def test_something_will_move_the_lock():
    """A pinned tree nobody bumps is a tree that rots until an upgrade is a week
    of work. Dependabot's pip ecosystem finds the .in/.txt pair by itself; it
    just has to be pointed at the directory."""
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    pip = [u for u in config["updates"] if u["package-ecosystem"] == "pip"]

    assert pip, "nothing bumps the backend dependencies"
    assert any(u["directory"].rstrip("/").endswith("backend") for u in pip), (
        "dependabot's pip entry does not point at backend/"
    )


async def test_ci_and_the_image_agree_on_which_python_this_is():
    """The lock is compiled for one interpreter. If the workflow and the image do
    not name the same one, half of what runs is running on a tree that was never
    resolved for it — and nothing else in this repo would say so."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    ci_version = re.search(r'PYTHON_VERSION:\s*"?([\d.]+)"?', workflow)
    im_image = set(re.findall(r"^FROM\s+python:([\d.]+)", dockerfile, re.M))

    assert ci_version, "the workflow no longer declares PYTHON_VERSION"
    assert im_image, "the backend image no longer pins a Python version"
    assert im_image == {ci_version.group(1)}, f"CI runs Python {ci_version.group(1)}, the image runs {sorted(im_image)}"


async def test_make_setup_says_something_when_the_local_python_is_a_different_one():
    """Installing a lock resolved for another minor usually works and sometimes
    fails with a compiler error that explains nothing. A warning is enough — a
    newer local venv is a choice, not a mistake."""
    ziel = (ROOT / "Makefile").read_text(encoding="utf-8")
    setup = ziel[ziel.index("\nsetup:") :].split("\n\n")[0]

    assert "PYTHON_VERSION" in setup, "`make setup` installs the lock without checking which Python it is for"
