// App state variables
let selectedFile = null;
let currentTab = 'upload';
let generatedJobId = null;
let generatedSvgFilename = null;
let originalFilename = null;
let cameraStream = null;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    setupDragAndDrop();
    startQueuePolling();
});

// Tab Switching
function switchTab(tabId) {
    if (tabId === currentTab) return;
    
    // Toggle active tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.currentTarget.classList.add('active');
    
    // Toggle active content panels
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');
    
    currentTab = tabId;
    
    if (tabId === 'camera') {
        startWebcam();
    } else {
        stopWebcam();
    }
}

// Drag and Drop Logic
function setupDragAndDrop() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    
    if (!dropZone) return;
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        }, false);
    });
    
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    }, false);
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

function handleFileSelect(file) {
    if (!file.type.startsWith('image/')) {
        showToast('error', 'Unsupported file type. Please upload an image.');
        return;
    }
    selectedFile = file;
    originalFilename = file.name;
    
    // Show image preview
    const reader = new FileReader();
    reader.onload = (e) => {
        const previewCard = document.getElementById('input-preview-card');
        const previewImg = document.getElementById('input-preview-img');
        
        previewImg.src = e.target.result;
        previewCard.style.display = 'flex';
        
        // Hide drop zone while preview is showing
        document.getElementById('tab-upload').style.display = 'none';
        document.querySelector('.tabs-container').style.display = 'none';
    };
    reader.readAsDataURL(file);
}

function resetInput() {
    selectedFile = null;
    originalFilename = null;
    document.getElementById('input-preview-card').style.display = 'none';
    document.getElementById('tab-upload').style.display = 'block';
    document.querySelector('.tabs-container').style.display = 'flex';
    document.getElementById('file-input').value = '';
    
    // Also reset canvas previews
    resetCanvas();
}

function resetCanvas() {
    generatedJobId = null;
    generatedSvgFilename = null;
    document.getElementById('sketch-canvas-wrapper').style.display = 'none';
    document.getElementById('empty-canvas-msg').style.display = 'flex';
    document.getElementById('draw-controls-card').style.display = 'none';
    document.getElementById('svg-render-container').innerHTML = '';
}

// Webcam Capture Logic
async function startWebcam() {
    const video = document.getElementById('camera-stream');
    const errorMsg = document.getElementById('camera-error');
    
    errorMsg.style.display = 'none';
    
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: 640, height: 480 },
            audio: false
        });
        video.srcObject = cameraStream;
    } catch (err) {
        console.error("Webcam access error: ", err);
        errorMsg.style.display = 'flex';
        showToast('error', 'Could not open webcam. Check browser permissions.');
    }
}

function stopWebcam() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
}

function capturePhoto() {
    const video = document.getElementById('camera-stream');
    const canvas = document.getElementById('camera-canvas');
    
    if (!cameraStream) {
        showToast('error', 'Camera is not active.');
        return;
    }
    
    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw the current video frame to the canvas
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert to a blob/file to upload
    canvas.toBlob((blob) => {
        const file = new File([blob], "webcam_capture.png", { type: "image/png" });
        
        // Stop camera stream
        stopWebcam();
        
        // Show upload tab and preview card
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector('[onclick="switchTab(\'upload\')"]').classList.add('active');
        document.getElementById('tab-camera').classList.remove('active');
        document.getElementById('tab-upload').classList.add('active');
        currentTab = 'upload';
        
        handleFileSelect(file);
    }, 'image/png');
}

// Generate Sketch via FastAPI Upload API
async function generateSketch() {
    if (!selectedFile) {
        showToast('warning', 'Please select or capture an image first.');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    // Show loader
    const loader = document.getElementById('loader-overlay');
    const loaderText = document.getElementById('loader-text');
    loader.style.display = 'flex';
    loaderText.innerText = 'Denoising control points...';
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to generate sketch.');
        }
        
        const data = await response.json();
        generatedJobId = data.jobId;
        generatedSvgFilename = `${data.jobId}_sketch.svg`;
        
        // Render SVG in preview canvas
        const container = document.getElementById('svg-render-container');
        container.innerHTML = data.svgContent;
        
        // Toggle canvas display
        document.getElementById('empty-canvas-msg').style.display = 'none';
        document.getElementById('sketch-canvas-wrapper').style.display = 'block';
        document.getElementById('draw-controls-card').style.display = 'block';
        
        showToast('success', 'Sketch generated successfully!');
        
    } catch (err) {
        console.error(err);
        showToast('error', err.message);
    } finally {
        loader.style.display = 'none';
    }
}

