#!/usr/bin/env python3
"""Populates the knowledge base with Known Error Manual entries."""
import sys
from pathlib import Path

import httpx

# Allow running this script directly (e.g. `python3 scripts/seed.py`) by
# putting the repo root on sys.path, so `app.core.seed_data` can be imported
# regardless of the current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.seed_data import KNOWN_ERROR_ENTRIES as ENTRIES  # noqa: E402

BASE_URL = "http://localhost:8000"


def main():
    url = f"{BASE_URL}/api/v1/knowledge-base/ingest"
    try:
        response = httpx.post(url, json=ENTRIES, timeout=60)
        response.raise_for_status()
        count = response.json().get("inserted_count", "?")
        print(f"Knowledge base seeded: {count} entries inserted.")
    except httpx.ConnectError:
        print(f"Error: could not connect to {BASE_URL}.")
        print("Make sure the API is running: docker compose up -d")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"Error: API returned {e.response.status_code}.")
        sys.exit(1)


if __name__ == "__main__":
    main()
