document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const video = document.getElementById('webcam');
    const canvas = document.getElementById('photo-canvas');
    const cameraStatus = document.getElementById('camera-status');
    const videoWrapper = document.getElementById('video-wrapper');
    const fallbackWrapper = document.getElementById('fallback-wrapper');
    
    const btnSnap = document.getElementById('btn-snap');
    const btnSwitchCamera = document.getElementById('btn-switch-camera');
    const btnCloseCamera = document.getElementById('btn-close-camera');
    const btnOpenCamera = document.getElementById('btn-open-camera');
    const nativeCameraInput = document.getElementById('native-camera');
    const captureCard = document.querySelector('.capture-card');
    const resultCard = document.querySelector('.result-card');
    
    const resultPlaceholder = document.getElementById('result-placeholder');
    const placeholderText = document.getElementById('placeholder-text');
    const loader = document.getElementById('loader');
    const comparisonView = document.getElementById('comparison-view');
    const rawPreview = document.getElementById('raw-preview');
    const sketchPreview = document.getElementById('sketch-preview');
    const sketchPreview96 = document.getElementById('sketch-preview-96');
    
    const resultActions = document.getElementById('result-actions');
    const btnReset = document.getElementById('btn-reset');
    const btnDraw = document.getElementById('btn-draw');
    
    let stream = null;
    let currentFacingMode = "environment"; // default to back camera
    
    let currentJobId = null;
    let currentSvgFilename = null;
    let currentOriginalName = null;

    // Initialize Camera Stream
    async function initCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.log("WebRTC camera stream not supported in this browser/context.");
            useFallbackMode();
            return;
        }

        try {
            // Request camera stream. Use currentFacingMode for toggling
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: { ideal: currentFacingMode },
                    width: { ideal: 1024 },
                    height: { ideal: 768 }
                },
                audio: false
            });
            
            video.srcObject = stream;
            videoWrapper.style.display = 'flex';
            fallbackWrapper.style.display = 'none';
            cameraStatus.textContent = 'Live Feed Connected';
            cameraStatus.classList.add('ready');
        } catch (err) {
            console.warn("Could not acquire direct camera feed:", err);
            // This is very common over non-localhost HTTP or if permission is denied
            useFallbackMode();
        }
    }

    function useFallbackMode() {
        videoWrapper.style.display = 'none';
        fallbackWrapper.style.display = 'flex';
        cameraStatus.textContent = 'Ready (Upload/Native Capture)';
        cameraStatus.classList.add('ready');
        
        // Stop any stream that might be half-initialized
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
    }

    // Capture Image from <video> Stream
    btnSnap.addEventListener('click', () => {
        if (!stream) return;
        
        // Set canvas dimensions to match video stream exactly
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        const ctx = canvas.getContext('2d');
        // Mirror the image horizontally if it's the front camera
        // Note: For simplicity and general use, we do standard capture:
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert canvas image to Blob and send
        canvas.toBlob((blob) => {
            if (blob) {
                uploadImageFile(blob, 'captured_photo.jpg');
            }
        }, 'image/jpeg', 0.9);
    });

    // Native Camera File Selection
    nativeCameraInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            uploadImageFile(file, file.name);
        }
    });


    // Send photo to Flask Server
    async function uploadImageFile(fileBlob, filename) {
        setLoadingState(true);
        
        const formData = new FormData();
        formData.append('file', fileBlob, filename);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || errData.error || 'Server error uploading image');
            }

            const data = await response.json();
            currentJobId = data.jobId;
            currentSvgFilename = data.svgUrl96.split('/').pop();
            currentOriginalName = fileBlob.name || "capture.jpg";
            displayResults(data.rawUrl, data.svgUrl, data.svgUrl96);
        } catch (error) {
            alert(`Error: ${error.message}`);
            setLoadingState(false);
            resetView();
        }
    }

    function setLoadingState(isLoading) {
        if (isLoading) {
            if (captureCard) {
                captureCard.style.display = 'none';
                captureCard.classList.remove('full-width');
            }
            if (resultCard) {
                resultCard.style.display = 'flex';
                resultCard.classList.add('full-width');
            }
            
            resultPlaceholder.style.display = 'flex';
            placeholderText.style.display = 'none';
            loader.style.display = 'block';
            comparisonView.style.display = 'none';
            resultActions.style.display = 'none';
        } else {
            loader.style.display = 'none';
        }
    }

    function displayResults(rawUrl, sketchUrl, sketchUrl96) {
        // Append cache-busting timestamp to bypass browser caching when repeating captures
        const timestamp = new Date().getTime();
        rawPreview.src = `${rawUrl}?t=${timestamp}`;
        sketchPreview.src = `${sketchUrl}?t=${timestamp}`;
        if (sketchPreview96 && sketchUrl96) {
            sketchPreview96.src = `${sketchUrl96}?t=${timestamp}`;
        }
        
        // Transition display states
        resultPlaceholder.style.display = 'none';
        loader.style.display = 'none';
        comparisonView.style.display = 'grid';
        
        // Hide capture card and expand result card
        if (captureCard) captureCard.style.display = 'none';
        if (resultCard) resultCard.classList.add('full-width');
        
        resultActions.style.display = 'flex';
    }

    function resetView() {
        rawPreview.src = '';
        sketchPreview.src = '';
        if (sketchPreview96) sketchPreview96.src = '';
        comparisonView.style.display = 'none';
        resultActions.style.display = 'none';
        
        resultPlaceholder.style.display = 'flex';
        placeholderText.style.display = 'flex';
        loader.style.display = 'none';
        
        // Reset file inputs
        if (nativeCameraInput) nativeCameraInput.value = '';
        
        // Show capture card full-width and hide result card entirely
        if (captureCard) {
            captureCard.style.display = 'flex';
            captureCard.classList.add('full-width');
        }
        if (resultCard) {
            resultCard.style.display = 'none';
            resultCard.classList.remove('full-width');
        }
    }

    // Reset Click Handler
    btnReset.addEventListener('click', resetView);

    // Dynamic QR Code update matching screen's current URL or server IP fallback
    const qrImg = document.querySelector('.qr-image-wrapper img');
    if (qrImg) {
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            // Fetch the real local IP from the server so scanning works over Wi-Fi
            fetch('/api/qr-data')
                .then(res => res.json())
                .then(data => {
                    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(data.local_ip_url)}`;
                })
                .catch(() => {
                    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(window.location.href)}`;
                });
        } else {
            // Already visiting via external IP or Pinggy tunnel link, so scan the current URL directly
            qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(window.location.href)}`;
        }
    }

    // Self-Destruct trigger matching presentation logic
    const sdBtn = document.getElementById('sd-btn');
    if (sdBtn) {
        sdBtn.addEventListener('click', () => {
            document.body.classList.add('shaking');
            sdBtn.innerText = "OH NO!!!";
            setTimeout(() => {
                document.body.classList.remove('shaking');
                sdBtn.innerText = "Self-Destruct";
                alert("CURSE YOU PERRY THE PLATYPUS!!!");
            }, 1500);
        });
    }

    // Switch Camera Button Click Handler
    if (btnSwitchCamera) {
        btnSwitchCamera.addEventListener('click', async () => {
            currentFacingMode = currentFacingMode === "environment" ? "user" : "environment";
            // Restart stream with new facingMode
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
            await initCamera();
        });
    }

    if (btnCloseCamera) {
        btnCloseCamera.addEventListener('click', useFallbackMode);
    }
    
    if (btnOpenCamera) {
        btnOpenCamera.addEventListener('click', async () => {
            await initCamera();
        });
    }

    if (btnDraw) {
        btnDraw.addEventListener('click', async () => {
            if (!currentJobId) return;
            const passcode = prompt("Enter Security Passcode to start robotic execution:");
            if (!passcode) return;
            
            const formData = new FormData();
            formData.append('job_id', currentJobId);
            formData.append('svg_filename', currentSvgFilename);
            formData.append('original_name', currentOriginalName);
            formData.append('passcode', passcode);
            
            try {
                const response = await fetch('/api/draw', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.detail || 'Failed to queue drawing');
                }
                
                if (result.status === "queued") {
                    alert(`Job queued successfully! Position in queue: ${result.position}`);
                } else if (result.status === "already_queued") {
                    alert("This job is already in the queue or processing.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        });
    }

    // Default to closed camera / fallback mode on startup
    useFallbackMode();
});
