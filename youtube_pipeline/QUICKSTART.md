# Quick Start Guide

Get the YouTube Audio Processing Pipeline running in 5 minutes!

## Prerequisites

- Python 3.11+ installed
- FFmpeg installed
- Docker (optional, for containerized deployment)

## Step 1: Setup Configuration

```bash
cd youtube_pipeline
cp config.json.example config.json
```

Edit `config.json` with your server details:
- `host`: Your server hostname or IP
- `username`: SSH username
- `password`: SSH password (or use `key_file` for key-based auth)
- `remote_path`: Where to upload files on the server

## Step 2: Install Dependencies

### Option A: Local Installation
```bash
pip install -r requirements.txt
```

### Option B: Using Make
```bash
make install
```

## Step 3: Run the Pipeline

### Command Line
```bash
python pipeline.py "The Beatles - Hey Jude"
```

### Using Make
```bash
make run QUERY="The Beatles - Hey Jude"
```

### Using Docker
```bash
# Build image
make build

# Run
make docker-run QUERY="The Beatles - Hey Jude"
```

## Step 4: Check Your Server

The processed files will be uploaded to your configured `remote_path` as a ZIP file named `separated_stems.zip`.

## What Happens?

1. **Search**: Finds the song on YouTube
2. **Download**: Downloads audio in highest quality (WAV format)
3. **Separate**: Uses AI to separate into stems:
   - `drums.wav`
   - `vocals.wav`
   - `guitar.wav`
   - `synth.wav`
4. **Package**: Creates a ZIP archive
5. **Upload**: Transfers to your server via SCP

## Troubleshooting

### "FFmpeg not found"
Install FFmpeg:
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt-get install ffmpeg`
- **Windows**: Download from https://ffmpeg.org/

### "Configuration file not found"
Make sure you've copied `config.json.example` to `config.json` and filled in your details.

### "Server connection failed"
- Verify SSH credentials
- Check firewall allows port 22
- Test manually: `ssh username@host`

### First run is slow
Demucs downloads AI models (~1GB) on first use. This is normal and only happens once.

## Next Steps

- Deploy to cloud: See `cloud_deploy.md`
- Use API server: `make api` then POST to `/process`
- Customize: Edit `pipeline.py` for different models or settings

## Example API Usage

Start the API server:
```bash
make api
```

Then in another terminal:
```bash
curl -X POST http://localhost:5000/process \
  -H "Content-Type: application/json" \
  -d '{"query": "The Beatles - Hey Jude"}'
```


