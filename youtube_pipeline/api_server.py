#!/usr/bin/env python3
"""
REST API server for the YouTube Audio Processing Pipeline with Web GUI.
Allows triggering the pipeline via HTTP requests with job queue system.
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for, Response
from flask_cors import CORS
import logging
import os
from pathlib import Path
import threading
import atexit
import tempfile
from typing import Optional
from functools import wraps
from werkzeug.utils import secure_filename
from pipeline import YouTubePipeline
from queue_manager import QueueManager
import secrets

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
COOKIES_DIR = BASE_DIR  # Store cookies in the app directory

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
CORS(app)  # Enable CORS for API access

# Session configuration for password protection
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_PATH = os.getenv('CONFIG_PATH', 'config.json')
PORT = int(os.getenv('PORT', 5000))
HOST = os.getenv('HOST', '0.0.0.0')
# Password protection - set via environment variable
APP_PASSWORD = os.getenv('APP_PASSWORD', 'changeme123')

# Initialize queue manager
queue_manager = QueueManager()


def login_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated', False):
            if request.path.startswith('/static/'):
                # Allow static files without authentication
                return f(*args, **kwargs)
            if request.path == '/login' or request.path == '/api/login':
                return f(*args, **kwargs)
            # For API endpoints, return 401
            if request.path.startswith('/api/') or request.path.startswith('/process') or request.path.startswith('/status'):
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            # For HTML pages, redirect to login
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET'])
def login_page():
    """Serve the login page."""
    if session.get('authenticated', False):
        return redirect(url_for('index'))
    return send_from_directory(BASE_DIR, 'login.html')


@app.route('/api/login', methods=['POST'])
def login():
    """Handle login authentication."""
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        if password == APP_PASSWORD:
            session['authenticated'] = True
            logger.info("User authenticated successfully")
            return jsonify({
                'success': True,
                'message': 'Authentication successful'
            }), 200
        else:
            logger.warning("Failed login attempt")
            return jsonify({
                'success': False,
                'error': 'Invalid password'
            }), 401
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Handle logout."""
    session.pop('authenticated', None)
    logger.info("User logged out")
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200


@app.route('/')
@login_required
def index():
    """Serve the main HTML page."""
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files explicitly."""
    return send_from_directory(STATIC_DIR, filename)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint (public, no auth required)."""
    return jsonify({'status': 'healthy', 'service': 'youtube-pipeline'})


