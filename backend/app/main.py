from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import async_session, engine
from app.core.errors import RequestContextMiddleware, install_error_handlers
from app.core.logging_config import configure_logging
from app.core.rate_limit import enforce_default_limit, limiter
from app.core.rls import verify_rls_role
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.sentry import configure_sentry
from app.core.uploads import MaxBodySizeMiddleware
from app.models.base import Base
from app.worker import BackgroundJobs

load_dotenv()
configure_logging(settings.LOG_LEVEL)
configure_sentry(settings.SENTRY_DSN, settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(application: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        # Dev/test convenience only — in production Alembic owns the schema.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    await verify_rls_role()
    # Scheduler + training worker share the API's event loop only when asked
    # to (dev default). In compose the `worker` service runs them instead.
    jobs: BackgroundJobs | None = None
    if settings.RUN_WORKER_IN_API:
        jobs = BackgroundJobs(async_session)
        jobs.start()
    application.state.background_jobs = jobs
    yield
    if jobs is not None:
        await jobs.stop()


application = FastAPI(
    title="Buchhaltung API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Default rate limit on every route (see core/rate_limit.py for why this is
    # a dependency and not slowapi's middleware).
    dependencies=[Depends(enforce_default_limit)],
    # Hide interactive docs in production; the OpenAPI schema stays available
    # for the type-generation pipeline in non-prod environments.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Starlette applies middleware in reverse: the LAST one added is the OUTERMOST.
# This block therefore reads inside-out, and CORS has to stay at the bottom.
#
# B-54: an oversized upload is refused on its Content-Length, before the router
# and before any body is read — inside CORS, so the browser reports a 413 and
# the user reads "file too large" instead of "network error".
# B-108: four response headers, innermost so every response carries them —
# including the ones the two middlewares below build for errors.
application.add_middleware(SecurityHeadersMiddleware)

application.add_middleware(MaxBodySizeMiddleware)

# RequestContextMiddleware catches an unhandled exception and *builds* the 500
# itself. A response built outside CORS never gets an Access-Control-Allow-Origin
# header, so the browser reports every server error as a CORS failure and the
# real cause never reaches the developer — the comment above had the principle
# right and the line below it used to break it.
#
# The first real run (2026-09-17) is what surfaced this: the console said
# "blocked by CORS policy", CORS was configured perfectly, and the actual error
# was an RLS refusal on /api/auth/register that nothing in the browser could
# show. Two hours of the wrong suspect.
#
# What it costs: CORS now answers preflights before they reach here, so OPTIONS
# no longer appears in the access log. A fair trade for errors that say what
# they are — and it removes a wall of OPTIONS lines from the log as a bonus.
application.add_middleware(RequestContextMiddleware)

# Outermost on purpose: every response leaves through here, including the ones
# the two middlewares above build for errors.
application.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
install_error_handlers(application)

# 429s go through the uniform error envelope (core/errors.py).
application.state.limiter = limiter

from app.routers import (
    abgleich,
    abschluss,
    ai,
    audit,
    auth,
    bookings,
    classify,
    classify_extra,
    dauerbuchungen,
    documents,
    email_intake,
    export,
    export_batch,
    health,
    import_data,
    liquiditaet,
    lohn,
    offene_posten,
    onboarding,
    pdf,
    platform_events,
    rechnung,
    review,
    scanner,
    scanner_config,
    sso,
    stats,
    usage,
)
from app.routers import kontenplan as kontenplan_router

application.include_router(auth.router, prefix="/api/auth", tags=["auth"])
application.include_router(sso.router)
application.include_router(platform_events.router)
application.include_router(classify.router)
application.include_router(classify_extra.router)
application.include_router(bookings.router)
application.include_router(kontenplan_router.router)
application.include_router(export.router)
application.include_router(export_batch.router)
application.include_router(scanner.router)
application.include_router(scanner_config.router)
application.include_router(pdf.router)
application.include_router(stats.router)
application.include_router(import_data.router)
application.include_router(review.router)
application.include_router(audit.router)
application.include_router(health.router)
application.include_router(ai.router)
application.include_router(documents.router)
application.include_router(abgleich.router)
application.include_router(offene_posten.router)
application.include_router(rechnung.router)
application.include_router(email_intake.router)
application.include_router(abschluss.router)
application.include_router(liquiditaet.router)
application.include_router(dauerbuchungen.router)
application.include_router(lohn.router)
application.include_router(onboarding.router)
application.include_router(usage.router)


app = application
