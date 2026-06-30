#!/usr/bin/env python3
"""Populates the knowledge base with Known Error Manual entries."""
import sys
import httpx

BASE_URL = "http://localhost:8000"

ENTRIES = [
    {
        "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT",
        "technical_description": (
            "The EVM Bridge Client failed to receive a response from the "
            "Stratus RPC node within the configured timeout window."
        ),
        "root_cause": (
            "Network congestion, RPC node overload, or node process crash."
        ),
        "action_plan": [
            "Check RPC node status via the infrastructure dashboard.",
            "Inspect node logs for OOM or panic events.",
            "Trigger failover to the secondary RPC endpoint.",
            "Notify the blockchain infrastructure on-call team.",
        ],
        "risk_level": "HIGH",
    },
    {
        "error_code": "CW_ERR_INSUFFICIENT_FUNDS",
        "technical_description": (
            "Transaction rejected by the ledger due to insufficient "
            "balance in the source wallet at broadcast time."
        ),
        "root_cause": (
            "Race condition between concurrent transactions or delayed "
            "balance sync from a prior settlement."
        ),
        "action_plan": [
            "Verify current wallet balance via the ledger API.",
            "Check for pending transactions draining the balance.",
            "Requeue the transaction after balance is confirmed.",
            "Alert the finance team if discrepancy exceeds threshold.",
        ],
        "risk_level": "MEDIUM",
    },
    {
        "error_code": "CW_ERR_LEDGER_SYNC_FAILURE",
        "technical_description": (
            "The local ledger state diverged from the canonical chain, "
            "causing block validation to fail."
        ),
        "root_cause": (
            "Missed blocks due to network partition or a node restart "
            "during active block propagation."
        ),
        "action_plan": [
            "Pause transaction processing for the affected service.",
            "Force a full ledger resync from a trusted checkpoint.",
            "Validate block hashes against a peer node after resync.",
            "Resume processing only after sync is confirmed.",
        ],
        "risk_level": "CRITICAL",
    },
    {
        "error_code": "CW_ERR_BRIDGE_UNAVAILABLE",
        "technical_description": (
            "The EVM bridge service is not responding to health checks, "
            "blocking all cross-chain transfers."
        ),
        "root_cause": (
            "Bridge service crash, misconfigured firewall rule, or "
            "relayer dependency failure."
        ),
        "action_plan": [
            "Check bridge service health endpoint directly.",
            "Review bridge container logs for panic or config errors.",
            "Restart the bridge service if no data loss risk exists.",
            "Escalate to the DevOps team if restart does not resolve.",
        ],
        "risk_level": "HIGH",
    },
]


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
