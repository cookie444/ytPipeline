FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY pipeline.py .
COPY api_server.py .
COPY config.json* ./

# Create directory for temporary files
RUN mkdir -p /tmp/youtube_pipeline

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEMUCS_CACHE_DIR=/app/.demucs_cache

# Default command (can be overridden)
CMD ["python", "pipeline.py"]

