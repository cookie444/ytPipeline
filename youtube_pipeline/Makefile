.PHONY: help install build run test clean docker-build docker-run api

help:
	@echo "YouTube Audio Processing Pipeline - Makefile"
	@echo ""
	@echo "Available commands:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make build        - Build Docker image"
	@echo "  make run QUERY=   - Run pipeline locally (e.g., make run QUERY='artist - song')"
	@echo "  make docker-run QUERY= - Run pipeline in Docker"
	@echo "  make api          - Start API server"
	@echo "  make clean        - Clean temporary files"
	@echo "  make test         - Test configuration"

install:
	pip install -r requirements.txt

build:
	docker build -t youtube-pipeline:latest .

run:
	@if [ -z "$(QUERY)" ]; then \
		echo "Error: QUERY is required. Usage: make run QUERY='artist - song'"; \
		exit 1; \
	fi
	python pipeline.py "$(QUERY)"

docker-run:
	@if [ -z "$(QUERY)" ]; then \
		echo "Error: QUERY is required. Usage: make docker-run QUERY='artist - song'"; \
		exit 1; \
	fi
	docker run --rm \
		-v $(PWD)/config.json:/app/config.json:ro \
		youtube-pipeline:latest "$(QUERY)"

api:
	python api_server.py

test:
	@echo "Testing configuration..."
	@if [ ! -f config.json ]; then \
		echo "Error: config.json not found. Copy config.json.example to config.json and configure it."; \
		exit 1; \
	fi
	@python -c "import json; json.load(open('config.json')); print('✓ Configuration file is valid')"

clean:
	rm -rf __pycache__ *.pyc .demucs_cache output/ *.wav *.mp3 *.zip
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true


