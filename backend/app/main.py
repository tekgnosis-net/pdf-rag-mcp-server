"""PDF Knowledge Base API Service.

This module provides API endpoints for the PDF Knowledge Base service, supporting uploading, processing, and querying PDF files.
"""

# Standard library imports
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

# Third-party library imports
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
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

# Local application/library imports
from app.database import PDFDocument, SessionLocal, get_db
from app.pdf_processor import PDFProcessor, PROCESSING_STATUS
from app.pdf_watcher import PDFDirectoryWatcher
from app.vector_store import VectorStore
from app.websocket import manager

# Global directory watcher placeholder to satisfy type checkers
directory_watcher: PDFDirectoryWatcher | None = None


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
            "file_id": pdf_id,
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

