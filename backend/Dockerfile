FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies (libgomp for PyTorch OpenMP, curl for container healthchecks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first to avoid downloading multi-gigabyte CUDA packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install application dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-privileged user and prepare directories
RUN useradd -m -u 1001 appuser && \
    mkdir -p /app/artifacts /app/data && \
    chown -R appuser:appuser /app

# Copy application source code and catalog datasets
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser data/ ./data/
COPY --chown=appuser:appuser artifacts/ ./artifacts/

USER appuser

EXPOSE 8000

# Container healthcheck using backend /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
