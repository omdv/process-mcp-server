# Use Python base image and install Node.js for supergateway
FROM python:3.13-slim

# Install Node.js, npm, and curl for health check
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application code
COPY mcp_server.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    npm_config_cache=/tmp/.npm

# Expose port for supergateway
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run supergateway wrapping the Python MCP server via npx
# Using streamableHttp in STATELESS mode - pagination handled via cursors in GraphQL variables
# Each request is independent; cursor state is maintained by the client (n8n/MCP Inspector)
CMD ["npx", "-y", "supergateway", "--port", "8000", "--cors", "--outputTransport", "streamableHttp", "--logLevel", "debug", "--stdio", "python3 mcp_server.py"]
