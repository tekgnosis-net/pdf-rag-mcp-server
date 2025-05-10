#!/usr/bin/env python3
"""
PDF知识库系统启动脚本

这个脚本用于直接在项目根目录启动PDF知识库系统。
前端静态文件应已构建并放置在 backend/static 目录中。
"""

import os
import sys
import subprocess
import time

def check_requirements():
    """检查项目依赖和环境"""
    print("检查项目环境...")
    
    # 检查Python版本
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("错误: 需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 检查静态文件目录
    if not os.path.exists("backend/static"):
        print("错误: 静态文件目录不存在，请确保前端已构建")
        sys.exit(1)
    
    # 检查index.html是否存在
    if not os.path.exists("backend/static/index.html"):
        print("错误: 静态文件目录中缺少index.html")
        sys.exit(1)
    
    print("环境检查通过!")

def start_server():
    """启动FastAPI服务器"""
    print("正在启动PDF知识库系统...")
    
    # 切换到后端目录
    os.chdir("backend")
    
    # 确保上传和数据库目录存在
    os.makedirs("uploads", exist_ok=True)
    
    # 启动服务器
    try:
        subprocess.run([
            sys.executable, 
            "-m", "app.main"
        ])
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"启动服务器时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # 确保脚本在项目根目录运行
    if not (os.path.exists("backend") and os.path.exists("backend/app")):
        print("错误: 请在项目根目录运行此脚本")
        sys.exit(1)
    
    # 检查环境
    check_requirements()
    
    # 启动服务器
    start_server()