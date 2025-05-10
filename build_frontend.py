#!/usr/bin/env python3
"""
构建并启动PDF知识库系统的脚本。

这个脚本会构建前端，将构建结果复制到后端的静态目录，
然后启动FastAPI后端服务器，实现一键同时启动前后端。
"""

import os
import shutil
import subprocess
import sys

def build_frontend():
    """构建前端应用"""
    print("正在构建前端应用...")
    os.chdir("frontend")
    
    # 安装依赖
    print("安装前端依赖...")
    subprocess.run(['npm', 'install'], check=True)
    
    # 构建前端
    print("构建前端...")
    subprocess.run(['npm', 'run', 'build'], check=True)
    
    os.chdir("..")
    
    # 复制构建结果到后端静态目录
    print("复制前端构建结果到后端静态目录...")
    if os.path.exists("frontend/dist"):
        # 清空静态目录
        if os.path.exists("backend/app/static"):
            shutil.rmtree("backend/app/static")
            
        # 复制构建结果
        shutil.copytree("frontend/dist", "backend/app/static")
        print("前端构建结果已复制到后端静态目录")
    else:
        print("错误: 前端构建目录不存在!")
        sys.exit(1)

def main():
    """主函数"""
    # 确保当前目录是项目根目录
    if not (os.path.isdir("frontend") and os.path.isdir("backend")):
        print("错误: 请在项目根目录运行此脚本!")
        sys.exit(1)
        
    # 构建前端
    build_frontend()
    


if __name__ == "__main__":
    main() 
