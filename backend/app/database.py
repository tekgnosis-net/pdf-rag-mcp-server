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
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create base class
Base = declarative_base()

# Create database engine and session
engine = create_engine(
    "sqlite:///./pdf_knowledge_base.db",
    connect_args={"check_same_thread": False, "timeout": 30}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: D401
    """Ensure SQLite uses WAL mode to reduce write contention."""
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