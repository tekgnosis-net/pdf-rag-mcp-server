#!/usr/bin/env python

import sys
import os
from pathlib import Path
import traceback

# 设置项目路径
project_path = Path(__file__).parent
if str(project_path) not in sys.path:
    sys.path.insert(0, str(project_path))

print(f"Python版本: {sys.version}")
print(f"当前工作目录: {os.getcwd()}")
print(f"系统路径: {sys.path}")

try:
    print("\n1. 导入基础依赖")
    from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Request  
    from fastapi.middleware.cors import CORSMiddleware  
    from fastapi.staticfiles import StaticFiles  
    from fastapi.responses import StreamingResponse
    from sqlalchemy.orm import Session  
    import uuid  
    import asyncio  
    import json  
    import time
    import logging
    print("基础依赖导入成功")
except Exception as e:
    print(f"导入基础依赖失败: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n2. 导入应用模块")
    from app.database import get_db, PDFDocument  
    print("数据库模块导入成功")
    
    from app.pdf_processor import PDFProcessor, processing_status  
    print("PDF处理器模块导入成功")
    
    from app.websocket import manager  
    print("WebSocket管理器模块导入成功")
    
    from app.vector_store import VectorStore  
    print("向量存储模块导入成功")
    
    from sentence_transformers import SentenceTransformer  
    print("文本嵌入模型导入成功")
except Exception as e:
    print(f"导入应用模块失败: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n3. 初始化应用组件")
    # 初始化日志
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("debug_main")
    print("日志初始化成功")
    
    # 初始化FastAPI应用
    app = FastAPI(title="MCP PDF Knowledge Base Debug")  
    print("FastAPI应用初始化成功")
    
    # 初始化PDF处理器
    pdf_processor = PDFProcessor()  
    print("PDF处理器初始化成功")
    
    # 初始化嵌入模型
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  
    print("嵌入模型初始化成功")
    
    # 初始化向量存储
    vector_store = VectorStore()  
    print(f"向量存储初始化成功，文档数量: {vector_store.get_document_count()}")
    
    # 确保目录存在
    os.makedirs("./uploads", exist_ok=True)  
    os.makedirs("./static", exist_ok=True)  
    print("目录创建成功")
    
    # 配置CORS
    app.add_middleware(  
        CORSMiddleware,  
        allow_origins=["*"],  
        allow_credentials=True,  
        allow_methods=["*"],  
        allow_headers=["*"],  
    )  
    print("CORS配置成功")
    
    # 挂载静态文件目录
    app.mount("/static", StaticFiles(directory="static"), name="static")  
    print("静态文件目录挂载成功")
    
    print("所有组件初始化成功")
except Exception as e:
    print(f"初始化应用组件失败: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n调试完成，应用初始化成功！")

# 如果需要，可以尝试启动应用
if __name__ == "__main__":
    import uvicorn
    
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        print("\n启动FastAPI应用...")
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False) 