# Dockerfile — LocalScript API container
# Base: python:3.11-slim (Debian Bookworm)
# Installs: Lua 5.4 for luac syntax validation
# Runs: uvicorn on port 8080

FROM python:3.11-slim

# Install Lua 5.4 directly from the Debian repository
RUN apt-get update && \
    apt-get install -y --no-install-recommends lua5.4 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Symlink the binary so your Python validator can call `luac` or `luac5.4` seamlessly
RUN ln -sf /usr/bin/luac5.4 /usr/local/bin/luac && \
    ln -sf /usr/bin/luac5.4 /usr/local/bin/luac5.5

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY api/ ./api/
COPY prompts/ ./prompts/

# Expose API port
EXPOSE 8080

# Run with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]