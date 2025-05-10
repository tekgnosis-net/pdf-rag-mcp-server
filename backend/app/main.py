from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware  
from sqlalchemy.orm import Session  
import os  
import uuid  
import asyncio  
import logging

from app.database import get_db, PDFDocument, SessionLocal
from app.pdf_processor import PDFProcessor, processing_status  
from app.websocket import manager  
from app.vector_store import VectorStore  
from sentence_transformers import SentenceTransformer  

from fastapi_mcp import FastApiMCP

# 初始化应用  
app = FastAPI(title="MCP PDF Knowledge Base")  
mcp_app = FastAPI(title="MCP PDF Knowledge MCP Server")  


pdf_processor = PDFProcessor()  
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  
vector_store = VectorStore()  
# 添加日志记录
logger = logging.getLogger("main")
logger.info(f"初始化应用，向量数据库文档数量: {vector_store.get_document_count()}")

# 配置CORS  
app.add_middleware(  
    CORSMiddleware,  
    allow_origins=["*"],  # 在生产环境中，应该限制为前端域名  
    allow_credentials=True,  
    allow_methods=["*"],  
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)  

# 确保上传目录存在  
os.makedirs("./uploads", exist_ok=True)  

# 存储活跃的MCP会话
active_sessions = {}

@app.post("/api/upload")  
async def upload_pdf(background_tasks: BackgroundTasks,   
                     file: UploadFile = File(...),   
                     db: Session = Depends(get_db)):  
    """上传PDF文件并处理"""  
    # 验证文件类型  
    if not file.filename.lower().endswith('.pdf'):  
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")  
    
    # 检查文件是否已存在  
    existing_doc = db.query(PDFDocument).filter(PDFDocument.filename == file.filename).first()  
    if existing_doc:  
        if existing_doc.processed:  
            return {"message": "File already processed", "id": existing_doc.id}  
        elif existing_doc.processing:  
            return {"message": "File is currently being processed", "id": existing_doc.id}  
    
    # 生成唯一的文件名  
    unique_filename = f"{uuid.uuid4()}_{file.filename}"  
    file_path = f"./uploads/{unique_filename}"  
    
    # 保存文件  
    with open(file_path, "wb") as f:  
        file_content = await file.read()  
        f.write(file_content)  
        file_size = len(file_content)  
    
    # 创建数据库记录  
    pdf_doc = PDFDocument(  
        filename=file.filename,  
        file_path=file_path,  
        file_size=file_size,  
        processed=False,  
        processing=True,  
        progress=0.0  
    )  
    db.add(pdf_doc)  
    db.commit()  
    db.refresh(pdf_doc)  
    
    # 在后台处理PDF  
    processing_status[file.filename] = {"progress": 0, "status": "Queued"}  
    background_tasks.add_task(process_pdf_background, pdf_doc.id, file_path, file.filename)  
    
    return {  
        "message": "PDF uploaded and queued for processing",  
        "id": pdf_doc.id,  
        "filename": file.filename  
    }  

async def process_pdf_background(pdf_id: int, file_path: str, filename: str):  
    """后台处理PDF的异步函数"""  
    await pdf_processor.process_pdf(pdf_id, file_path, filename)  
    # 处理完成后广播状态更新  
    await manager.broadcast({  
        "type": "processing_update",  
        "filename": filename,  
        "status": processing_status.get(filename, {})  
    })  

@app.get("/api/documents")  
async def get_documents(db: Session = Depends(get_db)):  
    """获取所有PDF文档的状态"""  
    docs = db.query(PDFDocument).all()  
    return [  
        {  
            "id": doc.id,  
            "filename": doc.filename,  
            "uploaded_at": doc.uploaded_at,  
            "file_size": doc.file_size,  
            "processed": doc.processed,  
            "processing": doc.processing,  
            "page_count": doc.page_count,  
            "chunks_count": doc.chunks_count,  
            "progress": doc.progress,  
            "error": doc.error  
        }  
        for doc in docs  
    ]  

