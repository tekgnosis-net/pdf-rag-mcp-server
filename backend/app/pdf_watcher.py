"""Directory watcher for automatic PDF ingestion."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

from app.database import PDFDocument, SessionLocal
from app.pdf_processor import PDFProcessor, PROCESSING_STATUS
from app.vector_store import VectorStore
from app.websocket import manager

logger = logging.getLogger("pdf_watcher")


class PDFDirectoryWatcher:
    """Monitor a directory tree for PDFs and enqueue them for processing."""

    def __init__(
        self,
        directory: str,
        pdf_processor: PDFProcessor,
        vector_store: VectorStore,
        poll_interval: float = 5.0,
        max_workers: int = 1,
    ) -> None:
        self.directory = os.path.abspath(directory)
        self.pdf_processor = pdf_processor
        self.vector_store = vector_store
        self.poll_interval = poll_interval
        self.max_workers = max(1, max_workers)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active_paths: Set[str] = set()
        self._active_lock = threading.Lock()
        self._db_lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None

    def start(self) -> None:
        """Start monitoring in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.debug("PDFDirectoryWatcher already running")
            return

        if not os.path.isdir(self.directory):
            logger.info("Creating watch directory %s", self.directory)
            os.makedirs(self.directory, exist_ok=True)

        self._stop_event.clear()
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="pdf-ingest-worker",
        )
        self._thread = threading.Thread(
            target=self._run,
            name="pdf-directory-watcher",
            daemon=True,
        )
        self._thread.start()
        logger.info("Started PDF directory watcher for %s", self.directory)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop monitoring and wait for the worker to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
        logger.info("Stopped PDF directory watcher for %s", self.directory)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._scan_once()
            except Exception as exc:  # noqa: BLE001
                logger.error("Error while scanning %s: %s", self.directory, exc, exc_info=True)
            self._stop_event.wait(self.poll_interval)

    def _scan_once(self) -> None:
        if not os.path.exists(self.directory):
            logger.warning("Watch directory %s does not exist", self.directory)
            return

        for root, _, files in os.walk(self.directory):
            for filename in files:
                if not filename.lower().endswith(".pdf"):
                    continue
                absolute_path = os.path.abspath(os.path.join(root, filename))
                if self._is_active(absolute_path):
                    continue
                self._handle_candidate(absolute_path)

    def _handle_candidate(self, absolute_path: str) -> None:
        relative_name = os.path.relpath(absolute_path, self.directory)
        display_name = relative_name if relative_name != os.curdir else os.path.basename(absolute_path)

        try:
            file_size = os.path.getsize(absolute_path)
            mtime = dt.datetime.utcfromtimestamp(os.path.getmtime(absolute_path))
        except OSError as exc:
            logger.warning("Unable to stat %s: %s", absolute_path, exc)
            return

        doc: Optional[PDFDocument] = None
        vector_cleanup_filter: Optional[Dict[str, int]] = None

        with self._db_lock:
            db: Session = SessionLocal()
            try:
                existing = db.query(PDFDocument).filter(PDFDocument.file_path == absolute_path).first()

                if existing:
                    if existing.processing:
                        logger.debug("Skipping %s – already processing", display_name)
                        return

                    needs_reprocess = (
                        not existing.processed
                        or (existing.uploaded_at and existing.uploaded_at < mtime)
                        or existing.file_size != file_size
                    )

                    if not needs_reprocess:
                        logger.debug("Skipping %s – already processed and unchanged", display_name)
                        return

                    logger.info("Detected updated PDF %s, scheduling reprocessing", display_name)
                    vector_cleanup_filter = {"pdf_id": existing.id}
                    existing.processing = True
                    existing.processed = False
                    existing.error = None
                    existing.progress = 0.0
                    existing.file_size = file_size
                    existing.uploaded_at = dt.datetime.utcnow()
                    doc = existing
                else:
                    logger.info("Detected new PDF %s, scheduling ingestion", display_name)
                    doc = PDFDocument(
                        filename=display_name,
                        file_path=absolute_path,
                        file_size=file_size,
                        processed=False,
                        processing=True,
                        progress=0.0,
                    )
                    db.add(doc)

                db.commit()
                db.refresh(doc)
            finally:
                db.close()

        if doc is None:
            return

        if vector_cleanup_filter:
            try:
                self.vector_store.delete(filter=vector_cleanup_filter)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to purge existing embeddings for %s: %s", display_name, exc, exc_info=True)

        PROCESSING_STATUS.pop(doc.filename, None)
        PROCESSING_STATUS[doc.filename] = {"progress": 0, "status": "Queued"}
        self._add_active_path(absolute_path)

        if not self._executor:
            logger.warning("Executor not available, skipping processing for %s", display_name)
            self._remove_active_path(absolute_path)
            return

        self._executor.submit(self._process_document, doc.id, absolute_path, doc.filename)

    def _process_document(self, doc_id: int, absolute_path: str, display_name: str) -> None:
        async def _runner() -> None:
            await self.pdf_processor.process_pdf(doc_id, absolute_path, display_name)
            await manager.broadcast(
                {
                    "type": "processing_update",
                    "filename": display_name,
                    "status": PROCESSING_STATUS.get(display_name, {}),
                }
            )

        try:
            asyncio.run(_runner())
        except Exception as exc:  # noqa: BLE001
            logger.error("Error processing %s: %s", display_name, exc, exc_info=True)
        finally:
            self._remove_active_path(absolute_path)
            time.sleep(0.1)

    def _is_active(self, path: str) -> bool:
        with self._active_lock:
            return path in self._active_paths

    def _add_active_path(self, path: str) -> None:
        with self._active_lock:
            self._active_paths.add(path)

    def _remove_active_path(self, path: str) -> None:
        with self._active_lock:
            self._active_paths.discard(path)