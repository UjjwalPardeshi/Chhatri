# Chhatri backend (SPEC §23)
# Build: backend FastAPI + uvicorn (factory pattern)
# Run: uvicorn --factory chhatri.api.app:create_app :8000
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend/ .

# Install Python dependencies (production; dev tools not needed in runtime)
RUN pip install --no-cache-dir -e .

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health', timeout=2)" || exit 1

# Expose port
EXPOSE 8000

# Default env
ENV PYTHONUNBUFFERED=1
ENV CHHATRI_PUBLIC_URL=http://backend:8000

# Run factory app
CMD ["uvicorn", "--factory", "chhatri.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
