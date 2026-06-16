import re
import json
from typing import Any, Union

class DataMaskingService:
    """
    Enterprise-grade Data Masking Service using Regex.
    Sanitizes PII, IPs, and Sensitive IDs before sending to LLM.
    """
    
    # Regex Patterns
    IP_PATTERN = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    TX_ID_PATTERN = r'tx_[a-zA-Z0-9_]+'
    
    def mask_string(self, text: str) -> str:
        """Applies masking to a raw string."""
        if not text:
            return text
        
        # Mask IPs
        text = re.sub(self.IP_PATTERN, "[MASKED_IP]", text)
        # Mask Emails
        text = re.sub(self.EMAIL_PATTERN, "[MASKED_EMAIL]", text)
        # Mask Transaction IDs
        text = re.sub(self.TX_ID_PATTERN, "[MASKED_TX_ID]", text)
        
        return text

    def mask_payload(self, payload: Union[dict, list]) -> Any:
        """
        Recursively traverses a dictionary or list to mask all string values.
        """
        if isinstance(payload, dict):
            return {k: self.mask_payload(v) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [self.mask_payload(i) for v in payload]
        elif isinstance(payload, str):
            return self.mask_string(payload)
        else:
            return payload

    def mask_log(self, payload_dict: dict) -> str:
        """
        Utility to mask a dictionary and return a clean JSON string for the LLM.
        """
        masked_dict = self.mask_payload(payload_dict)
        return json.dumps(masked_dict, indent=2)
