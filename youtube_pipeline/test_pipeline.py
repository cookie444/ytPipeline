#!/usr/bin/env python3
"""
Diagnostic script to test the YouTube pipeline.
Run this to identify issues before processing songs.
"""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 60)
print("YouTube Pipeline Diagnostic Test")
print("=" * 60)
print()

# Test 1: Check Python version
print("[1] Python Version:")
print(f"    {sys.version}")
print()

# Test 2: Check required modules
print("[2] Checking Required Modules:")
required_modules = {
    'flask': 'Flask',
    'flask_cors': 'Flask-CORS',
    'yt_dlp': 'yt-dlp',
    'paramiko': 'paramiko',
    'scp': 'scp',
    'requests': 'requests',
}

missing = []
for module, name in required_modules.items():
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f"    [OK] {name}: {version}")
    except ImportError:
        print(f"    [MISSING] {name}")
        missing.append(name)

if missing:
    print(f"\n    ERROR: Missing modules: {', '.join(missing)}")
    print(f"    Install with: pip install --user {' '.join(missing)}")
print()

# Test 3: Check optional modules
print("[3] Checking Optional Modules (for processing):")
optional_modules = {
    'demucs': 'Demucs (audio separation)',
    'torch': 'PyTorch (ML framework)',
}

for module, name in optional_modules.items():
    try:
        __import__(module)
        print(f"    [OK] {name}")
    except ImportError:
        print(f"    [MISSING] {name} - Processing will fail without this")
print()

# Test 4: Check configuration
print("[4] Checking Configuration:")
try:
    from pipeline import YouTubePipeline
    pipeline = YouTubePipeline()
    print(f"    [OK] Config loaded: config.json")
    print(f"    [OK] Cookie file: {pipeline.cookie_file or 'Not found'}")
    
    server_config = pipeline.config.get('server', {})
    if server_config.get('host') and server_config.get('username'):
        print(f"    [OK] Server configured: {server_config.get('host')}")
    else:
        print(f"    [INFO] No server configured - upload will be skipped")
    
except Exception as e:
    print(f"    [ERROR] Failed to load pipeline: {e}")
    import traceback
    traceback.print_exc()
print()

# Test 5: Check file structure
print("[5] Checking File Structure:")
files_to_check = [
    'pipeline.py',
    'api_server.py',
    'index.html',
    'config.json',
    'static/style.css',
    'static/script.js',
]

for file in files_to_check:
    path = Path(file)
    if path.exists():
        size = path.stat().st_size
        print(f"    [OK] {file} ({size} bytes)")
    else:
        print(f"    [MISSING] {file}")
print()

# Test 6: Test YouTube search (quick test)
print("[6] Testing YouTube Search:")
try:
    from pipeline import YouTubePipeline
    pipeline = YouTubePipeline()
    test_query = "test song"
    print(f"    Testing search for: '{test_query}'")
    result = pipeline.search_youtube(test_query)
    if result:
        print(f"    [OK] Search works! Found: {result}")
    else:
        print(f"    [WARNING] Search returned no results")
except Exception as e:
    print(f"    [ERROR] Search failed: {e}")
    import traceback
    traceback.print_exc()
print()

# Test 7: Check FFmpeg
print("[7] Checking FFmpeg:")
try:
    import subprocess
    result = subprocess.run(['ffmpeg', '-version'], 
                          capture_output=True, 
                          text=True, 
                          timeout=5)
    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"    [OK] {version_line}")
    else:
        print(f"    [WARNING] FFmpeg returned error code")
except FileNotFoundError:
    print(f"    [MISSING] FFmpeg not found - audio processing will fail")
except Exception as e:
    print(f"    [ERROR] FFmpeg check failed: {e}")
print()

print("=" * 60)
print("Diagnostic Complete!")
print("=" * 60)
print()
print("If all tests pass, try processing a song.")
print("If tests fail, fix the issues above and try again.")

