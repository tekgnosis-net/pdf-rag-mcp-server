# PDF RAG MCP Server
<img width="600" alt="image" src="https://github.com/user-attachments/assets/3aeb102a-6d7f-4d58-a15b-129e640b2e35" />

<img width="1614" alt="image" src="https://github.com/user-attachments/assets/2b6e12c0-48f1-49f8-8d50-db03da2d1ee8" />

A powerful document knowledge base system that leverages PDF processing, vector storage, and MCP (Model Context Protocol) to provide semantic search capabilities for PDF documents. This system allows you to upload, process, and query PDF documents through a modern web interface or via the MCP protocol for integration with AI tools like Cursor.

## Features

- **PDF Document Upload & Processing**: Upload PDFs and automatically extract, chunk, and vectorize content
- **Real-time Processing Status**: WebSocket-based real-time status updates during document processing
- **Semantic Search**: Vector-based semantic search across all processed documents
- **MCP Protocol Support**: Integrate with AI tools like Cursor using the Model Context Protocol
- **Modern Web Interface**: React/Chakra UI frontend for document management and querying
- **Fast Dependency Management**: Uses uv for efficient Python dependency management
- **Automatic Directory Ingestion**: Watches a mounted folder and processes new or updated PDFs without manual uploads

## System Architecture

The system consists of:

- **FastAPI Backend**: Handles API requests, PDF processing, and vector storage
- **React Frontend**: Provides a user-friendly interface for managing documents
- **Vector Database**: Stores embeddings for semantic search
- **WebSocket Server**: Provides real-time updates on document processing
- **MCP Server**: Exposes knowledge base to MCP-compatible clients
- **PDF Directory Watcher**: Monitors a configurable filesystem path and schedules ingestion jobs for new PDFs

## Automatic PDF Ingestion

The backend ships with a directory watcher (`backend/app/pdf_watcher.py`) that continuously scans the path defined by `PDF_RAG_WATCH_DIR`. Any new or modified PDFs found there are inserted into the database and processed just like uploaded files. The watcher:

- Debounces processing by comparing filesystem modification times against the database
- Clears existing embeddings for a document before reprocessing to avoid stale chunks
- Uses a thread pool sized by `PDF_RAG_WATCH_MAX_WORKERS` so large drops are handled concurrently without overwhelming the processor

To enable auto-ingestion in Docker, mount a host folder to the watch directory (see the Docker Deployment section) and copy PDFs into that folder. Status events for watched files flow through the same WebSocket channel as manual uploads, so the dashboard reflects progress automatically.

## Quick Start

### Prerequisites

