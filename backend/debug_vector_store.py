#!/usr/bin/env python

import sys
import os
from pathlib import Path
import chromadb
from chromadb.config import Settings

# 打印调试信息
print("Python版本:", sys.version)
print("当前工作目录:", os.getcwd())

# 获取当前文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 打印当前目录
print("当前脚本目录:", current_dir)

# 尝试直接连接当前目录下的chroma_db
persist_directory1 = "./chroma_db"
print(f"\n尝试连接相对路径: {persist_directory1}")
print(f"对应的绝对路径: {os.path.abspath(persist_directory1)}")

try:
    client1 = chromadb.Client(Settings(
        persist_directory=persist_directory1,
        anonymized_telemetry=False
    ))
    collection1 = client1.get_or_create_collection("pdf_documents")
    count1 = collection1.count()
    print(f"成功连接! 文档数量: {count1}")
except Exception as e:
    print(f"连接失败: {str(e)}")

# 尝试连接绝对路径
persist_directory2 = os.path.join(current_dir, "chroma_db")
print(f"\n尝试连接绝对路径: {persist_directory2}")

try:
    client2 = chromadb.Client(Settings(
        persist_directory=persist_directory2,
        anonymized_telemetry=False
    ))
    collection2 = client2.get_or_create_collection("pdf_documents")
    count2 = collection2.count()
    print(f"成功连接! 文档数量: {count2}")
except Exception as e:
    print(f"连接失败: {str(e)}")

# 列出目录内容
print("\n相对路径目录内容:")
if os.path.exists(persist_directory1):
    print(os.listdir(persist_directory1))
else:
    print(f"目录不存在: {persist_directory1}")

print("\n绝对路径目录内容:")
if os.path.exists(persist_directory2):
    print(os.listdir(persist_directory2))
else:
    print(f"目录不存在: {persist_directory2}")

# 创建新的向量数据库目录
persist_directory3 = os.path.join(current_dir, "chroma_db_new")
print(f"\n创建新的向量数据库目录: {persist_directory3}")
os.makedirs(persist_directory3, exist_ok=True)

try:
    client3 = chromadb.Client(Settings(
        persist_directory=persist_directory3,
        anonymized_telemetry=False
    ))
    collection3 = client3.get_or_create_collection("pdf_documents")
    print(f"成功创建新的向量数据库，文档数量: {collection3.count()}")
except Exception as e:
    print(f"创建失败: {str(e)}")

print("\n调试完成!") 