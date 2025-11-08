"""Chroma vector database backend."""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional

import chromadb
import numpy as np
from chromadb.errors import InternalError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from app.database import PDFDocument, PDFMarkdownPage, SessionLocal
from .base import BaseVectorBackend, markdown_is_current

logger = logging.getLogger("vector_store.chroma")


class ChromaVectorBackend(BaseVectorBackend):
    """Vector backend powered by ChromaDB."""

    def __init__(self, persist_directory: Optional[str] = None):
        if persist_directory is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(current_dir)
            persist_directory = os.path.join(backend_dir, "chroma_db")

        persist_directory = os.path.abspath(persist_directory)
        super().__init__(persist_directory=persist_directory)

        logger.info("Initializing Chroma backend in %s", persist_directory)
        os.makedirs(persist_directory, exist_ok=True)

        self.client: chromadb.PersistentClient | None = None
        self.collection = None

        need_rebuild = False
        try:
            self._initialize_collection()
        except InternalError as exc:  # noqa: BLE001
            logger.error("Chroma InternalError during initialization: %s", exc)
            recovered = False
            if self.client is not None:
                recovered = self._reset_collection()

            if recovered:
                try:
                    self._initialize_collection()
                    logger.info("Chroma collection recovered after reset")
                    need_rebuild = True
                except InternalError as exc_retry:  # noqa: BLE001
                    logger.error("Failed to reinitialize Chroma collection: %s", exc_retry)
                    exc = exc_retry

            if not recovered:
                logger.warning(
                    "Resetting persisted vector store at %s due to repeated Chroma errors",
                    self.persist_directory,
                )
                self._wipe_persistence()
                need_rebuild = True
                self._initialize_collection()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to initialize Chroma backend: %s", exc)
            raise

        if need_rebuild:
            self.ensure_async_rebuild()

    def _initialize_collection(self) -> None:
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection = self.client.get_or_create_collection("pdf_documents")
        logger.info("Connected to Chroma collection with %s entries", self.collection.count())

    def _reset_collection(self) -> bool:
        try:
            self.client.delete_collection("pdf_documents")
            logger.info("Deleted Chroma collection; a new one will be created")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete Chroma collection: %s", exc)
            return False

    def _wipe_persistence(self) -> None:
        try:
            if os.path.isdir(self.persist_directory):
                shutil.rmtree(self.persist_directory)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to remove persisted Chroma data: %s", exc)
        finally:
            os.makedirs(self.persist_directory, exist_ok=True)

    def _persist_if_available(self) -> None:
        if getattr(self.client, "persist", None):
            try:
                self.client.persist()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to persist Chroma client: %s", exc)

    def add_documents(
        self,
        chunks: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not chunks:
            return True
        try:
            before_count = self.collection.count()
            logger.info("Chroma count before add: %s", before_count)

            metadatas = metadatas or [{} for _ in chunks]
            ids = [f"doc_{meta.get('pdf_id')}_{meta.get('chunk_id')}" for meta in metadatas]

            existing_ids = set()
            for i in range(0, len(ids), 100):
                for candidate in ids[i : i + 100]:
                    try:
                        self.collection.get(ids=[candidate])
                        existing_ids.add(candidate)
                    except Exception:  # noqa: BLE001
                        continue

            if existing_ids:
                logger.warning("Deleting %s duplicate ids prior to insert", len(existing_ids))
                batches = list(existing_ids)
                for i in range(0, len(batches), 100):
                    self.collection.delete(ids=batches[i : i + 100])

            batch_size = 100
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            for start in range(0, len(chunks), batch_size):
                stop = min(start + batch_size, len(chunks))
                batch_chunks = chunks[start:stop]
                batch_embeddings = embeddings[start:stop].tolist()
                batch_metadatas = metadatas[start:stop]
                batch_ids = ids[start:stop]
                try:
                    self.collection.add(
                        documents=batch_chunks,
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                        ids=batch_ids,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to add Chroma batch %s/%s: %s", start, total_batches, exc)

            self._persist_if_available()
            after_count = self.collection.count()
            logger.info("Chroma count after add: %s", after_count)

            if after_count - before_count <= 0:
                logger.warning("Chroma add resulted in zero net new items (duplicates?)")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Error adding documents to Chroma: %s", exc, exc_info=True)
            return False

    def search(
        self,
        query_embedding: np.ndarray,
        n_results: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None,
        offset: int = 0,
    ) -> Dict[str, Any]:
        try:
            requested = max(int(n_results or 0), 0)
            offset_val = max(int(offset or 0), 0)
            fetch_total = requested + offset_val + 1
            if fetch_total <= 0:
                fetch_total = 1

            params: Dict[str, Any] = {
                "query_embeddings": [query_embedding.tolist()],
                "n_results": fetch_total,
            }
            if filter_criteria:
                params["where"] = filter_criteria

            total_docs = self.collection.count()
            if total_docs == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            results = self.collection.query(**params)
            documents_all = results.get("documents", [[]])
            metadatas_all = results.get("metadatas", [[]])
            distances_all = results.get("distances", [[]])

            docs_primary = documents_all[0] if documents_all else []
            metas_primary = metadatas_all[0] if metadatas_all else []
            dist_primary = distances_all[0] if distances_all else []

            window_start = offset_val
            window_end = offset_val + requested if requested > 0 else offset_val

            window_docs = docs_primary[window_start:window_end] if requested > 0 else []
            window_meta = metas_primary[window_start:window_end] if requested > 0 else []
            window_dist = dist_primary[window_start:window_end] if requested > 0 else []

            has_more = len(docs_primary) > window_end

            return {
                "documents": [window_docs],
                "metadatas": [window_meta],
                "distances": [window_dist],
                "has_more": has_more,
                "offset": offset_val,
                "limit": requested,
                "total_fetched": len(docs_primary),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Error querying Chroma: %s", exc, exc_info=True)
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def get_document_count(self) -> int:
        try:
            return self.collection.count()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to count Chroma documents: %s", exc)
            return 0

    def reset(self) -> bool:
        try:
            logger.info("Resetting Chroma collection")
            self.client.delete_collection("pdf_documents")
            self.collection = self.client.get_or_create_collection("pdf_documents")
            self._persist_if_available()
            self.ensure_async_rebuild()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Chroma reset failed: %s", exc)
            return False

    def delete(
        self,
        filter: Optional[Dict[str, Any]] = None,
        ids: Optional[Iterable[str]] = None,
    ) -> bool:
        try:
            before_count = self.collection.count()
            if filter:
                query_results = self.collection.get(where=filter)
                doc_ids = query_results.get("ids", [])
                if not doc_ids:
                    return True
                for i in range(0, len(doc_ids), 100):
                    self.collection.delete(ids=doc_ids[i : i + 100])
            elif ids:
                id_list = list(ids)
                for i in range(0, len(id_list), 100):
                    self.collection.delete(ids=id_list[i : i + 100])
            else:
                logger.warning("Chroma delete called with no filter or ids")
                return False

            self._persist_if_available()
            after_count = self.collection.count()
            logger.info("Chroma delete removed %s items", before_count - after_count)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Chroma delete failed: %s", exc, exc_info=True)
            return False

    def rebuild_from_markdown(self) -> None:
        if self.collection.count() > 0:
            logger.info("Chroma store already populated; skipping rebuild")
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
                logger.info("No processed documents available for rebuild")
                return

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )

            requested_device = os.getenv("SENTENCE_TRANSFORMERS_DEVICE", "cpu")
            logger.info("Rebuilding embeddings on device %s", requested_device)
            try:
                model = SentenceTransformer("all-MiniLM-L6-v2", device=requested_device)
            except Exception as exc:  # noqa: BLE001
                if requested_device.lower() != "cpu":
                    logger.warning(
                        "Falling back to CPU for rebuild due to error on %s: %s",
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
                    logger.info(
                        "Skipping rebuild for %s (id=%s) because source file changed",
                        doc.filename,
                        doc.id,
                    )
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
                logger.info("Chroma rebuild completed")
        finally:
            db.close()

    def _markdown_is_current(self, doc: PDFDocument) -> bool:  # pragma: no cover
        return markdown_is_current(doc)
