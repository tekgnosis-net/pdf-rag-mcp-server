"""Database Module.

This module provides database connections and ORM model definitions for managing PDF document metadata.
"""

# Standard library imports
import datetime

# Third-party library imports
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create base class
Base = declarative_base()

# Create database engine and session
engine = create_engine(
    "sqlite:///./pdf_knowledge_base.db",
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class PDFDocument(Base):
    """PDF document data model, used to store document metadata and processing status."""
    
    __tablename__ = "pdf_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    file_path = Column(String)
    file_size = Column(Integer)  # in bytes
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed = Column(Boolean, default=False)
    processing = Column(Boolean, default=False)
    page_count = Column(Integer, default=0)
    chunks_count = Column(Integer, default=0)
    progress = Column(Float, default=0.0)  # 0 to 100
    error = Column(String, nullable=True)


# Create database tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session.
    
    Yields:
        Session: Database session object.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  