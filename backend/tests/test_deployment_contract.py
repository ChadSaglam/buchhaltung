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

    for eintrag in ("node_modules/", ".next*/", ".env.local"):
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


# --------------------------------------------------------------------------- #
# What `docker compose up` actually does — found by finally running one
# --------------------------------------------------------------------------- #


async def test_no_service_demands_a_gpu(compose):
    """`reservations.devices: [capabilities: [gpu]]` is not a preference. Compose
    refuses to start on any host without an NVIDIA GPU and the container toolkit
    — which is every Mac — and it takes the whole `up` down with it, including the
    services that have nothing to do with it. A GPU belongs in that host's own
    `docker-compose.override.yml`."""
    fordernd = []
    for name, service in compose["services"].items():
        geraete = (service.get("deploy") or {}).get("resources", {}).get("reservations", {}).get("devices") or []
        if any("gpu" in (g.get("capabilities") or []) for g in geraete):
            fordernd.append(name)

    assert fordernd == [], f"these refuse to start without a GPU: {fordernd}"


async def test_the_default_up_is_the_five_services_the_product_needs(compose):
    """Everything else is opt-in. Ollama is gigabytes and optional by design
    (B-20 put it last on the checklist; B-61 keeps `/api/health` at 200 without
    it), and the backup writes volumes nobody asked for."""
    standard = {name for name, s in compose["services"].items() if not s.get("profiles")}

    assert standard == {"web", "api", "worker", "db", "redis"}


async def test_the_optional_services_say_which_profile_turns_them_on(compose):
    for name in ("ollama", "backup"):
        profile = compose["services"][name].get("profiles")
        assert profile, f"{name} must be behind a profile"
        assert all(p.strip() for p in profile), f"{name} has an empty profile name"


async def test_the_readme_tells_you_how_to_start_the_optional_ones():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "--profile ai" in readme
    assert "--profile backup" in readme


