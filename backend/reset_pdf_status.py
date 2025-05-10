#!/usr/bin/env python

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal, PDFDocument

def main():
    """重置所有PDF文档的处理状态"""
    db = SessionLocal()
    try:
        # 获取所有文档
        docs = db.query(PDFDocument).all()
        
        if not docs:
            print("没有找到任何PDF文档")
            return
        
        # 重置处理状态
        count = 0
        for doc in docs:
            doc.processed = False
            doc.processing = False
            doc.progress = 0.0
            doc.error = None
            count += 1
        
        # 提交更改
        db.commit()
        print(f"成功重置 {count} 个PDF文档的处理状态")
        
        # 显示更新后的状态
        print("\n当前文档状态:")
        for doc in docs:
            print(f"  ID: {doc.id}, 文件名: {doc.filename}, 状态: {'未处理'}")
    
    finally:
        db.close()

if __name__ == "__main__":
    main() 