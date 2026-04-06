# Normalizer Worker - Data Transformation
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install --no-cache-dir pdm

# Copy dependency files
COPY pyproject.toml pdm.lock* ./

# Install dependencies only (not the project itself)
RUN pdm install --prod --no-lock --no-self

# Copy application code
COPY apps/normalizer ./apps/normalizer
COPY core ./core
COPY domain ./domain
COPY providers ./providers

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Add PDM bin directory to PATH
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "apps.normalizer.worker"]
