"""Vector Storage Module.

This module provides a vector database interface for storing and retrieving vector representations of PDF documents.
"""

# Standard library imports
import logging
import os
from typing import Any, Dict, List, Optional

# Third-party library imports
import chromadb
import numpy as np
from chromadb.config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vector_store")


class VectorStore:
    """Vector storage class for managing and accessing the vector database."""
    
    def __init__(self, persist_directory=None):
        """Initialize vector storage.
        
        Args:
            persist_directory: Vector database persistence directory, if None then use default path.
        """
        # Use absolute path
        if persist_directory is None:
            # Get absolute path of current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Step back to backend directory
            backend_dir = os.path.dirname(current_dir)
            persist_directory = os.path.join(backend_dir, "chroma_db")
        
        # Convert relative path to absolute path
        persist_directory = os.path.abspath(persist_directory)
        
        logger.info(f"Initializing vector database, persistence directory: {persist_directory}")
        
        # Ensure directory exists
        os.makedirs(persist_directory, exist_ok=True)
        
        try:
            # Use persistence configuration
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection("pdf_documents")
            logger.info(
                f"Successfully connected to vector database, current document count: {self.collection.count()}"
            )
        except Exception as e:
            logger.error(f"Error connecting to vector database: {str(e)}")
            raise
    
    def add_documents(
        self, 
        chunks: List[str], 
        embeddings: np.ndarray, 
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """Add documents to the vector database.
        
        Args:
            chunks: List of text chunks.
            embeddings: Corresponding vector embeddings array.
            metadatas: List of metadata, containing relevant information for each text chunk.
            
        Returns:
            bool: Whether the operation was successful.
        """
        try:
            # Record document count before adding
            before_count = self.collection.count()
            logger.info(f"Vector database document count before adding: {before_count}")
            
            # Generate unique ID for each document
            ids = [f"doc_{meta['pdf_id']}_{meta['chunk_id']}" for meta in metadatas]
            
            logger.info(f"Adding {len(chunks)} documents to vector database")
            if chunks:
                logger.info(f"Sample document: {chunks[0][:100]}...")
                logger.info(f"Sample metadata: {metadatas[0]}")
                logger.info(f"Sample ID: {ids[0]}")
            
            # Check for duplicate IDs, delete them first if they exist
            try:
                # Try to get existing ID list
                existing_ids = set()
                for i in range(0, len(ids), 100):
                    batch_ids = ids[i:i+100]
                    # Check if each ID exists
                    for id in batch_ids:
                        try:
                            self.collection.get(ids=[id])
                            existing_ids.add(id)
                        except Exception:
                            # ID doesn't exist, ignore error
                            pass
                
                # If there are duplicate IDs, delete them first
                if existing_ids:
                    logger.warning(f"Found {len(existing_ids)} duplicate IDs, will delete them first")
                    # Delete in batches, max 100 at a time
                    for i in range(0, len(existing_ids), 100):
                        batch_ids = list(existing_ids)[i:i+100]
                        self.collection.delete(ids=batch_ids)
                    logger.info(f"Duplicate IDs deleted")
            except Exception as e:
                logger.warning(f"Error checking for duplicate IDs: {str(e)}")
            
            # Add in batches to avoid oversized requests
            batch_size = 100
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            
            for i in range(0, len(chunks), batch_size):
                end = min(i + batch_size, len(chunks))
                batch_num = i // batch_size + 1
                logger.info(
                    f"Adding batch {batch_num}/{total_batches}: "
                    f"{i}-{end}/{len(chunks)}"
                )
                
                batch_chunks = chunks[i:end]
                batch_embeddings = embeddings[i:end].tolist()
                batch_metadatas = metadatas[i:end]
                batch_ids = ids[i:end]
                
                # Check data legality
                for j, (doc, emb, meta, id) in enumerate(zip(
                    batch_chunks, batch_embeddings, batch_metadatas, batch_ids
                )):
                    if not doc or not isinstance(doc, str):
                        logger.warning(f"Skipping invalid document #{i+j}: {doc}")
                        continue
                
                # Add document
                try:
                    self.collection.add(
                        documents=batch_chunks,
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                        ids=batch_ids
                    )
                    logger.info(f"Batch {batch_num} added successfully")
                except Exception as e:
                    logger.error(f"Error adding batch {batch_num}: {str(e)}")
                    # Continue processing other batches, don't interrupt the process
            
            # Ensure data persistence
            try:
                if hasattr(self.client, "persist"):
                    self.client.persist()
                    logger.info("Data persisted successfully")
            except Exception as e:
                logger.error(f"Error persisting data: {str(e)}")
            
            # Calculate document count after adding
            after_count = self.collection.count()
            added_count = after_count - before_count
            
            logger.info(f"Document addition completed, current document total: {after_count}")
            logger.info(f"Actually added {added_count} documents")
            
            # If document count didn't change, record warning
            if added_count <= 0:
                logger.warning(
                    "Warning: Vector database document count did not increase, possibly duplicate IDs or addition failure"
                )
                # Return True, because this could be normal (all documents are duplicates)
                return True
            
            return True
        except Exception as e:
            logger.error(f"Error adding documents to vector database: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def search(
        self, 
        query_embedding: np.ndarray, 
        n_results: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ):
        """Search for relevant documents in the vector database.
        
        Args:
            query_embedding: Query vector embedding.
            n_results: Number of results to return.
            filter_criteria: Filter conditions.
            
        Returns:
            Dict: Dictionary containing search results.
        """
        try:
            logger.info(f"Executing vector search, requested result count: {n_results}")
            
            query_params = {
                "query_embeddings": [query_embedding.tolist()],
                "n_results": n_results
            }
            
            if filter_criteria:
                query_params["where"] = filter_criteria
                logger.info(f"Applied filter criteria: {filter_criteria}")
            
            # Get total document count in vector database
            total_docs = self.collection.count()
            logger.info(f"Total document count in vector database: {total_docs}")
            
            # If there are no documents, return empty result
            if total_docs == 0:
                logger.warning("Vector database has no documents, cannot execute search")
                return {
                    "documents": [[]],
                    "metadatas": [[]],
                    "distances": [[]]
                }
                
            results = self.collection.query(**query_params)
            
            # Record search results
            doc_count = len(results.get("documents", [[]])[0])
            logger.info(f"Search completed, found {doc_count} results")
            if doc_count > 0:
                logger.info(f"First result preview: {results['documents'][0][0][:100]}...")
            
            return results
        except Exception as e:
            logger.error(f"Error executing vector search: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def get_document_count(self):
        """Get the document count in the vector database.
        
        Returns:
            int: Document count.
        """
        try:
            count = self.collection.count()
            logger.info(f"Total document count in vector database: {count}")
            return count
        except Exception as e:
            logger.error(f"Error getting document count: {str(e)}")
            return 0
            
    def reset(self):
        """Reset the vector database (for testing and debugging).
        
        Returns:
            bool: Whether the operation was successful.
        """
        try:
            logger.info("Resetting vector database...")
            self.client.delete_collection("pdf_documents")
            self.collection = self.client.get_or_create_collection("pdf_documents")
            
            # Ensure data persistence
            if hasattr(self.client, "persist"):
                self.client.persist()
                
            logger.info("Vector database reset")
            return True
        except Exception as e:
            logger.error(f"Error resetting vector database: {str(e)}")
            return False
            
    def delete(self, filter: Dict[str, Any] = None, ids: List[str] = None):
        """Delete documents from the vector database.
        
        Args:
            filter: Filter condition, e.g. {"pdf_id": 1} will delete all documents with pdf_id of 1.
            ids: List of specific document IDs to delete.
            
        Returns:
            bool: Whether the operation was successful.
        """
        try:
            # Record document count before deleting
            before_count = self.collection.count()
            logger.info(f"Vector database document count before deleting: {before_count}")
            
            if filter:
                logger.info(f"Deleting documents based on filter: {filter}")
                # Use filter to get documents to delete
                # First query all documents that match the condition
                query_results = self.collection.get(where=filter)
                doc_ids = query_results.get("ids", [])
                
                if not doc_ids:
                    logger.warning(f"No documents found that match the condition: {filter}")
                    return True
                
                logger.info(f"Found {len(doc_ids)} documents that match deletion condition")
                
                # Delete in batches to avoid oversized requests
                batch_size = 100
                total_batches = (len(doc_ids) + batch_size - 1) // batch_size
                
                for i in range(0, len(doc_ids), batch_size):
                    end = min(i + batch_size, len(doc_ids))
                    batch_ids = doc_ids[i:end]
                    batch_num = i // batch_size + 1
                    
                    logger.info(f"Deleting batch {batch_num}/{total_batches}: {i}-{end}/{len(doc_ids)}")
                    self.collection.delete(ids=batch_ids)
            
            elif ids:
                logger.info(f"Deleting documents based on ID list, ID count: {len(ids)}")
                # Delete in batches to avoid oversized requests
                batch_size = 100
                total_batches = (len(ids) + batch_size - 1) // batch_size
                
                for i in range(0, len(ids), batch_size):
                    end = min(i + batch_size, len(ids))
                    batch_ids = ids[i:end]
                    batch_num = i // batch_size + 1
                    
                    logger.info(f"Deleting batch {batch_num}/{total_batches}: {i}-{end}/{len(ids)}")
                    self.collection.delete(ids=batch_ids)
            
            else:
                logger.warning("No filter or ID list provided, no deletion operation executed")
                return False
            
            # Ensure data persistence
            if hasattr(self.client, "persist"):
                self.client.persist()
                logger.info("Data persisted successfully")
                
            # Calculate document count after deleting
            after_count = self.collection.count()
            deleted_count = before_count - after_count
            
            logger.info(f"Document deletion completed, current document total: {after_count}")
            logger.info(f"Actually deleted {deleted_count} documents")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False