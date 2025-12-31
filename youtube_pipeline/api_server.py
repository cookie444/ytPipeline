#!/usr/bin/env python3
"""
REST API server for the YouTube Audio Processing Pipeline.
Allows triggering the pipeline via HTTP requests.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from pipeline import YouTubePipeline

app = Flask(__name__)
CORS(app)  # Enable CORS for API access

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_PATH = os.getenv('CONFIG_PATH', 'config.json')
PORT = int(os.getenv('PORT', 5000))
HOST = os.getenv('HOST', '0.0.0.0')


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
        "query": "artist name - song title"
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
        logger.info(f"Processing request for query: {query}")
        
        # Initialize and run pipeline
        pipeline = YouTubePipeline(config_path=CONFIG_PATH)
        success = pipeline.run(query)
        
        if success:
            return jsonify({
                'success': True,
                'query': query,
                'message': 'Song processed and uploaded successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'query': query,
                'message': 'Pipeline execution failed'
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
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
    logger.info(f"Starting API server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)


