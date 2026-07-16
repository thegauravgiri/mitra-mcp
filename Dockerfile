FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies if any are needed (none really since we use psycopg[binary])
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and source to install
COPY pyproject.toml /app/
COPY src /app/src/

# Install the package and its dependencies
RUN pip install --no-cache-dir .

# Expose the default port (optional, cloud providers override this)
EXPOSE 8000

# Run the server in SSE mode, dynamically listening on the port specified by $PORT (falls back to 8000)
CMD ["sh", "-c", "mitra start --transport sse --host 0.0.0.0 --port ${PORT:-8000}"]
