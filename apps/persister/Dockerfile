# Persister Worker - Database Persistence
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install --no-cache-dir pdm

# Copy dependency files
COPY pyproject.toml pdm.lock* ./

# Install dependencies only (not the project itself)
RUN pdm install --prod --no-lock --no-self

# Copy application code
COPY apps/persister ./apps/persister
COPY core ./core
COPY domain ./domain

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Add PATH to include the PDM venv
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "apps.persister.worker"]
