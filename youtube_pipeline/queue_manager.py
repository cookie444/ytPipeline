#!/usr/bin/env python3
"""
Job queue manager for processing YouTube audio pipeline requests.
Handles sequential processing of jobs to avoid resource contention.
"""

import threading
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Represents a processing job."""
    job_id: str
    query: str
    output_dir: Optional[str]
    upload_to_server: bool
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: int = 0
    message: str = "Waiting in queue..."


class QueueManager:
    """Manages job queue and sequential processing."""
    
    def __init__(self):
        self.queue = []
        self.jobs: Dict[str, Job] = {}
        self.current_job: Optional[str] = None
        self.lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False
        
    def start_worker(self, process_callback):
        """Start the background worker thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.running = True
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(process_callback,),
            daemon=True
        )
        self.worker_thread.start()
        logger.info("Queue worker thread started")
    
    def stop_worker(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Queue worker thread stopped")
    
    def add_job(self, query: str, output_dir: Optional[str] = None, 
                upload_to_server: bool = False) -> str:
        """Add a new job to the queue."""
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            query=query,
            output_dir=output_dir,
            upload_to_server=upload_to_server
        )
        
        with self.lock:
            self.jobs[job_id] = job
            self.queue.append(job_id)
            logger.info(f"Job {job_id} added to queue. Queue length: {len(self.queue)}")
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a job."""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            
            return {
                'job_id': job.job_id,
                'status': job.status.value,
                'query': job.query,
                'progress': job.progress,
                'message': job.message,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'result': job.result,
                'error': job.error,
                'queue_position': self._get_queue_position(job_id)
            }
    
    def _get_queue_position(self, job_id: str) -> int:
        """Get the position of a job in the queue (0 = currently processing)."""
        if self.current_job == job_id:
            return 0
        try:
            return self.queue.index(job_id) + 1
        except ValueError:
            return -1
    
    def _worker_loop(self, process_callback):
        """Background worker loop that processes jobs sequentially."""
        logger.info("Queue worker loop started")
        
        while self.running:
            job_id = None
            try:
                # Get next job from queue
                with self.lock:
                    if not self.queue:
                        time.sleep(1)  # Wait for jobs
                        continue
                    
                    job_id = self.queue.pop(0)
                    job = self.jobs.get(job_id)
                    if not job:
                        continue
                    
                    self.current_job = job_id
                    job.status = JobStatus.PROCESSING
                    job.started_at = datetime.now()
                    job.message = "Processing started..."
                    job.progress = 10
                
                logger.info(f"Processing job {job_id}: {job.query}")
                
                # Process the job
                try:
                    result = process_callback(
                        query=job.query,
                        output_dir=job.output_dir,
                        upload_to_server=job.upload_to_server,
                        progress_callback=lambda p, m: self._update_progress(job_id, p, m)
                    )
                    
                    # Job completed successfully
                    with self.lock:
                        job.status = JobStatus.COMPLETED
                        job.completed_at = datetime.now()
                        job.result = result
                        job.progress = 100
                        job.message = "Processing completed successfully!"
                    
                    logger.info(f"Job {job_id} completed successfully")
                    
                except Exception as e:
                    # Job failed
                    error_msg = str(e)
                    logger.error(f"Job {job_id} failed: {error_msg}")
                    
                    with self.lock:
                        job.status = JobStatus.FAILED
                        job.completed_at = datetime.now()
                        job.error = error_msg
                        job.message = f"Processing failed: {error_msg}"
                
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
            finally:
                with self.lock:
                    self.current_job = None
                
                # Small delay between jobs
                time.sleep(0.5)
        
        logger.info("Queue worker loop stopped")
    
    def _update_progress(self, job_id: str, progress: int, message: str):
        """Update job progress."""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.progress = progress
                job.message = message
    
    def get_queue_length(self) -> int:
        """Get the current queue length."""
        with self.lock:
            return len(self.queue)
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed/failed jobs to free memory."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        with self.lock:
            jobs_to_remove = []
            for job_id, job in self.jobs.items():
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    if job.completed_at and job.completed_at.timestamp() < cutoff_time:
                        jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
            
            if jobs_to_remove:
                logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")

