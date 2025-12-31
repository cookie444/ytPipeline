# YouTube Audio Processing Pipeline

A cloud-based pipeline system that automatically:
1. Searches YouTube for a song
2. Downloads the audio in highest quality
3. Separates the audio into stems (drums, vocals, guitar, synth)
4. Creates a ZIP archive
5. Uploads to your server

## Features

- **Automated YouTube Search**: Finds songs by query
- **High-Quality Audio Download**: Downloads best available audio quality
- **AI-Powered Source Separation**: Uses Demucs for professional-quality stem separation
- **Cloud-Ready**: Dockerized for easy cloud deployment
- **Secure Upload**: SCP-based secure file transfer

## Prerequisites

- Python 3.11+
- FFmpeg (for audio processing)
- Docker and Docker Compose (for cloud deployment)
- Server with SSH/SCP access (for file uploads)

## Setup

### 1. Configuration

Copy the example configuration file and fill in your server details:

```bash
cp config.json.example config.json
```

Edit `config.json` with your server credentials:

```json
{
  "server": {
    "host": "your-server.com",
    "port": 22,
    "username": "your-username",
    "password": "your-password",
    "key_file": null,
    "remote_path": "/home/username/uploads/"
  },
  "cleanup": true
}
```

**Security Note**: For production, use SSH key authentication instead of passwords:
- Set `"key_file": "/path/to/your/private/key"` 
- Set `"password": null`

### 2. Local Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the pipeline
python pipeline.py "artist name - song title"
```

### 3. Docker Deployment

#### Build the Docker image:

```bash
docker build -t youtube-pipeline .
```

#### Run a single job:

```bash
docker run --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  youtube-pipeline "artist name - song title"
```

#### Using Docker Compose:

```bash
# Edit docker-compose.yml to add your query in the command section
docker-compose up
```

## Cloud Deployment Options

### AWS ECS / Fargate

1. Build and push to ECR:
```bash
aws ecr create-repository --repository-name youtube-pipeline
docker tag youtube-pipeline:latest <account>.dkr.ecr.<region>.amazonaws.com/youtube-pipeline:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/youtube-pipeline:latest
```

2. Create ECS task definition with the image
3. Run tasks via API, CLI, or EventBridge scheduler

### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/<project-id>/youtube-pipeline

# Deploy
gcloud run deploy youtube-pipeline \
  --image gcr.io/<project-id>/youtube-pipeline \
  --platform managed \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600
```

### Azure Container Instances

```bash
# Build and push to ACR
az acr build --registry <registry-name> --image youtube-pipeline:latest .

# Run container
az container create \
  --resource-group <resource-group> \
  --name youtube-pipeline \
  --image <registry-name>.azurecr.io/youtube-pipeline:latest \
  --cpu 2 \
  --memory 4 \
  --command-line "python pipeline.py 'your query'"
```

### Kubernetes Job

Create a Kubernetes Job manifest:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: youtube-pipeline
spec:
  template:
    spec:
      containers:
      - name: pipeline
        image: youtube-pipeline:latest
        command: ["python", "pipeline.py", "your search query"]
        volumeMounts:
        - name: config
          mountPath: /app/config.json
          subPath: config.json
      volumes:
      - name: config
        configMap:
          name: pipeline-config
      restartPolicy: Never
```

## Usage

### Command Line

```bash
python pipeline.py "The Beatles - Hey Jude"
```

### Programmatic Usage

```python
from pipeline import YouTubePipeline

pipeline = YouTubePipeline(config_path="config.json")
success = pipeline.run("artist name - song title")
```

### API Integration

You can wrap this in a REST API using Flask/FastAPI:

```python
from flask import Flask, request, jsonify
from pipeline import YouTubePipeline

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_song():
    data = request.json
    query = data.get('query')
    
    pipeline = YouTubePipeline()
    success = pipeline.run(query)
    
    return jsonify({'success': success, 'query': query})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## Output

The pipeline creates a ZIP file containing:
- `drums.wav` - Drum track
- `vocals.wav` - Vocal track
- `guitar.wav` - Guitar track
- `synth.wav` - Synthesizer/other instruments track

The ZIP file is uploaded to your configured server path.

## Troubleshooting

### FFmpeg not found
Install FFmpeg:
- Ubuntu/Debian: `apt-get install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: Download from https://ffmpeg.org/

### Demucs model download
On first run, Demucs will download models (~1GB). Ensure sufficient disk space and network bandwidth.

### Memory issues
Audio separation is memory-intensive. For large files:
- Increase container memory limits
- Use GPU if available (modify `device='cuda'` in `pipeline.py`)

### Server upload failures
- Verify SSH credentials
- Check firewall rules allow port 22
- Ensure remote directory exists and is writable
- Test SSH connection manually: `ssh username@host`

## Performance

- **Download**: ~1-5 minutes (depends on video length and quality)
- **Separation**: ~5-15 minutes (depends on audio length and hardware)
- **Upload**: ~1-5 minutes (depends on file size and connection)

Total pipeline time: ~10-25 minutes per song

## License

This project is provided as-is for educational and personal use. Ensure you comply with YouTube's Terms of Service and copyright laws when using this tool.

## Contributing

Contributions welcome! Please open issues or pull requests for improvements.


