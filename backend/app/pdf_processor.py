import fitz  # PyMuPDF  
from langchain.text_splitter import RecursiveCharacterTextSplitter  
import os  
import asyncio  
from sentence_transformers import SentenceTransformer  
from app.database import SessionLocal, PDFDocument  
from app.vector_store import VectorStore  
import time  
from typing import Dict, List, Optional  
import logging
import traceback

# 配置日志记录  
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("pdf_processor")

# 全局变量用于跟踪处理进度  
processing_status: Dict[str, Dict] = {}  

class PDFProcessor:  
    def __init__(self):  
        self.text_splitter = RecursiveCharacterTextSplitter(  
            chunk_size=1000,  
            chunk_overlap=200,  
            length_function=len,  
        )  
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  
        self.vector_store = VectorStore()  
        
    async def process_pdf(self, pdf_id: int, pdf_path: str, filename: str):  
        """异步处理PDF文件"""  
        logger.info(f"开始处理PDF: {filename}，ID: {pdf_id}")
        db = SessionLocal()  
        pdf_doc = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()  
        
        if not pdf_doc:  
            logger.error(f"无法找到PDF文档记录，ID: {pdf_id}")
            db.close()  
            return False  
        
        # 标记为处理中  
        pdf_doc.processing = True  
        processing_status[filename] = {"progress": 0, "status": "Processing", "page_current": 0}  
        db.commit()  
        logger.info(f"PDF处理状态更新为处理中")
        
        try:  
            # 检查文件是否存在
            if not os.path.exists(pdf_path):
                error_msg = f"找不到PDF文件: {pdf_path}"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
                return False
                
            # 打开PDF  
            logger.info(f"打开PDF文件: {pdf_path}")
            doc = fitz.open(pdf_path)  
            pdf_doc.page_count = len(doc)  
            db.commit()  
            logger.info(f"PDF页数: {len(doc)}")
            
            all_texts = []  
            # 处理每一页  
            for i, page in enumerate(doc):  
                try:
                    text = page.get_text()  
                    all_texts.append(text)  
                    
                    # 更新进度  
                    progress = (i + 1) / len(doc) * 50  # 前50%是PDF解析  
                    pdf_doc.progress = progress  
                    processing_status[filename] = {  
                        "progress": progress,   
                        "status": "Parsing PDF",   
                        "page_current": i + 1  
                    }  
                    db.commit()  
                    
                    logger.info(f"处理PDF页面 {i+1}/{len(doc)}，进度 {progress:.2f}%")
                    
                    # 模拟耗时操作，并允许其他协程运行  
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"处理页面 {i+1} 时出错: {str(e)}")
            
            # 分块  
            logger.info(f"PDF解析完成，开始分块")
            chunks = self.text_splitter.split_text("\n".join(all_texts))  
            pdf_doc.chunks_count = len(chunks)  
            processing_status[filename]["status"] = "Generating embeddings"  
            db.commit()  
            logger.info(f"文本已分为 {len(chunks)} 个块")
            
            if not chunks:
                error_msg = "PDF解析后没有文本内容"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
                return False
            
            # 生成嵌入向量 - 这是计算密集型任务  
            logger.info("开始生成嵌入向量")
            embeddings = self.embedding_model.encode(chunks)  
            logger.info("嵌入向量生成完成")
            
            # 更新进度至75%  
            pdf_doc.progress = 75  
            processing_status[filename]["progress"] = 75  
            processing_status[filename]["status"] = "Storing in vector database"  
            db.commit()  
            
            # 存储到向量数据库  
            logger.info("开始存储到向量数据库")
            metadatas = [{"source": filename, "chunk_id": i, "pdf_id": pdf_id} for i, _ in enumerate(chunks)]  
            storage_success = self.vector_store.add_documents(chunks, embeddings, metadatas)  
            
            if not storage_success:
                error_msg = "存储到向量数据库失败"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                processing_status[filename]["status"] = f"Error: {error_msg}"
                db.commit()
                return False
            
            # 完成  
            pdf_doc.progress = 100  
            pdf_doc.processed = True  
            pdf_doc.processing = False  
            processing_status[filename]["progress"] = 100  
            processing_status[filename]["status"] = "Completed"  
            db.commit()  
            logger.info(f"PDF处理完成: {filename}")
            
            return True  
            
        except Exception as e:  
            # 详细的错误记录
            err_msg = f"处理PDF时出错: {str(e)}"
            logger.error(err_msg)
            logger.error(traceback.format_exc())
            
            # 错误处理  
            pdf_doc.error = str(e)  
            pdf_doc.processing = False  
            processing_status[filename]["status"] = f"Error: {str(e)}"  
            db.commit()  
            return False  
        finally:  
            db.close()  
    
    def get_processing_status(self, filename: Optional[str] = None):  
        """获取处理状态"""  
        if filename:  
            return processing_status.get(filename, {"progress": 0, "status": "Not started"})  
        return processing_status