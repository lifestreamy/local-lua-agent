# Dockerfile — LocalScript API container
# Base: python:3.11-slim (Debian Bookworm)
# Installs: Lua 5.5 (Compiled from source) for luac syntax validation
# Runs: uvicorn on port 8080

FROM python:3.11-slim

# Install compilation tools, download Lua 5.5 alpha, compile, and clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl libreadline-dev && \
    curl -R -O https://www.lua.org/work/lua-5.5.0-alpha.tar.gz && \
    tar -zxf lua-5.5.0-alpha.tar.gz && \
    cd lua-5.5.0-alpha && \
    make linux test && \
    make install && \
    cd .. && \
    rm -rf lua-5.5.0-alpha lua-5.5.0-alpha.tar.gz && \
    apt-get purge -y build-essential curl && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Symlink the compiled Lua 5.5 to luac5.5 so our validator finds it instantly
RUN ln -sf /usr/local/bin/luac /usr/local/bin/luac5.5

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