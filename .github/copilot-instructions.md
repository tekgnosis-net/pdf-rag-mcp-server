# PDF RAG MCP Server – Agent Guide

## General guidelines (Not to be changed)

- **Response style**: End every reply with a concise summary covering completed work and next steps or current status.
- **Editing**: Keep indentation, formatting, and ASCII-only text unless non-ASCII already exists and is justified. Make sure indentation is consistent (spaces vs tabs) as per the context as well.
- **Change tracking**: Document structural, dependency, and workflow updates here; perform work on feature branches rather than directly on `main`.
- **Workflow vigilance**: If CI/CD or automation files change, monitor subsequent runs and surface failures quickly.
- **Branch etiquette**: Maintain feature branches per change; never revert user edits unless explicitly requested.
- **UI baseline**: Display the running build/version near the primary title as Version: 1.0.0 as example(pulling from an env-driven constant such as `VITE_APP_VERSION`) and include a footer with `© {currentYear} Tekgnosis Pty Ltd`, computing the year at runtime so it stays current.
- **Docker build args**: Plumb an `APP_VERSION` build arg/ENV through container builds so the frontend/banner and metadata stay synchronized with release tags.
- **Runtime parity**: When merging frontend rewrites, ensure Dockerfile entrypoints, runtime scripts, and dependency sets are updated in the same change so published images launch the new stack.
- **Python environment**: Ensure all Python code is compatible with Python 3.11+ and leverages type hints where appropriate. Use virtual environments for local development to manage dependencies effectively.
- **Workflows**: Ensure github workflows are monitored after changes to catch any issues early. Use gh to check workflow statuses regularly.
- **Workflow topology**: `Release and Publish` (single workflow) runs semantic-release and always builds/pushes GHCR images. When no new release is cut it tags the image as `rolling-<sha>` alongside `latest`; there is no standalone docker workflow anymore, so failures here block image publication.
- **Copilot instructions file**: Treat this document as living release notes for contributors—whenever code, dependencies, or workflows change, review the diff and update this file with the new expectations before you finish the task. Never push this file to github main branch but keep it in feature branches for reference. Always maintain it locally for developer guidance.

## Release & versioning (Not to be changed)

- **Semantic-release**: Releases are computed by `.github/workflows/release.yml` using semantic-release; keep commit messages Conventional (`feat`, `fix`, etc.) so versioning stays accurate.
- **Version sync**: `scripts/update-version.cjs` runs during the semantic-release `prepare` step to update `package.json` and `package-lock.json`; the Docker build arg `APP_VERSION` propagates the same value into runtime assets.
- **Artifacts**: Successful releases publish GitHub releases, append to `CHANGELOG.md`, and tag GHCR images with both the computed SemVer (from the release tag) and `latest` via `.github/workflows/docker-publish.yml`.
- **Pipeline alignment**: The release workflow runs on Node 20—match that locally when testing semantic-release, and ensure Docker builds include the `APP_VERSION` build arg so UI banners and metadata remain in sync.
- **Release docs**: If semantic-release publishes a new minor or major version (e.g. 1.2.x → 1.3.x), update the README with a short note summarizing the release highlights before you finish the task.
- **README automation**: `.github/workflows/release.yml` calls `scripts/update-readme-release.mjs` after semantic-release to regenerate the "Release Highlights" block in `README.md` and commits with `[skip ci]`; keep the start/end markers intact and extend the script when the layout changes.
- **Commit hygiene**: Format commit messages as Conventional Commits (`feat`, `fix`, `chore`, etc.) to ensure correct version bumps.


