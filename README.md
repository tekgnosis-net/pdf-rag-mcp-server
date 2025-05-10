# PDF知识库MCP调用与测试指南

# 项目结构

``` 
mcp-pdf-knowledge-base/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI主应用
│   │   ├── database.py         # 数据库模型
│   │   ├── pdf_processor.py    # PDF处理逻辑
│   │   ├── vector_store.py     # 向量存储
│   │   └── websocket.py        # WebSocket处理
│   ├── uploads/                # 上传的PDF存储位置
│   ├── static/                 # 静态资源 
│   └── requirements.txt        # 后端依赖
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.jsx  # 文件上传组件
│   │   │   ├── FileList.jsx    # 文件列表组件
│   │   │   └── ProgressBar.jsx # 进度条组件
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── docker-compose.yml          # 容器化配置
```



## 目录
1. MCP协议概述
2. 系统架构简介
3. 启动与配置
4. Cursor连接设置
5. MCP功能测试方法
6. 故障排除
7. 高级使用技巧

---

## 1. MCP协议概述

MCP（Model Context Protocol，模型上下文协议）是一个开放标准协议，旨在解决AI模型与外部数据源（如知识库、数据库）的集成问题。通过MCP协议，Cursor等支持MCP的编辑器可以与本地知识库系统进行无缝对话，实现对本地PDF文档的智能检索和引用。

**核心优势：**
- 实现AI编辑器与本地知识库的标准化通信
- 保护私有数据，所有处理在本地完成
- 提高AI助手回答的准确性和相关性

## 2. 系统架构简介

本PDF知识库系统包含以下主要组件：

