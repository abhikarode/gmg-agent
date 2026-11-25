FROM scratch AS app-files
WORKDIR /app
COPY ai_agent.py member_enrichment.py people_match.py api.py directory_snapshot.py ./
COPY azure_storage.py inference_budget.py hosted_inference.py ./
COPY membership.py expertise.py expertise_catalog.json ./
COPY whatsapp_pilot.py seed_local_directory.py ./

FROM python:3.11-slim-bookworm AS azure-deps
WORKDIR /build
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --no-compile --target /opt/gmg-deps -r requirements.txt

FROM gcr.io/distroless/python3-debian12:nonroot AS azure
WORKDIR /app
ENV PYTHONPATH=/opt/gmg-deps PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=azure-deps /opt/gmg-deps /opt/gmg-deps
COPY --from=app-files /app/ /app/
EXPOSE 8000
ENTRYPOINT ["/usr/bin/python3", "-m", "uvicorn"]
CMD ["api:app", "--host", "127.0.0.1", "--port", "8000"]

FROM python:3.11-slim AS local

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --from=app-files /app/ /app/

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Expose port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run the FastAPI server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