- [Python](https://www.python.org/downloads/) 3.8 or later
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- Git
- Cursor (optional, for MCP integration)

### Quick Installation and Startup with uv and run.py

1. Clone the repository:
   ```bash
   git clone https://github.com/tekgnosis-net/pdf-rag-mcp-server.git
   cd pdf-rag-mcp-server
   ```

2. Install uv if you don't have it already:
   ```bash
   curl -sS https://astral.sh/uv/install.sh | bash
   ```

3. Install dependencies using uv:
   ```bash
   uv init .
   uv venv
   source .venv/bin/activate
   uv pip install -r backend/requirements.txt
   ```

4. Start the application with the convenient script:
   ```bash
   uv run run.py
   ```

5. Access the web interface at [http://localhost:8000](http://localhost:8000)

6. Using with Cursor 

Go Settings -> Cursor Settings -> MCP -> Add new global MCP server, paste below into your Cursor ~/.cursor/mcp.json file. See Cursor MCP docs for more info.
```json
{
  "mcpServers": {
    "pdf-rag": {
      "url": "http://localhost:7800/mcp"
    }
  }
}
```
You could also change localhost into the host ip you deployed the service. After this confige added to the mcp json, you will see the mcp server showes at the Cursor mcp config page, switch it on to enable the server:

<img width="742" alt="image" src="https://github.com/user-attachments/assets/d9b2c97c-c535-4d2a-bcf1-2d2c6343aeb3" />


### Building the Frontend (For Developers)

If you need to rebuild the frontend, you have two options:

#### Option 1: Using the provided script (recommended)

```bash
# Make the script executable if needed
chmod +x build_frontend.py

# Run the script
./build_frontend.py
```

This script will automatically:
- Install frontend dependencies
- Build the frontend
- Copy the build output to the backend's static directory

#### Option 2: Manual build process

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Build the frontend
npm run build

# Create static directory if it doesn't exist
mkdir -p ../backend/static

# Copy build files
cp -r dist/* ../backend/static/
```

After building the frontend, you can start the application using the run.py script.

### Simple Production Setup

For a production environment where the static files have already been built:

1. Place your pre-built frontend in the `backend/static` directory
2. Start the server:
   ```bash
   cd backend
   uv pip install -r requirements.txt
   python -m app.main
   ```

### Development Setup (Separate Services)

If you want to run the services separately for development:

#### Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install the dependencies with uv:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Run the backend server:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

#### Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install the dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

## Docker Deployment

The project publishes a container image to the GitHub Container Registry (GHCR) at `ghcr.io/tekgnosis-net/pdf-rag-mcp-server`. Using Docker Compose keeps the backend, vector store, uploads, and watcher volumes wired together with sensible defaults.

### Environment Configuration

Create a `.env` file (you can copy `.env.sample`) to tune ports, volume paths, and watcher behaviour:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_PORT` | `8000` | Host port exposed for the FastAPI and WebSocket server |
| `MCP_PORT` | `7800` | Host port for the MCP endpoint |
| `PDF_RAG_IMAGE` | `ghcr.io/tekgnosis-net/pdf-rag-mcp-server:latest` | Image reference pulled by Docker Compose |
| `PDF_RAG_UPLOADS` | `./data/uploads` | Host path for persisted uploaded PDFs |
| `PDF_RAG_CHROMA_DB` | `./data/chroma_db` | Host path for the Chroma vector database |
| `PDF_RAG_MODEL_CACHE` | `./data/model_cache` | Host path for the sentence-transformers model cache |
| `PDF_RAG_WATCH_DIR` | `/app/auto_ingest` | Path inside the container monitored by the watcher |
| `PDF_RAG_WATCH_VOLUME` | `./data/auto_ingest` | Host path mounted into the watcher directory |
| `PDF_RAG_WATCH_INTERVAL` | `5` | Poll interval (seconds) between directory scans |
| `PDF_RAG_WATCH_MAX_WORKERS` | `1` | Maximum concurrent processing tasks spawned by the watcher |
| `SENTENCE_TRANSFORMERS_DEVICE` | `cpu` | Set to `cuda` to use GPU embeddings when available |
| `SENTENCE_TRANSFORMERS_CACHE` | `/home/appuser/.cache/torch/sentence_transformers` | Override the cache location inside the container |

### Running with Docker Compose

```bash
cp .env.sample .env   # customise as needed
docker compose pull   # fetch latest GHCR image
docker compose up -d  # start the stack
```

After the stack boots:

- Upload PDFs through the web UI or drop them into the folder pointed to by `PDF_RAG_WATCH_VOLUME`
- Connect MCP clients to `http://<host>:${MCP_PORT}/mcp/v1`
- Persisted data lives in the `./data` folder (or the paths you configured)

To build a bespoke image (for example, to change the embedded user/group IDs), clone the repo and run `docker build` with the `PUID` and `PGID` build args. You can then point `PDF_RAG_IMAGE` at your custom tag.

## Usage

### Uploading Documents

1. Access the web interface at [http://localhost:8000](http://localhost:8000)
2. Click on "Upload New PDF" and select a PDF file
3. The system will process the file, showing progress in real-time
4. Once processed, the document will be available for searching

### Searching Documents

1. Use the search functionality in the web interface
2. Or integrate with Cursor using the MCP protocol

### MCP Integration with Cursor

1. Open Cursor
2. Go to Settings → AI & MCP
3. Add Custom MCP Server with URL: `http://localhost:8000/mcp/v1`
4. Save the settings
5. Now you can query your PDF knowledge base directly from Cursor

## Troubleshooting

### Connection Issues

- Verify that port 8000 is not in use by other applications
- Check that the WebSocket connection is working properly
- Ensure your browser supports WebSockets

### Processing Issues

- Check if your PDF contains extractable text (some scanned PDFs may not)
- Ensure the system has sufficient resources (memory and CPU)
- Check the backend logs for detailed error messages

## Project Structure

```
pdf-rag-mcp-server/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py        # Main FastAPI application
│   │   ├── database.py    # Database models
│   │   ├── pdf_processor.py # PDF processing logic
│   │   ├── pdf_watcher.py # Directory watcher for auto-ingestion
│   │   ├── vector_store.py # Vector database interface
│   │   └── websocket.py   # WebSocket handling
│   ├── static/            # Static files for the web interface
│   └── requirements.txt   # Backend dependencies
├── frontend/              # React frontend
│   ├── public/
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── context/       # React context
│   │   ├── pages/         # Page components
│   │   └── App.jsx        # Main application component
│   ├── package.json       # Frontend dependencies
│   └── vite.config.js     # Vite configuration
├── uploads/               # PDF file storage
└── README.md              # This documentation
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
