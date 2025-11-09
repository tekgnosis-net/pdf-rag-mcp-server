
# PDF RAG MCP Server
<div style="border:2px solid #2d3748; border-radius:12px; background:#1a202c; color:#e2e8f0; padding:20px; margin-bottom:32px;">

> ### ❤️ With Gratitude
>
> **This project proudly stands on the shoulders of the original work by [hyson666/pdf-rag-mcp-server](https://github.com/hyson666/pdf-rag-mcp-server).**
>
> Huge thanks to Hyson and the community for open-sourcing a rock-solid starting point and inspiring the continued evolution of this PDF RAG stack.
>
> I've built upon that foundation to enhance functionality, improve usability, and integrate modern practices so the project continues to serve the community effectively.
>
> These improvements make it easier to start with large collections of PDF specification documents while keeping the codebase maintainable and production-friendly.

</div>

<img width="600" alt="image" src="https://github.com/user-attachments/assets/3aeb102a-6d7f-4d58-a15b-129e640b2e35" />

<img width="1614" alt="image" src="https://github.com/user-attachments/assets/2b6e12c0-48f1-49f8-8d50-db03da2d1ee8" />

A powerful document knowledge base system that leverages PDF processing, vector storage, and MCP (Model Context Protocol) to provide semantic search capabilities for PDF documents. This system allows you to upload, process, and query PDF documents through a modern web interface or via the MCP protocol for integration with AI tools like Cursor.

## Table of Contents
- [PDF RAG MCP Server](#pdf-rag-mcp-server)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Release Highlights](#release-highlights)
  - [System Architecture](#system-architecture)
  - [Automatic PDF Ingestion](#automatic-pdf-ingestion)
  - [Quick Start](#quick-start)
    - [Prerequisites](#prerequisites)
    - [Quick Installation and Startup with uv and run.py](#quick-installation-and-startup-with-uv-and-runpy)
    - [Building the Frontend (For Developers)](#building-the-frontend-for-developers)
      - [Option 1: Using the provided script (recommended)](#option-1-using-the-provided-script-recommended)
      - [Option 2: Manual build process](#option-2-manual-build-process)
    - [Simple Production Setup](#simple-production-setup)
    - [Development Setup (Separate Services)](#development-setup-separate-services)
      - [Backend](#backend)
      - [Frontend](#frontend)
  - [Docker Deployment](#docker-deployment)
    - [Environment Configuration](#environment-configuration)
    - [Running with Docker Compose](#running-with-docker-compose)
    - [Choosing a Vector Database Backend](#choosing-a-vector-database-backend)
  - [Usage](#usage)
    - [Uploading Documents](#uploading-documents)
    - [Searching Documents](#searching-documents)
    - [Viewing Markdown in the Dashboard](#viewing-markdown-in-the-dashboard)
    - [Managing the Blacklist](#managing-the-blacklist)
    - [Reprocessing Documents](#reprocessing-documents)
    - [Searching the Knowledge Base](#searching-the-knowledge-base)
    - [MCP Integration with Cursor](#mcp-integration-with-cursor)
  - [MCP API Methods](#mcp-api-methods)
  - [Troubleshooting](#troubleshooting)
    - [Connection Issues](#connection-issues)
    - [Processing Issues](#processing-issues)
  - [Project Structure](#project-structure)
  - [Contributing](#contributing)
  - [License](#license)

## Features

- **PDF Document Upload & Processing**: Upload PDFs and automatically extract, chunk, and vectorize content
- **Real-time Processing Status**: WebSocket-based real-time status updates during document processing
- **Semantic Search**: Vector-based semantic search across all processed documents
- **MCP Protocol Support**: Integrate with AI tools like Cursor using the Model Context Protocol
- **Modern Web Interface**: React/Chakra UI frontend for document management and querying
- **Fast Dependency Management**: Uses uv for efficient Python dependency management
- **Automatic Directory Ingestion**: Watches a mounted folder and processes new or updated PDFs without manual uploads
- **Markdown Export**: Render any processed PDF as Markdown via MCP or the dashboard for quick reading and copy/paste
- **Blacklist Controls**: Dedicated Settings page to add or remove filenames that should be skipped during ingestion
- **Interactive Search Console**: Dedicated search page with pagination and markdown previews for matching chunks
- **Responsive Reparse Workflow**: Settings actions queue heavy cleanup in the background and stream WebSocket updates so the UI stays responsive even when fuzzy matches schedule large batches of PDFs

## Release Highlights

### Unreleased

- Settings reparse actions now defer markdown/vector cleanup to background workers, emit `processing_update` WebSocket events ("Clearing cached data", "Queued N") as progress ticks, and surface matching toasts so the UI stays responsive even when fuzzy matches enqueue dozens of PDFs.

<!-- RELEASE_HIGHLIGHTS_START -->
### v1.6.0 (2025-11-09)

- **Bug Fixes**: **Vector-store:** resolve lance persistence path.
- **Features**: Defer reparse cleanup. Enhance reparse controls and image handling.

### v1.5.1 (2025-11-08)

- **Bug Fixes**: Harden vector rebuild model loading.

### v1.5.0 (2025-11-08)

- **Features**: Enhance semantic search responses and mcp docs.

### v1.4.0 (2025-11-08)

- **Features**: Add lance vector backend with async rebuild.

### v1.3.0 (2025-11-08)

- **Features**: **Vector-store:** rebuild embeddings from markdown on reset.
<!-- RELEASE_HIGHLIGHTS_END -->

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

> **Note:** We intentionally do not commit `frontend/package-lock.json` because npm currently omits the ARM64 Rollup binary when the lockfile is generated on x86_64. Running `npm install --legacy-peer-deps` (as the Docker build does) ensures platform-specific packages are fetched at install time without needing the lockfile.

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
| `PDF_RAG_LANCE_DB` | `./data/lance_db` | Host path for the LanceDB vector database |
| `PDF_RAG_MODEL_CACHE` | `./data/model_cache` | Host path for the sentence-transformers model cache |
| `PDF_RAG_WATCH_DIR` | `/app/auto_ingest` | Path inside the container monitored by the watcher |
| `PDF_RAG_WATCH_VOLUME` | `./data/auto_ingest` | Host path mounted into the watcher directory |
| `PDF_RAG_WATCH_INTERVAL` | `5` | Poll interval (seconds) between directory scans |
| `PDF_RAG_WATCH_MAX_WORKERS` | `1` | Maximum concurrent processing tasks spawned by the watcher |
| `SENTENCE_TRANSFORMERS_DEVICE` | `cpu` | Set to `cuda` to use GPU embeddings when available |
| `PDF_RAG_VECTOR_BACKEND` | `lance` | Vector backend to use (`lance` default, set to `chroma` to opt back in) |
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

To build a bespoke image (for example, to change the embedded user/group IDs), clone the repo and run `docker build` with the `PUID` and `PGID` build args. Pass `--build-arg APP_VERSION=$(node -p "require('./package.json').version")` (or your desired tag) so the UI banner remains in sync with the container image. You can then point `PDF_RAG_IMAGE` at your custom tag.

### Choosing a Vector Database Backend

The project supports two embedded vector databases:

- **LanceDB (default)** – leave `PDF_RAG_VECTOR_BACKEND` unset (or set it to `lance`) to use the Arrow-backed Lance store with data persisted under `PDF_RAG_LANCE_DB`.
- **Chroma** – set `PDF_RAG_VECTOR_BACKEND=chroma` to use the Chroma store. Data lives under `PDF_RAG_CHROMA_DB`.

Both backends share the same ingestion code paths and metadata schema. When a backend initialises without vector data, it repopulates embeddings from the cached markdown pages in a background thread. Rebuilds skip PDFs whose on-disk files changed since their markdown snapshot, so only unchanged documents are restored without re-reading the PDFs.

## Usage

### Uploading Documents

1. Access the web interface at [http://localhost:8000](http://localhost:8000)
2. Click on "Upload New PDF" and select a PDF file
3. The system will process the file, showing progress in real-time
4. Once processed, the document will be available for searching

### Searching Documents

1. Use the search functionality in the web interface
2. Or integrate with Cursor using the MCP protocol

### Viewing Markdown in the Dashboard

Once a document finishes processing, the dashboard now offers a **View Markdown** action next to each entry. Clicking it fetches the pre-rendered Markdown (using the same title matching as the MCP endpoint) and displays it in a modal with rich formatting. From there you can copy the text or scroll through the rendered pages without leaving the browser.

### Managing the Blacklist

Select **Settings** in the navigation bar to review and manage the blacklist. You can:

- Add an exact filename (with an optional reason) to stop it from being queued again;
- Remove entries when you are ready to reprocess the file;
- See when an item was blacklisted and why. The backend stores this information in the database so it persists across restarts.

If a PDF fails OCR or contains no readable text, the processor automatically blacklists it and records the reason here so you can triage the issue later.

### Reprocessing Documents

The same **Settings** page provides **Reprocess All** and **Reprocess Selected** actions to refresh markdown snapshots and embeddings without shell access.

- **Reprocess All** wipes cached markdown and vectors for every non-blacklisted PDF, then re-queues ingestion. Cleanup runs in background workers, so the HTTP response and UI toasts confirm scheduling immediately while WebSocket updates ("Clearing cached data", "Queued N") reflect ongoing progress.
- **Reprocess Selected** accepts newline or comma-separated values and performs case-insensitive fuzzy matching against filenames and paths. Matches are processed one-by-one in the background to keep the UI responsive; the toast output lists queued and skipped entries so you can reconcile the results.
- While cleanup is in flight, you can leave the page open to watch progress, or monitor `docker compose logs -f pdf-rag` for the same `processing_update` events.

### Searching the Knowledge Base

Click **Search** in the navigation bar to query embeddings directly from the UI. The page lets you:

- Tune the result limit per page and page forward/backward through matches;
- Inspect similarity scores and page numbers for every hit;
- Open the rendered markdown for a result in one click, starting from the matched page.

The same pagination parameters (`limit`, `offset`) are now supported by the MCP `/query` endpoint, so automation clients can stream result pages just like the browser UI.

### MCP Integration with Cursor

1. Open Cursor
2. Go to Settings → AI & MCP
3. Add Custom MCP Server with URL: `http://localhost:8000/mcp/v1`
4. Save the settings
5. Now you can query your PDF knowledge base directly from Cursor

## MCP API Methods

The MCP service exposes lightweight HTTP endpoints that Cursor and other MCP clients can call directly:

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| `GET` | `/mcp/query` | Perform a semantic search against the vector database. | Provide a `query` string; returns the top 5 chunks with metadata. |
| `GET` | `/mcp/documents/markdown` | Retrieve a processed PDF rendered as Markdown. | Pass a `title` query parameter that matches the document filename (substring or fuzzy match). Optional `start_page`, `max_pages`, and `max_characters` parameters let you page through large documents without overrunning client context limits. |

Both endpoints return standard JSON responses and error codes (`404` for missing matches, `409` for in-progress/blacklisted files, etc.), making them easy to script against outside of MCP clients.

When using the Markdown endpoint with paging controls, the response echoes the window that was returned, indicates whether additional pages remain (`has_more`), and provides the next page cursor (`next_page`) you can supply as the subsequent `start_page`. This makes it straightforward to stream long specifications to an LLM in manageable chunks. The `max_characters` guard expects a budget of at least 2 000 characters to ensure at least one full page can be returned.

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
│   │   ├── api/           # Frontend API helpers
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
