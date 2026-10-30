# Use Microsoft's official Playwright Python image
# All browsers (Chromium, Firefox, WebKit) and OS dependencies are pre-installed
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OUTPUT_DIR=/app/output \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Copy pyproject.toml and README.md first to leverage Docker caching
COPY pyproject.toml README.md ./

# Install our custom MCP package and lightweight dependencies
RUN pip install .

# Copy application code
COPY . .

# Ensure output directories exist
RUN mkdir -p /app/output/screenshots /app/output/pdfs

EXPOSE 8000

# Healthcheck to verify MCP endpoint is alive
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/mcp || exit 1

# Default startup command: streamable-http on port 8000
CMD ["playwright-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
