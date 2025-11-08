"""Vector backend abstractions."""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from app.database import PDFDocument


class BaseVectorBackend(ABC):
    """Common interface for vector database backends."""

    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory
        self._rebuild_lock = threading.Lock()
        self._rebuild_thread: Optional[threading.Thread] = None

    @abstractmethod
    def add_documents(
        self,
        chunks: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[Dict[str, Any]]],
    ) -> bool:
        """Persist a batch of chunks and metadata."""

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        n_results: int,
        filter_criteria: Optional[Dict[str, Any]],
        offset: int,
    ) -> Dict[str, Any]:
        """Execute a similarity search."""

    @abstractmethod
    def get_document_count(self) -> int:
        """Return total chunk count for the backend."""

    @abstractmethod
    def reset(self) -> bool:
        """Drop all stored vectors."""

    @abstractmethod
    def delete(
        self,
        filter: Optional[Dict[str, Any]] = None,
        ids: Optional[Iterable[str]] = None,
    ) -> bool:
        """Delete vectors by filter or explicit ids."""

    @abstractmethod
    def rebuild_from_markdown(self) -> None:
        """Rehydrate embeddings from stored markdown pages."""

    def ensure_async_rebuild(self) -> None:
        """Schedule a background rebuild if one is not already running."""
        if self._rebuild_thread and self._rebuild_thread.is_alive():
            return

        def _runner() -> None:
            try:
                self.rebuild_from_markdown()
            finally:
                with self._rebuild_lock:
                    self._rebuild_thread = None

        with self._rebuild_lock:
            if self._rebuild_thread and self._rebuild_thread.is_alive():
                return
            thread = threading.Thread(target=_runner, name="vector-rebuild", daemon=True)
            self._rebuild_thread = thread
            thread.start()

    def close(self) -> None:  # pragma: no cover - hook for future use
        """Allow backends to release resources."""
        return


def markdown_is_current(doc: PDFDocument) -> bool:
    """Return True when persisted markdown likely matches the on-disk PDF."""
    if not doc.file_path:
        return True
    try:
        if not os.path.exists(doc.file_path):
            return True
        mtime = os.path.getmtime(doc.file_path)
        if not doc.uploaded_at:
            return True
        return mtime <= doc.uploaded_at.timestamp()
    except OSError:
        return True
