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
const clientSideDownloadCheckbox = document.getElementById('client-side-download');
const browseBtn = document.getElementById('browse-btn');
const processBtn = document.getElementById('process-btn');
const btnText = document.getElementById('btn-text');
const btnSpinner = document.getElementById('btn-spinner');
const statusDiv = document.getElementById('status');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const logOutput = document.getElementById('log-output');
const clearLogBtn = document.getElementById('clear-log-btn');
const cookiesFileInput = document.getElementById('cookies-file');
const uploadCookiesBtn = document.getElementById('upload-cookies-btn');
const cookiesStatusDiv = document.getElementById('cookies-status');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    setDefaultOutputDir();
    checkCookiesStatus();
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

    // Check if client-side download is selected
    if (clientSideDownloadCheckbox && clientSideDownloadCheckbox.checked) {
        await handleClientSideDownload(query);
        return;
    }

    // Normal server-side processing
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

// Handle client-side download - fully browser-based, no Python needed
async function handleClientSideDownload(query) {
    try {
        startProcessing();
        addLog('info', 'Browser-based download - using YOUR IP address...');
        showStatus('Preparing browser download...', 'info');
        updateProgress(5, 'Creating job...');
        
        // First, create a job
        const jobResponse = await fetch(`${API_BASE}/process`, {
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

        if (jobResponse.status === 401) {
            window.location.href = '/login';
            return;
        }

        const jobData = await jobResponse.json();
        
        if (!jobData.success || !jobData.job_id) {
            showStatus(jobData.error || 'Failed to create job', 'error');
            addLog('error', jobData.error || 'Failed to create job');
            stopProcessing();
            return;
        }

        currentJobId = jobData.job_id;
        addLog('info', `Job created: ${currentJobId}`);
        updateProgress(10, 'Getting download URL...');
        
        // Get direct download URL from server with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
        
        let urlResponse;
        try {
            urlResponse = await fetch(`${API_BASE}/api/get-download-url`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                showStatus('Request timed out - server may be slow. Try again or use server-side download.', 'error');
                addLog('error', 'Getting download URL timed out after 60 seconds');
            } else {
                showStatus(`Network error: ${error.message}`, 'error');
                addLog('error', `Network error: ${error.message}`);
            }
            stopProcessing();
            return;
        }

        if (urlResponse.status === 401) {
            window.location.href = '/login';
            return;
        }

        if (!urlResponse.ok) {
            let errorData;
            try {
                errorData = await urlResponse.json();
            } catch (e) {
                errorData = { error: `HTTP ${urlResponse.status}: ${urlResponse.statusText}` };
            }
            showStatus('Client-side download failed, falling back to server-side processing...', 'warning');
            addLog('error', `Failed to get download URL: ${errorData.error || 'Unknown error'}`);
            addLog('info', 'Falling back to server-side processing (using Render\'s IP)...');
            addLog('info', 'The job will continue processing on the server.');
            // Fall back to server-side processing - the job is already created
            startStatusPolling(currentJobId);
            return;
        }

        let urlData;
        try {
            urlData = await urlResponse.json();
        } catch (e) {
            showStatus('Invalid response from server', 'error');
            addLog('error', 'Server returned invalid JSON response');
            startStatusPolling(currentJobId);
            return;
        }
        
        if (!urlData.success || !urlData.download_url) {
            showStatus('Client-side download failed, falling back to server-side processing...', 'warning');
            addLog('error', urlData.error || 'No download URL available');
            addLog('info', 'Falling back to server-side processing (using Render\'s IP)...');
            addLog('info', 'The job will continue processing on the server.');
            // Fall back to server-side processing - the job is already created
            startStatusPolling(currentJobId);
            return;
        }

        addLog('info', `Found video: ${urlData.title}`);
        addLog('info', `Duration: ${Math.floor(urlData.duration / 60)}:${String(urlData.duration % 60).padStart(2, '0')}`);
        updateProgress(20, 'Downloading audio in browser...');
        addLog('info', 'Downloading using YOUR IP address (not Render\'s)...');
        
        // Download audio directly in browser
        const audioBlob = await downloadAudioInBrowser(urlData.download_url, urlData.format.ext);
        
        if (!audioBlob) {
            showStatus('Download failed', 'error');
            addLog('error', 'Failed to download audio');
            stopProcessing();
            return;
        }

        updateProgress(50, 'Uploading to Render for processing...');
        addLog('info', `Uploading ${(audioBlob.size / 1024 / 1024).toFixed(2)} MB to Render...`);
        
        // Upload to Render
        const uploadSuccess = await uploadAudioToRender(audioBlob, currentJobId, urlData.format.ext);
        
        if (!uploadSuccess) {
            showStatus('Upload failed', 'error');
            addLog('error', 'Failed to upload audio to Render');
            stopProcessing();
            return;
        }

        updateProgress(60, 'Processing on Render...');
        addLog('info', 'Audio uploaded! Processing will start automatically...');
        
        // Start polling for status
        startStatusPolling(currentJobId);
        
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
        addLog('error', `Browser download failed: ${error.message}`);
        stopProcessing();
    }
}

// Download audio directly in browser using fetch
async function downloadAudioInBrowser(downloadUrl, fileExt) {
    try {
        updateProgress(25, 'Connecting to YouTube...');
        
        // Fetch the audio with progress tracking
        const response = await fetch(downloadUrl);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentLength = response.headers.get('content-length');
        const total = contentLength ? parseInt(contentLength, 10) : 0;
        
        updateProgress(30, 'Downloading audio stream...');
        
        // Read the stream with progress updates
        const reader = response.body.getReader();
        const chunks = [];
        let received = 0;
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            chunks.push(value);
            received += value.length;
            
            if (total > 0) {
                const percent = 20 + (received / total) * 25; // 20-45% for download
                updateProgress(percent, `Downloading... ${(received / 1024 / 1024).toFixed(2)} MB`);
            }
        }
        
        // Combine chunks into blob
        const audioBlob = new Blob(chunks, { type: `audio/${fileExt}` });
        addLog('info', `Download complete: ${(audioBlob.size / 1024 / 1024).toFixed(2)} MB`);
        
        return audioBlob;
        
    } catch (error) {
        addLog('error', `Download error: ${error.message}`);
        return null;
    }
}

// Upload audio blob to Render
async function uploadAudioToRender(audioBlob, jobId, fileExt) {
    try {
        // Create FormData
        const formData = new FormData();
        formData.append('audio', audioBlob, `audio.${fileExt}`);
        formData.append('job_id', jobId);
        
        // Upload with progress
        const xhr = new XMLHttpRequest();
        
        return new Promise((resolve, reject) => {
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percent = 50 + (e.loaded / e.total) * 10; // 50-60% for upload
                    updateProgress(percent, `Uploading... ${((e.loaded / 1024 / 1024).toFixed(2))} MB`);
                }
            });
            
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        addLog('info', 'Upload successful!');
                        resolve(true);
                    } else {
                        addLog('error', response.error || 'Upload failed');
                        resolve(false);
                    }
                } else {
                    addLog('error', `Upload failed: HTTP ${xhr.status}`);
                    resolve(false);
                }
            });
            
            xhr.addEventListener('error', () => {
                addLog('error', 'Upload error');
                resolve(false);
            });
            
            xhr.open('POST', `${API_BASE}/api/upload-audio`);
            xhr.send(formData);
        });
        
    } catch (error) {
        addLog('error', `Upload error: ${error.message}`);
        return false;
    }
}

