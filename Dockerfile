# syntax=docker/dockerfile:1

# --- Frontend build stage ----------------------------------------------------
FROM node:20 AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps

COPY frontend/ ./
RUN npm run build

# --- Backend runtime stage ---------------------------------------------------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies required for PyMuPDF, sentence-transformers, and friends
RUN apt-get update \
     && apt-get install -y --no-install-recommends \
         build-essential \
         curl \
         gosu \
         libglib2.0-0 \
         libgl1 \
         tesseract-ocr \
     && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management (matches project docs)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv
ENV PATH="/root/.local/bin:${PATH}"

COPY backend/requirements.txt ./backend/requirements.txt
RUN uv pip install --system --no-cache -r backend/requirements.txt

# Copy backend sources and supporting scripts
COPY backend/ ./backend/
COPY run.py ./
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Bring built frontend assets into the backend static directory
COPY --from=frontend-builder /app/frontend/dist/ ./backend/app/static/

# Ensure expected data directories exist
RUN mkdir -p backend/uploads backend/chroma_db \
    && ln -sf /app/backend/uploads /app/uploads \
    && ln -sf /app/backend/app/static /app/backend/static

EXPOSE 8000 7800
ENV APP_PORT=8000
ENV MCP_PORT=7800
ENV SENTENCE_TRANSFORMERS_HOME=/home/appuser/.cache/torch/sentence_transformers
ARG PUID=1000
ARG PGID=1000
RUN groupadd -g ${PGID} appgroup && useradd -u ${PUID} -g appgroup -m appuser \
    && mkdir -p /home/appuser/.cache/torch/sentence_transformers \
    && chown -R appuser:appgroup backend /home/appuser/.cache
USER root

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uv", "run", "run.py"]
