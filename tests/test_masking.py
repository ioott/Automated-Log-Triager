import pytest
from app.services.masking import DataMaskingService

def test_mask_ip():
    masker = DataMaskingService()
    text = "The server at 192.168.1.1 is down."
    masked = masker.mask_string(text)
    assert "[MASKED_IP]" in masked
    assert "192.168.1.1" not in masked

def test_mask_tx_id():
    masker = DataMaskingService()
    text = "Transaction tx_12345 failed."
    masked = masker.mask_string(text)
    assert "[MASKED_TX_ID]" in masked
    assert "tx_12345" not in masked

def test_mask_email():
    masker = DataMaskingService()
    text = "Contact user@example.com for help."
    masked = masker.mask_string(text)
    assert "[MASKED_EMAIL]" in masked
    assert "user@example.com" not in masked

def test_mask_payload_recursive():
    masker = DataMaskingService()
    payload = {
        "user": "john@doe.com",
        "nested": {
            "ip": "10.0.0.5",
            "logs": ["Failed tx_999", "Other string"]
        }
    }
    masked = masker.mask_payload(payload)
    assert masked["user"] == "[MASKED_EMAIL]"
    assert masked["nested"]["ip"] == "[MASKED_IP]"
    assert masked["nested"]["logs"][0] == "Failed [MASKED_TX_ID]"
