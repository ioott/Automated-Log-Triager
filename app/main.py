import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.exceptions import (
    global_exception_handler,
    triage_exception_handler,
    TriagePipelineException,
)
from app.services.vector_db import VectorStore
from app.services.triage_pipeline import TriagePipelineService
from app.api import logs, knowledge_base, reports

logging.basicConfig(
    level=logging.INFO,
    format=(
        '{"time": "%(asctime)s", "level": "%(levelname)s",'
        ' "message": "%(message)s"}'
    ),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.vector_store = VectorStore()
    app.state.pipeline_service = TriagePipelineService(
        vector_store=app.state.vector_store
    )
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Asynchronous pipeline for triaging and diagnosing "
        "transaction failure logs."
    ),
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="app/templates")

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(TriagePipelineException, triage_exception_handler)

app.include_router(logs.router)
app.include_router(knowledge_base.router)
app.include_router(reports.router)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serves the frontend dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", status_code=200)
async def health_check():
    """Liveness probe for infrastructure monitoring."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}
