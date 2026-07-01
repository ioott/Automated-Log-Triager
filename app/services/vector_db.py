import chromadb
import logging
from typing import List
from app.core.config import settings
from app.models.schemas import KnownErrorManualEntry

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        try:
            url = settings.VECTOR_DB_URL.replace("http://", "").replace("https://", "")
            host, port = url.split(":") if ":" in url else (url, "8000")
            if not host:
                host = "localhost"

            self._client = chromadb.HttpClient(host=host, port=port)
            self._collection = self._client.get_or_create_collection(name="known_errors")
            logger.info("Successfully connected to ChromaDB and initialized 'known_errors' collection.")
            return self._collection
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            raise Exception("ChromaDB collection could not be initialized.")

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
