"""PDF处理模块。

该模块负责解析PDF文档，提取文本内容，并生成向量嵌入用于存储到向量数据库中。
"""

# 标准库导入
import asyncio
import logging
import os
import time
import traceback
import uuid
from typing import Dict, List, Optional

# 第三方库导入
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

# 本地应用/库导入
from app.database import PDFDocument, SessionLocal
from app.vector_store import VectorStore

# 配置日志记录
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pdf_processor")

# 全局变量用于跟踪处理进度
PROCESSING_STATUS: Dict[str, Dict] = {}


class PDFProcessor:
    """PDF处理器类，负责解析和处理PDF文档。"""
    
    def __init__(self):
        """初始化PDF处理器。"""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.vector_store = VectorStore()
        
    async def process_pdf(self, pdf_id: int, pdf_path: str, filename: str):
        """异步处理PDF文件。
        
        Args:
            pdf_id: PDF文档的ID。
            pdf_path: PDF文件的路径。
            filename: 原始文件名。
            
        Returns:
            bool: 处理是否成功。
        """
        logger.info(f"开始处理PDF: {filename}，ID: {pdf_id}")
        db = SessionLocal()
        pdf_doc = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
        
        if not pdf_doc:
            logger.error(f"无法找到PDF文档记录，ID: {pdf_id}")
            db.close()
            return False
        
        # 标记为处理中
        pdf_doc.processing = True
        PROCESSING_STATUS[filename] = {
            "progress": 0,
            "status": "Processing",
            "page_current": 0
        }
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
            page_numbers = []  # 存储每个文本块对应的页码
            
            # 处理每一页
            for i, page in enumerate(doc):
                try:
                    text = page.get_text()
                    # 只添加非空文本
                    if text.strip():
                        all_texts.append(text)
                        page_numbers.append(i + 1)  # 存储页码
                    
                    # 更新进度
                    progress = (i + 1) / len(doc) * 50  # 前50%是PDF解析
                    pdf_doc.progress = progress
                    PROCESSING_STATUS[filename] = {
                        "progress": progress,
                        "status": "Parsing PDF",
                        "page_current": i + 1
                    }
                    db.commit()
                    
                    logger.info(
                        f"处理PDF页面 {i+1}/{len(doc)}，进度 {progress:.2f}%"
                    )
                    
                    # 模拟耗时操作，并允许其他协程运行
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"处理页面 {i+1} 时出错: {str(e)}")
            
            # 分块
            logger.info(f"PDF解析完成，开始分块")
            joined_text = "\n".join(all_texts)
            
            # 检查是否有有效文本
            if not joined_text.strip():
                error_msg = "PDF解析后没有有效文本内容"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                db.commit()
                return False
                
            chunks = self.text_splitter.split_text(joined_text)
            pdf_doc.chunks_count = len(chunks)
            PROCESSING_STATUS[filename]["status"] = "Generating embeddings"
            db.commit()
            logger.info(f"文本已分为 {len(chunks)} 个块")
            
            if not chunks:
                error_msg = "文本分块后没有内容"
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
            PROCESSING_STATUS[filename]["progress"] = 75
            PROCESSING_STATUS[filename]["status"] = "Storing in vector database"
            db.commit()
            
            # 存储到向量数据库
            logger.info("开始存储到向量数据库")
            
            # 生成处理批次ID (防止重复)
            batch_id = str(uuid.uuid4())[:8]
            
            # 创建元数据，包含更多有用信息
            metadatas = []
            for i, chunk in enumerate(chunks):
                # 计算该分块可能来自的页码范围（简化估计）
                page_index = min(i, len(page_numbers) - 1) if page_numbers else 0
                page_num = page_numbers[page_index] if page_numbers else 0
                
                # 创建包含更多信息的元数据
                metadata = {
                    "source": filename,
                    "chunk_id": f"{batch_id}_{i}",  # 唯一的chunk_id
                    "pdf_id": pdf_id,
                    "page": page_num,
                    "batch": batch_id,
                    "index": i,
                    "length": len(chunk),
                    "timestamp": time.time()
                }
                metadatas.append(metadata)
            
            # 记录元数据示例
            if metadatas:
                logger.info(f"元数据示例: {metadatas[0]}")
            
            # 添加到向量数据库
            storage_success = self.vector_store.add_documents(
                chunks, embeddings, metadatas
            )
            
            if not storage_success:
                error_msg = "存储到向量数据库失败"
                logger.error(error_msg)
                pdf_doc.error = error_msg
                pdf_doc.processing = False
                PROCESSING_STATUS[filename]["status"] = f"Error: {error_msg}"
                db.commit()
                return False
            
            # 完成
            pdf_doc.progress = 100
            pdf_doc.processed = True
            pdf_doc.processing = False
            PROCESSING_STATUS[filename]["progress"] = 100
            PROCESSING_STATUS[filename]["status"] = "Completed"
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
            PROCESSING_STATUS[filename]["status"] = f"Error: {str(e)}"
            db.commit()
            return False
        finally:
            db.close()
    
    def get_processing_status(self, filename: Optional[str] = None):
        """获取处理状态。
        
        Args:
            filename: 文件名，如果为None则返回所有文件的状态。
            
        Returns:
            Dict: 处理状态信息。
        """
        if filename:
            return PROCESSING_STATUS.get(
                filename, {"progress": 0, "status": "Not started"}
            )
        return PROCESSING_STATUS