def process_pipeline_job(query: str, output_dir: Optional[str], 
                        upload_to_server: bool, progress_callback, job_id: Optional[str] = None) -> dict:
    """
    Process a pipeline job (called by queue worker).
    
    Args:
        query: YouTube URL or search query
        output_dir: Output directory path
        upload_to_server: Whether to upload to server
        progress_callback: Function to call with (progress, message)
        job_id: Optional job ID to check for uploaded audio
    
    Returns:
        Dictionary with result information
    """
    try:
        progress_callback(10, "Initializing pipeline...")
        pipeline = YouTubePipeline(config_path=CONFIG_PATH, output_dir=output_dir)
        
        # Check if audio was uploaded client-side
        uploaded_audio = None
        if job_id:
            job_status = queue_manager.get_job_status(job_id)
            if job_status and job_status.get('metadata', {}).get('uploaded_audio'):
                uploaded_audio = Path(job_status['metadata']['uploaded_audio'])
                if uploaded_audio.exists():
                    logger.info(f"Using client-side uploaded audio: {uploaded_audio}")
                    progress_callback(30, "Using client-side downloaded audio...")
                    audio_file = uploaded_audio
                else:
                    logger.warning(f"Uploaded audio file not found: {uploaded_audio}")
                    uploaded_audio = None
        
        if not uploaded_audio:
            progress_callback(20, "Searching YouTube...")
            video_url = pipeline.search_youtube(query)
            if not video_url:
                raise Exception("Failed to find video on YouTube")
            
            progress_callback(30, "Downloading audio...")
            try:
                audio_file = pipeline.download_audio(video_url, pipeline.temp_dir)
                if not audio_file:
                    raise Exception("Download failed: No audio file returned from download_audio. This may indicate the video has no audio or the download was interrupted.")
            except Exception as e:
                error_detail = str(e)
                logger.error(f"Download error details: {error_detail}")
                # Log the full exception for debugging
                import traceback
                logger.error(f"Download exception traceback: {traceback.format_exc()}")
                # Check if it's an age-restricted or authentication issue
                if any(keyword in error_detail.lower() for keyword in ['age', 'sign in', 'cookie', 'authentication', 'confirm your age']):
                    raise Exception(f"Download failed (authentication required): {error_detail}. For age-restricted videos, you need to upload a fresh cookies.txt file to the Render service.")
                # Preserve the original error message
                raise Exception(f"Download failed: {error_detail}")
        
        progress_callback(50, "Separating audio into stems...")
        stems_dir = pipeline.temp_dir / "stems"
        stems_dir.mkdir(exist_ok=True)
        stems = pipeline.separate_audio(audio_file, stems_dir)
        if not stems:
            raise Exception("Failed to separate audio")
        
        progress_callback(80, "Creating ZIP archive...")
        zip_file = pipeline.create_zip(stems, pipeline.output_dir, title=pipeline.video_title)
        
        if upload_to_server:
            progress_callback(90, "Uploading to server...")
            server_config = pipeline.config.get('server', {})
            if server_config.get('host') and server_config.get('username'):
                pipeline.upload_to_server(zip_file, server_config)
            else:
                logger.warning("Server upload requested but server not configured")
        
        progress_callback(100, "Processing completed successfully!")
        return {
            'success': True,
            'query': query,
            'message': 'Song processed successfully',
            'zip_file': str(zip_file) if zip_file else None
        }
            
    except Exception as e:
        error_msg = str(e)
        import traceback
        full_traceback = traceback.format_exc()
        logger.error(f"Pipeline job error: {error_msg}")
        logger.error(f"Full traceback: {full_traceback}")
        # Preserve the original error message (don't add "Pipeline error:" prefix if it's already there)
        if error_msg.startswith("Pipeline error:"):
            raise Exception(error_msg)
        else:
            raise Exception(f"Pipeline error: {error_msg}")


