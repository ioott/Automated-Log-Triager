import re
import json
from typing import Any, Union
from datetime import datetime

class DataMaskingService:
    """
    Enterprise-grade Data Masking Service using Regex.
    Sanitizes PII, IPs, and Sensitive IDs before sending to LLM.
    """
    
    IP_PATTERN = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    TX_ID_PATTERN = r'tx_[a-zA-Z0-9_]+'
    
    def mask_string(self, text: str) -> str:
        if not text: return text
        text = re.sub(self.IP_PATTERN, "[MASKED_IP]", text)
        text = re.sub(self.EMAIL_PATTERN, "[MASKED_EMAIL]", text)
        text = re.sub(self.TX_ID_PATTERN, "[MASKED_TX_ID]", text)
        return text

    def mask_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            return {k: self.mask_payload(v) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [self.mask_payload(item) for item in payload]
        elif isinstance(payload, str):
            return self.mask_string(payload)
        elif isinstance(payload, datetime):
            return payload.isoformat()
        else:
            return payload

    def mask_log(self, payload_dict: dict) -> str:
        masked_dict = self.mask_payload(payload_dict)
        return json.dumps(masked_dict, indent=2)