![系统架构图](https://placeholder-image.com/system-architecture)

- **Web前端**：用于上传、管理PDF文档
- **FastAPI后端**：处理文档解析、向量化和API请求
- **向量数据库**：存储文档的语义表示
- **MCP服务端点**：遵循MCP协议规范，处理来自Cursor的请求

系统工作流程：
1. 用户通过Web界面上传PDF文档
2. 系统解析PDF内容，分割成适当大小的文本块
3. 为每个文本块生成向量嵌入并存储
4. Cursor通过MCP协议查询知识库
5. 系统返回相关文档内容

## 3. 启动与配置

### 启动系统

**方法一：使用Docker（推荐）**
```bash
# 克隆项目（如果尚未克隆）
git clone https://github.com/yourusername/mcp-pdf-knowledge-base.git
cd mcp-pdf-knowledge-base

# 使用Docker Compose启动
docker-compose up -d
```

**方法二：手动启动**
```bash
# 启动后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 在另一个终端启动前端
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

### 访问系统

- **Web界面**：http://localhost:3000
- **API文档**：http://localhost:8000/docs
- **MCP端点**：http://localhost:8000/mcp/v1 (供Cursor连接使用)

## 4. Cursor连接设置

要将Cursor与您的PDF知识库连接，请按照以下步骤操作：

1. **打开Cursor应用**
2. **进入设置界面**：
   - 点击右上角头像
   - 选择"Settings"（设置）
   - 选择"AI & MCP"选项卡
3. **添加MCP服务器**：
   - 点击"Add Custom MCP Server"（添加自定义MCP服务器）
   - 输入名称：例如"本地PDF知识库"
   - 输入URL：`http://localhost:8000/mcp/v1`
   - 点击"Save"（保存）

![Cursor MCP设置截图](https://placeholder-image.com/cursor-settings)

配置完成后，Cursor将能够访问您的本地PDF知识库。

## 5. MCP功能测试方法

### 方法一：通过Cursor测试

1. **确认系统状态**：
   - 确保PDF知识库系统正在运行
   - Web界面上传并处理了至少一个PDF文档（处理状态显示为"已完成"）

2. **在Cursor中使用**：
   - 打开Cursor应用
   - 在AI对话框中，输入与您上传文档相关的问题
   - 例如：如果您上传了关于Python编程的PDF，可以询问"Python列表和元组有什么区别？"

3. **验证响应**：
   - Cursor应返回从您的PDF知识库中检索的相关信息
   - 响应中应包含引用源，指明信息来自哪个PDF文档

### 方法二：直接测试MCP端点

可以使用curl或Postman等工具直接测试MCP端点：

```bash
curl -X POST http://localhost:8000/mcp/v1 \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Python中的列表和元组有什么区别？"}
    ]
  }'
```

预期响应：
```json
{
  "type": "tool_result",
  "result": {
    "content": "**From python_basics.pdf:**\n列表（List）是可变的，而元组（Tuple）是不可变的。这意味着列表可以在创建后修改，添加或删除元素，而元组一旦创建就不能更改...",
    "metadata": {
      "source": "knowledge_base"
    }
  }
}
```

### 方法三：使用WebSocket监控MCP调用

系统提供了WebSocket接口，可以实时监控MCP调用情况：

1. 打开浏览器开发者工具
2. 运行以下JavaScript代码：

```javascript
const socket = new WebSocket('ws://localhost:8000/ws');
socket.onmessage = function(event) {
    console.log('收到消息:', JSON.parse(event.data));
};
```

3. 在Cursor中发送查询
4. 观察控制台输出的WebSocket消息，包含MCP调用详情

## 6. 故障排除

### 常见问题与解决方案

1. **Cursor无法连接到MCP服务器**
   - 检查MCP服务器是否正在运行（访问 http://localhost:8000 确认）
   - 确认防火墙或网络设置未阻止连接
   - 验证MCP URL是否正确输入：http://localhost:8000/mcp/v1

2. **MCP返回空结果**
   - 确保至少有一个PDF已成功处理完成
   - 检查查询内容是否与上传文档相关
   - 查看系统日志（backend/app.log）了解更多详情

3. **PDF处理失败**
   - 检查PDF文件是否可读
   - 确认PDF不是扫描图像（需要OCR处理的PDF可能无法正确提取文本）
   - 查看Web界面上的错误消息或系统日志

4. **系统性能问题**
   - 大型PDF文件可能需要更长的处理时间
   - 检查系统资源使用情况，确保有足够的内存和CPU资源
   - 考虑调整`chunk_size`参数（在`pdf_processor.py`中）以优化处理

## 7. 高级使用技巧

### 自定义向量数据库查询

可以使用API端点直接查询向量数据库，适用于特定需求：

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Python列表和元组的区别"}'
```

### 调整嵌入模型

系统默认使用`all-MiniLM-L6-v2`模型生成文本嵌入。如需更高质量的结果，可修改`pdf_processor.py`使用其他模型：

```python
# 将默认模型
self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# 替换为
self.embedding_model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")  # 多语言支持更好
```

### 批量导入PDF

对于需要导入大量PDF文件的场景，可以使用系统提供的批处理脚本：

```bash
cd backend
python scripts/batch_import.py --directory /path/to/your/pdfs
```

### MCP高级参数配置

通过修改`main.py`中的MCP处理逻辑，可以自定义检索行为：

```python
# 增加结果数量
results = vector_store.search(query_embedding, n_results=10)  # 默认为5

# 添加过滤条件（仅检索特定PDF）
filter_criteria = {"source": "specific_document.pdf"}
results = vector_store.search(query_embedding, n_results=5, filter_criteria=filter_criteria)
```

---

## 附录：常用命令速查表

| 功能 | 命令 |
|------|------|
| 启动系统 | `docker-compose up -d` |
| 查看后端日志 | `docker-compose logs -f backend` |
| 重启服务 | `docker-compose restart` |
| 停止服务 | `docker-compose down` |
| 手动处理目录中的PDF | `python backend/scripts/batch_import.py --directory ./pdfs` |
| 测试MCP端点 | `curl -X POST http://localhost:8000/mcp/v1 -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"查询内容"}]}'` |

---

## 资源与支持

- **项目GitHub仓库**：[github.com/yourusername/mcp-pdf-knowledge-base](https://github.com/yourusername/mcp-pdf-knowledge-base)
- **MCP协议规范**：[github.com/microsoft/model-context-protocol](https://github.com/microsoft/model-context-protocol)
- **Cursor文档**：[cursor.sh/docs](https://cursor.sh/docs)

如遇问题，请提交GitHub Issue或联系项目维护者。

