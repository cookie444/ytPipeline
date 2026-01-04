#!/usr/bin/env python3
"""
REST API server for the YouTube Audio Processing Pipeline with Web GUI.
Allows triggering the pipeline via HTTP requests.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import os
from pathlib import Path
import threading
from pipeline import YouTubePipeline

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


@app.route('/process', methods=['POST'])
def process_song():
    """
    Process a YouTube song.
    
    Request body:
    {
        "query": "artist name - song title" or YouTube URL,
        "output_dir": "/path/to/output" (optional),
        "upload_to_server": true/false (optional, default: false)
    }
    
    Returns:
    {
        "success": true/false,
        "query": "search query",
        "message": "status message"
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
        logger.info(f"Processing request for query: {query}")
        if output_dir:
            logger.info(f"Output directory specified: {output_dir}")
        logger.info(f"Upload to server: {upload_to_server}")
        
        # Run pipeline with output directory and upload flag
        pipeline = YouTubePipeline(config_path=CONFIG_PATH, output_dir=output_dir)
        
        success = pipeline.run(query, upload_to_server=upload_to_server)
        
        if success:
            logger.info(f"Successfully processed: {query}")
            return jsonify({
                'success': True,
                'query': query,
                'message': 'Song processed and uploaded successfully'
            }), 200
        else:
            logger.error(f"Pipeline failed for: {query}")
            return jsonify({
                'success': False,
                'query': query,
                'message': 'Pipeline execution failed - check server logs for details'
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/status', methods=['GET'])
def status():
    """Get API status."""
    return jsonify({
        'status': 'running',
        'config_path': CONFIG_PATH
    })


if __name__ == '__main__':
    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)
    
    logger.info(f"Starting API server on {HOST}:{PORT}")
    logger.info(f"Web interface available at http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)

