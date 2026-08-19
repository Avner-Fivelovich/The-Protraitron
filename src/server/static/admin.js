let pollInterval = setInterval(fetchQueue, 1000);

async function fetchQueue() {
    try {
        const res = await fetch('/api/admin/queue');
        if (!res.ok) {
            if (res.status === 403) {
                document.body.innerHTML = "<h1 style='color:red;text-align:center;margin-top:20%'>403 FORBIDDEN<br><small>Admin dashboard is restricted to localhost.</small></h1>";
                clearInterval(pollInterval);
            }
            throw new Error(`Status ${res.status}`);
        }
        const data = await res.json();
        
        document.getElementById('connection-dot').classList.add('online');
        document.getElementById('connection-status').innerText = 'Connected';

        renderActiveJob(data.activeJob);
        renderQueue(data.queue);
        renderHistory(data.history);

    } catch (e) {
        document.getElementById('connection-dot').classList.remove('online');
        document.getElementById('connection-status').innerText = 'Offline / Error';
    }
}

function renderActiveJob(job) {
    const container = document.getElementById('active-job-container');
    if (!job) {
        container.innerHTML = '<div class="empty-state">No active drawing job.</div>';
        return;
    }

    container.innerHTML = `
        <div class="job-item">
            <div class="job-info" style="width: 100%;">
                <h3>${job.original_name} <span style="color:#26a69a">(${job.progress}%)</span></h3>
                <div class="job-meta">ID: ${job.id} | Strokes: ${job.current_stroke}/${job.total_strokes}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${job.progress}%"></div>
                </div>
            </div>
            <div class="job-actions" style="margin-left: 1rem;">
                <button onclick="cancelJob('${job.id}')">Cancel</button>
            </div>
        </div>
    `;
}

function renderQueue(queue) {
    const container = document.getElementById('queue-container');
    if (!queue || queue.length === 0) {
        container.innerHTML = '<div class="empty-state">Queue is empty.</div>';
        return;
    }

    container.innerHTML = queue.map((job, idx) => `
        <div class="job-item">
            <div class="job-info">
                <h3>#${idx + 1} - ${job.original_name}</h3>
                <div class="job-meta">ID: ${job.id}</div>
            </div>
            <div class="job-actions">
                <button onclick="cancelJob('${job.id}')">Remove</button>
            </div>
        </div>
    `).join('');
}

function renderHistory(history) {
    const container = document.getElementById('history-container');
    if (!history || history.length === 0) {
        container.innerHTML = '<div class="empty-state">No history.</div>';
        return;
    }

    // reverse to show newest first
    const rev = [...history].reverse();
    
    container.innerHTML = rev.map((job) => {
        let color = job.status === 'completed' ? '#34c759' : (job.status === 'failed' ? '#ff3b30' : '#ff9500');
        return `
        <div class="job-item" style="opacity: 0.7">
            <div class="job-info">
                <h3>${job.original_name} <span style="color:${color}">[${job.status.toUpperCase()}]</span></h3>
                <div class="job-meta">ID: ${job.id}</div>
            </div>
        </div>
        `;
    }).join('');
}

async function cancelJob(jobId) {
    if (!confirm('Are you sure you want to cancel this job?')) return;
    
    const fd = new FormData();
    fd.append('job_id', jobId);
    await fetch('/api/admin/cancel', { method: 'POST', body: fd });
    fetchQueue();
}

async function parkRobot() {
    if (!confirm('EMERGENCY PARK: This will immediately move the robot to the home position. Continue?')) return;
    await fetch('/api/admin/park', { method: 'POST' });
}

async function triggerPaperSwap() {
    if (!confirm('Trigger automatic paper swap?')) return;
    await fetch('/api/admin/swap_paper', { method: 'POST' });
}

async function clearQueue() {
    if (!confirm('Are you sure you want to clear all waiting jobs?')) return;
    await fetch('/api/admin/clear_queue', { method: 'POST' });
    fetchQueue();
}
