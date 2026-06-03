from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api.questions import router as questions_router
from app.core import observability
from app.core.config import settings
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    observability.setup(settings)
    if settings.sigil_enabled:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine)
    Base.metadata.create_all(bind=engine)
    yield
    observability.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions_router, prefix=settings.api_prefix)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
