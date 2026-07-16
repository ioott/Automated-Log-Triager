"""
Single source of truth for the Known Error Manual seed entries, plus a
reusable `ensure_seeded()` helper for auto-populating the ChromaDB
collection when it's empty.

Shared by:
- scripts/seed.py (manual/local seeding via HTTP against a running instance)
- app/main.py (seeds on API startup)
- app/services/triage_pipeline.py (seeds again before every RAG lookup)

The vector DB is Chroma Cloud, with persistent storage, so this is no
longer compensating for data being wiped on every dependency restart the
way it was when ChromaDB was self-hosted on a disk-less free-tier
instance. It's kept as a cheap defense-in-depth check regardless: a
single `count()` call before each RAG lookup costs nothing once the
collection is already seeded, and it means a brand-new database (e.g. a
freshly created Chroma Cloud project) gets populated automatically on
first use instead of requiring a manual seed step.
"""

import logging

logger = logging.getLogger(__name__)

KNOWN_ERROR_ENTRIES = [
    {
        "error_code": "ERR_RPC_NODE_TIMEOUT",
        "technical_description": (
            "The EVM client failed to receive a response from the RPC node "
            "within the configured timeout window during transaction broadcast."
        ),
        "root_cause": (
            "Network congestion, RPC node overload, or node process crash "
            "caused by memory exhaustion or a panic in the execution engine."
        ),
        "action_plan": [
            "Check RPC node health via the infrastructure dashboard.",
            "Inspect node logs for OOM kills or runtime panics.",
            "Trigger automatic failover to the secondary RPC endpoint.",
            "Notify the blockchain infrastructure on-call rotation.",
        ],
        "risk_level": "HIGH",
    },
    {
        "error_code": "ERR_INSUFFICIENT_WALLET_FUNDS",
        "technical_description": (
            "Transaction rejected by the ledger because the source wallet "
            "balance fell below the required amount at broadcast time."
        ),
        "root_cause": (
            "Race condition between concurrent transactions or a delayed "
            "balance sync following a prior settlement cycle."
        ),
        "action_plan": [
            "Verify current wallet balance via the ledger API.",
            "Identify and hold any pending transactions draining the balance.",
            "Requeue the failed transaction once balance is confirmed.",
            "Alert the treasury team if the discrepancy exceeds the threshold.",
        ],
        "risk_level": "MEDIUM",
    },
    {
        "error_code": "ERR_LEDGER_SYNC_DIVERGENCE",
        "technical_description": (
            "The local ledger state diverged from the canonical chain, "
            "causing block validation to fail on the affected node."
        ),
        "root_cause": (
            "Missed blocks due to a network partition or a node restart "
            "that occurred during active block propagation."
        ),
        "action_plan": [
            "Pause transaction processing for the affected service immediately.",
            "Force a full ledger resync from the last trusted checkpoint.",
            "Validate block hashes against a healthy peer node after resync.",
            "Resume processing only after sync integrity is confirmed.",
        ],
        "risk_level": "CRITICAL",
    },
    {
        "error_code": "ERR_BRIDGE_SERVICE_UNAVAILABLE",
        "technical_description": (
            "The cross-chain bridge service stopped responding to health "
            "checks, blocking all in-flight cross-chain transfers."
        ),
        "root_cause": (
            "Bridge process crash, misconfigured firewall rule blocking "
            "the relayer port, or an upstream dependency failure."
        ),
        "action_plan": [
            "Hit the bridge health endpoint directly to confirm unreachability.",
            "Review bridge container logs for panics or config parsing errors.",
            "Restart the bridge container if no data loss risk is present.",
            "Escalate to the DevOps on-call team if restart does not resolve.",
        ],
        "risk_level": "HIGH",
    },
    {
        "error_code": "ERR_NONCE_MISMATCH",
        "technical_description": (
            "The transaction was rejected because the submitted nonce does "
            "not match the expected nonce for the sender account."
        ),
        "root_cause": (
            "A previously submitted transaction is still pending in the "
            "mempool, or a nonce counter desync occurred after a node restart."
        ),
        "action_plan": [
            "Fetch the current account nonce from the node via eth_getTransactionCount.",
            "Resubmit the transaction with the correct nonce.",
            "Check for stuck pending transactions and cancel or replace them.",
            "Investigate nonce tracking logic in the transaction manager.",
        ],
        "risk_level": "MEDIUM",
    },
    {
        "error_code": "ERR_GAS_LIMIT_EXCEEDED",
        "technical_description": (
            "Transaction execution ran out of gas before completing, "
            "causing the EVM to revert all state changes."
        ),
        "root_cause": (
            "Gas estimate was too low for the actual execution path, "
            "often triggered by an unexpected contract branch or a "
            "spike in storage write costs."
        ),
        "action_plan": [
            "Re-estimate gas with a 20% safety buffer using eth_estimateGas.",
            "Review the contract logic for unbounded loops or heavy storage ops.",
            "Resubmit the transaction with the corrected gas limit.",
            "Monitor gas usage trends to detect regressions after contract upgrades.",
        ],
        "risk_level": "LOW",
    },
    {
        "error_code": "ERR_MEMPOOL_CONGESTION",
        "technical_description": (
            "The node mempool has reached its maximum capacity, causing "
            "new transaction submissions to be rejected outright."
        ),
        "root_cause": (
            "Sudden spike in transaction volume exceeded mempool limits, "
            "possibly triggered by a bot storm or a misconfigured retry loop "
            "flooding the network."
        ),
        "action_plan": [
            "Monitor mempool depth via the node metrics endpoint.",
            "Raise the minimum gas price threshold to evict low-priority txs.",
            "Throttle transaction submission from the application layer.",
            "Investigate retry loops for runaway submission behavior.",
        ],
        "risk_level": "HIGH",
    },
    {
        "error_code": "ERR_RELAYER_STUCK",
        "technical_description": (
            "The message relayer has stopped forwarding cross-chain events, "
            "causing a growing backlog of unprocessed messages."
        ),
        "root_cause": (
            "Relayer process deadlocked on a malformed event, lost its "
            "RPC connection, or ran out of signing wallet funds for gas."
        ),
        "action_plan": [
            "Check relayer process health and confirm it is running.",
            "Inspect relayer logs for the last processed event hash.",
            "Verify the relayer signing wallet has sufficient gas funds.",
            "Restart the relayer and monitor the message queue drain rate.",
        ],
        "risk_level": "HIGH",
    },
    {
        "error_code": "ERR_BLOCK_FINALITY_TIMEOUT",
        "technical_description": (
            "A submitted transaction did not reach finality within the "
            "expected number of confirmation blocks."
        ),
        "root_cause": (
            "Slow block production due to reduced validator participation, "
            "or the transaction was silently dropped from the mempool "
            "due to a low gas price."
        ),
        "action_plan": [
            "Check current block production rate on the network explorer.",
            "Query the transaction hash to confirm if it is still pending.",
            "Resubmit with a higher gas price if the tx was dropped.",
            "Alert the validator team if block production has stalled.",
        ],
        "risk_level": "MEDIUM",
    },
    {
        "error_code": "ERR_CONSENSUS_ROUND_FAILURE",
        "technical_description": (
            "The consensus layer failed to reach agreement within the "
            "allowed round timeout, causing a block production gap."
        ),
        "root_cause": (
            "One or more validators became unreachable mid-round due to "
            "network partition, clock skew, or a software crash on a "
            "leader node."
        ),
        "action_plan": [
            "Identify which validators missed the consensus round via metrics.",
            "Restart unreachable validator nodes and verify peer connectivity.",
            "Check system clocks across validators for skew above tolerance.",
            "Escalate if more than one-third of validators are unreachable.",
        ],
        "risk_level": "CRITICAL",
    },
]


def ensure_seeded(vector_store) -> bool:
    """
    Ensures the `known_errors` collection has data, seeding it from
    KNOWN_ERROR_ENTRIES if it's currently empty.

    Safe to call frequently (e.g. on every triage request): the emptiness
    check is a single cheap `count()` call, and ingestion only runs when
    the count is actually zero, so a fully-seeded collection costs one
    extra round-trip and nothing else.

    Returns True if seeding was performed, False if the collection
    already had data or the check/seed itself failed (failures are
    logged, not raised, so a transient ChromaDB hiccup here doesn't take
    down the caller).
    """
    from app.models.schemas import KnownErrorManualEntry

    try:
        if vector_store.count_entries() > 0:
            return False

        entries = [KnownErrorManualEntry(**e) for e in KNOWN_ERROR_ENTRIES]
        inserted = vector_store.ingest_entries(entries)
        logger.info(f"Knowledge base was empty; auto-seeded {inserted} entries.")
        return True
    except Exception as e:
        logger.error(f"Auto-seed check failed, continuing without seeding: {e}")
        return False
