#!/usr/bin/env python3
"""
YouTube Audio Processing Pipeline
Downloads audio from YouTube, separates into stems, and uploads to server.
"""

import os
import sys
import json
import logging
import zipfile
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, List
import argparse

import yt_dlp
import subprocess
import paramiko
from scp import SCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YouTubePipeline:
    """Main pipeline class for YouTube audio processing."""
    
    def __init__(self, config_path: str = "config.json", output_dir: Optional[str] = None):
        """Initialize pipeline with configuration."""
        self.config = self._load_config(config_path)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="youtube_pipeline_"))
        logger.info(f"Using temporary directory: {self.temp_dir}")
        
        # Set output directory (where ZIP will be saved)
        if output_dir:
            # Convert to absolute path and create directory
            self.output_dir = Path(output_dir).resolve()
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Output directory: {self.output_dir} (absolute: {self.output_dir.absolute()})")
        else:
            # Default to temp_dir if no output_dir specified
            self.output_dir = self.temp_dir
            logger.info(f"No output directory specified, using temp directory")
        
        self.cookie_file = self._find_cookie_file()
        self.video_title = None  # Will be set during download
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {config_path} not found")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
    
    def _find_cookie_file(self) -> Optional[str]:
        """Find cookie file in common locations."""
        import time
        cookie_files = [
            '../cookies.txt',  # Parent directory (most likely location)
            '../www.youtube.com_cookies.txt',
            'cookies.txt',
            'www.youtube.com_cookies.txt',
            'youtube_cookies.txt',
        ]
        
        for cookie_file in cookie_files:
            cookie_path = Path(cookie_file)
            if cookie_path.exists():
                # Check if file is recent (less than 7 days old)
                file_age_days = (time.time() - cookie_path.stat().st_mtime) / (24 * 3600)
                if file_age_days > 7:
                    logger.warning(f"Cookie file {cookie_file} is {file_age_days:.1f} days old. Consider updating it.")
                else:
                    logger.info(f"Using cookie file: {cookie_file} (age: {file_age_days:.1f} days)")
                return str(cookie_path.resolve())  # Return absolute path
        
        logger.info("No cookie file found. Age-restricted videos may fail.")
        return None
    
    def search_youtube(self, query: str) -> Optional[str]:
        """
        Search YouTube for a song and return the first video URL.
        
        Args:
            query: Search query (song name, artist, etc.)
            
        Returns:
            YouTube video URL or None if not found
        """
        logger.info(f"Searching YouTube for: {query}")
        
        ydl_opts = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': True,
            'default_search': 'ytsearch1',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_url = f"ytsearch1:{query}"
                info = ydl.extract_info(search_url, download=False)
                
                if info and 'entries' in info and len(info['entries']) > 0:
                    video_id = info['entries'][0]['id']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    title = info['entries'][0].get('title', 'Unknown')
                    logger.info(f"Found video: {title} - {video_url}")
                    return video_url
                else:
                    logger.warning(f"No results found for query: {query}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return None
    
    def download_audio(self, video_url: str, output_path: Path) -> Optional[Path]:
        """
        Download audio from YouTube in highest quality.
        Handles age-restricted videos with cookie authentication.
        
        Args:
            video_url: YouTube video URL
            output_path: Path to save the audio file
            
        Returns:
            Path to downloaded audio file or None if failed
        """
        logger.info(f"Downloading audio from: {video_url}")
        
        # Build yt-dlp options with cookie support
        # Use mobile clients to avoid YouTube's challenge solving requirements
        ydl_opts = {
            # Flexible format selection - prefer audio, fallback to video with audio
            'format': 'bestaudio/best[height<=720]/best',
            'outtmpl': str(output_path / '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
            'age_limit': None,  # Don't restrict by age
            # Use mobile clients to avoid challenge solving (ios/android work better)
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android'],  # Mobile clients avoid challenges
                }
            },
            # Additional options
            'writesubtitles': False,
            'writeautomaticsub': False,
            'skip_download': False,
        }
        
        # Add cookie file if found
        if self.cookie_file:
            ydl_opts['cookiefile'] = self.cookie_file
            logger.info(f"Using authentication cookies from: {self.cookie_file}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get('title', 'audio')
                self.video_title = title  # Store for ZIP naming
                
                # Clean title for filename matching
                import re
                safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
                
                # Wait a moment for postprocessor to finish
                import time
                time.sleep(1)
                
                # Find the downloaded/converted WAV file
                wav_files = list(output_path.glob("*.wav"))
                if wav_files:
                    wav_file = wav_files[0]
                    logger.info(f"Downloaded audio to: {wav_file}")
                    return wav_file
                
                # If no WAV found, check for other audio formats
                audio_files = list(output_path.glob("*.m4a")) + list(output_path.glob("*.mp3")) + list(output_path.glob("*.ogg"))
                if audio_files:
                    logger.warning(f"Found audio file but not WAV: {audio_files[0]}")
                    logger.warning("Postprocessor may have failed. Trying to convert manually...")
                    # Could add manual conversion here if needed
                    return None
                
                # Check what files were actually downloaded
                all_files = list(output_path.glob("*"))
                logger.error(f"No audio file found. Downloaded files: {[f.name for f in all_files]}")
                logger.error("This video may not have audio available, or download failed.")
                return None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error downloading audio: {error_msg}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            
            # If age-restricted or sign-in required, try with different clients
            if any(keyword in error_msg.lower() for keyword in ['age', 'sign in', 'inappropriate', 'confirm your age']):
                logger.info("Age-restricted video detected. Trying alternative authentication methods...")
                
                # Strategy: Try different client combinations
                # Mobile clients (ios/android) avoid YouTube's challenge solving
                client_combos = [
                    ['ios'],  # iOS client - most reliable
                    ['android'],  # Android client
                    ['ios', 'android'],  # Try both
                    ['mweb'],  # Mobile web
                    ['web'],  # Web client as last resort (may need challenge solving)
                ]
                
                for clients in client_combos:
                    try:
                        logger.info(f"Retrying with client(s): {clients}")
                        ydl_opts_retry = ydl_opts.copy()
                        ydl_opts_retry['extractor_args'] = {
                            'youtube': {
                                'player_client': clients,
                            }
                        }
                        # Ensure cookie file is still included
                        if self.cookie_file:
                            ydl_opts_retry['cookiefile'] = self.cookie_file
                        
                            with yt_dlp.YoutubeDL(ydl_opts_retry) as ydl:
                                info = ydl.extract_info(video_url, download=True)
                                title = info.get('title', 'audio')
                                self.video_title = title  # Store for ZIP naming
                                wav_files = list(output_path.glob("*.wav"))
                                if wav_files:
                                    wav_file = wav_files[0]
                                    logger.info(f"Successfully downloaded audio to: {wav_file}")
                                    return wav_file
                    except Exception as e2:
                        logger.debug(f"Client {clients} failed: {e2}")
                        continue
                
                # If all methods failed
                logger.error("All download methods failed for age-restricted video.")
                if self.cookie_file:
                    logger.warning(f"Cookie file was used: {self.cookie_file}")
                    logger.warning("Possible issues:")
                    logger.warning("  1. Cookies may be expired - export fresh cookies from browser")
                    logger.warning("  2. Cookies may not include YouTube domain - ensure cookies.txt has .youtube.com cookies")
                    logger.warning("  3. Video may require additional verification")
                else:
                    logger.warning("No cookie file found. Export cookies from your browser:")
                    logger.warning("  - Install 'Get cookies.txt LOCALLY' extension")
                    logger.warning("  - Export cookies from YouTube while logged in")
                    logger.warning("  - Save as 'cookies.txt' in the project directory")
            
            return None
    
    def separate_audio(self, audio_path: Path, output_dir: Path) -> Dict[str, Path]:
        """
        Separate audio into stems: drums, vocals, guitar, synth.
        
        Args:
            audio_path: Path to input audio file
            output_dir: Directory to save separated stems
            
        Returns:
            Dictionary mapping stem names to file paths
        """
        logger.info(f"Separating audio: {audio_path}")
        
        # Check if Demucs is available
        try:
            import demucs
        except ImportError:
            logger.error("Demucs is not installed. Cannot separate audio.")
            logger.error("Install with: pip install --user demucs torch torchaudio")
            logger.error("Note: This requires ~2GB download for PyTorch and models")
            return {}
        
        try:
            # Sanitize filename to avoid encoding issues
            # Create a safe copy with ASCII-only filename in the same directory as original
            import re
            safe_name = re.sub(r'[^\w\s-]', '', audio_path.stem)
            safe_audio_path = audio_path.parent / f"{safe_name}_temp.wav"
            
            # Copy original to safe filename
            shutil.copy2(audio_path, safe_audio_path)
            logger.info(f"Using sanitized filename: {safe_audio_path.name}")
            
            # Use Demucs command-line interface for source separation
            # Demucs will create separate files for each stem
            # Note: Demucs v4+ uses -n for model name, not --model
            # Use --float32 to force WAV output and avoid torchcodec dependency issues
            cmd = [
                'python', '-m', 'demucs.separate',
                '-n', 'htdemucs',  # High-quality model (use -n not --model)
                '-d', 'cpu',  # Use 'cuda' if GPU available (use -d not --device)
                '--shifts', '1',
                '--float32',  # Force WAV output format (avoids torchcodec dependency)
                '-o', str(output_dir),  # Use -o not --out
                str(safe_audio_path)  # File path comes last
            ]
            
            logger.info(f"Running Demucs: {' '.join(cmd)}")
            
            # Set environment to use UTF-8 encoding and force soundfile backend
            import os as os_module
            env = os_module.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            # Force torchaudio to use soundfile instead of torchcodec
            env['TORCHAUDIO_USE_SOUNDFILE'] = '1'
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't fail immediately, check if files were created
                timeout=3600,  # 1 hour timeout
                env=env,
                encoding='utf-8',
                errors='replace'  # Replace encoding errors instead of failing
            )
            
            # Log Demucs output for debugging
            if result.stdout:
                logger.info(f"Demucs stdout (last 1000 chars):\n{result.stdout[-1000:]}")
            if result.stderr:
                logger.warning(f"Demucs stderr (last 1000 chars):\n{result.stderr[-1000:]}")
            logger.info(f"Demucs exit code: {result.returncode}")
            
            # Check if Demucs actually created files even if it returned non-zero
            # Demucs creates a structure like: output_dir/htdemucs/track_name/stem.wav
            # We need to find and rename the stems
            stems_dir = output_dir / "htdemucs" / safe_name
            stems = {}
            
            # Check if stems were created (even if Demucs returned non-zero)
            # Demucs uses the input filename (without extension) as the subdirectory name
            # So we need to check for the safe_name (which includes _temp)
            stems_dir_with_temp = output_dir / "htdemucs" / f"{safe_name}_temp"
            stems_dir = output_dir / "htdemucs" / safe_name
            
            # Try both possible directory names
            actual_stems_dir = None
            if stems_dir_with_temp.exists():
                actual_stems_dir = stems_dir_with_temp
                logger.info(f"Found stems directory: {actual_stems_dir}")
            elif stems_dir.exists():
                actual_stems_dir = stems_dir
                logger.info(f"Found stems directory: {actual_stems_dir}")
            else:
                # Search for any subdirectory in htdemucs
                htdemucs_dir = output_dir / "htdemucs"
                if htdemucs_dir.exists():
                    logger.info(f"Searching htdemucs directory for output...")
                    for subdir in htdemucs_dir.iterdir():
                        if subdir.is_dir():
                            logger.info(f"Found subdirectory: {subdir}")
                            actual_stems_dir = subdir
                            break
            
            if actual_stems_dir and actual_stems_dir.exists():
                # Map Demucs output to our desired stems
                # Demucs typically outputs: drums, bass, other, vocals
                stem_mapping = {
                    'drums.wav': 'drums',
                    'bass.wav': 'bass',
                    'other.wav': 'guitar',  # Map 'other' to guitar
                    'vocals.wav': 'vocals',
                }
                
                # Copy and rename stems
                for file in actual_stems_dir.glob("*.wav"):
                    stem_name = file.name
                    if stem_name in stem_mapping:
                        target_name = stem_mapping[stem_name]
                        target_path = output_dir / f"{target_name}.wav"
                        shutil.copy2(file, target_path)
                        stems[target_name] = target_path
                        logger.info(f"Created stem: {target_name} -> {target_path}")
                
                # Create synth from 'other' if it exists and we haven't used it
                other_file = actual_stems_dir / "other.wav"
                if other_file.exists() and 'guitar' not in stems:
                    synth_path = output_dir / "synth.wav"
                    shutil.copy2(other_file, synth_path)
                    stems['synth'] = synth_path
                    logger.info(f"Created synth stem: {synth_path}")
                elif other_file.exists() and 'synth' not in stems:
                    # Use other as synth if we haven't already
                    synth_path = output_dir / "synth.wav"
                    shutil.copy2(other_file, synth_path)
                    stems['synth'] = synth_path
                    logger.info(f"Created synth stem: {synth_path}")
                
                # If we found stems, consider it successful even if exit code was non-zero
                if stems:
                    logger.info("Demucs completed successfully (files found despite exit code)")
                else:
                    logger.warning(f"Stems directory exists but no stem files found in: {actual_stems_dir}")
                    logger.warning(f"Files in directory: {list(actual_stems_dir.glob('*'))}")
            else:
                logger.error(f"Stems directory not found. Checked:")
                logger.error(f"  - {stems_dir_with_temp}")
                logger.error(f"  - {stems_dir}")
                logger.error(f"  - {output_dir / 'htdemucs'}")
                if result.returncode != 0:
                    logger.error(f"Demucs exited with code {result.returncode}")
                    logger.error(f"stdout: {result.stdout[-500:] if result.stdout else 'None'}")
                    logger.error(f"stderr: {result.stderr[-500:] if result.stderr else 'None'}")
            
            # Clean up temporary safe file
            if safe_audio_path.exists():
                safe_audio_path.unlink()
            
            logger.info(f"Separated audio into {len(stems)} stems")
            return stems
            
        except subprocess.TimeoutExpired:
            logger.error("Demucs process timed out after 1 hour")
            # Clean up temporary safe file on error
            if 'safe_audio_path' in locals() and safe_audio_path.exists():
                safe_audio_path.unlink()
            return {}
        except Exception as e:
            logger.error(f"Demucs process error: {e}")
            # Check if files were created despite the error
            if 'stems_dir' in locals() and stems_dir.exists():
                logger.info("Files were created, attempting to recover...")
                # Try to process the files anyway
                pass  # Will be handled in the main try block
            else:
                # Clean up temporary safe file on error
                if 'safe_audio_path' in locals() and safe_audio_path.exists():
                    safe_audio_path.unlink()
                return {}
        except Exception as e:
            logger.error(f"Error separating audio: {e}")
            import traceback
            traceback.print_exc()
            # Clean up temporary safe file on error
            if 'safe_audio_path' in locals() and safe_audio_path.exists():
                safe_audio_path.unlink()
            return {}
    
    def create_zip(self, files: Dict[str, Path], output_path: Path, title: Optional[str] = None) -> Path:
        """
        Create a ZIP archive of the separated stems.
        
        Args:
            files: Dictionary of stem names to file paths
            output_path: Directory to save the ZIP file
            title: Optional title for the ZIP filename (will be sanitized)
            
        Returns:
            Path to created ZIP file
        """
        # Generate ZIP filename from title if provided
        if title:
            import re
            # Sanitize title for filename: remove invalid characters
            safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title)
            # Replace spaces with underscores and limit length
            safe_title = safe_title.replace(' ', '_')[:100]  # Limit to 100 chars
            zip_filename = f"{safe_title}_stems.zip"
        else:
            zip_filename = "separated_stems.zip"
        
        zip_path = output_path / zip_filename
        logger.info(f"Creating ZIP archive: {zip_path}")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for stem_name, file_path in files.items():
                if file_path.exists():
                    zipf.write(file_path, arcname=f"{stem_name}.wav")
                    logger.info(f"Added {stem_name}.wav to ZIP")
        
        logger.info(f"Created ZIP archive: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.2f} MB)")
        return zip_path
    
    def upload_to_server(self, zip_path: Path) -> bool:
        """
        Upload ZIP file to server via SCP.
        
        Args:
            zip_path: Path to ZIP file to upload
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Uploading {zip_path} to server")
        
        server_config = self.config.get('server', {})
        host = server_config.get('host')
        port = server_config.get('port', 22)
        username = server_config.get('username')
        password = server_config.get('password')
        key_file = server_config.get('key_file')  # Optional SSH key file
        remote_path = server_config.get('remote_path', '/tmp/')
        
        if not all([host, username]):
            logger.error("Server configuration incomplete (missing host or username)")
            return False
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect using password or key file
            if key_file and os.path.exists(key_file):
                ssh.connect(host, port=port, username=username, key_filename=key_file)
            elif password:
                ssh.connect(host, port=port, username=username, password=password)
            else:
                logger.error("No authentication method provided (password or key_file)")
                return False
            
            # Upload file using SCP
            with SCPClient(ssh.get_transport()) as scp:
                remote_file = f"{remote_path.rstrip('/')}/{zip_path.name}"
                scp.put(str(zip_path), remote_file)
                logger.info(f"Successfully uploaded to {host}:{remote_file}")
            
            ssh.close()
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to server: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run(self, query: str, upload_to_server: bool = None) -> bool:
        """
        Run the complete pipeline.
        
        Args:
            query: YouTube search query
            upload_to_server: If True, upload to server. If None, use config settings.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("Starting YouTube Audio Processing Pipeline")
            logger.info("=" * 60)
            
            # Step 1: Search YouTube
            video_url = self.search_youtube(query)
            if not video_url:
                logger.error("Failed to find video on YouTube")
                return False
            
            # Step 2: Download audio
            audio_file = self.download_audio(video_url, self.temp_dir)
            if not audio_file:
                logger.error("Failed to download audio")
                return False
            
            # Step 3: Separate audio
            stems_dir = self.temp_dir / "stems"
            stems_dir.mkdir(exist_ok=True)
            stems = self.separate_audio(audio_file, stems_dir)
            if not stems:
                logger.error("Failed to separate audio")
                return False
            
            # Step 4: Create ZIP (save to output_dir, not temp_dir)
            zip_file = self.create_zip(stems, self.output_dir, title=self.video_title)
            
            # Step 5: Upload to server (optional)
            # If upload_to_server is explicitly set, use that. Otherwise check config.
            should_upload = upload_to_server
            if should_upload is None:
                # Check config to determine if we should upload
                server_config = self.config.get('server', {})
                should_upload = bool(server_config.get('host') and server_config.get('username'))
            
            if should_upload:
                server_config = self.config.get('server', {})
                if server_config.get('host') and server_config.get('username'):
                    if not self.upload_to_server(zip_file):
                        logger.warning("Failed to upload to server, but continuing...")
                        # Don't fail the pipeline if upload fails
                else:
                    logger.warning("Upload to server requested but server configuration is incomplete")
            else:
                logger.info("Skipping server upload (disabled or not configured)")
            
            logger.info(f"ZIP file saved at: {zip_file}")
            logger.info("=" * 60)
            logger.info("Pipeline completed successfully!")
            logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup temp directory (but keep output_dir)
            if self.config.get('cleanup', True) and self.temp_dir != self.output_dir:
                logger.info(f"Cleaning up temporary directory: {self.temp_dir}")
                shutil.rmtree(self.temp_dir, ignore_errors=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='YouTube Audio Processing Pipeline'
    )
    parser.add_argument(
        'query',
        help='YouTube search query (song name, artist, etc.)'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    
    args = parser.parse_args()
    
    pipeline = YouTubePipeline(config_path=args.config)
    success = pipeline.run(args.query)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

