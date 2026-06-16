from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, async_session
from app.models.base import Base
from app.services.training_worker import init_training_worker, get_training_worker
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(application: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    init_training_worker(async_session)
    yield
    await get_training_worker().shutdown()


application = FastAPI(title="Buchhaltung API", version="2.0.0", lifespan=lifespan)

application.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import auth, classify, bookings, kontenplan as kontenplan_router
from app.routers import export, scanner, pdf, classify_extra, stats, import_data, review, scanner_config

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


@application.get("/api/health")
async def health():
    return {"status": "ok"}


app = application