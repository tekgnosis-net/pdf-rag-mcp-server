import chromadb  
from chromadb.config import Settings  
from typing import List, Dict, Any, Optional  
import os  
import numpy as np  
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vector_store")

class VectorStore:  
    def __init__(self, persist_directory=None):  
        # 使用绝对路径
        if persist_directory is None:
            # 获取当前文件的绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 回退到backend目录
            backend_dir = os.path.dirname(current_dir)
            persist_directory = os.path.join(backend_dir, "chroma_db")
        
        # 将相对路径转换为绝对路径
        persist_directory = os.path.abspath(persist_directory)
        
        logger.info(f"初始化向量数据库，持久化目录: {persist_directory}")
        
        # 确保目录存在  
        os.makedirs(persist_directory, exist_ok=True)  
        
        try:
            # 使用持久化配置
            self.client = chromadb.PersistentClient(
                path=persist_directory
            )
            self.collection = self.client.get_or_create_collection("pdf_documents")
            logger.info(f"成功连接向量数据库，当前文档数量: {self.collection.count()}")
        except Exception as e:
            logger.error(f"连接向量数据库时出错: {str(e)}")
            raise
    
    def add_documents(self, chunks: List[str], embeddings: np.ndarray, metadatas: Optional[List[Dict[str, Any]]] = None):  
        """添加文档到向量数据库"""  
        try:
            # 为每个文档生成唯一ID  
            ids = [f"doc_{meta['pdf_id']}_{meta['chunk_id']}" for meta in metadatas]  
            
            logger.info(f"正在添加 {len(chunks)} 个文档到向量数据库")
            if chunks:
                logger.info(f"示例文档: {chunks[0][:100]}...")
                logger.info(f"示例元数据: {metadatas[0]}")
            
            # 分批添加，避免过大的请求
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                end = min(i + batch_size, len(chunks))
                logger.info(f"添加批次 {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}: {i}-{end}/{len(chunks)}")
                
                batch_chunks = chunks[i:end]
                batch_embeddings = embeddings[i:end].tolist()
                batch_metadatas = metadatas[i:end]
                batch_ids = ids[i:end]
                
                self.collection.add(  
                    documents=batch_chunks,  
                    embeddings=batch_embeddings,  
                    metadatas=batch_metadatas,  
                    ids=batch_ids  
                )
            
            # 确保数据持久化
            if hasattr(self.client, "persist"):
                self.client.persist()
                
            doc_count = self.collection.count()
            logger.info(f"文档添加成功，当前文档总数: {doc_count}")
            return True
        except Exception as e:
            logger.error(f"添加文档到向量数据库时出错: {str(e)}")
            return False
    
    def search(self, query_embedding: np.ndarray, n_results: int = 5,   
               filter_criteria: Optional[Dict[str, Any]] = None):  
        """在向量数据库中搜索相关文档"""  
        try:
            logger.info(f"执行向量搜索，请求结果数量: {n_results}")
            
            query_params = {  
                "query_embeddings": [query_embedding.tolist()],  
                "n_results": n_results  
            }  
            
            if filter_criteria:  
                query_params["where"] = filter_criteria  
                logger.info(f"应用过滤条件: {filter_criteria}")
            
            # 获取向量数据库中的总文档数
            total_docs = self.collection.count()
            logger.info(f"向量数据库中的总文档数量: {total_docs}")
            
            # 如果没有文档，直接返回空结果
            if total_docs == 0:
                logger.warning("向量数据库中没有文档，无法执行搜索")
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
                
            results = self.collection.query(**query_params)  
            
            # 记录搜索结果
            doc_count = len(results.get("documents", [[]])[0])
            logger.info(f"搜索完成，找到 {doc_count} 条结果")
            if doc_count > 0:
                logger.info(f"第一条结果预览: {results['documents'][0][0][:100]}...")
            
            return results
        except Exception as e:
            logger.error(f"向量搜索时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def get_document_count(self):  
        """获取向量数据库中的文档数量"""  
        try:
            count = self.collection.count()
            logger.info(f"向量数据库中的文档数量: {count}")
            return count
        except Exception as e:
            logger.error(f"获取文档数量时出错: {str(e)}")
            return 0
            
    def reset(self):
        """清空向量数据库（用于测试和调试）"""
        try:
            logger.info("正在重置向量数据库...")
            self.client.delete_collection("pdf_documents")
            self.collection = self.client.get_or_create_collection("pdf_documents")
            
            # 确保数据持久化
            if hasattr(self.client, "persist"):
                self.client.persist()
                
            logger.info("向量数据库已重置")
            return True
        except Exception as e:
            logger.error(f"重置向量数据库时出错: {str(e)}")
            return False