"""Database Module.

This module provides database connections and ORM model definitions for managing PDF document metadata.
"""

# Standard library imports
import datetime
import os

# Third-party library imports
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create base class
Base = declarative_base()

# Database configuration sourced from environment for container persistence
_db_url = os.getenv("PDF_RAG_DB_URL")
_db_path = os.getenv("PDF_RAG_DB_PATH", "./pdf_knowledge_base.db")

if _db_url:
    engine_url = _db_url
else:
    if _db_path.startswith("sqlite://"):
        engine_url = _db_path
    else:
        if os.path.dirname(_db_path):
            os.makedirs(os.path.dirname(_db_path), exist_ok=True)
        engine_url = f"sqlite:///{_db_path}"

connect_args = {"check_same_thread": False, "timeout": 30} if engine_url.startswith("sqlite") else {}

# Create database engine and session
engine = create_engine(
    engine_url,
    connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: D401
    """Ensure SQLite uses WAL mode to reduce write contention."""
    if not engine_url.startswith("sqlite"):
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
    finally:
        cursor.close()


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