// Ask user for permission to run automatically
async function askPermissionToRun() {
    return new Promise((resolve) => {
        const message = 'Would you like to automatically download and run the script?\n\n' +
                       'This will:\n' +
                       '1. Download a Python script to your machine\n' +
                       '2. Attempt to run it automatically (requires Python)\n' +
                       '3. Use YOUR IP address to download from YouTube\n' +
                       '4. Upload the audio to Render for processing\n\n' +
                       'Click "Yes" to proceed automatically, or "No" to download the script manually.';
        
        const userChoice = confirm(message);
        resolve(userChoice);
    });
}

// Execute download automatically
async function executeDownloadAutomatically(query, jobId) {
    try {
        updateProgress(15, 'Generating download script...');
        addLog('info', 'Generating download script for automatic execution...');
        
        // Get download script
        const scriptResponse = await fetch(`${API_BASE}/api/get-download-script`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                job_id: jobId
            })
        });

        if (scriptResponse.status === 401) {
            window.location.href = '/login';
            return;
        }

        if (!scriptResponse.ok) {
            const errorData = await scriptResponse.json();
            showStatus(errorData.error || 'Failed to generate script', 'error');
            addLog('error', errorData.error || 'Failed to generate script');
            return;
        }

        updateProgress(20, 'Downloading script...');
        const scriptText = await scriptResponse.text();
        
        // Save script to a temporary location
        const scriptBlob = new Blob([scriptText], { type: 'text/plain' });
        const scriptUrl = URL.createObjectURL(scriptBlob);
        
        // Try to use File System Access API if available (Chrome/Edge)
        if ('showSaveFilePicker' in window) {
            try {
                updateProgress(25, 'Requesting file save permission...');
                const fileHandle = await window.showSaveFilePicker({
                    suggestedName: 'download_client_side.py',
                    types: [{
                        description: 'Python Script',
                        accept: { 'text/x-python': ['.py'] }
                    }]
                });
                
                const writable = await fileHandle.createWritable();
                await writable.write(scriptText);
                await writable.close();
                
                addLog('info', 'Script saved successfully');
                updateProgress(30, 'Script saved. Attempting to execute...');
                
                // Try to execute via custom protocol or provide instructions
                await attemptAutoExecute(fileHandle.name);
                
            } catch (error) {
                if (error.name === 'AbortError') {
                    addLog('info', 'File save cancelled, falling back to download');
                    downloadScriptFile(scriptUrl);
                } else {
                    addLog('warn', `File System API failed: ${error.message}, falling back to download`);
                    downloadScriptFile(scriptUrl);
                }
            }
        } else {
            // Fallback: download the file
            downloadScriptFile(scriptUrl);
            updateProgress(30, 'Script downloaded. Please run it manually.');
            showAutoRunInstructions();
        }
        
        // Start polling for status
        startStatusPolling(jobId);
        updateProgress(35, 'Waiting for download to complete...');
        
    } catch (error) {
        addLog('error', `Automatic execution failed: ${error.message}`);
        showStatus('Automatic execution failed. Please run the script manually.', 'error');
    }
}

