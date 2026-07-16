import chromadb
import logging
import threading
from typing import List
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
from app.core.config import settings
from app.models.schemas import KnownErrorManualEntry

logger = logging.getLogger(__name__)

# chromadb's HttpClient/CloudClient hardcode their underlying httpx client
# with timeout=None (confirmed by reading api/fastapi.py in the chromadb
# package: `httpx.Client(timeout=None, ...)`) - there is no supported way
# to configure a request timeout through the client's own constructor
# parameters. That's true regardless of host, so it's still a real risk
# even against Chroma Cloud's always-on infra (a stalled TCP connection or
# a proxy hiccup can still hang indefinitely). Run each attempt in a
# daemon thread and bound it with a hard wall-clock timeout so a stuck
# attempt gives up and hands control back to the retry loop instead of
# hanging - daemon=True so an abandoned, still-hung attempt never blocks
# process shutdown either.
#
# The chromadb 1.x `Client` also does more work per "attempt" than it
# looks like: constructing it runs get_user_identity(), then
# _validate_tenant_database() -> get_tenant() + get_database() (all in
# Client.__init__, see api/client.py), and get_or_create_collection() adds
# a 4th request on top - 4 sequential HTTP round-trips per connection
# attempt. That handshake is inherent to the chromadb 1.x client and
# happens against ANY host, including Chroma Cloud - it's not something
# moving off Render removes. What changes is what those 4 round-trips hit:
# previously, against a Render free-tier ChromaDB instance still spinning
# up from a cold stop, a single round-trip measured ~12s (vs ~0.3s once
# warm), which is what forced a 25s per-attempt timeout in the first
# place. Chroma Cloud is always-on production infrastructure, so the same
# 4-request handshake should complete in well under a second end-to-end -
# 10s stays generous for a slow network without being sized for a cold
# boot that no longer happens.
_CONNECT_ATTEMPT_TIMEOUT_SECONDS = 10


def _worth_retrying(exception: BaseException) -> bool:
    """
    Retry predicate for the connect loop below.

    The chromadb 1.x client makes 4 sequential HTTP requests per
    connection attempt (user identity, tenant lookup, database lookup,
    then get_or_create_collection). Multiplied across retry attempts,
    that's still real request volume against Chroma Cloud's own
    usage-based rate limits - and retrying a 429 immediately just adds
    more requests on top of an already-throttled window, digging the hole
    deeper instead of recovering from it (this is exactly what happened
    against Render/Cloudflare's free-tier edge in production before this
    check existed). So 429s are not retried at all; fail fast and let the
    caller try again once the rate-limit window has passed. Genuine
    transient errors (timeouts, connection resets, DNS hiccups) are still
    retried as before.
    """
    message = str(exception).lower()
    return "429" not in message and "too many requests" not in message


class VectorStore:
    def __init__(self):
        self._client = None
        self._collection = None

    def _connect_and_get_collection_once(self):
        client = chromadb.CloudClient(
            api_key=settings.CHROMA_API_KEY,
            tenant=settings.CHROMA_TENANT,
            database=settings.CHROMA_DATABASE,
        )
        collection = client.get_or_create_collection(name="known_errors")
        return client, collection

    @retry(
        # Chroma Cloud is always-on managed infrastructure - there's no
        # cold-start scenario to ride out here, unlike the old self-hosted
        # ChromaDB-on-Render setup this replaced. This retry is now purely
        # a defense against ordinary transient network issues (a dropped
        # connection, a DNS blip, a momentary blip on Chroma Cloud's side),
        # so it's tuned much shorter than before: 3 attempts, 2-10s apart
        # instead of 5-30s apart.
        #
        # Still deliberately not aggressive: each attempt is still 4 HTTP
        # requests (see _worth_retrying's docstring), and retrying harder/
        # faster into a rate-limited window was what caused production 429s
        # against the old Render deployment - that risk doesn't disappear
        # just because the host changed.
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_worth_retrying),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _connect_and_get_collection(self):
        result: dict = {}
        done = threading.Event()

        def _run():
            try:
                result["value"] = self._connect_and_get_collection_once()
            except Exception as e:
                result["error"] = e
            finally:
                done.set()

        # daemon=True: if this attempt is still hung when the timeout below
        # fires, we abandon it rather than wait for it - it'll finish (or
        # never will) entirely on its own, without holding up the retry
        # loop or the process.
        threading.Thread(target=_run, daemon=True).start()

        if not done.wait(timeout=_CONNECT_ATTEMPT_TIMEOUT_SECONDS):
            raise TimeoutError(
                f"ChromaDB did not respond within {_CONNECT_ATTEMPT_TIMEOUT_SECONDS}s"
            )
        if "error" in result:
            raise result["error"]
        return result["value"]

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        try:
            self._client, self._collection = self._connect_and_get_collection()
            logger.info("Successfully connected to ChromaDB and initialized 'known_errors' collection.")
            return self._collection
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB after retries: {e}")
            raise Exception("ChromaDB collection could not be initialized.")

    def count_entries(self) -> int:
        """
        Returns the number of entries currently stored in the knowledge
        base collection, without fetching the documents themselves.
        """
        collection = self._get_collection()
        return collection.count()

    def ingest_entries(self, entries: List[KnownErrorManualEntry]) -> int:
        """
        Ingests a batch of KnownErrorManualEntry objects into the Vector Database.
        """
        collection = self._get_collection()

        ids = [entry.error_code for entry in entries]
        documents = [
            f"Error Code: {entry.error_code}. Technical Description: {entry.technical_description} "
            f"Root Cause: {entry.root_cause}. Action Plan: {entry.action_plan}"
            for entry in entries
        ]
        metadatas = [
            {"risk_level": entry.risk_level, "error_code": entry.error_code}
            for entry in entries
        ]

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        logger.info(f"Successfully ingested {len(ids)} entries into the knowledge base.")
        return len(ids)

    def list_entries(self) -> List[dict]:
        """
        Returns every Known Error Manual entry currently stored in the
        knowledge base collection.
        """
        collection = self._get_collection()
        results = collection.get(include=["documents", "metadatas"])

        return [
            {
                "error_code": entry_id,
                "risk_level": metadata.get("risk_level"),
                "document": document,
            }
            for entry_id, document, metadata in zip(
                results["ids"], results["documents"], results["metadatas"]
            )
        ]

    def search_similar_errors(self, query: str, n_results: int = 1):
        """
        Performs similarity search to find the most relevant known errors for a given log.
        """
        collection = self._get_collection()

        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results
