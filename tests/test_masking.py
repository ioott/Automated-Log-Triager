from app.services.masking import mask_string, mask_payload


def test_mask_ip():
    masked = mask_string("The server at 192.168.1.1 is down.")
    assert "[MASKED_IP]" in masked
    assert "192.168.1.1" not in masked


def test_mask_tx_id():
    masked = mask_string("Transaction tx_12345 failed.")
    assert "[MASKED_TX_ID]" in masked
    assert "tx_12345" not in masked


def test_mask_email():
    masked = mask_string("Contact user@example.com for help.")
    assert "[MASKED_EMAIL]" in masked
    assert "user@example.com" not in masked


def test_mask_payload_recursive():
    payload = {
        "user": "john@doe.com",
        "nested": {
            "ip": "10.0.0.5",
            "logs": ["Failed tx_999", "Other string"],
        },
    }
    masked = mask_payload(payload)
    assert masked["user"] == "[MASKED_EMAIL]"
    assert masked["nested"]["ip"] == "[MASKED_IP]"
    assert masked["nested"]["logs"][0] == "Failed [MASKED_TX_ID]"