@app.route('/process', methods=['POST'])
@login_required
def process_song():
    """
    Queue a YouTube song for processing.
    
    Request body:
    {
        "query": "artist name - song title" or YouTube URL,
        "output_dir": "/path/to/output" (optional),
        "upload_to_server": true/false (optional, default: false)
    }
    
    Returns:
    {
        "success": true,
        "job_id": "unique-job-id",
        "message": "Job queued successfully",
        "queue_position": 1
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing "query" in request body'
            }), 400
        
        query = data['query']
        output_dir = data.get('output_dir')
        upload_to_server = data.get('upload_to_server', False)
        
        # Add job to queue
        job_id = queue_manager.add_job(
            query=query,
            output_dir=output_dir,
            upload_to_server=upload_to_server
        )
        
        queue_position = queue_manager.get_queue_length()
        
        logger.info(f"Job {job_id} queued for query: {query} (position: {queue_position})")
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Job queued successfully',
            'queue_position': queue_position
        }), 202  # 202 Accepted
            
    except Exception as e:
        logger.error(f"Error queueing request: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/status/<job_id>', methods=['GET'])
@login_required
def get_job_status(job_id: str):
    """
    Get the status of a processing job.
    
    Returns:
    {
        "job_id": "job-id",
        "status": "pending|processing|completed|failed",
        "progress": 0-100,
        "message": "status message",
        "queue_position": 0 (if processing) or position in queue,
        "result": {...} (if completed),
        "error": "error message" (if failed)
    }
    """
    status = queue_manager.get_job_status(job_id)
    
    if not status:
        return jsonify({
            'success': False,
            'error': 'Job not found'
        }), 404
    
    return jsonify({
        'success': True,
        **status
    }), 200


@app.route('/queue', methods=['GET'])
@login_required
def get_queue_info():
    """Get information about the current queue."""
    return jsonify({
        'success': True,
        'queue_length': queue_manager.get_queue_length(),
        'current_job': queue_manager.current_job
    }), 200


@app.route('/status', methods=['GET'])
@login_required
def status():
    """Get API status."""
    # Check if cookies.txt exists
    cookies_file = Path(COOKIES_DIR) / 'cookies.txt'
    has_cookies = cookies_file.exists()
    cookies_age = None
    if has_cookies:
        import time
        cookies_age = (time.time() - cookies_file.stat().st_mtime) / (24 * 3600)  # Age in days
    
    return jsonify({
        'status': 'running',
        'config_path': CONFIG_PATH,
        'queue_length': queue_manager.get_queue_length(),
        'has_cookies': has_cookies,
        'cookies_age_days': round(cookies_age, 1) if cookies_age else None
    })


@app.route('/api/upload-cookies', methods=['POST'])
@login_required
def upload_cookies():
    """Upload cookies.txt file for YouTube authentication."""
    try:
        if 'cookies' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided. Please select a cookies.txt file.'
            }), 400
        
        file = request.files['cookies']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Validate filename
        filename = secure_filename(file.filename)
        if not filename.lower().endswith('.txt'):
            return jsonify({
                'success': False,
                'error': 'File must be a .txt file'
            }), 400
        
        # Save to cookies.txt in the app directory
        cookies_path = Path(COOKIES_DIR) / 'cookies.txt'
        file.save(str(cookies_path))
        
        # Verify the file was saved and has content
        if not cookies_path.exists():
            return jsonify({
                'success': False,
                'error': 'Failed to save cookies file'
            }), 500
        
        file_size = cookies_path.stat().st_size
        if file_size == 0:
            return jsonify({
                'success': False,
                'error': 'Uploaded file is empty'
            }), 400
        
        logger.info(f"Cookies file uploaded successfully: {cookies_path} ({file_size} bytes)")
        
        return jsonify({
            'success': True,
            'message': f'Cookies file uploaded successfully ({file_size} bytes)',
            'file_size': file_size
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading cookies: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Error uploading cookies: {str(e)}'
        }), 500


@app.route('/api/cookies-status', methods=['GET'])
@login_required
def cookies_status():
    """Get status of cookies.txt file."""
    cookies_file = Path(COOKIES_DIR) / 'cookies.txt'
    has_cookies = cookies_file.exists()
    
    result = {
        'success': True,
        'has_cookies': has_cookies
    }
    
    if has_cookies:
        import time
        cookies_age = (time.time() - cookies_file.stat().st_mtime) / (24 * 3600)
        file_size = cookies_file.stat().st_size
        result.update({
            'age_days': round(cookies_age, 1),
            'file_size': file_size,
            'is_recent': cookies_age < 7
        })
    
    return jsonify(result), 200


@app.route('/api/get-download-script', methods=['POST'])
@login_required
def get_download_script():
    """Generate a downloadable script for client-side YouTube download."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request body'
            }), 400
        
        # Accept either video_url or query (search query)
        video_url = data.get('video_url') or data.get('query')
        if not video_url:
            return jsonify({
                'success': False,
                'error': 'Missing "video_url" or "query" in request body'
            }), 400
        
        job_id = data.get('job_id', 'unknown')
        
        # Get the base URL (handle both local and Render)
        base_url = request.host_url.rstrip('/')
        if not base_url.startswith('http'):
            # Fallback for local development
            base_url = f"http://{request.host}"
        
        # Generate Python script for client-side download
        script_content = f'''#!/usr/bin/env python3
"""
Client-side YouTube downloader - runs on your machine using YOUR IP address
This bypasses YouTube's bot detection by using your residential IP instead of Render's datacenter IP.

Usage:
    python download_client_side.py [RENDER_PASSWORD]

Requirements:
    pip install yt-dlp requests
"""

import yt_dlp
import requests
import sys
import os
from pathlib import Path

# Configuration
RENDER_URL = "{base_url}"
QUERY = "{video_url}"  # Can be URL or search query
JOB_ID = "{job_id}"

def search_youtube(query):
    """Search YouTube if query is not a URL."""
    if query.startswith('http'):
        return query
    
    print(f"Searching YouTube for: {{query}}")
    ydl_opts = {{
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'default_search': 'ytsearch',
        'max_downloads': 1,
    }}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{{query}}", download=False)
            if info and 'entries' in info and len(info['entries']) > 0:
                video_url = info['entries'][0]['url']
                print(f"Found video: {{info['entries'][0].get('title', 'Unknown')}}")
                return video_url
    except Exception as e:
        print(f"Search failed: {{e}}")
    
    return None

def download_audio():
    """Download audio from YouTube using your IP address."""
    # Handle search query or direct URL
    video_url = QUERY
    if not QUERY.startswith('http'):
        video_url = search_youtube(QUERY)
        if not video_url:
            print("ERROR: Could not find video on YouTube")
            return False
    
    print(f"Downloading audio from: {{video_url}}")
    print("Using YOUR IP address (not Render's datacenter IP)...")
    
    # Create temp directory
    temp_dir = Path("temp_download")
    temp_dir.mkdir(exist_ok=True)
    
    # Configure yt-dlp options
    ydl_opts = {{
        'format': 'bestaudio/best',
        'postprocessors': [{{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }}],
        'outtmpl': str(temp_dir / 'audio.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
    }}
    
    # Try to use cookies from common locations
    cookie_paths = [
        Path.home() / '.config' / 'youtube-dl' / 'cookies.txt',
        Path('cookies.txt'),
        Path.home() / 'Downloads' / 'cookies.txt',
        Path.home() / 'Downloads' / 'www.youtube.com_cookies.txt',
    ]
    
    for cookie_path in cookie_paths:
        if cookie_path.exists():
            ydl_opts['cookiefile'] = str(cookie_path)
            print(f"Using cookies from: {{cookie_path}}")
            break
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # Find the downloaded file
        audio_files = list(temp_dir.glob('*.wav'))
        if not audio_files:
            audio_files = list(temp_dir.glob('*.m4a'))
        if not audio_files:
            audio_files = list(temp_dir.glob('*.mp3'))
        
        if not audio_files:
            print("ERROR: Could not find downloaded audio file")
            return False
        
        audio_file = audio_files[0]
        print(f"Downloaded: {{audio_file}} ({{audio_file.stat().st_size / 1024 / 1024:.2f}} MB)")
        return audio_file
        
    except Exception as e:
        print(f"ERROR: Download failed: {{e}}")
        return False

def upload_to_render(audio_file):
    """Upload downloaded audio to Render for processing."""
    print(f"\\nUploading to Render for stem separation...")
    
    # Get session token (you'll need to login first)
    session = requests.Session()
    
    # Try to login
    password = input("Enter Render password (or set RENDER_PASSWORD env var): ").strip()
    if not password:
        password = os.getenv('RENDER_PASSWORD', '')
    
    if not password:
        print("ERROR: Password required. Set RENDER_PASSWORD environment variable or enter when prompted.")
        return False
    
    login_response = session.post(
        f"{{RENDER_URL}}/api/login",
        json={{"password": password}}
    )
    
    if not login_response.ok:
        print(f"ERROR: Login failed: {{login_response.status_code}}")
        return False
    
    login_data = login_response.json()
    if not login_data.get('success'):
        print(f"ERROR: Login failed: {{login_data.get('error')}}")
        return False
    
    print("Login successful")
    
    # Upload audio file
    with open(audio_file, 'rb') as f:
        files = {{'audio': (audio_file.name, f, 'audio/wav')}}
        data = {{'job_id': JOB_ID}}
        upload_response = session.post(
            f"{{RENDER_URL}}/api/upload-audio",
            files=files,
            data=data
        )
    
    if not upload_response.ok:
        print(f"ERROR: Upload failed: {{upload_response.status_code}}")
        print(f"Response: {{upload_response.text}}")
        return False
    
    upload_data = upload_response.json()
    if upload_data.get('success'):
        print(f"SUCCESS: Audio uploaded! Job ID: {{upload_data.get('job_id')}}")
        print(f"Monitor progress at: {{RENDER_URL}}/status/{{upload_data.get('job_id')}}")
        return True
    else:
        print(f"ERROR: Upload failed: {{upload_data.get('error')}}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Client-Side YouTube Downloader")
    print("=" * 60)
    print(f"Video URL: {{VIDEO_URL}}")
    print(f"Job ID: {{JOB_ID}}")
    print("=" * 60)
    
    audio_file = download_audio()
    if audio_file:
        if upload_to_render(audio_file):
            print("\\n" + "=" * 60)
            print("SUCCESS: Audio downloaded and uploaded to Render!")
            print("Processing will continue on Render...")
            print("=" * 60)
            # Cleanup
            audio_file.unlink()
            temp_dir.rmdir()
            sys.exit(0)
        else:
            print("\\nUpload failed, but audio file is saved at:", audio_file)
            sys.exit(1)
    else:
        print("\\nDownload failed")
        sys.exit(1)
'''
        
        return Response(
            script_content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename=download_client_side.py'
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating download script: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Error generating script: {str(e)}'
        }), 500