- **Instruction upkeep**: When you touch the codebase, reassess these guidelines and update them so they continue to reflect current behaviour and testing expectations.
- **Architecture**: `backend/app/main.py` hosts the FastAPI REST API, background processing, WebSocket broadcasting, and mounts an MCP-specific FastAPI (`mcp_app`) for Model Context Protocol clients.
- **HTTP API**: Primary routes live in `backend/app/main.py`; `/api/upload` queues background processing, `/api/documents` surfaces status, `/api/documents/{id}` and `DELETE` manage lifecycle.
- **Upload flow**: Files land in `./uploads` (created relative to the backend working directory), gain a DB row in `PDFDocument` (`backend/app/database.py`), then `_process_pdf_background` awaits `PDFProcessor.process_pdf`.
- **Auto-ingest**: `PDFDirectoryWatcher` (`backend/app/pdf_watcher.py`) scans `PDF_RAG_WATCH_DIR` (mapped via Compose) for PDFs, inserts/updates `PDFDocument` rows, and reuses `PDFProcessor.process_pdf`; it compares the file’s `mtime` against `uploaded_at` to avoid reprocessing unchanged files and purges old embeddings via `VectorStore.delete` before reruns.
- **Processing status**: Progress is tracked via the module-level `PROCESSING_STATUS` dict in `backend/app/pdf_processor.py`; WebSocket clients expect `{"type": "processing_update", "filename", "status"}` payloads, so preserve that contract.
- **Chunking pipeline**: `PDFProcessor` uses PyMuPDF for extraction and LangChain's `RecursiveCharacterTextSplitter` (1 000/200 overlap). Coordinate changes with chunk metadata assumptions in `VectorStore` and query formatting.
- **Image capture**: `PDFProcessor` embeds page images into the persisted markdown as base64 data URIs while adding textual placeholders so vector embeddings still reference the media. It skips duplicates per document, merges masks when `smask` data exists, and falls back to PNG when the source format is unsupported. Big assets are skipped when they exceed `PDF_IMAGE_MAX_PER_PAGE` (default 8 images), `PDF_IMAGE_MAX_PIXELS` (default 5,000,000), or `PDF_IMAGE_MAX_BYTES` (default 2 MiB); adjust env vars if you need larger captures. Downstream markdown consumers must be ready to render or strip inline `data:image/*;base64,...` blobs.
- **Embedding model**: Both `PDFProcessor` and `/query` reuse the singleton `SentenceTransformer("all-MiniLM-L6-v2")`; avoid re-instantiating it inside request handlers to prevent GPU/CPU thrash.
- **Chunk metadata**: Metadata stored in the vector backends includes `pdf_id`, `chunk_id`, `page`, and `batch`; downstream code (query responses, deletions) relies on these keys, so extend rather than replace them.
- **Vector maintenance**: `backend/app/vector_store.py` fronts pluggable backends (`PDF_RAG_VECTOR_BACKEND`), defaulting to LanceDB (persisted under `data/lance_db`) with Chroma (`data/chroma_db`) still available. Always use the facade helpers (`add_documents`, `delete`, `reset`, `ensure_async_rebuild`) instead of talking to backend clients directly; both backends rebuild from cached markdown in a background thread when the store is empty. Relative paths in the env (e.g., `./data/lance_db`) resolve against the project root, so containerized and local runs share the same mount point.
- **Database**: SQLite lives at `backend/pdf_knowledge_base.db`; session helpers come from `get_db()` in `database.py`. Remember to close sessions when writing new background utilities.
- **Deletion logic**: `/api/documents/{id}` cleans up files, vector entries, and DB rows; replicate its filtering logic if you add batch-delete features so partial-processing assets are removed.
- **Reprocessing controls**: `/api/reparse` clears markdown rows and vector entries before re-queuing document processing. `mode:'all'` nukes both stores and schedules every non-blacklisted PDF; `mode:'selected'` accepts exact filenames along with case-insensitive substring/fuzzy matches against `filename` and `file_path`, then defers markdown/vector cleanup to background tasks so the HTTP response stays snappy. Expect WebSocket updates to show the "Clearing cached data" status before processing resumes.
- **Static serving**: The backend serves from `backend/app/static`; `vite.config.js` sets `base: '/static/'`, so production builds must land in that folder structure (index + nested `static/assets`).
- **Frontend build**: `build_frontend.py` installs deps, runs `npm run build`, and copies `frontend/dist` into `backend/app/static`; prefer this script whenever you regenerate assets.
- **Dev servers**: Run `uv pip install -r backend/requirements.txt` then `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` for the backend; `npm install` + `npm run dev` starts Vite with API/WebSocket proxying to `localhost:8000`.
- **Local images**: Prefer `docker build -t pdf-rag-mcp-server:local .` for backend image changes, then start services with `PDF_RAG_IMAGE=pdf-rag-mcp-server:local docker compose up -d`; avoid `docker compose build` because `docker-compose.yml` lacks a build section.
- **Combined start**: `uv run run.py` (or `python run.py`) expects pre-built static files and also launches the MCP server thread on port 7800.
- **MCP endpoint**: `FastApiMCP` mounts `mcp_app` under `/mcp/v1`; Cursor clients typically hit `http://localhost:7800/mcp`, so keep that route stable or update docs/UI hints (see `Dashboard.jsx`).
- **WebSockets**: `frontend/src/context/WebSocketContext.jsx` hard-codes `ws://{hostname}:8000/ws` with auto-retry to drive live progress; any new event types should follow the same `{type, ...}` envelope.
- **Frontend API usage**: Components use Axios with relative paths (e.g., `/api/upload` in `FileUpload.jsx`, `/api/documents` in `Dashboard.jsx`); align backend route signatures with these expectations or update both sides together.
- **Settings UX**: `frontend/src/pages/Settings.jsx` now exposes reparse actions (all or newline/comma-delimited filenames) alongside blacklist management, surfaces asynchronous cleanup messaging in toasts, and reminds users that fuzzy matches (e.g. `series-22`) may queue many PDFs. Keep toast summaries informative (`Queued N`, `Skipped -> reason`) when adjusting response payloads.
- **UI conventions**: Chakra UI drives layout; keep new components within `frontend/src/components` and wire them through `Dashboard` or `PDFView` using the existing context providers.
- **Search UX**: The navigation now includes a dedicated Search page (`/search`) that calls `/api/search`; backend pagination parameters (`limit`, `offset`) must stay in sync with the MCP `/query` endpoint.
- **Storage hygiene**: Large artifacts accumulate in `uploads/`, `data/lance_db/`, and `data/chroma_db/`; `backend/tests/test_query.py --reset` invokes `VectorStore.reset()` for clean test runs.
- **Diagnostics**: Logging is already configured in `pdf_processor` and `vector_store`; prefer `logger.info`/`logger.error` over prints when extending backend workflows to keep messages consistent across async tasks.
- **Testing utility**: `python backend/tests/test_query.py --query` exercises vector searches; other flags (`--list`, `--process`, `--reset`) help validate ingestion without hitting the HTTP API.
- **When adding features**: Mirror new REST routes with accompanying WebSocket or MCP hooks if they affect long-running tasks, and document any new background events so front-end consumers can subscribe safely.
- **Syntax hygiene**: Before shipping changes, run `python -m compileall` against modified Python modules and `docker compose config` (or another YAML parser) over updated YAML to catch indentation or formatting issues early.
- **Testing**: Test new features locally using the provided `docker-compose.sample.yml` (copy to `docker-compose.yml`), thoroughly before pushing changes.
- **Python Use**: Use python3 locally instead of python.
- **Cleanup**: After running compiles or builds, remove generated artifacts (e.g., `__pycache__`, build outputs, locally built Docker images) unless the user explicitly asks to keep them.
- **Committing changes**: Ensure pushing commits to master and branches.