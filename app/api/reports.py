from fastapi import APIRouter
from app.services.storage import ReportStorage

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("")
async def get_reports():
    """Returns all diagnosed reports for the dashboard."""
    return ReportStorage.get_all()