async def test_make_check_verifies_the_generated_types():
    """They went stale between two commits and the push was refused by the hook.
    The hook and CI both checked; the only thing that did not was the command
    people actually run before pushing."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ziel = next(line for line in makefile.splitlines() if line.startswith("check:"))

    assert "api-types-check" in ziel, f"`make check` does not check the API types: {ziel}"


# --------------------------------------------------------------------------- #
# The frontend image, second pass (B-80)
# --------------------------------------------------------------------------- #

NEXT_CONFIG = ROOT / "frontend" / "next.config.ts"


def _stages(dockerfile: str) -> list[tuple[str, list[str]]]:
    """[(stage name or "", its lines)], in file order."""
    stufen: list[tuple[str, list[str]]] = []
    for zeile in dockerfile.splitlines():
        kopf = re.match(r"^FROM\s+\S+(?:\s+AS\s+(\S+))?\s*$", zeile, re.I)
        if kopf:
            stufen.append((kopf.group(1) or "", []))
        elif stufen:
            stufen[-1][1].append(zeile)
    return stufen


@pytest.fixture(scope="module")
def runtime_stage(dockerfile) -> list[str]:
    stufen = _stages(dockerfile)
    assert stufen, "the frontend Dockerfile has no FROM"
    return stufen[-1][1]


async def test_the_image_is_multi_stage(dockerfile):
    """Single-stage means the published image carries the source tree and every
    devDependency `npm ci` installed — typescript, eslint, vitest, Playwright."""
    assert len(_stages(dockerfile)) >= 2, "the frontend image is still single-stage"


async def test_the_last_stage_installs_nothing_and_builds_nothing(runtime_stage):
    """Anything the runtime stage installs, it also ships."""
    verboten = [z for z in runtime_stage if re.match(r"^RUN\s+(npm|yarn|pnpm|apk|apt)", z.strip(), re.I)]

    assert verboten == [], f"the runtime stage installs at build time: {verboten}"


async def test_the_last_stage_only_copies_what_the_server_needs(runtime_stage):
    """A `COPY . .` or a `COPY --from=build /app .` in the runtime stage undoes
    the whole point of splitting the build in two."""
    quellen = []
    for zeile in runtime_stage:
        treffer = re.match(r"^COPY\s+(?:--\S+\s+)*(\S+)\s+(\S+)\s*$", zeile.strip(), re.I)
        if treffer:
            quellen.append(treffer.group(1))

    assert quellen, "the runtime stage copies nothing — there is no application in it"
    for quelle in quellen:
        assert quelle not in (".", "./"), f"the runtime stage copies a whole tree: {quelle}"
        assert "/.next/standalone" in quelle or "/.next/static" in quelle or "/public" in quelle, (
            f"the runtime stage copies something outside the standalone bundle: {quelle}"
        )


async def test_the_static_assets_are_copied_next_to_the_server(dockerfile):
    """`output: "standalone"` deliberately leaves `.next/static` out, because Next
    expects a CDN to serve it. There is no CDN here, so the container that forgets
    this line boots, answers 200, and renders an unstyled page."""
    assert re.search(r"COPY\s+--from=\S+.*/\.next/static\s", dockerfile), (
        "the image never copies .next/static; the app would render without CSS or JS"
    )


async def test_the_container_does_not_run_as_root(runtime_stage):
    benutzer = [z.split(maxsplit=1)[1].strip() for z in runtime_stage if z.strip().upper().startswith("USER ")]

    assert benutzer, "the runtime stage never drops root"
    assert benutzer[-1] != "root", "the runtime stage explicitly switches back to root"


async def test_the_command_is_the_standalone_server(dockerfile):
    """`next start` is not part of the standalone output — the bundle ships its
    own `server.js`, and a CMD that calls `npm start` fails at container start."""
    befehl = re.findall(r"^CMD\s+(.+)$", dockerfile, re.M)[-1]

    assert "server.js" in befehl, f"the image does not start the standalone server: {befehl}"
    assert "npm" not in befehl, f"npm is not in the runtime stage: {befehl}"


async def test_the_build_is_told_to_emit_a_standalone_bundle():
    """Without this, `.next/standalone` does not exist and the COPY above fails —
    at build time, which is the good case. This test is the cheap case."""
    konfiguration = NEXT_CONFIG.read_text(encoding="utf-8")

    assert re.search(r'output:\s*"standalone"', konfiguration), (
        'frontend/next.config.ts must set output: "standalone" or the image has nothing to copy'
    )


async def test_the_image_says_when_it_is_ready(dockerfile):
    assert "HEALTHCHECK" in dockerfile, "the frontend image reports no health"


async def test_compose_waits_for_the_web_service_too(compose):
    """The API got one in B-61; the web service booting into a blank page was
    still indistinguishable from a healthy one."""
    assert "healthcheck" in compose["services"]["web"]


async def test_the_healthcheck_asks_for_a_page_that_needs_no_session(compose, dockerfile):
    """`/dashboard` answers 401 without a cookie, and a probe that reads its own
    401 as an outage restarts a container that is working perfectly."""
    probe = " ".join(compose["services"]["web"]["healthcheck"]["test"])
    im_image = dockerfile[dockerfile.index("HEALTHCHECK") :]

    for ort in (probe, im_image):
        assert "/login" in ort, f"the health probe does not ask for a public page: {ort}"
        assert "/dashboard" not in ort, f"the health probe asks for a page behind the session: {ort}"


async def test_every_build_directory_is_out_of_the_image_context():
    """`.next/` alone does not match `.next-e2e/` or a one-off verification
    build's directory, and both are hundreds of megabytes of stale cache."""
    ignoriert = (FRONTEND_DOCKERFILE.parent / ".dockerignore").read_text(encoding="utf-8").split()

    assert ".next*/" in ignoriert, "only the default dist dir is excluded from the build context"


async def test_every_build_directory_is_out_of_git():
    """1265 files from a `.next-sa/` once reached a commit this way."""
    for datei in (ROOT / ".gitignore", ROOT / "frontend" / ".gitignore"):
        muster = datei.read_text(encoding="utf-8").split()
        assert ".next*/" in muster, f"{datei.relative_to(ROOT)} does not ignore every NEXT_DIST_DIR"
