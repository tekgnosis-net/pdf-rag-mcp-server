"""数据库模块。

该模块提供数据库连接和ORM模型定义，用于管理PDF文档的元数据。
"""

# 标准库导入
import datetime

# 第三方库导入
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

# 创建基础类
Base = declarative_base()

# 创建数据库引擎和会话
engine = create_engine(
    "sqlite:///./pdf_knowledge_base.db",
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class PDFDocument(Base):
    """PDF文档数据模型，用于存储文档的元数据和处理状态。"""
    
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


# 创建数据库表
Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话。
    
    Yields:
        Session: 数据库会话对象。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  