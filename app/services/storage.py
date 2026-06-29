import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

_reports: List[Dict] = []
_MAX = 50


def add_report(report: Dict) -> None:
    _reports.insert(0, report)
    if len(_reports) > _MAX:
        _reports.pop()
    logger.info(f"Report added to storage. Total: {len(_reports)}")


def get_all() -> List[Dict]:
    return _reports
