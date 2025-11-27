# Multi-stage Dockerfile for BCN Art Compass
# Uses uv for fast Python dependency management

# Stage 1: Builder
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy pyproject.toml for dependency installation
COPY pyproject.toml ./

# Install dependencies using uv (syncs from pyproject.toml)
RUN uv pip install --system .

# Stage 2: Runtime
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY agents ./agents
COPY api ./api
COPY memory ./memory
COPY observability ./observability
COPY rag ./rag
COPY tools ./tools
COPY config.py ./config.py
COPY main.py ./main.py

# Copy data files
COPY data ./data

# Create storage directory for ChromaDB and profiles
RUN mkdir -p storage/chromadb

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
