#!/usr/bin/env python

import sys
import os
from pathlib import Path
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
import numpy as np
import logging
from sentence_transformers import SentenceTransformer
import time

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal, PDFDocument
from app.vector_store import VectorStore

# 配置日志记录
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("process_pdf_simple")

def process_pdf(pdf_id):
    """处理指定ID的PDF文件"""
    logger.info(f"开始处理PDF，ID: {pdf_id}")
    
    # 获取数据库连接
    db = SessionLocal()
    try:
        # 查找PDF记录
        pdf_doc = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
        if not pdf_doc:
            logger.error(f"找不到ID为 {pdf_id} 的PDF记录")
            return False
            
        # 显示PDF信息
        logger.info(f"PDF文件: {pdf_doc.filename}")
        logger.info(f"文件路径: {pdf_doc.file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(pdf_doc.file_path):
            logger.error(f"找不到PDF文件: {pdf_doc.file_path}")
            pdf_doc.error = f"找不到PDF文件: {pdf_doc.file_path}"
            db.commit()
            return False
        
        # 标记为处理中
        pdf_doc.processing = True
        pdf_doc.progress = 0.0
        pdf_doc.error = None
        db.commit()
        
        start_time = time.time()
        
        # 1. 打开并解析PDF
        logger.info("1. 打开并解析PDF...")
        doc = fitz.open(pdf_doc.file_path)
        pdf_doc.page_count = len(doc)
        db.commit()
        
        all_texts = []
        for i, page in enumerate(doc):
            text = page.get_text()
            all_texts.append(text)
            
            # 更新进度
            progress = (i + 1) / len(doc) * 30  # 前30%是PDF解析
            pdf_doc.progress = progress
            db.commit()
            
            if (i + 1) % 50 == 0 or i == 0 or i == len(doc) - 1:
                logger.info(f"  处理页面 {i+1}/{len(doc)}, 进度: {progress:.1f}%")
        
        # 2. 文本分块
        logger.info("2. 文本分块...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        pdf_text = "\n".join(all_texts)
        chunks = text_splitter.split_text(pdf_text)
        pdf_doc.chunks_count = len(chunks)
        pdf_doc.progress = 40.0
        db.commit()
        
        logger.info(f"  共生成 {len(chunks)} 个文本块")
        if len(chunks) > 0:
            logger.info(f"  第一个文本块示例: {chunks[0][:100]}...")
        
        if not chunks:
            logger.error("没有从PDF中提取到文本内容")
            pdf_doc.error = "没有从PDF中提取到文本内容"
            pdf_doc.processing = False
            db.commit()
            return False
        
        # 3. 生成嵌入向量
        logger.info("3. 生成嵌入向量...")
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        pdf_doc.progress = 50.0
        db.commit()
        
        # 分批处理，避免内存占用过大
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            logger.info(f"  处理批次 {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}, "
                       f"{i}-{min(i+batch_size, len(chunks))}/{len(chunks)}")
            
            batch_embeddings = embedding_model.encode(batch)
            all_embeddings.append(batch_embeddings)
            
            # 更新进度，从50%到80%
            progress = 50 + (i + len(batch)) / len(chunks) * 30
            pdf_doc.progress = progress
            db.commit()
        
        # 合并所有嵌入向量
        embeddings = np.vstack(all_embeddings) if len(all_embeddings) > 1 else all_embeddings[0]
        logger.info(f"  生成的嵌入向量形状: {embeddings.shape}")
        
        # 4. 存储到向量数据库
        logger.info("4. 存储到向量数据库...")
        vector_store = VectorStore()
        
        # 准备元数据
        metadatas = [
            {
                "source": pdf_doc.filename, 
                "chunk_id": i, 
                "pdf_id": pdf_doc.id,
                "page": f"Pages {i//3}-{min((i//3)+3, pdf_doc.page_count)}"  # 估计页码范围
            } 
            for i in range(len(chunks))
        ]
        
        # 添加到向量数据库
        success = vector_store.add_documents(chunks, embeddings, metadatas)
        
        if not success:
            logger.error("添加到向量数据库失败")
            pdf_doc.error = "添加到向量数据库失败"
            pdf_doc.processing = False
            db.commit()
            return False
        
        # 5. 更新处理状态
        pdf_doc.progress = 100.0
        pdf_doc.processed = True
        pdf_doc.processing = False
        db.commit()
        
        elapsed_time = time.time() - start_time
        logger.info(f"PDF处理完成，耗时: {elapsed_time:.1f}秒")
        
        # 测试向量数据库查询
        logger.info("5. 测试向量数据库查询...")
        test_query = "金融机器学习"
        query_embedding = embedding_model.encode(test_query)
        results = vector_store.search(query_embedding, n_results=2)
        
        # 检查结果
        doc_count = len(results.get("documents", [[]])[0])
        logger.info(f"  查询 '{test_query}' 找到 {doc_count} 条结果")
        
        return True
        
    except Exception as e:
        import traceback
        logger.error(f"处理PDF时出错: {str(e)}")
        logger.error(traceback.format_exc())
        
        if 'pdf_doc' in locals():
            pdf_doc.error = str(e)
            pdf_doc.processing = False
            db.commit()
        
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="简化版PDF处理工具")
    parser.add_argument("pdf_id", type=int, help="要处理的PDF文档ID")
    
    args = parser.parse_args()
    
    success = process_pdf(args.pdf_id)
    
    if success:
        logger.info("处理成功!")
        sys.exit(0)
    else:
        logger.error("处理失败!")
        sys.exit(1) 