@app.route('/api/get-download-url', methods=['POST'])
@login_required
def get_download_url():
    """Get direct download URL for YouTube video (for browser-based download)."""
    try:
        data = request.get_json()
        query = data.get('query')
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Missing query parameter'
            }), 400
        
        # Initialize pipeline to use its search/download logic
        pipeline = YouTubePipeline(CONFIG_PATH)
        
        # Handle search query or direct URL
        video_url = query
        if not query.startswith('http'):
            video_url = pipeline.search_youtube(query)
            if not video_url:
                return jsonify({
                    'success': False,
                    'error': 'Could not find video on YouTube'
                }), 404
        
        # Use yt-dlp to extract video info and get direct download URL
        # Use the same client configurations as the main download function
        import yt_dlp
        
        cookies_file = Path(COOKIES_DIR) / 'cookies.txt'
        
        # Build client configurations (same as pipeline.py)
        if cookies_file.exists():
            client_configs = [
                # Mobile clients WITHOUT cookies - best for bypassing bot detection
                {'player_client': ['android'], 'name': 'android', 'use_cookies': False},
                {'player_client': ['ios'], 'name': 'ios', 'use_cookies': False},
                {'player_client': ['mweb'], 'name': 'mweb', 'use_cookies': False},
                # Web/TV clients WITH cookies - for age-restricted content
                {'player_client': ['web'], 'name': 'web', 'use_cookies': True},
                {'player_client': ['tv', 'web'], 'name': 'tv+web', 'use_cookies': True},
                {'player_client': None, 'name': 'default', 'use_cookies': True},
            ]
        else:
            client_configs = [
                {'player_client': None, 'name': 'default', 'use_cookies': False},
                {'player_client': ['web'], 'name': 'web', 'use_cookies': False},
                {'player_client': ['ios'], 'name': 'ios', 'use_cookies': False},
                {'player_client': ['android'], 'name': 'android', 'use_cookies': False},
                {'player_client': ['mweb'], 'name': 'mweb', 'use_cookies': False},
            ]
        
        last_error = None
        for config in client_configs:
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': False,
                    'extract_flat': False,
                }
                
                if config['player_client']:
                    ydl_opts['player_client'] = config['player_client']
                
                if config['use_cookies'] and cookies_file.exists():
                    ydl_opts['cookiefile'] = str(cookies_file)
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    
                    # Get best audio format URL
                    formats = info.get('formats', [])
                    audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                    
                    if not audio_formats:
                        # Fallback to best format with audio
                        audio_formats = [f for f in formats if f.get('acodec') != 'none']
                    
                    if not audio_formats:
                        last_error = 'No audio format available'
                        continue
                    
                    # Get the best quality audio format
                    best_format = max(audio_formats, key=lambda f: f.get('abr', 0) or 0)
                    download_url = best_format.get('url')
                    
                    if not download_url:
                        last_error = 'Could not extract download URL'
                        continue
                    
                    return jsonify({
                        'success': True,
                        'download_url': download_url,
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'format': {
                            'abr': best_format.get('abr', 0),
                            'acodec': best_format.get('acodec', 'unknown'),
                            'ext': best_format.get('ext', 'm4a')
                        }
                    }), 200
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Error with client '{config['name']}': {last_error}, trying next...")
                continue
        
        # All clients failed
        logger.error(f"All clients failed. Last error: {last_error}")
        return jsonify({
            'success': False,
            'error': f'Failed to extract download URL: {last_error}'
        }), 500
            
    except Exception as e:
        logger.error(f"Error getting download URL: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/download-stems/<job_id>', methods=['GET'])
@login_required
def download_stems(job_id: str):
    """Download the stems ZIP file for a completed job."""
    try:
        job_status = queue_manager.get_job_status(job_id)
        
        if not job_status:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
        
        if job_status['status'] != 'completed':
            return jsonify({
                'success': False,
                'error': f'Job is not completed (status: {job_status["status"]})'
            }), 400
        
        result = job_status.get('result', {})
        zip_file_path = result.get('zip_file')
        
        if not zip_file_path:
            return jsonify({
                'success': False,
                'error': 'No ZIP file available for this job'
            }), 404
        
        zip_path = Path(zip_file_path)
        if not zip_path.exists():
            return jsonify({
                'success': False,
                'error': 'ZIP file not found on server'
            }), 404
        
        return send_from_directory(
            zip_path.parent,
            zip_path.name,
            as_attachment=True,
            download_name=zip_path.name
        )
        
    except Exception as e:
        logger.error(f"Error downloading stems: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/upload-audio', methods=['POST'])
@login_required
def upload_audio():
    """Accept pre-downloaded audio file from client for processing."""
    try:
        if 'audio' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No audio file provided'
            }), 400
        
        file = request.files['audio']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        job_id = request.form.get('job_id')
        if not job_id:
            return jsonify({
                'success': False,
                'error': 'Missing job_id'
            }), 400
        
        # Get job status
        job_status = queue_manager.get_job_status(job_id)
        if not job_status:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
        
        if job_status['status'] not in ['pending', 'processing']:
            return jsonify({
                'success': False,
                'error': f'Job is in {job_status["status"]} status, cannot upload audio'
            }), 400
        
        # Save uploaded audio file
        temp_dir = Path(tempfile.gettempdir()) / f"youtube_pipeline_{job_id}"
        temp_dir.mkdir(exist_ok=True)
        
        # Determine file extension
        filename = secure_filename(file.filename)
        if not filename.lower().endswith(('.wav', '.mp3', '.m4a', '.ogg', '.flac')):
            # Default to .wav if extension not recognized
            filename = f"audio.wav"
        
        audio_path = temp_dir / filename
        file.save(str(audio_path))
        
        # Verify file was saved
        if not audio_path.exists():
            return jsonify({
                'success': False,
                'error': 'Failed to save audio file'
            }), 500
        
        file_size = audio_path.stat().st_size
        if file_size == 0:
            return jsonify({
                'success': False,
                'error': 'Uploaded file is empty'
            }), 400
        
        logger.info(f"Audio file uploaded for job {job_id}: {audio_path} ({file_size} bytes)")
        
        # Update job to use uploaded audio (skip download step)
        # Store the audio path in job metadata
        if 'metadata' not in job_status:
            job_status['metadata'] = {}
        job_status['metadata']['uploaded_audio'] = str(audio_path)
        job_status['metadata']['skip_download'] = True
        
        # Update job status
        queue_manager.update_job_metadata(job_id, job_status['metadata'])
        
        return jsonify({
            'success': True,
            'message': f'Audio file uploaded successfully ({file_size} bytes)',
            'job_id': job_id,
            'file_size': file_size,
            'file_path': str(audio_path)
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading audio: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Error uploading audio: {str(e)}'
        }), 500


if __name__ == '__main__':
    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)
    
    # Start queue worker
    queue_manager.start_worker(process_pipeline_job)
    
    # Register cleanup function
    def cleanup():
        queue_manager.stop_worker()
        queue_manager.cleanup_old_jobs()
    
    atexit.register(cleanup)
    
    logger.info(f"Starting API server on {HOST}:{PORT}")
    logger.info(f"Web interface available at http://{HOST}:{PORT}")
    logger.info("Job queue system initialized")
    
    app.run(host=HOST, port=PORT, debug=False)

