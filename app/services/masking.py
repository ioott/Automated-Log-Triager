import re
import json
from typing import Any
from datetime import datetime

_IP = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_EMAIL = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)
_TX_ID = re.compile(r'tx_[a-zA-Z0-9_]+')


def mask_string(text: str) -> str:
    if not text:
        return text
    text = _IP.sub("[MASKED_IP]", text)
    text = _EMAIL.sub("[MASKED_EMAIL]", text)
    text = _TX_ID.sub("[MASKED_TX_ID]", text)
    return text


def mask_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: mask_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [mask_payload(item) for item in payload]
    if isinstance(payload, str):
        return mask_string(payload)
    if isinstance(payload, datetime):
        return payload.isoformat()
    return payload


def mask_log(payload_dict: dict) -> str:
    return json.dumps(mask_payload(payload_dict), indent=2)