@app.get("/api/documents/{doc_id}")  
async def get_document(doc_id: int, db: Session = Depends(get_db)):  
    """获取单个PDF文档的详细信息"""  
    doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()  
    if not doc:  
        raise HTTPException(status_code=404, detail="Document not found")  
    
    return {  
        "id": doc.id,  
        "filename": doc.filename,  
        "uploaded_at": doc.uploaded_at,  
        "file_size": doc.file_size,  
        "processed": doc.processed,  
        "processing": doc.processing,  
        "page_count": doc.page_count,  
        "chunks_count": doc.chunks_count,  
        "progress": doc.progress,  
        "error": doc.error,  
        "status": processing_status.get(doc.filename, {"progress": doc.progress, "status": "Unknown"})  
    }  

@app.delete("/api/documents/{doc_id}")  
async def delete_document(doc_id: int, db: Session = Depends(get_db)):  
    """删除PDF文档"""  
    doc = db.query(PDFDocument).filter(PDFDocument.id == doc_id).first()  
    if not doc:  
        raise HTTPException(status_code=404, detail="Document not found")  
    
    # 如果正在处理，不允许删除  
    if doc.processing:  
        raise HTTPException(status_code=400, detail="Cannot delete document while it's being processed")  
    
    # 删除文件  
    if os.path.exists(doc.file_path):  
        os.remove(doc.file_path)  
    
    # 从数据库删除记录  
    db.delete(doc)  
    db.commit()  
    
    # TODO: 从向量数据库删除相关文档（未实现）  
    
    return {"message": f"Document {doc.filename} deleted successfully"}  

@app.websocket("/ws")  
async def websocket_endpoint(websocket: WebSocket):  
    """WebSocket连接处理实时更新"""  
    await manager.connect(websocket)  
    try:  
        # 初始发送所有当前状态  
        await websocket.send_json({  
            "type": "initial_status",  
            "status": processing_status  
        })  
        
        # 保持连接活跃  
        while True:  
            data = await websocket.receive_text()  
            # 这里可以处理来自客户端的消息  
            await asyncio.sleep(1)  
            
    except WebSocketDisconnect:  
        manager.disconnect(websocket)  



@mcp_app.get("/")  
async def read_root():  
    return {
        "message": "MCP PDF Knowledge Base API is running",
        "description": "PDF知识库服务，支持MCP协议集成",
        "endpoints": {
            "api": "/api/query",
            "mcp": {
                "legacy": "/mcp/v1",
                "jsonrpc": "/jsonrpc",
                "sse": "/sse",
                "fastmcp": "/fastmcp"
            },
            "documents": "/api/documents",
            "websocket": "/ws"
        },
        "version": "1.1.0",
        "documentation": "访问 /docs 获取API文档"
    }  

@mcp_app.get("/query")  
async def query_knowledge_base(query: str):  
    """查询知识库，优化后的MCP兼容接口"""
    request_id = str(uuid.uuid4())
    logger.info(f"接收到查询请求: {query}")
    
    # 生成查询嵌入并搜索  
    query_embedding = embedding_model.encode(query)  
    results = vector_store.search(query_embedding, n_results=5)  
    
    # 提取结果  
    documents = results.get("documents", [[]])[0]  
    metadatas = results.get("metadatas", [[]])[0]  

    db = SessionLocal()
    
    # 没有结果的情况
    if not documents:
        logger.warning(f"查询 '{query}' 没有找到结果")
        
        if is_mcp_request:
            return {
                "jsonrpc": "2.0",
                "result": {"content": "没有找到与您的问题相关的信息。请尝试使用不同的关键词查询。"},
                "id": request_id
            }
        else:
            return {"query": query, "results": []}
    
    # MCP响应格式
    context_parts = []
    
    for doc, meta in zip(documents, metadatas):
        pdf_id = meta.get("pdf_id")
        
        if pdf_id:
            pdf_doc = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
            if pdf_doc:
                source = pdf_doc.filename
        
        page_info = f" (页码: {meta.get('page')})" if meta.get('page') else ""
        context_parts.append(f"{page_info}\n\n{doc}")
    
    return "\n\n---\n\n".join(context_parts)


mcp = FastApiMCP(mcp_app)
mcp.mount()

# 启动服务  
if __name__ == "__main__":
    import uvicorn
    import threading

        # 在单独的线程中启动指标服务
    def run_metrics():
        uvicorn.run(mcp_app, host="0.0.0.0", port=7800)
    
    # 启动指标服务线程
    metrics_thread = threading.Thread(target=run_metrics)
    metrics_thread.daemon = True
    metrics_thread.start()

    # 在主线程中启动 FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)