// Download script file (fallback)
function downloadScriptFile(scriptUrl) {
    const a = document.createElement('a');
    a.href = scriptUrl;
    a.download = 'download_client_side.py';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(scriptUrl);
}

// Attempt to auto-execute the script
async function attemptAutoExecute(filename) {
    // Check if we can use a custom protocol handler or local service
    // For now, provide clear instructions and try to open terminal
    
    addLog('info', 'Attempting to execute script automatically...');
    updateProgress(35, 'Executing script...');
    
    // Try to detect OS and provide appropriate command
    const isWindows = navigator.platform.toLowerCase().includes('win');
    const isMac = navigator.platform.toLowerCase().includes('mac');
    const isLinux = navigator.platform.toLowerCase().includes('linux');
    
    let command = '';
    if (isWindows) {
        // Try to execute via PowerShell or CMD
        command = `python "${filename}"`;
        addLog('info', 'Windows detected. Trying to execute via command prompt...');
        
        // Try to use a data URL to execute (limited browser support)
        // For now, show instructions
        showAutoRunInstructions(filename, command);
    } else if (isMac || isLinux) {
        command = `python3 "${filename}" || python "${filename}"`;
        addLog('info', 'Unix-like system detected. Trying to execute...');
        showAutoRunInstructions(filename, command);
    } else {
        showAutoRunInstructions(filename);
    }
    
    // Ask for password
    const password = await askForPassword();
    if (password) {
        addLog('info', 'Password provided. You can now run the script with this password.');
        addLog('info', `Command: ${command} ${password}`);
        showStatus('Script ready! Run the command shown in the logs.', 'info');
    }
}

// Ask user for Render password
async function askForPassword() {
    return new Promise((resolve) => {
        const password = prompt('Enter your Render password (or leave blank to enter later):');
        resolve(password || null);
    });
}

// Show auto-run instructions
function showAutoRunInstructions(filename = 'download_client_side.py', command = null) {
    addLog('info', '='.repeat(60));
    addLog('info', 'AUTOMATIC EXECUTION INSTRUCTIONS:');
    addLog('info', '='.repeat(60));
    
    if (command) {
        addLog('info', `1. Open terminal/command prompt in the folder containing: ${filename}`);
        addLog('info', `2. Run: ${command} [YOUR_PASSWORD]`);
    } else {
        addLog('info', `1. Open terminal/command prompt`);
        addLog('info', `2. Navigate to the folder containing: ${filename}`);
        addLog('info', `3. Run: python "${filename}" [YOUR_PASSWORD]`);
        addLog('info', '   (or: python3 "${filename}" [YOUR_PASSWORD] on Mac/Linux)');
    }
    
    addLog('info', '3. The script will automatically:');
    addLog('info', '   - Download the video using YOUR IP address');
    addLog('info', '   - Upload the audio to Render');
    addLog('info', '   - Processing will continue automatically');
    addLog('info', '='.repeat(60));
    
    showStatus('Script ready! Follow the instructions in the logs to run it.', 'info');
}

