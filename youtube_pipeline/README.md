# ⚠️ DEPRECATED: YouTube Pipeline

**This project is deprecated due to YouTube API calls from Render being blocked.**

**Service Status: SUSPENDED** - The Render service has been suspended. Re-enable it to see only the working GUI in action: [Render Dashboard](https://dashboard.render.com/web/srv-d5e0u53uibrs73910fug)

YouTube's bot detection system blocks requests from Render's shared IP addresses, making it impossible to reliably download videos from YouTube using this service. Despite attempts to work around this (including proxy solutions, client-side downloads, and various yt-dlp configurations), the service cannot consistently bypass YouTube's restrictions.

## What This Project Was

A web service for downloading YouTube videos, extracting audio, and separating them into stems (vocals, drums, bass, etc.) using AI-powered source separation.

## Why It's Deprecated

- **IP Blocking**: Render's shared IP addresses are flagged by YouTube's bot detection
- **Proxy Limitations**: Local proxy solutions require keeping your computer running 24/7 and expose your residential IP
- **Client-Side Workarounds**: Browser-based solutions are unreliable and still require server-side processing
- **No Reliable Alternative**: YouTube's protections make automated downloads from cloud services impractical

## Alternative Solutions

If you need to extract stems from YouTube videos:

1. **Download locally** using yt-dlp on your own machine
2. **Use local stem separation** tools like Spleeter, Demucs, or LALAL.AI
3. **Use dedicated services** that have residential IP infrastructure (paid services)
4. **Manual download** + upload to a processing service

## Technical Details

The project used:
- **Backend**: Flask (Python) with yt-dlp for YouTube downloads
- **Frontend**: Vanilla JavaScript with a web-based UI
- **Stem Separation**: Spleeter (AI-powered source separation)
- **Hosting**: Render (cloud platform)
- **Docker**: Containerized deployment with FFmpeg and Node.js

## Files

- `pipeline.py` - Core YouTube download and stem separation logic
- `api_server.py` - Flask API server
- `static/` - Frontend HTML, CSS, and JavaScript
- `Dockerfile` - Container configuration
- `local_proxy.py` / `local_proxy_secure.py` - Proxy solutions (attempted workaround)

## License

This project is provided as-is for educational purposes.

