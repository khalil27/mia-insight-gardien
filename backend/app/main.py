import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# Donne au logger "app.*" son propre handler pour rester visible
# indépendamment de la configuration logging d'uvicorn
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)-8s  %(name)s - %(message)s"))
    _app_logger.addHandler(_h)
_app_logger.setLevel(logging.INFO)
_app_logger.propagate = False

from .core.config import CORS_ORIGINS
from .db.database import engine
from .db import models
from .api import auth, evaluations, insights, results

# Create tables on startup (no-op if they already exist)
models.Base.metadata.create_all(bind=engine)

# Lightweight migration: add new columns to existing DB without Alembic
from sqlalchemy import text  # noqa: E402
with engine.connect() as _conn:
    for _col in (
        "model_name VARCHAR",
        "dataset_name VARCHAR",
        "dataset_intra_variance FLOAT",
        "dataset_inter_class_distance FLOAT",
        "model_used VARCHAR",
    ):
        try:
            _conn.execute(text(f"ALTER TABLE evaluations ADD COLUMN {_col}"))
            _conn.commit()
        except Exception:
            pass  # column already exists

app = FastAPI(
    title="MIA Insight Guardian API",
    description="Backend for Membership Inference Attack risk evaluation of Transformer models.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def plain_http_exception(request: Request, exc: HTTPException) -> PlainTextResponse:
    """Return errors as plain text so the frontend can display them directly."""
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


app.include_router(auth.router)
app.include_router(evaluations.router)
app.include_router(insights.router)
app.include_router(results.router)


@app.get("/", include_in_schema=False)
def health():
    return {"status": "ok"}
