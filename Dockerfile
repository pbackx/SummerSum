FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY app/app_utils/.requirements.txt ./

# Install dependencies (system-wide inside the container)
RUN uv pip install --system -r .requirements.txt

# Copy the application source code files
COPY app/ ./app/
COPY frontend/ ./frontend/
COPY data/ ./data/
COPY deployment_metadata.json ./

# Expose port
EXPOSE 8080

# Start the application using uvicorn on the PORT env var (which is default 8080 on Cloud Run)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
