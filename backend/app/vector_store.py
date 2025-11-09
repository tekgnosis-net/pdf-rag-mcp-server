"""Vector store facade selecting between supported backends."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from app.vector_backends.base import BaseVectorBackend
from app.vector_backends.chroma_backend import ChromaVectorBackend
from app.vector_backends.lance_backend import LanceVectorBackend

logger = logging.getLogger("vector_store")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


_BACKENDS = {
    "chroma": ChromaVectorBackend,
    "lance": LanceVectorBackend,
}


def _select_backend_name(explicit: Optional[str] = None) -> str:
    backend_name = explicit or os.getenv("PDF_RAG_VECTOR_BACKEND", "lance")
    backend_name = backend_name.strip().lower()
    if backend_name not in _BACKENDS:
        logger.warning("Unknown vector backend '%s', falling back to 'lance'", backend_name)
        backend_name = "lance"
    return backend_name


def _resolve_directory(path_value: Optional[str], default_subdir: Optional[str]) -> Optional[str]:
    if path_value and path_value.strip():
        candidate = Path(path_value.strip())
    elif default_subdir:
        candidate = Path(default_subdir)
    else:
        return None

    if not candidate.is_absolute():
        candidate = (_PROJECT_ROOT / candidate).resolve()

    return str(candidate)


def _persist_directory_for(backend_name: str) -> Optional[str]:
    if backend_name == "chroma":
        return _resolve_directory(os.getenv("PDF_RAG_CHROMA_DB"), "data/chroma_db")
    if backend_name == "lance":
        return _resolve_directory(os.getenv("PDF_RAG_LANCE_DB"), "data/lance_db")
    return None


class VectorStore:
    """Facade delegating to the configured vector backend."""

    def __init__(self, backend_name: Optional[str] = None, persist_directory: Optional[str] = None):
        backend_choice = _select_backend_name(backend_name)
        backend_cls = _BACKENDS[backend_choice]

        directory_override = persist_directory or _persist_directory_for(backend_choice)
        self.backend: BaseVectorBackend = backend_cls(persist_directory=directory_override)
        self.backend_name = backend_choice
        logger.info("VectorStore using backend '%s'", self.backend_name)

    def add_documents(
        self,
        chunks: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        return self.backend.add_documents(chunks, embeddings, metadatas)

    def search(
        self,
        query_embedding: np.ndarray,
        n_results: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None,
        offset: int = 0,
    ) -> Dict[str, Any]:
        return self.backend.search(query_embedding, n_results, filter_criteria, offset)

    def get_document_count(self) -> int:
        return self.backend.get_document_count()

    def reset(self) -> bool:
        return self.backend.reset()

    def delete(
        self,
        filter: Optional[Dict[str, Any]] = None,
        ids: Optional[Iterable[str]] = None,
    ) -> bool:
        return self.backend.delete(filter=filter, ids=ids)

    def rebuild_from_markdown(self) -> None:
        self.backend.rebuild_from_markdown()

    def ensure_async_rebuild(self) -> None:
        self.backend.ensure_async_rebuild()

    def close(self) -> None:
        self.backend.close()