// Trigger Drawing via FastAPI Draw API
async function triggerDraw() {
    if (!generatedJobId || !generatedSvgFilename) {
        showToast('warning', 'No generated sketch available to draw.');
        return;
    }
    
    const passcode = document.getElementById('passcode-input').value;
    if (!passcode) {
        showToast('warning', 'Please enter the security handshake passcode.');
        return;
    }
    
    const formData = new FormData();
    formData.append('job_id', generatedJobId);
    formData.append('svg_filename', generatedSvgFilename);
    formData.append('original_name', originalFilename || "Webcam Portrait");
    formData.append('passcode', passcode);
    
    try {
        const response = await fetch('/api/draw', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to trigger drawing.');
        }
        
        const data = await response.json();
        
        if (data.status === 'queued') {
            showToast('success', `Job queued successfully! Position: ${data.position}`);
            resetInput();
        } else if (data.status === 'already_queued') {
            showToast('info', 'This sketch is already in the drawing queue.');
        }
        
        // Force refresh queue status
        pollQueueStatus();
        
    } catch (err) {
        console.error(err);
        showToast('error', err.message);
    }
}

// Queue Polling
function startQueuePolling() {
    pollQueueStatus();
    setInterval(pollQueueStatus, 2000); // Poll every 2 seconds
}

async function pollQueueStatus() {
    try {
        const response = await fetch('/api/queue');
        if (!response.ok) return;
        
        const data = await response.json();
        
        // Update active job panel
        const activeCard = document.getElementById('active-job-card');
        const activeName = document.getElementById('active-job-name');
        const activeProgress = document.getElementById('active-job-progress');
        const activeProgressVal = document.getElementById('active-progress-val');
        const activeStrokeVal = document.getElementById('active-stroke-val');
        const emptyQueueMsg = document.getElementById('empty-queue-msg');
        
        if (data.activeJob) {
            activeName.innerText = `Subject: ${data.activeJob.original_name}`;
            activeProgress.style.width = `${data.activeJob.progress}%`;
            activeProgressVal.innerText = `${data.activeJob.progress}%`;
            activeStrokeVal.innerText = `${data.activeJob.current_stroke} / ${data.activeJob.total_strokes}`;
            
            activeCard.style.display = 'flex';
            emptyQueueMsg.style.display = 'none';
        } else {
            activeCard.style.display = 'none';
            // Show empty queue message if no queued items exist
            if (data.queue.length === 0) {
                emptyQueueMsg.style.display = 'block';
            } else {
                emptyQueueMsg.style.display = 'none';
            }
        }
        
        // Update pending queue list
        const queueSection = document.getElementById('queue-list-section');
        const queueContainer = document.getElementById('queue-container');
        
        // Filter out active job from display queue list
        const pendingJobs = data.queue.filter(j => j.status === 'queued');
        
        if (pendingJobs.length > 0) {
            queueContainer.innerHTML = '';
            pendingJobs.forEach(job => {
                const item = document.createElement('div');
                item.className = 'queue-item';
                item.innerHTML = `
                    <div class="queue-item-info">
                        <span class="queue-item-name">${job.original_name}</span>
                        <span class="queue-item-status">Status: Queued</span>
                    </div>
                    <button class="btn-cancel-queued" onclick="cancelJob('${job.id}')" title="Remove from queue">
                        <i class="fa-solid fa-circle-minus"></i>
                    </button>
                `;
                queueContainer.appendChild(item);
            });
            queueSection.style.display = 'block';
        } else {
            queueSection.style.display = 'none';
        }
        
        // Update history list
        const historyContainer = document.getElementById('history-container');
        if (data.history && data.history.length > 0) {
            historyContainer.innerHTML = '';
            // Show newest history items first
            [...data.history].reverse().forEach(job => {
                const item = document.createElement('div');
                item.className = 'history-item';
                
                let statusLabel = job.status;
                if (job.status === 'failed' && job.error) {
                    statusLabel = `Failed: ${job.error}`;
                }
                
                item.innerHTML = `
                    <div class="history-item-info">
                        <span class="history-item-name">${job.original_name}</span>
                    </div>
                    <span class="history-item-status ${job.status}">${job.status}</span>
                `;
                historyContainer.appendChild(item);
            });
        } else {
            historyContainer.innerHTML = '<p class="drop-subtitle" style="text-align: center; padding: 10px;">No historical entries found.</p>';
        }
        
    } catch (err) {
        console.error("Queue polling error: ", err);
    }
}

// Cancel queue items
async function cancelJob(jobId) {
    const formData = new FormData();
    formData.append('job_id', jobId);
    
    try {
        const response = await fetch('/api/cancel', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error("Failed to cancel job.");
        showToast('info', 'Job removed from queue.');
        pollQueueStatus();
    } catch (err) {
        showToast('error', err.message);
    }
}

async function cancelActiveJob() {
    if (confirm("Are you sure you want to stop the robot and cancel the active drawing?")) {
        if (active_job) {
            await cancelJob(active_job.id);
        }
    }
}

// Toast Notification Handler
function showToast(type, message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let iconClass = 'fa-circle-info';
    if (type === 'success') iconClass = 'fa-circle-check';
    else if (type === 'error') iconClass = 'fa-circle-xmark';
    else if (type === 'warning') iconClass = 'fa-triangle-exclamation';
    
    toast.innerHTML = `
        <i class="fa-solid ${iconClass}"></i>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Automatically remove toast after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse forwards';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4000);
}
