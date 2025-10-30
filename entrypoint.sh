#!/bin/sh
set -eu

# Ensure runtime directories exist and are owned by the application user.
ensure_dir_owned() {
    dir_path="$1"
    owner="$2"
    group="$3"

    if [ -z "$dir_path" ]; then
        return
    fi

    mkdir -p "$dir_path"
    chown -R "$owner":"$group" "$dir_path"
}

APP_USER="appuser"
APP_GROUP="appgroup"

# Prepare SQLite directory if configured.
if [ -n "${PDF_RAG_DB_PATH:-}" ]; then
    ensure_dir_owned "$(dirname "$PDF_RAG_DB_PATH")" "$APP_USER" "$APP_GROUP"
fi

# Uploads and vector store directories live under /app/backend.
ensure_dir_owned "/app/backend/uploads" "$APP_USER" "$APP_GROUP"
ensure_dir_owned "/app/backend/chroma_db" "$APP_USER" "$APP_GROUP"

# Sentence transformer cache directory may be overridden via env vars.
if [ -n "${SENTENCE_TRANSFORMERS_HOME:-}" ]; then
    ensure_dir_owned "${SENTENCE_TRANSFORMERS_HOME}" "$APP_USER" "$APP_GROUP"
fi

exec gosu "$APP_USER":"$APP_GROUP" "$@"
