"""LanceDB vector database backend."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional

import lancedb
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from app.database import PDFDocument, PDFMarkdownPage, SessionLocal
from .base import BaseVectorBackend, markdown_is_current

logger = logging.getLogger("vector_store.lance")


class LanceVectorBackend(BaseVectorBackend):
    """Vector backend backed by LanceDB tables."""

    _TABLE_NAME = "pdf_documents"

    def __init__(self, persist_directory: Optional[str] = None):
        if persist_directory is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(current_dir)
            persist_directory = os.path.join(backend_dir, "lance_db")

        persist_directory = os.path.abspath(persist_directory)
        super().__init__(persist_directory=persist_directory)

        os.makedirs(persist_directory, exist_ok=True)
        logger.info("Initializing LanceDB backend in %s", persist_directory)
        self.client = lancedb.connect(persist_directory)
        self.table = self._open_table()

        if self.table is None:
            logger.info("Lance table not found; will be created on first insert")
            self.ensure_async_rebuild()
        elif self.get_document_count() == 0:
            logger.info("Lance table empty; scheduling rebuild from markdown")
            self.ensure_async_rebuild()

    def _open_table(self):
        try:
            if self._TABLE_NAME in self.client.table_names():
                return self.client.open_table(self._TABLE_NAME)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to open Lance table: %s", exc)
        return None

    def _ensure_table(self, records: List[Dict[str, Any]]) -> None:
        if self.table is not None:
            return
        if not records:
            return
        try:
            self.table = self.client.create_table(self._TABLE_NAME, records)
            logger.info("Created Lance table with %s initial rows", len(records))
        except Exception as exc:  # noqa: BLE001
            logger.error("Unable to create Lance table: %s", exc)
            raise

    def _build_records(
        self,
        chunks: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        metadatas = metadatas or [{} for _ in chunks]
        for chunk, embedding, meta in zip(chunks, embeddings, metadatas):
            record = {
                "id": f"doc_{meta.get('pdf_id')}_{meta.get('chunk_id')}",
                "text": chunk,
                "vector": embedding.tolist(),
                "pdf_id": meta.get("pdf_id"),
                "source": meta.get("source"),
                "chunk_id": meta.get("chunk_id"),
                "page": meta.get("page"),
                "batch": meta.get("batch"),
                "index": meta.get("index"),
                "length": meta.get("length"),
                "timestamp": meta.get("timestamp"),
                "metadata": meta,
            }
            records.append(record)
        return records

    def add_documents(
        self,
        chunks: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not chunks:
            return True
        try:
            records = self._build_records(chunks, embeddings, metadatas)
            if self.table is None:
                self._ensure_table(records)
                if self.table is None:
                    return False
                return True
            self.table.add(records)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Error adding documents to LanceDB: %s", exc, exc_info=True)
            return False

    def search(
        self,
        query_embedding: np.ndarray,
        n_results: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None,
        offset: int = 0,
    ) -> Dict[str, Any]:
        if self.table is None or self.get_document_count() == 0:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        try:
            requested = max(int(n_results or 0), 0)
            offset_val = max(int(offset or 0), 0)
            fetch_total = requested + offset_val + 1
            if fetch_total <= 0:
                fetch_total = 1

            query = self.table.search(query_embedding.tolist())
            if filter_criteria:
                query = query.where(filter_criteria)
            df = query.limit(fetch_total).to_pandas()

            if df.empty:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            documents = df["text"].tolist()
            metadatas = df["metadata"].tolist()
            distances = df.get("score") or df.get("distance")
            if distances is None:
                distances = [0.0 for _ in documents]
            else:
                distances = distances.tolist()

            window_docs = documents[offset_val : offset_val + requested] if requested > 0 else []
            window_meta = metadatas[offset_val : offset_val + requested] if requested > 0 else []
            window_dist = distances[offset_val : offset_val + requested] if requested > 0 else []
            has_more = len(documents) > offset_val + requested

            return {
                "documents": [window_docs],
                "metadatas": [window_meta],
                "distances": [window_dist],
                "has_more": has_more,
                "offset": offset_val,
                "limit": requested,
                "total_fetched": len(documents),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Error querying LanceDB: %s", exc, exc_info=True)
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def get_document_count(self) -> int:
        if self.table is None:
            return 0
        try:
            return self.table.count_rows()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to count Lance rows: %s", exc)
            return 0

    def reset(self) -> bool:
        try:
            if self._TABLE_NAME in self.client.table_names():
                self.client.drop_table(self._TABLE_NAME)
            self.table = None
            self.ensure_async_rebuild()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to reset Lance table: %s", exc)
            return False

    def _delete_where_expr(self, filter: Dict[str, Any]) -> Optional[str]:
        if not filter:
            return None
        clauses = []
        for key, value in filter.items():
            if isinstance(value, str):
                escaped = value.replace("'", "''")
                clauses.append(f"{key} == '{escaped}'")
            else:
                clauses.append(f"{key} == {value}")
        return " and ".join(clauses) if clauses else None

    def delete(
        self,
        filter: Optional[Dict[str, Any]] = None,
        ids: Optional[Iterable[str]] = None,
    ) -> bool:
        if self.table is None:
            return True
        try:
            if filter:
                expr = self._delete_where_expr(filter)
                if expr:
                    self.table.delete(where=expr)
                return True
            if ids:
                id_list = list(ids)
                if not id_list:
                    return True
                quoted = ",".join(f"'{item.replace("'", "''")}'" for item in id_list)
                self.table.delete(where=f"id in ({quoted})")
                return True
            logger.warning("Lance delete called without filter or ids")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Error deleting from LanceDB: %s", exc, exc_info=True)
            return False

    def rebuild_from_markdown(self) -> None:
        if self.get_document_count() > 0:
            logger.info("Lance store already populated; skipping rebuild")
            return

        db = SessionLocal()
        try:
            processed_docs = (
                db.query(PDFDocument)
                .filter(PDFDocument.processed == True)  # noqa: E712
                .order_by(PDFDocument.id)
                .all()
            )
            if not processed_docs:
                return

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )

            requested_device = os.getenv("SENTENCE_TRANSFORMERS_DEVICE", "cpu")
            logger.info("Rebuilding Lance embeddings on %s", requested_device)
            try:
                model = SentenceTransformer("all-MiniLM-L6-v2", device=requested_device)
            except Exception as exc:  # noqa: BLE001
                if requested_device.lower() != "cpu":
                    logger.warning(
                        "Falling back to CPU for Lance rebuild due to error on %s: %s",
                        requested_device,
                        exc,
                    )
                    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
                else:
                    raise

            rebuilt_any = False
            for doc in processed_docs:
                if doc.blacklisted:
                    continue
                if not markdown_is_current(doc):
                    continue

                pages = (
                    db.query(PDFMarkdownPage)
                    .filter(PDFMarkdownPage.pdf_id == doc.id)
                    .order_by(PDFMarkdownPage.page)
                    .all()
                )
                if not pages:
                    continue

                doc_chunks: List[str] = []
                metadatas: List[Dict[str, Any]] = []
                batch_id = f"rebuild-{uuid.uuid4().hex[:8]}"
                chunk_counter = 0

                for page in pages:
                    page_text = (page.markdown or "").strip()
                    if not page_text:
                        continue
                    page_chunks = text_splitter.split_text(page_text)
                    for chunk in page_chunks:
                        doc_chunks.append(chunk)
                        metadatas.append(
                            {
                                "source": doc.filename,
                                "chunk_id": f"{batch_id}_{chunk_counter}",
                                "pdf_id": doc.id,
                                "page": page.page,
                                "batch": batch_id,
                                "index": chunk_counter,
                                "length": len(chunk),
                                "timestamp": time.time(),
                            }
                        )
                        chunk_counter += 1

                if not doc_chunks:
                    continue

                embeddings = model.encode(doc_chunks)
                if self.add_documents(doc_chunks, embeddings, metadatas):
                    rebuilt_any = True

            if rebuilt_any:
                logger.info("Lance rebuild finished")
        finally:
            db.close()
