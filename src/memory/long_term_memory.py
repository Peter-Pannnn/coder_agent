"""Chroma-backed long-term personal memory for CoderAgent."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DEFAULT_LONG_TERM_MEMORY_PERSIST_DIRECTORY = "src/storage/long_term_memory"
DEFAULT_LONG_TERM_MEMORY_COLLECTION_NAME = "personal_memory"
DEFAULT_LONG_TERM_MEMORY_STORAGE_MODE = "local"


@dataclass(frozen=True)
class LongTermMemoryRecord:
    """One retrieved long-term personal memory record."""

    id: str
    content: str
    user_id: str = "default"
    category: str = "preference"
    source: str = "manual"
    created_at: str = ""
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChromaLongTermMemory:
    """Persist and retrieve user preferences with Chroma semantic search."""

    def __init__(
        self,
        storage_mode: str = DEFAULT_LONG_TERM_MEMORY_STORAGE_MODE,
        persist_directory: str = DEFAULT_LONG_TERM_MEMORY_PERSIST_DIRECTORY,
        collection_name: str = DEFAULT_LONG_TERM_MEMORY_COLLECTION_NAME,
        embedding_function: Any | None = None,
    ):
        if not collection_name.strip():
            raise ValueError("collection_name must be a non-empty string.")

        self.storage_mode = storage_mode
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        self._client: Any | None = None
        self._vector_store: Any | None = None

    def add_memory(
        self,
        content: str,
        user_id: str = "default",
        category: str = "preference",
        source: str = "manual",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store one long-term personal memory and return its memory id."""
        normalized_content = self._normalize_content(content)
        normalized_user_id = self._normalize_label(user_id, "user_id")
        normalized_category = self._normalize_label(category, "category")
        normalized_source = self._normalize_label(source, "source")
        created_at = datetime.now(timezone.utc).isoformat()
        memory_id = self._build_memory_id(
            user_id=normalized_user_id,
            category=normalized_category,
            content=normalized_content,
            created_at=created_at,
        )
        memory_metadata = self._build_metadata(
            memory_id=memory_id,
            user_id=normalized_user_id,
            category=normalized_category,
            source=normalized_source,
            created_at=created_at,
            metadata=metadata,
        )

        from langchain_core.documents import Document

        document = Document(page_content=normalized_content, metadata=memory_metadata)
        self._get_vector_store().add_documents(documents=[document], ids=[memory_id])
        return memory_id

    def retrieve_memories(
        self,
        query: str,
        user_id: str = "default",
        k: int = 4,
        categories: list[str] | None = None,
    ) -> list[LongTermMemoryRecord]:
        """Retrieve semantically relevant memories for one user."""
        normalized_query = self._normalize_content(query)
        normalized_user_id = self._normalize_label(user_id, "user_id")
        if k <= 0 or self.count() <= 0:
            return []

        results = self._get_vector_store().similarity_search_with_score(
            normalized_query,
            k=k,
            filter={"user_id": normalized_user_id},
        )
        records = [
            self._record_from_document(document, score)
            for document, score in results
        ]
        if categories is None:
            return records

        category_set = set(categories)
        return [record for record in records if record.category in category_set]

    def render_relevant(
        self,
        query: str,
        user_id: str = "default",
        k: int = 4,
    ) -> str:
        """Render relevant memories as prompt context."""
        records = self.retrieve_memories(query=query, user_id=user_id, k=k)
        if not records:
            return ""

        blocks = [
            "长期个人记忆：",
            "以下内容来自用户长期偏好或个人约定。它只用于调整回答风格、默认偏好和协作习惯，不可作为仓库事实依据。",
        ]
        for index, record in enumerate(records, start=1):
            blocks.extend(
                [
                    f"[{index}] category={record.category}; source={record.source}; created_at={record.created_at}",
                    record.content,
                ]
            )
        return "\n".join(blocks)

    def clear(self, user_id: str | None = None) -> int:
        """Clear long-term memories. Passing None clears the whole collection."""
        if self.count() <= 0:
            return 0

        if user_id is None:
            deleted_count = self.count()
            self._get_client().delete_collection(self.collection_name)
            self._reset_cached_vector_store()
            return deleted_count

        normalized_user_id = self._normalize_label(user_id, "user_id")
        collection = self._get_collection()
        result = collection.get(where={"user_id": normalized_user_id})
        ids = result.get("ids", [])
        if not ids:
            return 0

        collection.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        """Return the number of stored long-term memory records."""
        return int(self._get_collection().count())

    def _get_vector_store(self) -> Any:
        if self._vector_store is None:
            from langchain_chroma import Chroma
            from src.models import get_ali_embeddings

            embedding_function = self.embedding_function or get_ali_embeddings()
            self._vector_store = Chroma(
                client=self._get_client(),
                collection_name=self.collection_name,
                embedding_function=embedding_function,
            )

        return self._vector_store

    def _get_client(self) -> Any:
        if self._client is None:
            from src.tools.utils import get_chroma_client, normalize_chroma_storage_mode

            normalized_storage_mode = normalize_chroma_storage_mode(self.storage_mode)
            self._client = get_chroma_client(
                normalized_storage_mode,
                self.persist_directory,
            )

        return self._client

    def _get_collection(self) -> Any:
        return self._get_client().get_or_create_collection(self.collection_name)

    def _reset_cached_vector_store(self) -> None:
        self._vector_store = None

    def _record_from_document(self, document: Any, score: float) -> LongTermMemoryRecord:
        metadata = dict(document.metadata)
        return LongTermMemoryRecord(
            id=str(metadata.get("memory_id", "")),
            content=str(document.page_content),
            user_id=str(metadata.get("user_id", "")),
            category=str(metadata.get("category", "")),
            source=str(metadata.get("source", "")),
            created_at=str(metadata.get("created_at", "")),
            score=score,
            metadata=metadata,
        )

    def _build_metadata(
        self,
        memory_id: str,
        user_id: str,
        category: str,
        source: str,
        created_at: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        base_metadata: dict[str, Any] = {
            "memory_id": memory_id,
            "user_id": user_id,
            "category": category,
            "source": source,
            "created_at": created_at,
        }
        if metadata:
            base_metadata.update(self._sanitize_metadata(metadata))

        return base_metadata

    def _sanitize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[str(key)] = value
            else:
                sanitized[str(key)] = str(value)

        return sanitized

    def _build_memory_id(
        self,
        user_id: str,
        category: str,
        content: str,
        created_at: str,
    ) -> str:
        digest = hashlib.sha1(
            f"{user_id}:{category}:{content}:{created_at}".encode("utf-8")
        ).hexdigest()
        return f"ltm_{digest}"

    def _normalize_content(self, content: str) -> str:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be a non-empty string.")
        return content.strip()

    def _normalize_label(self, value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()
