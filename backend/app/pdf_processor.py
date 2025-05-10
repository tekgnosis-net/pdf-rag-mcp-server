"""PDF Processing Module.

This module is responsible for parsing PDF documents, extracting text content, and generating vector embeddings for storage in a vector database.
"""

# Standard library imports
import asyncio
import logging
import os
import time
import traceback
import uuid
from typing import Dict, List, Optional

# Third-party library imports
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

# Local application/library imports
from app.database import PDFDocument, SessionLocal
from app.vector_store import VectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pdf_processor")

# Global variable to track processing progress
PROCESSING_STATUS: Dict[str, Dict] = {}


class PDFProcessor:
    """PDF processor class, responsible for parsing and processing PDF documents."""
    
    def __init__(self):
        """Initialize PDF processor."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.vector_store = VectorStore()
        
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
            "page_current": 0
        }
        db.commit()
        logger.info(f"PDF processing status updated to processing")
        
        try:
            # Check if the file exists
            if not os.path.exists(pdf_path):
                error_msg = f"Cannot find PDF file: {pdf_path}"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
                return False
                
            # Open PDF
            logger.info(f"Opening PDF file: {pdf_path}")
            doc = fitz.open(pdf_path)
            pdf_doc.page_count = len(doc)
            db.commit()
            logger.info(f"PDF page count: {len(doc)}")
            
            all_texts = []
            page_numbers = []  # Store page numbers for each text chunk
            
            # Process each page
            for i, page in enumerate(doc):
                try:
                    text = page.get_text()
                    # Only add non-empty text
                    if text.strip():
                        all_texts.append(text)
                        page_numbers.append(i + 1)  # Store page numbers
                    
                    # Update progress
                    progress = (i + 1) / len(doc) * 50  # First 50% is PDF parsing
                    pdf_doc.progress = progress
                    PROCESSING_STATUS[filename] = {
                        "progress": progress,
                        "status": "Parsing PDF",
                        "page_current": i + 1
                    }
                    db.commit()
                    
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
            
            # Check if there is valid text
            if not joined_text.strip():
                error_msg = "No valid text content after PDF parsing"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
                return False
                
            chunks = self.text_splitter.split_text(joined_text)
            pdf_doc.chunks_count = len(chunks)
            PROCESSING_STATUS[filename]["status"] = "Generating embeddings"
            db.commit()
            logger.info(f"Text split into {len(chunks)} chunks")
            
            if not chunks:
                error_msg = "Text split into chunks but no content"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
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
                return False
            
            # Complete
            pdf_doc.progress = 100
            pdf_doc.processed = True
            pdf_doc.processing = False
            PROCESSING_STATUS[filename]["progress"] = 100
            PROCESSING_STATUS[filename]["status"] = "Completed"
            db.commit()
            logger.info(f"PDF processing completed: {filename}")
            
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
            return False
        finally:
            db.close()
    
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