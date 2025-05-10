#!/usr/bin/env python

import requests
import json
import os

# 设置代理
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'

# 测试查询API
def test_query():
    print("测试查询API...")
    
    # 方法1: 使用查询参数
    url = "http://localhost:8000/api/query"
    query = "金融机器学习的主要方法"
    
    # 尝试参数格式1: 表单数据
    print("\n尝试表单数据格式:")
    response = requests.post(url, data={"query": query})
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text[:200]}...")
    
    # 尝试参数格式2: JSON数据
    print("\n尝试JSON数据格式:")
    response = requests.post(url, json={"query": query})
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text[:200]}...")
    
    # 尝试参数格式3: URL查询字符串
    print("\n尝试URL查询字符串格式:")
    response = requests.post(f"{url}?query={query}")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text[:200]}...")
    
    # 尝试参数格式4: URL查询字符串 + 请求头
    print("\n尝试URL查询字符串+请求头格式:")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(f"{url}?query={query}", headers=headers)
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text[:200]}...")
    
    # 尝试参数格式5: 表单数据 + 请求头
    print("\n尝试表单数据+请求头格式:")
    response = requests.post(url, data=f"query={query}", headers=headers)
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text[:200]}...")

if __name__ == "__main__":
    test_query() 