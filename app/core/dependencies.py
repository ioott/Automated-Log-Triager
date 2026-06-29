from fastapi import Request
from app.services.vector_db import VectorStore
from app.services.triage_pipeline import TriagePipelineService


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


def get_pipeline_service(request: Request) -> TriagePipelineService:
    return request.app.state.pipeline_service
