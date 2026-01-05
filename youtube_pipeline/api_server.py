#!/usr/bin/env python3
"""
REST API server for the YouTube Audio Processing Pipeline with Web GUI.
Allows triggering the pipeline via HTTP requests with job queue system.
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import logging
import os
from pathlib import Path
import threading
import atexit
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
                        upload_to_server: bool, progress_callback) -> dict:
    """
    Process a pipeline job (called by queue worker).
    
    Args:
        query: YouTube URL or search query
        output_dir: Output directory path
        upload_to_server: Whether to upload to server
        progress_callback: Function to call with (progress, message)
    
    Returns:
        Dictionary with result information
    """
    try:
        progress_callback(10, "Initializing pipeline...")
        pipeline = YouTubePipeline(config_path=CONFIG_PATH, output_dir=output_dir)
        
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

