from typing import Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RecordingManager:
    def __init__(self):
        self.active_recordings: Dict[int, 'Recording'] = {}

    def start_recording(self, camera_id: int) -> bool:
        """Start recording for a camera."""
        if camera_id in self.active_recordings:
            return False
        
        try:
            recording = Recording(camera_id)
            self.active_recordings[camera_id] = recording
            recording.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start recording for camera {camera_id}: {str(e)}")
            return False

    def stop_recording(self, camera_id: int) -> bool:
        """Stop recording for a camera."""
        if camera_id not in self.active_recordings:
            return False
        
        try:
            recording = self.active_recordings[camera_id]
            recording.stop()
            del self.active_recordings[camera_id]
            return True
        except Exception as e:
            logger.error(f"Failed to stop recording for camera {camera_id}: {str(e)}")
            return False

    def is_recording(self, camera_id: int) -> bool:
        """Check if a camera is currently recording."""
        return camera_id in self.active_recordings

class Recording:
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.filename: Optional[str] = None
        self.is_active = False

    def start(self):
        """Start the recording."""
        self.start_time = datetime.utcnow()
        self.is_active = True
        logger.info(f"Started recording for camera {self.camera_id}")

    def stop(self):
        """Stop the recording."""
        self.end_time = datetime.utcnow()
        self.is_active = False
        logger.info(f"Stopped recording for camera {self.camera_id}")

    def add_frame(self, frame: bytes):
        """Add a frame to the recording."""
        if not self.is_active:
            return
        
        # This would normally write the frame to a video file
        pass

# Create a global instance
recording_manager = RecordingManager()