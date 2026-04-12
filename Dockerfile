# Dockerfile — LocalScript API container
# Base: python:3.11-slim (Debian Bookworm)
# Installs: lua5.4 for luac syntax validation
# Runs: uvicorn on port 8080

FROM python:3.11-slim

# Install luac (syntax validator) — available in Debian repos as lua5.4
RUN apt-get update && \
    apt-get install -y --no-install-recommends lua5.4 && \
    ln -sf /usr/bin/luac5.4 /usr/local/bin/luac && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY api/ ./api/
COPY prompts/ ./prompts/

# Expose API port (matches localscript-openapi.yaml server url)
EXPOSE 8080

# Run with uvicorn — single worker is fine for hackathon demo
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]