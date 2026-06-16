import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class ReportStorage:
    """Simple in-memory storage for diagnosed reports to be viewed in the dashboard."""
    _reports: List[Dict] = []

    @classmethod
    def add_report(cls, report: Dict):
        cls._reports.insert(0, report) # Keep newest first
        # Limit to last 50 reports to prevent memory issues
        if len(cls._reports) > 50:
            cls._reports.pop()
        logger.info(f"Report added to storage. Total: {len(cls._reports)}")

    @classmethod
    def get_all(cls) -> List[Dict]:
        return cls._reports
