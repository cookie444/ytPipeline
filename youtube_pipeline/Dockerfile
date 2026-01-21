# Dockerfile for YouTube Audio Processing Pipeline
FROM python:3.11-slim

# Install system dependencies including Node.js for yt-dlp signature solving
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /app/output

# Create default config.json if it doesn't exist
RUN if [ ! -f /app/config.json ]; then \
    echo '{"server": {"host": null, "port": 22, "username": null, "password": null, "key_file": null, "remote_path": "/tmp/uploads/"}, "cleanup": true}' > /app/config.json; \
    fi

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV TORCHAUDIO_USE_SOUNDFILE=1

# Expose port (Render will set PORT env var)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT:-5000}/health')" || exit 1

# Run the application
CMD ["python", "api_server.py"]

