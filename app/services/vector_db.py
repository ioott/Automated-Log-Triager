import chromadb
import logging
import threading
from urllib.parse import urlparse
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

# chromadb's HttpClient hardcodes its underlying httpx client with
# timeout=None (see api/fastapi.py in the chromadb package) - there is no
# supported way to configure a request timeout through HttpClient()'s own
# parameters. Against a Render free-tier instance that's still spinning up,
# that means a single attempt can hang far longer than expected instead of
# failing fast, which silently defeats the retry/backoff below (one hung
# attempt can burn the entire retry budget on its own, and no retry ever
# actually happens). Run each attempt in a daemon thread and bound it with
# a hard wall-clock timeout so a slow attempt gives up and hands control
# back to the retry loop instead of hanging - daemon=True so an abandoned,
# still-hung attempt never blocks process shutdown either.
#
# The chromadb 1.x client also does more work per "attempt" than it used
# to: get_or_create_collection() now makes 4 sequential HTTP round-trips
# (auth identity check, tenant lookup, database lookup, then the actual
# create/get call) instead of one, for its multi-tenancy handshake. Timed
# directly against this deployment's production ChromaDB URL, a single
# round-trip took ~12s while the instance was still warming up (and ~0.3s
# once warm) - so a tight per-attempt timeout can get eaten by legitimate
# (if slow) round-trips before the 4-request handshake ever completes,
# not just by genuinely hung connections. 25s gives that handshake enough
# room to finish even when each leg is individually slow.
_CONNECT_ATTEMPT_TIMEOUT_SECONDS = 25


def _worth_retrying(exception: BaseException) -> bool:
    """
    Retry predicate for the connect loop below.

    get_or_create_collection() makes 4 sequential HTTP requests per
    attempt (auth identity, tenant lookup, database lookup, create/get).
    Multiplied across retry attempts - and again across every click of
    the dashboard's "Wake up ChromaDB" button, or every scheduled/keep-alive
    hit - that's enough request volume that Render/Cloudflare's free-tier
    edge started responding with 429 Too Many Requests (confirmed in
    production logs: "Failed to connect to ChromaDB after retries: Too
    Many Requests"). Retrying a 429 immediately just adds more requests to
    an already-throttled endpoint, digging the hole deeper instead of
    recovering from it - so don't retry those at all; fail fast and let
    the caller (or the user, via the wake button) try again later once
    the rate-limit window has passed. Genuine cold-start errors (timeouts,
    connection refused, a placeholder HTML page instead of JSON) are still
    retried as before.
    """
    message = str(exception).lower()
    return "429" not in message and "too many requests" not in message


class VectorStore:
    def __init__(self):
        self._client = None
        self._collection = None

    def _connect_and_get_collection_once(self):
        raw_url = settings.VECTOR_DB_URL

        # Support bare "host:port" values (legacy/local docker-compose
        # style, e.g. "chromadb:8000") by defaulting to http:// when no
        # scheme is present, in addition to full URLs like
        # "https://my-chroma.onrender.com".
        parsed = urlparse(raw_url if "://" in raw_url else f"http://{raw_url}")

        host = parsed.hostname or "localhost"
        use_ssl = parsed.scheme == "https"
        # Render's public onrender.com URLs are HTTPS-only and don't
        # expose a custom port (traffic terminates on 443 and is
        # forwarded internally) - only fall back to Chroma's default
        # dev port (8000) when neither the URL nor the scheme implies one.
        port = parsed.port or (443 if use_ssl else 8000)

        client = chromadb.HttpClient(host=host, port=port, ssl=use_ssl)
        collection = client.get_or_create_collection(name="known_errors")
        return client, collection

    @retry(
        # ChromaDB's free-tier instance spins down after inactivity and can
        # take well over a minute to come back: Render's own infra spin-up
        # (~30-50s) plus Chroma re-downloading/initializing its default
        # embedding model from scratch, since there's no persistent disk to
        # cache it across restarts. A single failed attempt against a
        # sleeping instance used to surface immediately as a hard failure -
        # retry with backoff instead, so one triage request rides out the
        # wake-up instead of every request in that window failing outright.
        #
        # Kept intentionally modest (3 attempts, 5-30s apart) rather than
        # aggressive: each attempt is already 4 HTTP requests (see
        # _worth_retrying's docstring), and retrying harder/faster was
        # actively counterproductive in practice - it's what triggered the
        # 429s in the first place.
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=5, max=30),
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
