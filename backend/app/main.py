"""PDF Knowledge Base API Service.

This module provides API endpoints for the PDF Knowledge Base service, supporting uploading, processing, and querying PDF files.
"""

# Standard library imports
import asyncio
import io
import logging
import os
import uuid
import datetime as dt
from difflib import SequenceMatcher
from contextlib import asynccontextmanager

# Third-party library imports
import fitz  # PyMuPDF
import pytesseract
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_mcp import FastApiMCP
from PIL import Image
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

# Local application/library imports
from app.database import PDFDocument, PDFMarkdownPage, SessionLocal, get_db
from app.pdf_processor import PDFProcessor, PROCESSING_STATUS
from app.pdf_watcher import PDFDirectoryWatcher
from app.vector_store import VectorStore
from app.websocket import manager

# Global directory watcher placeholder to satisfy type checkers
directory_watcher: PDFDirectoryWatcher | None = None
# Track whether the current PyMuPDF build can emit markdown output
MARKDOWN_OUTPUT_SUPPORTED = True


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    """Coordinate startup/shutdown tasks without deprecated on_event hooks."""
    await reset_interrupted_processing()
    try:
        yield
    finally:
        await stop_directory_watcher()


# Initialize application
app = FastAPI(title="MCP PDF Knowledge Base", lifespan=app_lifespan)
mcp_app = FastAPI(title="MCP PDF Knowledge MCP Server")

# Configure logging
logger = logging.getLogger("main")


def _load_embedding_model():
    """Load SentenceTransformer embedding model honoring device preference."""
    requested_device = os.getenv("SENTENCE_TRANSFORMERS_DEVICE", "cpu")
    logger.info(
        "Loading SentenceTransformer for query handler on device '%s'",
        requested_device
    )
    try:
        return SentenceTransformer(
            "all-MiniLM-L6-v2",
            device=requested_device
        )
    except Exception as exc:
        if requested_device.lower() != "cpu":
            logger.warning(
                "Failed to initialize SentenceTransformer on device '%s': %s. "
                "Falling back to CPU.",
                requested_device,
                exc
            )
            return SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        raise


# Initialize processor and model
pdf_processor = PDFProcessor()
embedding_model = _load_embedding_model()
vector_store = VectorStore()

watch_directory = os.getenv("PDF_RAG_WATCH_DIR")
if watch_directory:
    interval_raw = os.getenv("PDF_RAG_WATCH_INTERVAL", "5")
    try:
        poll_interval = float(interval_raw)
    except ValueError:
        logger.warning(
            "Invalid PDF_RAG_WATCH_INTERVAL value '%s', defaulting to 5 seconds",
            interval_raw,
        )
        poll_interval = 5.0

    max_workers_raw = os.getenv("PDF_RAG_WATCH_MAX_WORKERS", "1")
    try:
        max_workers = max(1, int(max_workers_raw))
    except ValueError:
        logger.warning(
            "Invalid PDF_RAG_WATCH_MAX_WORKERS value '%s', defaulting to 1",
            max_workers_raw,
        )
        max_workers = 1

    directory_watcher = PDFDirectoryWatcher(
        watch_directory,
        pdf_processor,
        vector_store,
        poll_interval=poll_interval,
        max_workers=max_workers,
    )
    logger.info(
        "Auto-ingest watcher configured for %s (interval %.1fs, max_workers %d)",
        watch_directory,
        poll_interval,
        max_workers,
    )

