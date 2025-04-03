import cv2
import threading
import time
import logging
from typing import Dict, Optional
from queue import Queue
import numpy as np

logger = logging.getLogger(__name__)

class CameraStream:
    def __init__(self, camera_id: int, url: str, ai_enabled: bool = True):
        self.camera_id = camera_id
        self.url = url
        self.ai_enabled = ai_enabled
        self.is_running = False
        self._frame = None
        self._lock = threading.Lock()
        self._frame_queue = Queue(maxsize=10)  # Buffer last 10 frames
        self._thread = None
        self._last_frame_time = 0
        self._reconnect_timeout = 5  # Seconds to wait before reconnection attempts
        self._frame_timeout = 10  # Seconds to wait before considering stream dead

    def _stream_worker(self):
        """Worker thread to continuously read frames from camera."""
        while self.is_running:
            try:
                # Initialize video capture
                cap = cv2.VideoCapture(self.url)
                if not cap.isOpened():
                    raise Exception(f"Failed to open RTSP stream: {self.url}")

                logger.info(f"Successfully connected to camera {self.camera_id}")

                # Read frames while camera is working
                while self.is_running:
                    ret, frame = cap.read()
                    if not ret:
                        raise Exception("Failed to read frame")

                    # Update frame timestamp
                    self._last_frame_time = time.time()

                    # Convert frame to JPEG
                    _, jpeg_frame = cv2.imencode('.jpg', frame)
                    jpeg_bytes = jpeg_frame.tobytes()

                    # Update frame with thread safety
                    with self._lock:
                        self._frame = jpeg_bytes

                    # Add to frame queue, removing old frame if full
                    if self._frame_queue.full():
                        try:
                            self._frame_queue.get_nowait()
                        except:
                            pass
                    self._frame_queue.put(jpeg_bytes)

                    # Small sleep to prevent CPU overload
                    time.sleep(0.001)

            except Exception as e:
                logger.error(f"Stream error for camera {self.camera_id}: {str(e)}")
                if cap:
                    cap.release()

                # If stream is still supposed to be running, attempt reconnection
                if self.is_running:
                    logger.info(f"Attempting to reconnect camera {self.camera_id} in {self._reconnect_timeout} seconds")
                    time.sleep(self._reconnect_timeout)
                    continue

            finally:
                if cap:
                    cap.release()

    def start(self):
        """Start the camera stream."""
        if self.is_running:
            return

        self.is_running = True
        self._thread = threading.Thread(target=self._stream_worker)
        self._thread.daemon = True
        self._thread.start()
        logger.info(f"Started camera stream {self.camera_id}")

    def stop(self):
        """Stop the camera stream."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info(f"Stopped camera stream {self.camera_id}")

    def get_frame(self) -> Optional[bytes]:
        """Get the current frame as JPEG bytes."""
        with self._lock:
            # Check if stream is dead
            if self._last_frame_time and time.time() - self._last_frame_time > self._frame_timeout:
                logger.warning(f"Camera {self.camera_id} stream appears to be dead")
                return None
            return self._frame

    def get_stream_status(self) -> Dict:
        """Get current stream status."""
        current_time = time.time()
        return {
            "is_running": self.is_running,
            "has_recent_frames": bool(self._last_frame_time and current_time - self._last_frame_time < self._frame_timeout),
            "last_frame_age": current_time - self._last_frame_time if self._last_frame_time else None,
            "queue_size": self._frame_queue.qsize()
        }

class CameraManager:
    def __init__(self):
        self.streams: Dict[int, CameraStream] = {}
        self._lock = threading.Lock()

    def get_stream(self, camera_id: int, url: str, ai_enabled: bool = True) -> CameraStream:
        """Get or create a camera stream."""
        with self._lock:
            if camera_id not in self.streams:
                self.streams[camera_id] = CameraStream(camera_id, url, ai_enabled)
            return self.streams[camera_id]

    def remove_stream(self, camera_id: int):
        """Remove a camera stream."""
        with self._lock:
            if camera_id in self.streams:
                self.streams[camera_id].stop()
                del self.streams[camera_id]

    def get_all_streams_status(self) -> Dict[int, Dict]:
        """Get status of all streams."""
        return {
            camera_id: stream.get_stream_status()
            for camera_id, stream in self.streams.items()
        }

# Create a global instance
camera_manager = CameraManager()