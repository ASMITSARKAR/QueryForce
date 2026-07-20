# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Model Cache (Bake HuggingFace models into image)
FROM python:3.11-slim as model-cache

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV HF_HOME=/app/model_cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache

# Download the sentence transformer model so it's baked into the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Stage 3: Runtime
FROM python:3.11-slim as runtime

WORKDIR /app

# Add curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy packages and model cache
COPY --from=builder /opt/venv /opt/venv
COPY --from=model-cache /app/model_cache /app/model_cache

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV HF_HOME=/app/model_cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache
ENV HF_HUB_OFFLINE=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy application source
COPY src/ /app/src/
COPY ui/ /app/ui/
# Copy the data folder (including analytics.db and metrics.yaml)
COPY data/ /app/data/

# Ensure data directories exist and are owned by appuser
RUN mkdir -p /app/data/chroma_persist && \
    chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

CMD sh -c "uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT:-8000}"
