#!/usr/bin/env python3
"""
REST API server for the YouTube Audio Processing Pipeline with Web GUI.
Allows triggering the pipeline via HTTP requests with job queue system.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import os
from pathlib import Path
import threading
import atexit
from typing import Optional
from pipeline import YouTubePipeline
from queue_manager import QueueManager

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
CORS(app)  # Enable CORS for API access

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_PATH = os.getenv('CONFIG_PATH', 'config.json')
PORT = int(os.getenv('PORT', 5000))
HOST = os.getenv('HOST', '0.0.0.0')

# Initialize queue manager
queue_manager = QueueManager()


@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files explicitly."""
    return send_from_directory(STATIC_DIR, filename)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
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
        success = pipeline.run(query, upload_to_server=upload_to_server)
        
        if success:
            progress_callback(100, "Processing completed successfully!")
            return {
                'success': True,
                'query': query,
                'message': 'Song processed successfully'
            }
        else:
            raise Exception("Pipeline execution failed")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Pipeline job error: {error_msg}")
        raise Exception(f"Pipeline error: {error_msg}")


@app.route('/process', methods=['POST'])
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
def get_queue_info():
    """Get information about the current queue."""
    return jsonify({
        'success': True,
        'queue_length': queue_manager.get_queue_length(),
        'current_job': queue_manager.current_job
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Get API status."""
    return jsonify({
        'status': 'running',
        'config_path': CONFIG_PATH,
        'queue_length': queue_manager.get_queue_length()
    })


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

