#!/usr/bin/env python

import sys
import os
from pathlib import Path
import asyncio
import argparse

# Add project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.vector_store import VectorStore
from app.pdf_processor import PDFProcessor
from app.database import SessionLocal, PDFDocument
from sentence_transformers import SentenceTransformer

async def test_vector_db():
    """Test vector database query functionality"""
    # 1. Check if there is data in the vector database
    vector_store = VectorStore()
    doc_count = vector_store.get_document_count()
    print(f"Document count in vector database: {doc_count}")
    
    if doc_count == 0:
        print("Warning: No documents in vector database, please upload and process PDF files first.")
        return
    
    # 2. Test queries
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Test several different queries
    test_queries = [
        "This is a test query",
        "What is the MCP protocol",
        "Features of the PDF knowledge base",
        "How does the vector database work"
    ]
    
    for query in test_queries:
        print(f"\nExecuting query: '{query}'")
        query_embedding = embedding_model.encode(query)
        results = vector_store.search(query_embedding, n_results=3)
        
        # Print results
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])
        
        if not documents[0]:
            print("  No relevant documents found")
            continue
        
        print(f"  Found {len(documents[0])} results:")
        for i, (doc, meta, dist) in enumerate(zip(documents[0], metadatas[0], distances[0])):
            doc_preview = doc[:100] + "..." if len(doc) > 100 else doc
            print(f"  {i+1}. Similarity: {1-dist:.4f}, PDF ID: {meta.get('pdf_id')}, Chunk ID: {meta.get('chunk_id')}")
            print(f"     Text preview: {doc_preview}")

async def reset_vector_db():
    """Reset vector database"""
    vector_store = VectorStore()
    if vector_store.reset():
        print("Vector database has been successfully reset")
    else:
        print("Failed to reset vector database")

async def list_documents():
    """List all PDF documents"""
    db = SessionLocal()
    try:
        docs = db.query(PDFDocument).all()
        if not docs:
            print("No PDF documents found")
            return
        
        print(f"Found {len(docs)} PDF documents:")
        for doc in docs:
            status = "Processed" if doc.processed else "Processing" if doc.processing else "Not processed"
            error = f" (Error: {doc.error})" if doc.error else ""
            print(f"  ID: {doc.id}, Filename: {doc.filename}, Status: {status}{error}")
    finally:
        db.close()

async def process_document(doc_id=None):
    """Manually process a specified PDF document"""
    db = SessionLocal()
    try:
        if doc_id is None:
            # Get the first unprocessed document
            doc = db.query(PDFDocument).filter(
                PDFDocument.processed == False, 
                PDFDocument.processing == False
            ).first()
        else:
            # Get document with specified ID
            doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()
        
        if not doc:
            print("No PDF documents found that need processing")
            return
        
        print(f"Starting to process document: {doc.filename} (ID: {doc.id})")
        
        # Start processing
        processor = PDFProcessor()
        result = await processor.process_pdf(doc.id, doc.file_path, doc.filename)
        
        if result:
            print(f"Document processing successful: {doc.filename}")
        else:
            print(f"Document processing failed: {doc.filename}")
            
    finally:
        db.close()

async def main():
    parser = argparse.ArgumentParser(description="PDF Knowledge Base Testing Tool")
    parser.add_argument("--reset", action="store_true", help="Reset vector database")
    parser.add_argument("--list", action="store_true", help="List all PDF documents")
    parser.add_argument("--process", type=int, nargs="?", const=0, help="Process a PDF document with the specified ID, if no ID is specified, process the first unprocessed document")
    parser.add_argument("--query", action="store_true", help="Test vector database queries")
    
    args = parser.parse_args()
    
    if args.reset:
        await reset_vector_db()
    
    if args.list:
        await list_documents()
    
    if args.process is not None:
        doc_id = args.process if args.process > 0 else None
        await process_document(doc_id)
    
    if args.query or (not args.reset and not args.list and args.process is None):
        await test_vector_db()

if __name__ == "__main__":
    asyncio.run(main()) 