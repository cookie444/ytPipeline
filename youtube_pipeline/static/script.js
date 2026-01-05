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

// Check API status and authentication
async function checkStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        if (response.status === 401) {
            // Not authenticated, redirect to login
            window.location.href = '/login';
            return;
        }
        const data = await response.json();
        addLog('info', `API Status: ${data.status}`);
    } catch (error) {
        // If it's a 401, redirect to login
        if (error.message.includes('401') || error.message.includes('Authentication')) {
            window.location.href = '/login';
            return;
        }
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

        // Handle authentication errors
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

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
    updateProgress(5, 'Submitting job...');
    addLog('info', 'Submitting job to queue...');
    clearStatus();
    
    // Don't simulate progress - we'll get real updates from queue polling
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
        logPollInterval = null;
    }
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
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
        
        // Handle authentication errors
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        
        const data = await response.json();
        
        if (!data.success) {
            addLog('error', `Failed to get job status: ${data.error}`);
            return;
        }
        
        const status = data.status;
        const progress = data.progress || 0;
        const message = data.message || 'Processing...';
        const queuePosition = data.queue_position;
        
        // Update UI with real progress from server
        // Only update if we have valid progress data
        if (progress !== undefined && progress !== null) {
            updateProgress(progress, message);
        }
        addLog('info', `[${status}] ${message} (${progress}%)`);
        
        // Handle queue position
        if (queuePosition > 0 && status === 'pending') {
            // Show queue position with minimal progress
            const queueProgress = Math.max(1, 5 - (queuePosition * 2)); // 1-5% based on position
            updateProgress(queueProgress, `Waiting in queue (position ${queuePosition})...`);
            showStatus(`Queued (position ${queuePosition} in queue)`, 'info');
        } else if (status === 'processing') {
            showStatus('Processing...', 'info');
            // Progress will come from server updates
        } else if (status === 'pending' && queuePosition === 0) {
            updateProgress(10, 'Starting soon...');
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

// Logout button
const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const data = await response.json();
            if (data.success) {
                window.location.href = '/login';
            }
        } catch (error) {
            console.error('Logout error:', error);
            // Redirect anyway
            window.location.href = '/login';
        }
    });
}

// Note: Progress updates now come from real-time queue status polling via pollJobStatus()
// The simulateProgress() function has been removed in favor of actual progress from the server

