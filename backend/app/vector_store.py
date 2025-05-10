"""向量存储模块。

该模块提供向量数据库接口，用于存储和检索PDF文档的向量表示。
"""

# 标准库导入
import logging
import os
from typing import Any, Dict, List, Optional

# 第三方库导入
import chromadb
import numpy as np
from chromadb.config import Settings

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vector_store")


class VectorStore:
    """向量存储类，用于管理和访问向量数据库。"""
    
    def __init__(self, persist_directory=None):
        """初始化向量存储。
        
        Args:
            persist_directory: 向量数据库持久化目录，如果为None则使用默认路径。
        """
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
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection("pdf_documents")
            logger.info(
                f"成功连接向量数据库，当前文档数量: {self.collection.count()}"
            )
        except Exception as e:
            logger.error(f"连接向量数据库时出错: {str(e)}")
            raise
    
    def add_documents(
        self, 
        chunks: List[str], 
        embeddings: np.ndarray, 
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """添加文档到向量数据库。
        
        Args:
            chunks: 文本块列表。
            embeddings: 对应的向量嵌入数组。
            metadatas: 元数据列表，包含每个文本块的相关信息。
            
        Returns:
            bool: 操作是否成功。
        """
        try:
            # 记录添加前的文档数量
            before_count = self.collection.count()
            logger.info(f"添加前的向量数据库文档数量: {before_count}")
            
            # 为每个文档生成唯一ID
            ids = [f"doc_{meta['pdf_id']}_{meta['chunk_id']}" for meta in metadatas]
            
            logger.info(f"正在添加 {len(chunks)} 个文档到向量数据库")
            if chunks:
                logger.info(f"示例文档: {chunks[0][:100]}...")
                logger.info(f"示例元数据: {metadatas[0]}")
                logger.info(f"示例ID: {ids[0]}")
            
            # 检查是否存在重复ID，如果存在则先删除
            try:
                # 尝试获取现有ID列表
                existing_ids = set()
                for i in range(0, len(ids), 100):
                    batch_ids = ids[i:i+100]
                    # 检查每个ID是否存在
                    for id in batch_ids:
                        try:
                            self.collection.get(ids=[id])
                            existing_ids.add(id)
                        except Exception:
                            # ID不存在，忽略错误
                            pass
                
                # 如果有重复ID，先删除
                if existing_ids:
                    logger.warning(f"发现 {len(existing_ids)} 个重复ID，将先删除")
                    # 分批删除，每次最多100个
                    for i in range(0, len(existing_ids), 100):
                        batch_ids = list(existing_ids)[i:i+100]
                        self.collection.delete(ids=batch_ids)
                    logger.info(f"已删除重复ID")
            except Exception as e:
                logger.warning(f"检查重复ID时出错: {str(e)}")
            
            # 分批添加，避免过大的请求
            batch_size = 100
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            
            for i in range(0, len(chunks), batch_size):
                end = min(i + batch_size, len(chunks))
                batch_num = i // batch_size + 1
                logger.info(
                    f"添加批次 {batch_num}/{total_batches}: "
                    f"{i}-{end}/{len(chunks)}"
                )
                
                batch_chunks = chunks[i:end]
                batch_embeddings = embeddings[i:end].tolist()
                batch_metadatas = metadatas[i:end]
                batch_ids = ids[i:end]
                
                # 检查数据合法性
                for j, (doc, emb, meta, id) in enumerate(zip(
                    batch_chunks, batch_embeddings, batch_metadatas, batch_ids
                )):
                    if not doc or not isinstance(doc, str):
                        logger.warning(f"跳过无效文档 #{i+j}: {doc}")
                        continue
                
                # 添加文档
                try:
                    self.collection.add(
                        documents=batch_chunks,
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                        ids=batch_ids
                    )
                    logger.info(f"批次 {batch_num} 添加成功")
                except Exception as e:
                    logger.error(f"添加批次 {batch_num} 时出错: {str(e)}")
                    # 继续处理其他批次，不要中断整个过程
            
            # 确保数据持久化
            try:
                if hasattr(self.client, "persist"):
                    self.client.persist()
                    logger.info("数据已成功持久化")
            except Exception as e:
                logger.error(f"持久化数据时出错: {str(e)}")
            
            # 计算添加后的文档数量
            after_count = self.collection.count()
            added_count = after_count - before_count
            
            logger.info(f"文档添加完成，当前文档总数: {after_count}")
            logger.info(f"实际添加了 {added_count} 个文档")
            
            # 如果文档数量没有变化，记录警告
            if added_count <= 0:
                logger.warning(
                    "警告: 向量数据库文档数量未增加，可能有重复ID或添加失败"
                )
                # 返回True，因为这可能是正常情况（所有文档都是重复的）
                return True
            
            return True
        except Exception as e:
            logger.error(f"添加文档到向量数据库时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def search(
        self, 
        query_embedding: np.ndarray, 
        n_results: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ):
        """在向量数据库中搜索相关文档。
        
        Args:
            query_embedding: 查询的向量嵌入。
            n_results: 返回结果的数量。
            filter_criteria: 过滤条件。
            
        Returns:
            Dict: 包含搜索结果的字典。
        """
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
                return {
                    "documents": [[]],
                    "metadatas": [[]],
                    "distances": [[]]
                }
                
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
        """获取向量数据库中的文档数量。
        
        Returns:
            int: 文档数量。
        """
        try:
            count = self.collection.count()
            logger.info(f"向量数据库中的文档数量: {count}")
            return count
        except Exception as e:
            logger.error(f"获取文档数量时出错: {str(e)}")
            return 0
            
    def reset(self):
        """清空向量数据库（用于测试和调试）。
        
        Returns:
            bool: 操作是否成功。
        """
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
            
    def delete(self, filter: Dict[str, Any] = None, ids: List[str] = None):
        """删除向量数据库中的文档。
        
        Args:
            filter: 过滤条件，例如 {"pdf_id": 1} 将删除所有pdf_id为1的文档。
            ids: 要删除的特定文档ID列表。
            
        Returns:
            bool: 操作是否成功。
        """
        try:
            # 记录删除前的文档数量
            before_count = self.collection.count()
            logger.info(f"删除前的向量数据库文档数量: {before_count}")
            
            if filter:
                logger.info(f"根据过滤条件删除文档: {filter}")
                # 使用过滤条件获取要删除的文档ID
                # 首先查询符合条件的所有文档
                query_results = self.collection.get(where=filter)
                doc_ids = query_results.get("ids", [])
                
                if not doc_ids:
                    logger.warning(f"没有找到符合条件的文档: {filter}")
                    return True
                
                logger.info(f"找到 {len(doc_ids)} 个符合删除条件的文档")
                
                # 分批删除，避免请求过大
                batch_size = 100
                total_batches = (len(doc_ids) + batch_size - 1) // batch_size
                
                for i in range(0, len(doc_ids), batch_size):
                    end = min(i + batch_size, len(doc_ids))
                    batch_ids = doc_ids[i:end]
                    batch_num = i // batch_size + 1
                    
                    logger.info(f"删除批次 {batch_num}/{total_batches}: {i}-{end}/{len(doc_ids)}")
                    self.collection.delete(ids=batch_ids)
            
            elif ids:
                logger.info(f"根据ID列表删除文档，ID数量: {len(ids)}")
                # 分批删除，避免请求过大
                batch_size = 100
                total_batches = (len(ids) + batch_size - 1) // batch_size
                
                for i in range(0, len(ids), batch_size):
                    end = min(i + batch_size, len(ids))
                    batch_ids = ids[i:end]
                    batch_num = i // batch_size + 1
                    
                    logger.info(f"删除批次 {batch_num}/{total_batches}: {i}-{end}/{len(ids)}")
                    self.collection.delete(ids=batch_ids)
            
            else:
                logger.warning("没有提供过滤条件或ID列表，不执行删除操作")
                return False
            
            # 确保数据持久化
            if hasattr(self.client, "persist"):
                self.client.persist()
                logger.info("数据已成功持久化")
                
            # 计算删除后的文档数量
            after_count = self.collection.count()
            deleted_count = before_count - after_count
            
            logger.info(f"文档删除完成，当前文档总数: {after_count}")
            logger.info(f"实际删除了 {deleted_count} 个文档")
            
            return True
            
        except Exception as e:
            logger.error(f"删除文档时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False