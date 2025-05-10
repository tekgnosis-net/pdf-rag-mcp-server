from sqlalchemy import Column, Integer, String, Float, Boolean, create_engine, DateTime  
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import sessionmaker  
import datetime  

Base = declarative_base()  
engine = create_engine("sqlite:///./pdf_knowledge_base.db", connect_args={"check_same_thread": False})  
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)  

class PDFDocument(Base):  
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
    db = SessionLocal()  
    try:  
        yield db  
    finally:  
        db.close()  