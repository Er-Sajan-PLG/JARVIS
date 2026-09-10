# Multi-stage Dockerfile for JARVIS
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim as runtime

WORKDIR /app

# Create non-root user
RUN groupadd -r jarvis && useradd -r -g jarvis jarvis

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=jarvis:jarvis app/ ./app/
COPY --chown=jarvis:jarvis prompts/ ./prompts/
COPY --chown=jarvis:jarvis config.yaml ./
COPY --chown=jarvis:jarvis pyproject.toml ./
COPY --chown=jarvis:jarvis README.md ./

# Create data directory
RUN mkdir -p /app/data && chown -R jarvis:jarvis /app/data

# Switch to non-root user
USER jarvis

# Health check (JSON form: httpx.raise_for_status() already exits non-zero on failure,
# so the shell `|| exit 1` was redundant — and shell form trips hadolint DL3025)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import httpx; httpx.get('http://localhost:8000/api/v1/health', timeout=5).raise_for_status()"]

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "app.main"]
