from fastapi import APIRouter
from app.services import storage

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("")
async def get_reports():
    """Returns all diagnosed reports for the dashboard."""
    return storage.get_all()
