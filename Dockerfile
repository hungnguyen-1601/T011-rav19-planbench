# ---- Stage 1: Build ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    PYTHONPATH=/app/packages/schemas:/app/packages/planning:/app/packages/metrics:/app/packages/benchmark:/app/packages/decision:/app/packages/explanation:/app/packages/plugin_sdk:/app/services/simulator:/app/services/tracking:/app/services/agent_service:/app/ml:/app/apps/api

# Security: Hugging Face Spaces expects non-root user UID 1000
RUN useradd -m -u 1000 appuser

# Copy application code
COPY . .

# Create data directory with correct ownership
RUN mkdir -p /app/data /data/artifacts /app/maps/custom /tmp/planbench_maps && chown -R appuser:appuser /app /data /tmp/planbench_maps

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/v1/health')" || exit 1

CMD ["sh", "-c", "uvicorn planbench_api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
