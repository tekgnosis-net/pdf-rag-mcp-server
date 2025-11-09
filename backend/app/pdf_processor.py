"""PDF Processing Module.

This module is responsible for parsing PDF documents, extracting text content, and generating vector embeddings for storage in a vector database.
"""

# Standard library imports
import asyncio
import base64
import datetime as dt
import io
import logging
import os
import time
import traceback
import uuid
from typing import Dict, List, Optional, Tuple

# Third-party library imports
import fitz  # PyMuPDF
import pytesseract
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from PIL import Image

# Local application/library imports
from app.database import PDFDocument, SessionLocal
from app.vector_store import VectorStore
from app.database import PDFMarkdownPage
from app.websocket import manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pdf_processor")

# Global variable to track processing progress
PROCESSING_STATUS: Dict[str, Dict] = {}

MAX_IMAGE_BYTES = int(os.getenv("PDF_IMAGE_MAX_BYTES", str(2 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("PDF_IMAGE_MAX_PIXELS", "5000000"))
MAX_IMAGES_PER_PAGE = int(os.getenv("PDF_IMAGE_MAX_PER_PAGE", "8"))


class PDFProcessor:
    """PDF processor class, responsible for parsing and processing PDF documents."""
    
    def __init__(self):
        """Initialize PDF processor."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        requested_device = os.getenv("SENTENCE_TRANSFORMERS_DEVICE", "cpu")
        logger.info(f"Loading SentenceTransformer on device '{requested_device}'")
        try:
            self.embedding_model = SentenceTransformer(
                "all-MiniLM-L6-v2",
                device=requested_device
            )
        except Exception as exc:
            if requested_device.lower() != "cpu":
                logger.warning(
                    "Failed to load SentenceTransformer on device '%s': %s. "
                    "Falling back to CPU.",
                    requested_device,
                    exc
                )
                self.embedding_model = SentenceTransformer(
                    "all-MiniLM-L6-v2",
                    device="cpu"
                )
            else:
                raise
        self.vector_store = VectorStore()
        self._last_broadcast: Dict[str, Dict[str, float | str]] = {}

    async def _emit_status(self, filename: str):
        """Broadcast the current processing status over WebSocket with basic throttling."""
        status = PROCESSING_STATUS.get(filename)
        if not status:
            return

        progress = float(status.get("progress", 0) or 0)
        now = time.monotonic()
        marker = {
            "progress": progress,
            "status": status.get("status", ""),
            "ts": now,
        }

        previous = self._last_broadcast.get(filename)
        # Only emit if status text changed or progress jumped at least 0.5%
        if previous:
            if (
                marker["status"] == previous.get("status")
                and abs(progress - float(previous.get("progress", 0))) < 0.2
                and (now - float(previous.get("ts", 0))) < 1.0
            ):
                return

        self._last_broadcast[filename] = marker
        await manager.broadcast({
            "type": "processing_update",
            "filename": filename,
            "status": status,
        })

    def _clear_broadcast_marker(self, filename: str):
        self._last_broadcast.pop(filename, None)
        
    async def process_pdf(self, pdf_id: int, pdf_path: str, filename: str):
        """Asynchronously process a PDF file.
        
        Args:
            pdf_id: ID of the PDF document.
            pdf_path: Path to the PDF file.
            filename: Original file name.
            
        Returns:
            bool: Whether processing was successful.
        """
        logger.info(f"Starting to process PDF: {filename}, ID: {pdf_id}")
        db = SessionLocal()
        pdf_doc = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
        
        if not pdf_doc:
            logger.error(f"Cannot find PDF document record, ID: {pdf_id}")
            db.close()
            return False
        
        # Mark as processing
        pdf_doc.processing = True
        PROCESSING_STATUS[filename] = {
            "progress": 0,
            "status": "Processing",
            "page_current": 0,
            "page_total": 0,
        }
        db.commit()
        logger.info(f"PDF processing status updated to processing")
        await self._emit_status(filename)
        
        try:
            # Check if the file exists
            if not os.path.exists(pdf_path):
                error_msg = f"Cannot find PDF file: {pdf_path}"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
                await self._emit_status(filename)
                self._clear_broadcast_marker(filename)
                return False
                
            # Open PDF
            logger.info(f"Opening PDF file: {pdf_path}")
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            pdf_doc.page_count = total_pages
            db.commit()
            logger.info(f"PDF page count: {total_pages}")
            PROCESSING_STATUS[filename]["page_total"] = total_pages
            PROCESSING_STATUS[filename]["status"] = "Parsing PDF"
            await self._emit_status(filename)
            # Before persisting new markdown rows for this PDF, delete any
            # existing ones for the same pdf_id (reprocessing behavior)
            try:
                db_cleanup = SessionLocal()
                db_cleanup.query(PDFMarkdownPage).filter(PDFMarkdownPage.pdf_id == pdf_id).delete()
                db_cleanup.commit()
            except Exception:
                logger.exception("Failed to clear existing markdown rows for pdf_id=%s", pdf_id)
            finally:
                try:
                    db_cleanup.close()
                except Exception:
                    pass

            all_texts: List[str] = []
            page_numbers = []  # Store page numbers for each text chunk
            markdown_by_page: List[tuple[int, str]] = []
            extracted_images_total = 0
            seen_image_refs: set[int] = set()
            
            # Process each page
            for i, page in enumerate(doc):
                try:
                    page_number = i + 1
                    text = page.get_text()

                    page_markdown_parts: List[str] = []

                    if text and text.strip():
                        all_texts.append(text)
                        page_numbers.append(page_number)  # Store page numbers
                        page_markdown_parts.append(text.strip())

                    images_markdown = self._extract_page_images(
                        doc,
                        page,
                        page_number,
                        seen_image_refs,
                    )
                    if images_markdown:
                        extracted_images_total += len(images_markdown)
                        page_markdown_parts.extend(images_markdown)
                        for idx in range(len(images_markdown)):
                            placeholder = f"[Embedded image {idx + 1} on page {page_number}]"
                            all_texts.append(placeholder)
                            page_numbers.append(page_number)

                    if page_markdown_parts:
                        markdown_by_page.append((page_number, "\n\n".join(page_markdown_parts)))
                    
                    # Update progress
                    progress = (i + 1) / len(doc) * 50  # First 50% is PDF parsing
                    pdf_doc.progress = progress
                    PROCESSING_STATUS[filename] = {
                        "progress": progress,
                        "status": f"Parsing PDF ({i + 1}/{total_pages})",
                        "page_current": i + 1,
                        "page_total": total_pages,
                    }
                    db.commit()
                    await self._emit_status(filename)
                    
                    logger.info(
                        f"Processing PDF page {i+1}/{len(doc)}, progress {progress:.2f}%"
                    )
                    
                    # Simulate time-consuming operation and allow other coroutines to run
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing page {i+1}: {str(e)}")
            
            # Split into chunks
            logger.info(f"PDF parsing completed, starting to split into chunks")
            joined_text = "\n".join(all_texts)
            
            # Check if there is valid text and attempt OCR fallback if needed
            if not joined_text.strip():
                logger.warning("No text extracted via built-in parser for %s; attempting OCR fallback", filename)
                PROCESSING_STATUS[filename] = {
                    "progress": pdf_doc.progress,
                    "status": "Running OCR",
                    "page_current": 0,
                    "page_total": total_pages,
                }
                db.commit()
                await self._emit_status(filename)

                ocr_texts: List[str] = []
                ocr_pages: List[int] = []
                matrix = fitz.Matrix(2, 2)

                for page_index in range(len(doc)):
                    try:
                        page = doc.load_page(page_index)
                        pix = page.get_pixmap(matrix=matrix)
                        image_bytes = io.BytesIO(pix.tobytes("png"))
                        with Image.open(image_bytes) as pil_image:
                            ocr_text = pytesseract.image_to_string(pil_image)
                    except Exception as ocr_error:  # noqa: BLE001
                        logger.error(
                            "OCR extraction failed for page %s of %s: %s",
                            page_index + 1,
                            filename,
                            ocr_error,
                        )
                        continue

                    if ocr_text.strip():
                        ocr_texts.append(ocr_text)
                        ocr_pages.append(page_index + 1)

                    progress = 50 + ((page_index + 1) / max(len(doc), 1) * 20)
                    pdf_doc.progress = min(progress, 70)
                    PROCESSING_STATUS[filename] = {
                        "progress": pdf_doc.progress,
                        "status": f"Running OCR ({page_index + 1}/{total_pages})",
                        "page_current": page_index + 1,
                        "page_total": total_pages,
                    }
                    db.commit()
                    await self._emit_status(filename)
                    await asyncio.sleep(0.05)

                if ocr_texts:
                    all_texts = ocr_texts
                    page_numbers = ocr_pages
                    joined_text = "\n".join(all_texts)
                    markdown_by_page = list(zip(ocr_pages, (chunk.strip() for chunk in ocr_texts)))
                    logger.info(
                        "OCR fallback recovered text for %s (pages with content: %s)",
                        filename,
                        len(ocr_texts),
                    )
                else:
                    error_msg = "No valid text content after PDF parsing or OCR fallback"
                    logger.error(error_msg)
                    pdf_doc.error = error_msg
                    pdf_doc.blacklisted = True
                    pdf_doc.blacklisted_at = dt.datetime.utcnow()
                    pdf_doc.blacklist_reason = error_msg
                    pdf_doc.processing = False
                    PROCESSING_STATUS[filename] = {
                        "progress": pdf_doc.progress,
                        "status": "Blacklisted",
                        "page_current": page_index + 1,
                        "page_total": total_pages,
                    }
                    db.commit()
                    await self._emit_status(filename)
                    self._clear_broadcast_marker(filename)
                    return False
                
            chunks = self.text_splitter.split_text(joined_text)
            pdf_doc.chunks_count = len(chunks)
            PROCESSING_STATUS[filename]["status"] = "Generating embeddings"
            PROCESSING_STATUS[filename]["page_current"] = total_pages
            PROCESSING_STATUS[filename]["page_total"] = total_pages
            db.commit()
            logger.info(
                "Text split into %s chunks%s",
                len(chunks),
                f"; extracted {extracted_images_total} images" if extracted_images_total else ""
            )
            await self._emit_status(filename)
            
            if not chunks:
                error_msg = "Text split into chunks but no content"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
                await self._emit_status(filename)
                self._clear_broadcast_marker(filename)
                return False
            
            # Generate embeddings - this is a compute-intensive task
            logger.info("Starting to generate embeddings")
            embeddings = self.embedding_model.encode(chunks)
            logger.info("Embeddings generation completed")
            
            # Update progress to 75%
            pdf_doc.progress = 75
            PROCESSING_STATUS[filename]["progress"] = 75
            PROCESSING_STATUS[filename]["status"] = "Storing in vector database"
            db.commit()
            await self._emit_status(filename)
            
            # Store to vector database
            logger.info("Starting to store to vector database")
            
            # Generate processing batch ID (to prevent duplicates)
            batch_id = str(uuid.uuid4())[:8]
            
            # Create metadata, including more useful information
            metadatas = []
            for i, chunk in enumerate(chunks):
                # Calculate possible page range for this chunk (simplified estimate)
                page_index = min(i, len(page_numbers) - 1) if page_numbers else 0
                page_num = page_numbers[page_index] if page_numbers else 0
                
                # Create metadata with more information
                metadata = {
                    "source": filename,
                    "chunk_id": f"{batch_id}_{i}",  # Unique chunk_id
                    "pdf_id": pdf_id,
                    "page": page_num,
                    "batch": batch_id,
                    "index": i,
                    "length": len(chunk),
                    "timestamp": time.time()
                }
                metadatas.append(metadata)
            
            # Record metadata example
            if metadatas:
                logger.info(f"Metadata example: {metadatas[0]}")
            
            # Persist per-page markdown for the processed document
            if markdown_by_page:
                try:
                    markdown_rows = [
                        PDFMarkdownPage(pdf_id=pdf_id, page=page_num, markdown=content)
                        for page_num, content in markdown_by_page
                        if content
                    ]
                    if markdown_rows:
                        db.bulk_save_objects(markdown_rows)
                        db.commit()
                        logger.info(
                            "Persisted %s markdown pages for %s",
                            len(markdown_rows),
                            filename,
                        )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to persist markdown pages for pdf_id=%s", pdf_id)
                    db.rollback()

            # Add to vector database
            storage_success = self.vector_store.add_documents(
                chunks, embeddings, metadatas
            )
            
            if not storage_success:
                error_msg = "Failed to store to vector database"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                PROCESSING_STATUS[filename]["status"] = f"Error: {error_msg}"
                db.commit()
                await self._emit_status(filename)
                self._clear_broadcast_marker(filename)
                return False
            
            # Complete
            pdf_doc.progress = 100
            pdf_doc.processed = True
            pdf_doc.processing = False
            PROCESSING_STATUS[filename]["progress"] = 100
            PROCESSING_STATUS[filename]["status"] = "Completed"
            PROCESSING_STATUS[filename]["page_current"] = total_pages
            PROCESSING_STATUS[filename]["page_total"] = total_pages
            db.commit()
            logger.info(f"PDF processing completed: {filename}")
            await self._emit_status(filename)
            self._clear_broadcast_marker(filename)
            
            return True
            
        except Exception as e:
            # Detailed error logging
            err_msg = f"Error processing PDF: {str(e)}"
            logger.error(err_msg)
            logger.error(traceback.format_exc())
            
            # Error handling
            pdf_doc.error = str(e)
            pdf_doc.processing = False
            PROCESSING_STATUS[filename]["status"] = f"Error: {str(e)}"
            db.commit()
            await self._emit_status(filename)
            self._clear_broadcast_marker(filename)
            return False
        finally:
            db.close()

    def _extract_page_images(
        self,
        document: fitz.Document,
        page: fitz.Page,
        page_number: int,
        seen_image_refs: set[int],
    ) -> List[str]:
        """Extract images from a page and return them as markdown image tags with embedded data URIs."""
        images_markdown: List[str] = []

        for image_index, image_info in enumerate(page.get_images(full=True), start=1):
            if MAX_IMAGES_PER_PAGE and image_index > MAX_IMAGES_PER_PAGE:
                logger.debug(
                    "Skipping remaining images on page %s after reaching limit %s",
                    page_number,
                    MAX_IMAGES_PER_PAGE,
                )
                break

            xref = image_info[0]

            if xref in seen_image_refs:
                logger.debug(
                    "Skipping duplicate image xref %s already captured earlier",
                    xref,
                )
                continue
            seen_image_refs.add(xref)

            try:
                image_bytes, mime_type, dimensions = self._extract_image_bytes(document, xref)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to extract image %s on page %s: %s",
                    image_index,
                    page_number,
                    exc,
                )
                continue

            width, height = dimensions
            pixel_count = width * height if width and height else 0

            if pixel_count and pixel_count > MAX_IMAGE_PIXELS:
                logger.info(
                    "Skipping image %s on page %s – pixel count %s exceeds limit %s",
                    image_index,
                    page_number,
                    pixel_count,
                    MAX_IMAGE_PIXELS,
                )
                continue

            if len(image_bytes) > MAX_IMAGE_BYTES:
                logger.info(
                    "Skipping image %s on page %s – byte size %s exceeds limit %s",
                    image_index,
                    page_number,
                    len(image_bytes),
                    MAX_IMAGE_BYTES,
                )
                continue

            encoded = base64.b64encode(image_bytes).decode("ascii")
            images_markdown.append(
                f"![Page {page_number} Image {image_index}](data:{mime_type};base64,{encoded})"
            )

        return images_markdown

    def _extract_image_bytes(self, document: fitz.Document, xref: int) -> Tuple[bytes, str, Tuple[int, int]]:
        """Return raw image bytes, MIME type, and dimensions for a given xref."""
        image_info = document.extract_image(xref)
        image_bytes = image_info.get("image")
        if not image_bytes:
            raise ValueError("Image stream is empty")

        ext = (image_info.get("ext") or "png").lower()
        width = int(image_info.get("width") or 0)
        height = int(image_info.get("height") or 0)
        mime_type = self._extension_to_mime(ext)

        smask_xref = int(image_info.get("smask") or 0)
        if smask_xref:
            try:
                image_bytes, (width, height) = self._merge_image_with_mask(document, image_bytes, smask_xref)
                mime_type = "image/png"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to merge image mask for xref %s: %s",
                    xref,
                    exc,
                )

        if not mime_type:
            image_bytes, (width, height) = self._convert_image_to_png(image_bytes, fallback_size=(width, height))
            mime_type = "image/png"

        return image_bytes, mime_type, (width, height)

    @staticmethod
    def _extension_to_mime(ext: str) -> Optional[str]:
        mapping = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }
        return mapping.get(ext.lower())

    @staticmethod
    def _convert_image_to_png(
        image_bytes: bytes,
        fallback_size: Tuple[int, int] | None = None,
    ) -> Tuple[bytes, Tuple[int, int]]:
        buffer = io.BytesIO(image_bytes)
        with Image.open(buffer) as pil_image:
            if pil_image.mode not in {"RGB", "RGBA"}:
                pil_image = pil_image.convert("RGBA")
            output = io.BytesIO()
            pil_image.save(output, format="PNG")
            width, height = pil_image.size
        if not width or not height:
            width, height = fallback_size or (0, 0)
        return output.getvalue(), (width, height)

    def _merge_image_with_mask(
        self,
        document: fitz.Document,
        base_bytes: bytes,
        mask_xref: int,
    ) -> Tuple[bytes, Tuple[int, int]]:
        base_pix = fitz.Pixmap(base_bytes)
        mask_info = document.extract_image(mask_xref)
        mask_bytes = mask_info.get("image")
        if not mask_bytes:
            raise ValueError("Mask stream is empty")

        mask_pix = fitz.Pixmap(mask_bytes)
        combined_pix = fitz.Pixmap(base_pix, mask_pix)

        try:
            png_bytes = combined_pix.tobytes("png")
            dimensions = (combined_pix.width, combined_pix.height)
        finally:
            base_pix = None
            mask_pix = None
            combined_pix = None

        return png_bytes, dimensions
    
    def get_processing_status(self, filename: Optional[str] = None):
        """Get processing status.
        
        Args:
            filename: File name, if None returns status for all files.
            
        Returns:
            Dict: Processing status information.
        """
        if filename:
            return PROCESSING_STATUS.get(
                filename, {"progress": 0, "status": "Not started"}
            )
        return PROCESSING_STATUS