// Download and run script (manual fallback)
async function downloadAndRunScript(query, jobId) {
    updateProgress(20, 'Generating download script...');
    
    const scriptResponse = await fetch(`${API_BASE}/api/get-download-script`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            query: query,
            job_id: jobId
        })
    });

    if (!scriptResponse.ok) {
        const errorData = await scriptResponse.json();
        showStatus(errorData.error || 'Failed to generate script', 'error');
        return;
    }

    const scriptBlob = await scriptResponse.blob();
    const scriptUrl = URL.createObjectURL(scriptBlob);
    downloadScriptFile(scriptUrl);
    
    updateProgress(30, 'Script downloaded!');
    showStatus('Script downloaded. Please run it manually.', 'info');
    addLog('info', 'Script saved as download_client_side.py');
    addLog('info', 'Run it with: python download_client_side.py [YOUR_PASSWORD]');
    
    startStatusPolling(jobId);
}

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
            
            // Automatically download stems
            const result = data.result || {};
            const zipFile = result.zip_file;
            if (zipFile) {
                addLog('info', 'Downloading stems...');
                downloadStems(jobId);
            } else {
                addLog('warn', 'No ZIP file available for download');
            }
            
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

// Download stems ZIP file
async function downloadStems(jobId) {
    try {
        addLog('info', 'Preparing stem download...');
        const response = await fetch(`${API_BASE}/api/download-stems/${jobId}`);
        
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const errorData = await response.json();
            addLog('error', errorData.error || 'Failed to download stems');
            return;
        }
        
        // Get filename from Content-Disposition header or use default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'stems.zip';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (filenameMatch) {
                filename = filenameMatch[1].replace(/['"]/g, '');
            }
        }
        
        // Download the blob
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        addLog('success', `Stems downloaded: ${filename}`);
        showStatus(`Stems downloaded: ${filename}`, 'success');
        
    } catch (error) {
        addLog('error', `Download error: ${error.message}`);
    }
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

// Check cookies status
async function checkCookiesStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/cookies-status`);
        if (response.ok) {
            const data = await response.json();
            if (data.has_cookies) {
                const ageText = data.age_days < 7 
                    ? `Uploaded ${data.age_days} days ago` 
                    : `⚠️ Uploaded ${data.age_days} days ago (may be expired)`;
                showCookiesStatus(`✅ Cookies file found. ${ageText}`, data.age_days < 7 ? 'success' : 'warning');
            } else {
                showCookiesStatus('⚠️ No cookies file uploaded. Age-restricted videos will fail.', 'warning');
            }
        }
    } catch (error) {
        console.error('Error checking cookies status:', error);
    }
}

// Show cookies status message
function showCookiesStatus(message, type = 'info') {
    cookiesStatusDiv.textContent = message;
    cookiesStatusDiv.className = `cookie-status show ${type}`;
}

// Upload cookies file
uploadCookiesBtn.addEventListener('click', async () => {
    if (!cookiesFileInput.files || cookiesFileInput.files.length === 0) {
        showCookiesStatus('Please select a cookies.txt file first', 'error');
        return;
    }

    const file = cookiesFileInput.files[0];
    if (!file.name.toLowerCase().endsWith('.txt')) {
        showCookiesStatus('Error: File must be a .txt file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('cookies', file);

    uploadCookiesBtn.disabled = true;
    uploadCookiesBtn.textContent = 'Uploading...';
    showCookiesStatus('Uploading cookies file...', 'info');

    try {
        const response = await fetch(`${API_BASE}/api/upload-cookies`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showCookiesStatus(`✅ ${data.message}`, 'success');
            addLog('success', `Cookies file uploaded successfully (${data.file_size} bytes)`);
            // Refresh cookies status after a moment
            setTimeout(checkCookiesStatus, 1000);
        } else {
            showCookiesStatus(`❌ Error: ${data.error}`, 'error');
            addLog('error', `Failed to upload cookies: ${data.error}`);
        }
    } catch (error) {
        showCookiesStatus(`❌ Upload failed: ${error.message}`, 'error');
        addLog('error', `Cookies upload error: ${error.message}`);
    } finally {
        uploadCookiesBtn.disabled = false;
        uploadCookiesBtn.textContent = 'Upload Cookies';
        cookiesFileInput.value = ''; // Clear file input
    }
});

// Note: Progress updates now come from real-time queue status polling via pollJobStatus()
// The simulateProgress() function has been removed in favor of actual progress from the server

