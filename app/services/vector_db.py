import chromadb
import logging
from urllib.parse import urlparse
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from app.core.config import settings
from app.models.schemas import KnownErrorManualEntry

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self._client = None
        self._collection = None

    @retry(
        # ChromaDB's free-tier instance spins down after inactivity and can
        # take well over a minute to come back: Render's own infra spin-up
        # (~30-50s) plus Chroma re-downloading/initializing its default
        # embedding model from scratch, since there's no persistent disk to
        # cache it across restarts. A single failed attempt against a
        # sleeping instance used to surface immediately as a hard failure -
        # retry with backoff instead, so one triage request rides out the
        # wake-up instead of every request in that window failing outright.
        stop=stop_after_attempt(8),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _connect_and_get_collection(self):
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
