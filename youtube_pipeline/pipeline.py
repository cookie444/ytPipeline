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
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize pipeline with configuration."""
        self.config = self._load_config(config_path)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="youtube_pipeline_"))
        logger.info(f"Using temporary directory: {self.temp_dir}")
        
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
        
        Args:
            video_url: YouTube video URL
            output_path: Path to save the audio file
            
        Returns:
            Path to downloaded audio file or None if failed
        """
        logger.info(f"Downloading audio from: {video_url}")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path / '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get('title', 'audio')
                
                # Find the downloaded file
                downloaded_file = list(output_path.glob(f"{title}.*"))[0]
                wav_file = output_path / f"{title}.wav"
                
                # If not already WAV, it will be converted by postprocessor
                if not wav_file.exists():
                    # Find the converted file
                    wav_file = list(output_path.glob("*.wav"))[0]
                
                logger.info(f"Downloaded audio to: {wav_file}")
                return wav_file
                
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
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
        
        try:
            # Use Demucs command-line interface for source separation
            # Demucs will create separate files for each stem
            cmd = [
                'python', '-m', 'demucs.separate',
                '--model', 'htdemucs',  # High-quality model
                '--device', 'cpu',  # Use 'cuda' if GPU available
                '--shifts', '1',
                '--out', str(output_dir),
                str(audio_path)
            ]
            
            logger.info(f"Running Demucs: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Demucs creates a structure like: output_dir/htdemucs/track_name/stem.wav
            # We need to find and rename the stems
            stems_dir = output_dir / "htdemucs" / audio_path.stem
            stems = {}
            
            if stems_dir.exists():
                # Map Demucs output to our desired stems
                # Demucs typically outputs: drums, bass, other, vocals
                stem_mapping = {
                    'drums.wav': 'drums',
                    'bass.wav': 'bass',
                    'other.wav': 'guitar',  # Map 'other' to guitar
                    'vocals.wav': 'vocals',
                }
                
                # Copy and rename stems
                for file in stems_dir.glob("*.wav"):
                    stem_name = file.name
                    if stem_name in stem_mapping:
                        target_name = stem_mapping[stem_name]
                        target_path = output_dir / f"{target_name}.wav"
                        shutil.copy2(file, target_path)
                        stems[target_name] = target_path
                        logger.info(f"Created stem: {target_name} -> {target_path}")
                
                # Create synth from 'other' if it exists and we haven't used it
                other_file = stems_dir / "other.wav"
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
            else:
                logger.warning(f"Stems directory not found: {stems_dir}")
            
            logger.info(f"Separated audio into {len(stems)} stems")
            return stems
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Demucs process failed: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            return {}
        except Exception as e:
            logger.error(f"Error separating audio: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def create_zip(self, files: Dict[str, Path], output_path: Path) -> Path:
        """
        Create a ZIP archive of the separated stems.
        
        Args:
            files: Dictionary of stem names to file paths
            output_path: Directory to save the ZIP file
            
        Returns:
            Path to created ZIP file
        """
        zip_path = output_path / "separated_stems.zip"
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
            logger.warning("Server configuration incomplete (missing host or username)")
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
    
    def run(self, query: str) -> bool:
        """
        Run the complete pipeline.
        
        Args:
            query: YouTube search query
            
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
            
            # Step 4: Create ZIP
            zip_file = self.create_zip(stems, self.temp_dir)
            
            # Step 5: Upload to server (optional)
            server_config = self.config.get('server', {})
            if server_config.get('host') and server_config.get('username'):
                if not self.upload_to_server(zip_file):
                    logger.warning("Failed to upload to server, but continuing...")
            else:
                logger.info("No server configuration provided, skipping upload")
            
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
            # Cleanup (optional - comment out if you want to keep files for debugging)
            if self.config.get('cleanup', True):
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

