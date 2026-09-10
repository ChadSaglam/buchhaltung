from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import async_session, engine
from app.core.errors import RequestContextMiddleware, install_error_handlers
from app.core.logging_config import configure_logging
from app.core.rate_limit import enforce_default_limit, limiter
from app.core.sentry import configure_sentry
from app.models.base import Base
from app.services.scheduler import get_scheduler
from app.services.training_worker import get_training_worker, init_training_worker

load_dotenv()
configure_logging(settings.LOG_LEVEL)
configure_sentry(settings.SENTRY_DSN, settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(application: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        # Dev/test convenience only — in production Alembic owns the schema.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    init_training_worker(async_session)
    get_scheduler().start_all()
    yield
    get_scheduler().stop_all()
    await get_training_worker().shutdown()


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

application.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

application.add_middleware(RequestContextMiddleware)
install_error_handlers(application)

# 429s go through the uniform error envelope (core/errors.py).
application.state.limiter = limiter

from app.routers import (
    ai,
    audit,
    auth,
    bookings,
    classify,
    classify_extra,
    export,
    health,
    import_data,
    pdf,
    review,
    scanner,
    scanner_config,
    stats,
)
from app.routers import kontenplan as kontenplan_router

application.include_router(auth.router, prefix="/api/auth", tags=["auth"])
application.include_router(classify.router)
application.include_router(classify_extra.router)
application.include_router(bookings.router)
application.include_router(kontenplan_router.router)
application.include_router(export.router)
application.include_router(scanner.router)
application.include_router(scanner_config.router)
application.include_router(pdf.router)
application.include_router(stats.router)
application.include_router(import_data.router)
application.include_router(review.router)
application.include_router(audit.router)
application.include_router(health.router)
application.include_router(ai.router)


app = application
