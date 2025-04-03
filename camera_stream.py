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
        self._frame_queue = Queue(maxsize=3)  # Reduced buffer size
        self._thread = None
        self._last_frame_time = 0
        self._reconnect_timeout = 5  # Seconds to wait before reconnection attempts
        self._frame_timeout = 30  # Increased timeout
        self._cap = None
        self._fps_limit = 10  # Reduced FPS to lower resource usage
        self._frame_interval = 1.0 / self._fps_limit
        self._max_retries = 3  # Maximum number of immediate reconnection attempts

    def _stream_worker(self):
        """Worker thread to continuously read frames from camera."""
        retry_count = 0
        
        while self.is_running:
            try:
                # Initialize video capture with optimized settings
                if self._cap is None:
                    self._cap = cv2.VideoCapture(self.url)
                    if not self._cap.isOpened():
                        raise Exception(f"Failed to open RTSP stream: {self.url}")
                    
                    # Optimize buffer size and timeouts
                    self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    self._cap.set(cv2.CAP_PROP_FPS, self._fps_limit)
                    
                    logger.info(f"Successfully connected to camera {self.camera_id}")
                    retry_count = 0  # Reset retry counter on successful connection

                # Read frames while camera is working
                last_frame_time = time.time()
                while self.is_running:
                    # Implement FPS limiting
                    current_time = time.time()
                    if current_time - last_frame_time < self._frame_interval:
                        time.sleep(0.001)  # Short sleep to prevent CPU overload
                        continue

                    ret, frame = self._cap.read()
                    if not ret:
                        raise Exception("Failed to read frame")

                    # Update frame timestamp
                    self._last_frame_time = current_time
                    last_frame_time = current_time

                    # Resize frame to reduce memory usage
                    frame = cv2.resize(frame, (640, 360))

                    # Convert frame to JPEG with reduced quality
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
                    _, jpeg_frame = cv2.imencode('.jpg', frame, encode_param)
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

            except Exception as e:
                logger.error(f"Stream error for camera {self.camera_id}: {str(e)}")
                if self._cap:
                    self._cap.release()
                    self._cap = None

                # If stream is still supposed to be running, attempt reconnection
                if self.is_running:
                    retry_count += 1
                    if retry_count > self._max_retries:
                        # If max retries reached, wait longer before next attempt
                        logger.info(f"Attempting to reconnect camera {self.camera_id} in {self._reconnect_timeout} seconds")
                        time.sleep(self._reconnect_timeout)
                        retry_count = 0
                    else:
                        # Quick retry for transient errors
                        time.sleep(1)
                    continue

            finally:
                if self._cap:
                    self._cap.release()
                    self._cap = None

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
        if self._cap:
            self._cap.release()
            self._cap = None
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