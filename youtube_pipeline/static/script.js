// script.js
const API_BASE = window.location.origin;

let isProcessing = false;
let logPollInterval = null;
let statusPollInterval = null;
let currentJobId = null;

// DOM Elements
const youtubeInput = document.getElementById('youtube-input');
const outputDirInput = document.getElementById('output-dir');
const uploadToServerCheckbox = document.getElementById('upload-to-server');
const browseBtn = document.getElementById('browse-btn');
const processBtn = document.getElementById('process-btn');
const btnText = document.getElementById('btn-text');
const btnSpinner = document.getElementById('btn-spinner');
const statusDiv = document.getElementById('status');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const logOutput = document.getElementById('log-output');
const clearLogBtn = document.getElementById('clear-log-btn');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    setDefaultOutputDir();
});

// Set default output directory
function setDefaultOutputDir() {
    // In containerized environment, default to /app/output
    outputDirInput.value = '/app/output';
}

// Check API status
async function checkStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        addLog('info', `API Status: ${data.status}`);
    } catch (error) {
        addLog('error', `Failed to connect to API: ${error.message}`);
    }
}

// Browse button - allow user to edit the path directly or use prompt
browseBtn.addEventListener('click', () => {
    // Make input editable temporarily
    outputDirInput.readOnly = false;
    outputDirInput.focus();
    outputDirInput.select();
    
    // Also show a prompt as alternative
    const path = prompt('Enter output directory path (or edit in the field above):', outputDirInput.value);
    if (path && path.trim()) {
        outputDirInput.value = path.trim();
    }
    
    // Keep it editable so user can type directly
    outputDirInput.readOnly = false;
});

// Process button
processBtn.addEventListener('click', async () => {
    if (isProcessing) {
        return;
    }

    const query = youtubeInput.value.trim();
    if (!query) {
        showStatus('Please enter a YouTube URL or search query', 'error');
        return;
    }

    startProcessing();
    
    try {
        const response = await fetch(`${API_BASE}/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                output_dir: outputDirInput.value || '/app/output',
                upload_to_server: uploadToServerCheckbox.checked
            })
        });

        const data = await response.json();

        if (data.success && data.job_id) {
            // Job queued successfully, start polling for status
            currentJobId = data.job_id;
            const queuePos = data.queue_position || 0;
            
            if (queuePos > 0) {
                showStatus(`Job queued (position ${queuePos} in queue)`, 'info');
                updateProgress(5, `Waiting in queue (position ${queuePos})...`);
                addLog('info', `Job ${data.job_id} queued. Position: ${queuePos}`);
            } else {
                showStatus('Job started processing', 'info');
                updateProgress(10, 'Processing started...');
                addLog('info', `Job ${data.job_id} started processing`);
            }
            
            // Start polling for job status
            startStatusPolling(data.job_id);
        } else {
            showStatus(data.message || data.error || 'Failed to queue job', 'error');
            updateProgress(0, 'Failed');
            addLog('error', data.error || 'Failed to queue job');
            stopProcessing();
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
        addLog('error', `Request failed: ${error.message}`);
        stopProcessing();
    }
});

// Start processing state
function startProcessing() {
    isProcessing = true;
    processBtn.disabled = true;
    btnText.textContent = 'Processing...';
    btnSpinner.classList.remove('hidden');
    youtubeInput.disabled = true;
    updateProgress(10, 'Starting...');
    addLog('info', 'Starting pipeline...');
    clearStatus();
    
    // Simulate progress updates
    simulateProgress();
}

// Stop processing state
function stopProcessing() {
    isProcessing = false;
    processBtn.disabled = false;
    btnText.textContent = 'Process Song';
    btnSpinner.classList.add('hidden');
    youtubeInput.disabled = false;
    if (logPollInterval) {
        clearInterval(logPollInterval);
    }
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }
    currentJobId = null;
}

// Start polling for job status
function startStatusPolling(jobId) {
    // Clear any existing polling
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }
    
    // Poll immediately, then every 2 seconds
    pollJobStatus(jobId);
    statusPollInterval = setInterval(() => {
        pollJobStatus(jobId);
    }, 2000);
}

// Poll job status from server
async function pollJobStatus(jobId) {
    try {
        const response = await fetch(`${API_BASE}/status/${jobId}`);
        const data = await response.json();
        
        if (!data.success) {
            addLog('error', `Failed to get job status: ${data.error}`);
            return;
        }
        
        const status = data.status;
        const progress = data.progress || 0;
        const message = data.message || 'Processing...';
        const queuePosition = data.queue_position;
        
        // Update UI
        updateProgress(progress, message);
        addLog('info', `[${status}] ${message} (${progress}%)`);
        
        // Handle queue position
        if (queuePosition > 0 && status === 'pending') {
            updateProgress(5, `Waiting in queue (position ${queuePosition})...`);
            showStatus(`Queued (position ${queuePosition} in queue)`, 'info');
        } else if (status === 'processing') {
            showStatus('Processing...', 'info');
        } else if (status === 'pending' && queuePosition === 0) {
            showStatus('Starting soon...', 'info');
        }
        
        // Handle completion
        if (status === 'completed') {
            clearInterval(statusPollInterval);
            showStatus('Processing completed successfully!', 'success');
            updateProgress(100, 'Complete!');
            addLog('success', 'Pipeline completed successfully');
            stopProcessing();
        } else if (status === 'failed') {
            clearInterval(statusPollInterval);
            showStatus(`Processing failed: ${data.error || 'Unknown error'}`, 'error');
            updateProgress(0, 'Failed');
            addLog('error', `Pipeline failed: ${data.error || 'Unknown error'}`);
            stopProcessing();
        }
    } catch (error) {
        addLog('error', `Error polling status: ${error.message}`);
    }
}

// Update progress bar
function updateProgress(percent, text) {
    progressFill.style.width = `${percent}%`;
    progressText.textContent = text;
}

// Show status message
function showStatus(message, type) {
    statusDiv.textContent = message;
    statusDiv.className = `status-message ${type}`;
}

// Clear status message
function clearStatus() {
    statusDiv.className = 'status-message';
    statusDiv.textContent = '';
}

// Add log entry
function addLog(level, message) {
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;
    entry.textContent = `[${timestamp}] ${message}`;
    logOutput.appendChild(entry);
    logOutput.scrollTop = logOutput.scrollHeight;
}

// Clear log
clearLogBtn.addEventListener('click', () => {
    logOutput.innerHTML = '';
    addLog('info', 'Log cleared');
});

// Simulate progress updates (in real implementation, use WebSockets or polling)
function simulateProgress() {
    let progress = 10;
    const uploadEnabled = uploadToServerCheckbox.checked;
    const stages = [
        { percent: 20, text: 'Searching YouTube...' },
        { percent: 40, text: 'Downloading audio...' },
        { percent: 60, text: 'Separating audio...' },
        { percent: 80, text: 'Creating ZIP archive...' }
    ];
    
    if (uploadEnabled) {
        stages.push({ percent: 90, text: 'Uploading to server...' });
    }
    
    let currentStage = 0;
    
    const interval = setInterval(() => {
        if (!isProcessing) {
            clearInterval(interval);
            return;
        }
        
        // Gradually increase progress
        progress += Math.random() * 3;
        
        // Move to next stage if threshold reached
        if (currentStage < stages.length - 1 && progress >= stages[currentStage].percent) {
            currentStage++;
            addLog('info', stages[currentStage].text);
        }
        
        // Cap at 90% until completion
        if (progress > 90) progress = 90;
        
        updateProgress(progress, stages[currentStage].text);
    }, 2000);
}

