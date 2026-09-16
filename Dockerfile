# ================================================================
# Agentic AI Traffic Intelligence — Production Dockerfile
# Optimized for FastAPI Backend + TraCI + Eclipse SUMO Simulation
# Deployable to Render and any container runtime.
# ================================================================

FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    SUMO_HOME=/usr/share/sumo \
    PATH="/usr/share/sumo/bin:${PATH}" \
    PORT=8000

# Install Eclipse SUMO, SUMO tools, curl for health checks, and essential dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sumo \
    sumo-tools \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies (cached layer)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir traci sumolib

# Copy the complete application codebase into the container
COPY . /app/

# Ensure all required runtime directories exist
RUN mkdir -p /app/data/raw /app/data/results /app/logs /app/models

# Expose default backend port
EXPOSE 8000

# Healthcheck for container orchestrators (Render / Kubernetes / Docker)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start the FastAPI backend with uvicorn on the PORT assigned by Render (defaults to 8000)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