logger.info(
    "Initializing application, vector database document count: %s",
    vector_store.get_document_count()
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted to the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Ensure upload directory exists
os.makedirs("./uploads", exist_ok=True)
# Ensure static files directory exists
os.makedirs("./static", exist_ok=True)

# Store active MCP sessions
_active_sessions = {}

# Mount static file service after all API route definitions
# Note: This must be done after route definitions but before application startup
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Set favicon.ico path
@app.get("/favicon.ico")
async def favicon():
    """Serve website icon"""
    return FileResponse("static/vite.svg")

# Set root path to serve index.html
@app.get("/")
async def read_root():
    """Serve frontend application entry page"""
    return FileResponse("static/index.html")

# Important: Do not mount static files to the root path, but to a specific path
# Avoid intercepting WebSocket connections and API requests
app.mount("/static", StaticFiles(directory="static"), name="static_files")
# Note: Static assets directory is static/static/assets, so the mount path is /static/static
app.mount("/static/static", StaticFiles(directory="static/static"), name="nested_static_files")

# If the user accesses a non-existent route (neither API nor static files match),
# return the frontend's index.html to support frontend routing
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """If the route does not exist, return the frontend application to let the frontend handle routing"""
    return FileResponse("static/index.html")

@app.post("/api/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process PDF file.
    
    Args:
        background_tasks: Background task manager.
        file: Uploaded PDF file.
        db: Database session.
        
    Returns:
        Dictionary containing upload status information.
        
    Raises:
        HTTPException: If file is not in PDF format.
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    # Check if file already exists
    existing_doc = db.query(PDFDocument).filter(
        PDFDocument.filename == file.filename
    ).first()
    
    if existing_doc:
        if existing_doc.processed:
            return {"message": "File already processed", "id": existing_doc.id}
        elif existing_doc.processing:
            return {
                "message": "File is currently being processed",
                "id": existing_doc.id
            }
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = f"./uploads/{unique_filename}"
    
    # Save file
    with open(file_path, "wb") as f:
        file_content = await file.read()
        f.write(file_content)
        file_size = len(file_content)
    
    # Create database record
    pdf_doc = PDFDocument(
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        processed=False,
        processing=True,
        progress=0.0
    )
    db.add(pdf_doc)
    db.commit()
    db.refresh(pdf_doc)
    
    # Process PDF in background
    PROCESSING_STATUS[file.filename] = {"progress": 0, "status": "Queued"}
    background_tasks.add_task(
        _process_pdf_background,
        pdf_doc.id,
        file_path,
        file.filename
    )
    
    return {
        "message": "PDF uploaded and queued for processing",
        "id": pdf_doc.id,
        "filename": file.filename
    }


async def _process_pdf_background(pdf_id: int, file_path: str, filename: str):
    """Asynchronous function to process PDF in the background.
    
    Args:
        pdf_id: PDF document ID.
        file_path: Path to the PDF file.
        filename: Original filename.
    """
    await pdf_processor.process_pdf(pdf_id, file_path, filename)
    # Broadcast status update after processing is complete
    await manager.broadcast({
        "type": "processing_update",
        "filename": filename,
        "status": PROCESSING_STATUS.get(filename, {})
    })


@app.get("/api/documents")
async def get_documents(db: Session = Depends(get_db)):
    """Get status of all PDF documents.
    
    Args:
        db: Database session.
        
    Returns:
        List containing information for all documents.
    """
    docs = db.query(PDFDocument).all()
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "uploaded_at": doc.uploaded_at,
            "file_size": doc.file_size,
            "processed": doc.processed,
            "processing": doc.processing,
            "page_count": doc.page_count,
            "chunks_count": doc.chunks_count,
            "progress": doc.progress,
            "error": doc.error,
            "blacklisted": doc.blacklisted,
            "blacklisted_at": doc.blacklisted_at,
            "blacklist_reason": doc.blacklist_reason,
        }
        for doc in docs
    ]


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: int, db: Session = Depends(get_db)):
    """Get detailed information for a single PDF document.
    
    Args:
        doc_id: Document ID.
        db: Database session.
        
    Returns:
        Dictionary containing detailed document information.
        
    Raises:
        HTTPException: If document is not found.
    """
    doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": doc.id,
        "filename": doc.filename,
        "uploaded_at": doc.uploaded_at,
        "file_size": doc.file_size,
        "processed": doc.processed,
        "processing": doc.processing,
        "page_count": doc.page_count,
        "chunks_count": doc.chunks_count,
        "progress": doc.progress,
        "error": doc.error,
        "blacklisted": doc.blacklisted,
        "blacklisted_at": doc.blacklisted_at,
        "blacklist_reason": doc.blacklist_reason,
        "status": PROCESSING_STATUS.get(
            doc.filename,
            {"progress": doc.progress, "status": "Unknown"}
        )
    }


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Delete a PDF document.
    
    Args:
        doc_id: Document ID.
        db: Database session.
        
    Returns:
        Dictionary containing deletion status information.
        
    Raises:
        HTTPException: If document is not found or is currently being processed.
    """
    doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if document is actually being processed
    is_actually_processing = False
    if doc.processing and doc.filename in PROCESSING_STATUS:
        status = PROCESSING_STATUS.get(doc.filename, {}).get("status", "")
        # If status indicates active processing and not an error state
        if (status and "Error" not in status and status != "Completed" 
            and PROCESSING_STATUS[doc.filename].get("progress", 0) < 100):
            is_actually_processing = True
    
    # Only prevent deletion if document is actually being processed
    if is_actually_processing:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete document while it's being processed"
        )
    
    # If document was marked as processing but isn't anymore, clean up status
    if doc.processing and doc.filename in PROCESSING_STATUS:
        PROCESSING_STATUS.pop(doc.filename, None)
        logger.info(f"Cleaned up interrupted processing status for {doc.filename}")
    
    # Delete file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    
    # Delete related documents from vector database
    vector_store.delete(filter={"pdf_id": doc_id})
    logger.info(f"Deleted entries with document ID {doc_id} from vector database")
    
    # Delete persisted markdown pages for this document
    try:
        db.query(PDFMarkdownPage).filter(PDFMarkdownPage.pdf_id == doc_id).delete()
        db.commit()
        logger.info(f"Deleted persisted markdown pages for document ID {doc_id}")
    except Exception:
        logger.exception("Failed to delete markdown pages for document ID %s", doc_id)

    # Delete record from database
    db.delete(doc)
    db.commit()
    
    return {"message": f"Document {doc.filename} deleted successfully"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection handler for real-time updates.
    
    Args:
        websocket: WebSocket connection.
    """
    await manager.connect(websocket)
    try:
        # Initially send all current statuses
        await websocket.send_json({
            "type": "initial_status",
            "status": PROCESSING_STATUS
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Can process messages from the client here
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@mcp_app.get("/query")
async def query_knowledge_base(query: str):
    """Query Knowledge Base
    
    Query the knowledge vector database.
    
    Args:
        query: The search query string.
        
    Returns:
        Dictionary containing the query results.
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Received query request: {query}")
    
    # Record vector database size
    doc_count = vector_store.get_document_count()
    logger.info(f"Current vector database document count: {doc_count}")
    
    # Generate query embedding and search
    query_embedding = embedding_model.encode(query)
    results = vector_store.search(query_embedding, n_results=5)
    
    # Extract results
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    db = SessionLocal()
    
    # Log query result count
    logger.info(f"Query '{query}' found {len(documents)} results")
    
    # Handle no results case
    if not documents:
        logger.warning(f"Query '{query}' found no results")
        
        # Check if is_mcp_request variable exists before using it
        if 'is_mcp_request' in locals() and is_mcp_request:
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": "No information related to your question was found. Please try using different keywords for your query."
                },
                "id": request_id
            }
        else:
            return {"query": query, "results": []}
    
    # Process results, including document name and page information
    formatted_results = []
    
    for doc, meta, distance in zip(documents, metadatas, distances):
        pdf_id = meta.get("pdf_id")
        page_num = meta.get("page", "Unknown page")
        
        result_item = {
            "content": doc,
            "page": page_num,
            "relevance": float(1 - distance),  # Convert distance to relevance score
            "pdf_id": pdf_id,
            "filename": "Unknown document"
        }
        
        # Get document name from database
        if pdf_id:
            pdf_doc = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
            if pdf_doc:
                result_item["filename"] = pdf_doc.filename
        
        formatted_results.append(result_item)
    
    db.close()
    logger.info(f"Returning {len(formatted_results)} formatted results")
    
    return {
        "query": query,
        "results": formatted_results
    }


@app.get("/api/documents/{pdf_id}/markdown")
async def get_document_markdown_by_id(
    pdf_id: int,
    start_page: int = 1,
    max_pages: int | None = None,
    max_characters: int | None = None,
    db: Session = Depends(get_db),
):
    """Return persisted markdown for a PDF by pdf_id. If not present, fall back to on-demand render."""
    doc = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.blacklisted:
        raise HTTPException(status_code=409, detail="Document is blacklisted")

    rows = db.query(PDFMarkdownPage).filter(PDFMarkdownPage.pdf_id == pdf_id).order_by(PDFMarkdownPage.page).all()
    if not rows:
        # Fall back to on-demand renderer which expects a title
        return _render_document_markdown(title=doc.filename, start_page=start_page, max_pages=max_pages, max_characters=max_characters)

    # Use persisted pages to compose the response, respecting paging and character budgets
    total_pages = len(rows)
    if start_page < 1 or start_page > total_pages:
        raise HTTPException(status_code=400, detail="Invalid start_page")

    last_page_allowed = total_pages
    if max_pages is not None:
        last_page_allowed = min(total_pages, start_page + max_pages - 1)

    page_sections = []
    characters_consumed = 0
    processed_pages = 0
    last_page_rendered = start_page - 1
    truncated_by_budget = False

    for p in rows[start_page - 1:last_page_allowed]:
        section_markdown = f"## Page {p.page}\n\n{p.markdown}\n"

        if max_characters is not None:
            remaining_budget = max_characters - characters_consumed
            if remaining_budget <= 0:
                truncated_by_budget = True
                break
            if len(section_markdown) > remaining_budget:
                if not page_sections:
                    raise HTTPException(status_code=400, detail="max_characters is too restrictive to include a single page")
                truncated_by_budget = True
                break

        page_sections.append(section_markdown)
        characters_consumed += len(section_markdown)
        processed_pages += 1
        last_page_rendered = p.page

        if max_characters is not None and characters_consumed >= max_characters:
            truncated_by_budget = True
            break

    has_more = last_page_rendered < total_pages or truncated_by_budget

    markdown_header = f"# {doc.filename}\n"
    page_window_line = f"_Pages {start_page}-{last_page_rendered} of {total_pages}_\n\n"
    markdown_output = markdown_header + page_window_line + "".join(page_sections)

    return {
        "id": doc.id,
        "filename": doc.filename,
        "markdown": markdown_output,
        "page_start": start_page,
        "page_end": last_page_rendered,
        "total_pages": total_pages,
        "pages_returned": processed_pages,
        "has_more": has_more,
        "next_page": last_page_rendered + 1 if has_more and last_page_rendered < total_pages else None,
        "truncated_by_characters": truncated_by_budget,
    }


@app.get("/api/blacklist")
async def list_blacklist(db: Session = Depends(get_db)):
    """List blacklisted documents."""
    docs = db.query(PDFDocument).filter(PDFDocument.blacklisted == True).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "blacklisted_at": d.blacklisted_at,
            "blacklist_reason": d.blacklist_reason,
        }
        for d in docs
    ]


@app.post("/api/blacklist")
async def add_blacklist(entry: dict, db: Session = Depends(get_db)):
    """Add or update a blacklist entry.

    Body can be {"doc_id": int} or {"filename": str, "reason": str}
    """
    doc_id = entry.get("doc_id")
    filename = entry.get("filename")
    reason = entry.get("reason")

    if doc_id:
        doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        doc.blacklisted = True
        doc.blacklisted_at = dt.datetime.utcnow()
        doc.blacklist_reason = reason
        doc.processing = False
        db.commit()
        return {"id": doc.id, "filename": doc.filename}

    if filename:
        existing = db.query(PDFDocument).filter(PDFDocument.filename == filename).first()
        if existing:
            existing.blacklisted = True
            existing.blacklisted_at = dt.datetime.utcnow()
            existing.blacklist_reason = reason
            existing.processing = False
            db.commit()
            return {"id": existing.id, "filename": existing.filename}
        # Create a placeholder record for the blacklist
        new_doc = PDFDocument(
            filename=filename,
            file_path="",
            file_size=0,
            processed=False,
            processing=False,
            blacklisted=True,
            blacklisted_at=dt.datetime.utcnow(),
            blacklist_reason=reason,
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        return {"id": new_doc.id, "filename": new_doc.filename}

    raise HTTPException(status_code=400, detail="Must provide doc_id or filename")


@app.delete("/api/blacklist/{doc_id}")
async def remove_blacklist(doc_id: int, db: Session = Depends(get_db)):
    """Remove a document from the blacklist (un-blacklist)."""
    doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.blacklisted = False
    doc.blacklisted_at = None
    doc.blacklist_reason = None
    db.commit()
    return {"id": doc.id, "filename": doc.filename, "blacklisted": False}


def _render_document_markdown(
    title: str,
    start_page: int = 1,
    max_pages: int | None = None,
    max_characters: int | None = None,
):
    """Render PDF content as Markdown enforcing pagination and character budgets."""
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Title query must be provided")

    if start_page < 1:
        raise HTTPException(status_code=400, detail="start_page must be >= 1")
    if max_pages is not None and max_pages < 1:
        raise HTTPException(status_code=400, detail="max_pages must be >= 1 when supplied")
    if max_characters is not None and max_characters < 2000:
        raise HTTPException(status_code=400, detail="max_characters must be at least 2000 when supplied")

    query_normalized = title.strip().lower()
    global MARKDOWN_OUTPUT_SUPPORTED
    db = SessionLocal()

    try:
        documents = db.query(PDFDocument).all()
        if not documents:
            raise HTTPException(status_code=404, detail="No documents available")

        scored_docs: list[tuple[float, PDFDocument]] = []
        for document in documents:
            filename_lower = document.filename.lower()
            if query_normalized in filename_lower:
                score = 2.0
            else:
                score = SequenceMatcher(None, filename_lower, query_normalized).ratio()
            scored_docs.append((score, document))

        top_score, matched_doc = max(scored_docs, key=lambda item: item[0])
        if top_score < 0.3:
            raise HTTPException(status_code=404, detail="No matching document found")

        if matched_doc.blacklisted:
            raise HTTPException(status_code=409, detail="Document is currently blacklisted")
        if not matched_doc.processed:
            raise HTTPException(status_code=409, detail="Document has not completed processing")

        if not os.path.exists(matched_doc.file_path):
            raise HTTPException(status_code=404, detail="Document file is missing from storage")

        doc_handle = fitz.open(matched_doc.file_path)
        try:
            total_pages = doc_handle.page_count
            if start_page > total_pages:
                raise HTTPException(status_code=404, detail="start_page exceeds document length")

            last_page_allowed = total_pages
            if max_pages is not None:
                last_page_allowed = min(total_pages, start_page + max_pages - 1)

            markdown_header = f"# {matched_doc.filename}\n"
            page_sections: list[str] = []
            characters_consumed = 0
            processed_pages = 0
            last_page_rendered = start_page - 1
            truncated_by_budget = False
            matrix = fitz.Matrix(2, 2)

            for page_number in range(start_page, last_page_allowed + 1):
                page = doc_handle.load_page(page_number - 1)
                page_markdown = ""

                if MARKDOWN_OUTPUT_SUPPORTED:
                    try:
                        page_markdown = page.get_text("markdown").strip()
                    except (AssertionError, RuntimeError, ValueError) as exc:
                        MARKDOWN_OUTPUT_SUPPORTED = False
                        logger.warning(
                            "PyMuPDF markdown extraction unsupported; falling back to plain text: %s",
                            exc,
                        )
                        page_markdown = ""

                if not page_markdown:
                    page_text = ""
                    try:
                        page_text = page.get_text().strip()
                    except (RuntimeError, ValueError) as exc:  # noqa: BLE001
                        logger.error(
                            "Text extraction failed while rendering markdown for %s page %s: %s",
                            matched_doc.filename,
                            page_number,
                            exc,
                        )

                    if not page_text:
                        try:
                            pix = page.get_pixmap(matrix=matrix)
                            image_bytes = io.BytesIO(pix.tobytes("png"))
                            with Image.open(image_bytes) as image:
                                page_text = pytesseract.image_to_string(image)
                        except Exception as exc:  # noqa: BLE001
                            logger.error(
                                "OCR extraction failed while rendering markdown for %s page %s: %s",
                                matched_doc.filename,
                                page_number,
                                exc,
                            )

                    page_markdown = page_text

                section_content = page_markdown.strip() if page_markdown else "_No extractable content_"
                section_markdown = f"## Page {page_number}\n\n{section_content}\n"

                if max_characters is not None:
                    remaining_budget = max_characters - characters_consumed
                    if remaining_budget <= 0:
                        truncated_by_budget = True
                        break
                    if len(section_markdown) > remaining_budget:
                        if not page_sections:
                            raise HTTPException(
                                status_code=400,
                                detail="max_characters is too restrictive to include a single page",
                            )
                        truncated_by_budget = True
                        break

                page_sections.append(section_markdown)
                characters_consumed += len(section_markdown)
                processed_pages += 1
                last_page_rendered = page_number

                if max_characters is not None and characters_consumed >= max_characters:
                    truncated_by_budget = True
                    break

        finally:
            doc_handle.close()

        if processed_pages == 0:
            raise HTTPException(status_code=500, detail="No pages were rendered")

        if truncated_by_budget and last_page_rendered >= total_pages:
            truncated_by_budget = False

        end_page = last_page_rendered
        has_more = end_page < total_pages or truncated_by_budget

        page_window_line = f"_Pages {start_page}-{end_page} of {total_pages}_\n\n"
        markdown_output = markdown_header + page_window_line + "".join(page_sections)

        return {
            "id": matched_doc.id,
            "filename": matched_doc.filename,
            "markdown": markdown_output,
            "page_start": start_page,
            "page_end": end_page,
            "total_pages": total_pages,
            "pages_returned": processed_pages,
            "has_more": has_more,
            "next_page": end_page + 1 if has_more and end_page < total_pages else None,
            "truncated_by_characters": truncated_by_budget,
        }
    finally:
        db.close()


@mcp_app.get("/documents/markdown")
async def get_document_markdown(
    title: str,
    start_page: int = 1,
    max_pages: int | None = None,
    max_characters: int | None = None,
):
    """Return PDF content rendered as Markdown with optional paging limits."""
    return _render_document_markdown(
        title=title,
        start_page=start_page,
        max_pages=max_pages,
        max_characters=max_characters,
    )


@app.get("/mcp/documents/markdown")
async def get_document_markdown_http(
    title: str,
    start_page: int = 1,
    max_pages: int | None = None,
    max_characters: int | None = None,
):
    """Expose the MCP markdown renderer on the primary HTTP application."""
    return _render_document_markdown(
        title=title,
        start_page=start_page,
        max_pages=max_pages,
        max_characters=max_characters,
    )


mcp = FastApiMCP(mcp_app)
mcp.mount()

# Check for and reset interrupted document processing
async def reset_interrupted_processing():
    """Check for documents marked as processing but interrupted, and reset their status."""
    db = SessionLocal()
    try:
        processing_docs = db.query(PDFDocument).filter(PDFDocument.processing == True).all()
        
        if processing_docs:
            logger.info(f"Found {len(processing_docs)} documents with interrupted processing status")
            
            for doc in processing_docs:
                # Mark as not processing, but keep error message if any
                doc.processing = False
                if not doc.error:
                    doc.error = "Processing was interrupted"
                
                logger.info(f"Reset interrupted processing status for document: {doc.filename}")
                
                # Remove from PROCESSING_STATUS if it exists
                if doc.filename in PROCESSING_STATUS:
                    PROCESSING_STATUS.pop(doc.filename)
            
            db.commit()
            logger.info("All interrupted processing statuses have been reset")
    finally:
        db.close()

    if directory_watcher:
        directory_watcher.start()


async def stop_directory_watcher():
    """Stop the directory watcher thread when the application shuts down."""
    if directory_watcher:
        directory_watcher.stop()

# Start service
if __name__ == "__main__":
    import uvicorn
    import threading

    # Start metrics service in a separate thread
    def run_mcp_server():
        uvicorn.run(mcp_app, host="0.0.0.0", port=7800)
    
    # Start metrics service thread
    metrics_thread = threading.Thread(target=run_mcp_server)
    metrics_thread.daemon = True
    metrics_thread.start()

    # Start FastAPI in the main thread
    uvicorn.run(app, host="0.0.0.0", port=8000)

