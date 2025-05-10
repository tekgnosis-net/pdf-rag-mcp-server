#!/usr/bin/env python

import sys
import os
from pathlib import Path
import asyncio
import argparse

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from app.vector_store import VectorStore
from app.pdf_processor import PDFProcessor
from app.database import SessionLocal, PDFDocument
from sentence_transformers import SentenceTransformer

async def test_vector_db():
    """测试向量数据库的查询功能"""
    # 1. 检查向量数据库中是否有数据
    vector_store = VectorStore()
    doc_count = vector_store.get_document_count()
    print(f"向量数据库中的文档数量: {doc_count}")
    
    if doc_count == 0:
        print("警告：向量数据库中没有文档，请先上传并处理PDF文件。")
        return
    
    # 2. 测试查询
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # 测试几个不同的查询
    test_queries = [
        "这是一个测试查询",
        "MCP协议是什么",
        "PDF知识库的功能",
        "向量数据库如何工作"
    ]
    
    for query in test_queries:
        print(f"\n执行查询: '{query}'")
        query_embedding = embedding_model.encode(query)
        results = vector_store.search(query_embedding, n_results=3)
        
        # 打印结果
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])
        
        if not documents[0]:
            print("  没有找到相关文档")
            continue
        
        print(f"  找到 {len(documents[0])} 条结果:")
        for i, (doc, meta, dist) in enumerate(zip(documents[0], metadatas[0], distances[0])):
            doc_preview = doc[:100] + "..." if len(doc) > 100 else doc
            print(f"  {i+1}. 相似度: {1-dist:.4f}, PDF ID: {meta.get('pdf_id')}, Chunk ID: {meta.get('chunk_id')}")
            print(f"     文本预览: {doc_preview}")

async def reset_vector_db():
    """重置向量数据库"""
    vector_store = VectorStore()
    if vector_store.reset():
        print("向量数据库已成功重置")
    else:
        print("重置向量数据库失败")

async def list_documents():
    """列出所有PDF文档"""
    db = SessionLocal()
    try:
        docs = db.query(PDFDocument).all()
        if not docs:
            print("没有找到任何PDF文档")
            return
        
        print(f"找到 {len(docs)} 个PDF文档:")
        for doc in docs:
            status = "已处理" if doc.processed else "处理中" if doc.processing else "未处理"
            error = f" (错误: {doc.error})" if doc.error else ""
            print(f"  ID: {doc.id}, 文件名: {doc.filename}, 状态: {status}{error}")
    finally:
        db.close()

async def process_document(doc_id=None):
    """手动处理指定的PDF文档"""
    db = SessionLocal()
    try:
        if doc_id is None:
            # 获取第一个未处理的文档
            doc = db.query(PDFDocument).filter(
                PDFDocument.processed == False, 
                PDFDocument.processing == False
            ).first()
        else:
            # 获取指定ID的文档
            doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()
        
        if not doc:
            print("没有找到需要处理的PDF文档")
            return
        
        print(f"开始处理文档: {doc.filename} (ID: {doc.id})")
        
        # 开始处理
        processor = PDFProcessor()
        result = await processor.process_pdf(doc.id, doc.file_path, doc.filename)
        
        if result:
            print(f"文档处理成功: {doc.filename}")
        else:
            print(f"文档处理失败: {doc.filename}")
            
    finally:
        db.close()

async def main():
    parser = argparse.ArgumentParser(description="PDF知识库测试工具")
    parser.add_argument("--reset", action="store_true", help="重置向量数据库")
    parser.add_argument("--list", action="store_true", help="列出所有PDF文档")
    parser.add_argument("--process", type=int, nargs="?", const=0, help="处理指定ID的PDF文档，不指定ID则处理第一个未处理的文档")
    parser.add_argument("--query", action="store_true", help="测试向量数据库查询")
    
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