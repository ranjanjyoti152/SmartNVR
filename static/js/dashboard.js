// Modal handling
function showAddCameraModal() {
    document.getElementById('addCameraModal').classList.remove('hidden');
}

function hideAddCameraModal() {
    document.getElementById('addCameraModal').classList.add('hidden');
}

// Form submission
document.addEventListener('DOMContentLoaded', function() {
    const addCameraForm = document.getElementById('addCameraForm');
    if (addCameraForm) {
        addCameraForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const data = {
                name: formData.get('name'),
                url: formData.get('url'),
                ai_enabled: formData.get('ai_enabled') === 'on'
            };
            
            try {
                const response = await fetch('/api/cameras', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    hideAddCameraModal();
                    window.location.reload();
                } else {
                    const errorData = await response.json();
                    alert(errorData.detail || 'Failed to add camera');
                }
            } catch (error) {
                console.error('Error adding camera:', error);
                alert('Failed to add camera. Please try again.');
            }
        });
    }
});

// System status updates
async function updateSystemStatus() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        
        // Update CPU
        document.getElementById('cpuUsage').textContent = `${data.cpu_percent}%`;
        document.getElementById('cpuBar').style.width = `${data.cpu_percent}%`;
        
        // Update Memory
        document.getElementById('memoryUsage').textContent = `${data.memory_percent}%`;
        document.getElementById('memoryBar').style.width = `${data.memory_percent}%`;
        
        // Update Disk
        document.getElementById('diskUsage').textContent = `${data.disk_percent}%`;
        document.getElementById('diskBar').style.width = `${data.disk_percent}%`;
        
    } catch (error) {
        console.error('Error updating system status:', error);
    }
}

async function updateStorageInfo() {
    try {
        const response = await fetch('/api/system/storage');
        const data = await response.json();
        
        document.getElementById('storageSize').textContent = `${data.total_space_gb} GB`;
        document.getElementById('recordingCount').textContent = `${data.recording_count} recordings`;
        
    } catch (error) {
        console.error('Error updating storage info:', error);
    }
}

// AI toggle functionality
async function toggleAI(cameraId) {
    try {
        const response = await fetch(`/api/cameras/${cameraId}/ai_toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const button = document.getElementById(`ai-toggle-${cameraId}`);
            
            if (data.ai_enabled) {
                button.innerHTML = '<i class="fas fa-brain mr-1"></i>AI ON';
                button.classList.remove('bg-gray-500/20');
                button.classList.add('bg-green-500/20');
            } else {
                button.innerHTML = '<i class="fas fa-brain mr-1"></i>AI OFF';
                button.classList.remove('bg-green-500/20');
                button.classList.add('bg-gray-500/20');
            }
        }
    } catch (error) {
        console.error('Error toggling AI:', error);
    }
}

// Initialize status updates
setInterval(updateSystemStatus, 5000);
setInterval(updateStorageInfo, 5000);

// Initial update
updateSystemStatus();
updateStorageInfo();