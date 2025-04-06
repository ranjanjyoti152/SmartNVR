from flask import Flask, request, jsonify, Response, render_template, redirect, url_for, session, flash, send_from_directory
import requests
import cv2
import numpy as np
from PIL import Image
import io
import logging
import os
import random
from collections import defaultdict
import time
import json
import threading
from datetime import datetime, timedelta
import uuid
import hashlib
import psutil
import shutil
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import glob
import re
# Import database functionality - fix incorrect function names
from database import init_db, store_recording, get_recordings_by_date_range, clean_old_recordings, get_session, Recording

# Ensure app can serve static files
app = Flask(__name__, static_folder='static')

# App configuration
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
os.makedirs(CONFIG_DIR, exist_ok=True)

# Use a fixed secret key instead of generating a new one on each startup
# This ensures sessions persist across app restarts
SECRET_KEY_FILE = os.path.join(CONFIG_DIR, 'secret_key')
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'rb') as f:
        app.secret_key = f.read()
else:
    # Generate a new secret key if one doesn't exist
    app.secret_key = os.urandom(24)
    with open(SECRET_KEY_FILE, 'wb') as f:
        f.write(app.secret_key)

app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to session cookie

# Main configuration file
MAIN_CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# Default configuration
DEFAULT_CONFIG = {
    "ai_server": {
        "url": "http://localhost:5054",
        "enabled": True
    },
    "recording": {
        "path": "",  # Empty by default, will prompt user to set this
        "retention_days": 7,
        "max_space_gb": 100,
        "storage_mode": "hybrid"  # 'hybrid', 'file', or 'database'
    },
    "system": {
        "name": "SmartNVR",
        "version": "1.0.0"
    }
}

# User authentication
USERS_FILE = os.path.join(CONFIG_DIR, 'users.json')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("nvr-app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create a color mapping for different object classes
COLOR_MAP = {}

# Predefined colors for common objects
PRESET_COLORS = {
    'person': (0, 255, 0),     # Green
    'car': (255, 0, 0),        # Red
    'truck': (0, 0, 255),      # Blue
    'dog': (255, 255, 0),      # Cyan
    'cat': (255, 0, 255)       # Magenta
}

# Add prediction cache to store the latest detection results
prediction_cache = {}
# How long to keep predictions visible (in seconds)
PREDICTION_CACHE_DURATION = 1.0

# Stream configuration storage
STREAM_CONFIG_DIR = os.path.join(CONFIG_DIR, 'streams')
os.makedirs(STREAM_CONFIG_DIR, exist_ok=True)
STREAM_CONFIG_FILE = os.path.join(STREAM_CONFIG_DIR, 'streams.json')

# ROI storage
ROI_CONFIG_DIR = os.path.join(CONFIG_DIR, 'roi')
os.makedirs(ROI_CONFIG_DIR, exist_ok=True)

# ROI visualization settings
ROI_COLOR = (0, 255, 255)  # Yellow for ROI outline
ROI_THICKNESS = 2
ROI_ACTIVE_COLOR = (255, 0, 255)  # Magenta for active ROIs
SHOW_ROIS = True

# Object counting
object_counts = defaultdict(int)
last_count_update = time.time()
COUNT_UPDATE_INTERVAL = 1  # Update counts every second

# Stream cache for handling multiple streams
stream_cache = {}
# Track reconnection attempts and backoff timing for each stream
reconnection_tracker = {}

# Global variable to track AI server status
ai_server_status = {
    'last_check': 0,
    'available': False,
    'last_error': None,
    'status_cache_time': 30  # Cache status for 30 seconds
}

# Setup directories
def setup_directories():
    """Setup all required directories"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(STREAM_CONFIG_DIR, exist_ok=True)
    os.makedirs(ROI_CONFIG_DIR, exist_ok=True)
    
    # Create recordings directory from config
    config = load_config()
    
    # Check if recording path is empty and prompt user on first run
    if not config["recording"]["path"]:
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recordings')
        logger.info(f"Recording path not set. Using default path: {default_path}")
        logger.info("You can change this in the settings page.")
        config["recording"]["path"] = default_path
        save_config(config)
    
    os.makedirs(config["recording"]["path"], exist_ok=True)
    
    # Create users file if it doesn't exist
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)

# Configuration functions
def load_config():
    """Load main configuration with better error handling"""
    try:
        if os.path.exists(MAIN_CONFIG_FILE):
            with open(MAIN_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            # Ensure all required fields exist by merging with default config
            merged_config = DEFAULT_CONFIG.copy()
            for section, values in config.items():
                if section in merged_config:
                    if isinstance(merged_config[section], dict) and isinstance(values, dict):
                        merged_config[section].update(values)
                    else:
                        merged_config[section] = values
                else:
                    merged_config[section] = values
                    
            return merged_config
        else:
            logger.warning("Config file not found, creating default config")
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        logger.warning("Using default configuration")
        return DEFAULT_CONFIG
        
def save_config(config):
    """Save main configuration with error handling"""
    try:
        # Ensure config directory exists
        os.makedirs(os.path.dirname(MAIN_CONFIG_FILE), exist_ok=True)
        
        with open(MAIN_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
            
        logger.info("Configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

# User authentication functions
def get_users():
    """Get all users"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        return {}

def save_users(users):
    """Save users dictionary"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def add_user(username, password, is_admin=False):
    """Add a new user with better validation and security"""
    if not username or not password:
        return False, "Username and password are required"
        
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    users = get_users()
    
    if username in users:
        return False, "Username already exists"
    
    # Use a more secure password hashing method
    hashed_password = generate_password_hash(password)
    
    users[username] = {
        "password_hash": hashed_password,
        "is_admin": is_admin,
        "created_at": datetime.now().isoformat()
    }
    
    save_users(users)
    logger.info(f"User {username} added successfully")
    return True, "User created successfully"

def verify_user(username, password):
    """Verify user credentials with improved security"""
    if not username or not password:
        return False, "Username and password are required"
        
    users = get_users()
    
    if username not in users:
        # Use constant time comparison to prevent timing attacks
        # This dummy check takes the same time as a real check would
        generate_password_hash(password)
        return False, "Invalid username or password"
    
    user = users[username]
    
    if check_password_hash(user["password_hash"], password):
        logger.info(f"User {username} authenticated successfully")
        return True, {"is_admin": user.get("is_admin", False)}
    
    return False, "Invalid username or password"

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please login to access this page", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please login to access this page", "warning")
            return redirect(url_for('login', next=request.url))
            
        users = get_users()
        username = session['user']
        if not users.get(username, {}).get('is_admin', False):
            flash("Administrator access required", "danger")
            return redirect(url_for('dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def get_color(label):
    """Get consistent color for object label"""
    if label in PRESET_COLORS:
        return PRESET_COLORS[label]
    if label not in COLOR_MAP:
        color = (
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255)
        )
        COLOR_MAP[label] = color
    return COLOR_MAP[label]

def load_stream_config():
    """Load stream configuration from file"""
    try:
        if os.path.exists(STREAM_CONFIG_FILE):
            with open(STREAM_CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        logger.error(f"Error loading stream config: {e}")
        return {}

def save_stream_config(config):
    """Save stream configuration to file"""
    try:
        with open(STREAM_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving stream config: {e}")

# Load stream configuration at startup
stream_config = load_stream_config()

# System monitoring functions
def get_system_stats():
    """Get system resource statistics"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    # Get recording directory usage
    config = load_config()
    rec_path = config["recording"]["path"]
    if os.path.exists(rec_path):
        rec_disk = psutil.disk_usage(rec_path)
        rec_usage = {
            'total': rec_disk.total,
            'used': rec_disk.used,
            'free': rec_disk.free,
            'percent': rec_disk.percent
        }
    else:
        rec_usage = {'error': 'Recording path not found'}
    return {
        'cpu': cpu_percent,
        'memory': {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'percent': memory.percent
        },
        'disk': {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent
        },
        'recording_storage': rec_usage,
        'timestamp': datetime.now().isoformat()
    }

# Recording management
def manage_recordings():
    """Manage recordings based on retention policy"""
    config = load_config()
    recording_path = config['recording']['path']
    retention_days = config['recording']['retention_days']
    max_space_gb = config['recording']['max_space_gb']
    
    if not recording_path or not os.path.exists(recording_path):
        logger.error(f"Recording path {recording_path} does not exist")
        return
    
    try:
        # 1. Remove old recordings based on retention_days
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # Either use database or file system depending on storage mode
        if config['recording']['storage_mode'] in ['database', 'hybrid']:
            # Use database to find old recordings
            session = get_session()
            try:
                old_recordings = session.query(Recording).filter(
                    Recording.timestamp < cutoff_date
                ).all()
                
                for recording in old_recordings:
                    try:
                        file_path = recording.path
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted old recording: {file_path}")
                        session.delete(recording)
                    except Exception as e:
                        logger.error(f"Error deleting recording {recording.id}: {e}")
                session.commit()
            finally:
                session.close()
                
        # If using file or hybrid mode, also clean up files
        if config['recording']['storage_mode'] in ['file', 'hybrid']:
            # Use file system to find old recordings
            for root, dirs, files in os.walk(recording_path):
                for file in files:
                    if not file.endswith('.mp4') and not file.endswith('.avi') and not file.endswith('.mkv'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        if file_time < cutoff_date:
                            os.remove(file_path)
                            logger.info(f"Deleted old recording: {file_path}")
                            
                            # For hybrid mode, also remove database entry if exists
                            if config['recording']['storage_mode'] == 'hybrid':
                                try:
                                    session = get_session()
                                    recording = session.query(Recording).filter(Recording.path == file_path).first()
                                    if recording:
                                        session.delete(recording)
                                        session.commit()
                                except Exception as e:
                                    logger.error(f"Error removing database entry for {file_path}: {e}")
                                finally:
                                    if 'session' in locals():
                                        session.close()
                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {e}")
        
        # 2. Check total space and remove oldest recordings if needed
        total_size_gb = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                            for dirpath, _, filenames in os.walk(recording_path) 
                            for filename in filenames if filename.endswith(('.mp4', '.avi', '.mkv'))) / 1e9
        
        if total_size_gb > max_space_gb:
            logger.info(f"Recording storage exceeds limit: {total_size_gb:.2f}GB > {max_space_gb}GB")
            
            # Find all recordings and sort by creation time
            recordings = []
            for root, _, files in os.walk(recording_path):
                for file in files:
                    if file.endswith(('.mp4', '.avi', '.mkv')):
                        file_path = os.path.join(root, file)
                        ctime = os.path.getctime(file_path)
                        size = os.path.getsize(file_path)
                        recordings.append((file_path, ctime, size))
            
            # Sort by creation time (oldest first)
            recordings.sort(key=lambda x: x[1])
            
            # Remove oldest recordings until we're under the limit
            current_size_gb = total_size_gb
            for file_path, _, size in recordings:
                if current_size_gb <= max_space_gb:
                    break
                
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        size_gb = size / 1e9
                        current_size_gb -= size_gb
                        logger.info(f"Deleted recording to save space: {file_path} ({size_gb:.2f}GB)")
                        
                        # Also remove from database if using hybrid mode
                        if config['recording']['storage_mode'] == 'hybrid':
                            session = get_session()
                            try:
                                recording = session.query(Recording).filter(Recording.path == file_path).first()
                                if recording:
                                    session.delete(recording)
                                    session.commit()
                            finally:
                                session.close()
                except Exception as e:
                    logger.error(f"Error deleting recording {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error managing recordings: {e}")

def open_stream(rtsp_url):
    """Open a video stream with optimized settings and fallback options"""
    global reconnection_tracker
    stream = None
    current_time = time.time()
    
    # Check for reconnection backoff
    if rtsp_url in reconnection_tracker:
        last_attempt = reconnection_tracker[rtsp_url]['last_attempt']
        attempts = reconnection_tracker[rtsp_url]['attempts']
        
        # Calculate backoff delay using exponential backoff: 2^attempts seconds (max 5 minutes)
        backoff_delay = min(2 ** attempts, 300)  # Cap at 5 minutes
        
        # If we're still within the backoff period, don't attempt reconnection
        if current_time - last_attempt < backoff_delay:
            logger.debug(f"Respecting backoff delay for {rtsp_url}, next attempt in {backoff_delay - (current_time - last_attempt):.1f}s")
            return None
    
    # Check if we already have this stream cached
    if rtsp_url in stream_cache:
        stream = stream_cache[rtsp_url]['stream']
        last_access = stream_cache[rtsp_url]['last_access']
        # If it's been more than 5 minutes, refresh the stream
        if current_time - last_access > 300:
            try:
                stream.release()
            except:
                pass
            stream = None
    
    if stream is None:
        # Update reconnection tracking
        if rtsp_url not in reconnection_tracker:
            reconnection_tracker[rtsp_url] = {'attempts': 0, 'last_attempt': current_time, 'last_success': 0}
        else:
            reconnection_tracker[rtsp_url]['attempts'] += 1
            reconnection_tracker[rtsp_url]['last_attempt'] = current_time
            
        # Log attempt with backoff information
        attempts = reconnection_tracker[rtsp_url]['attempts']
        if attempts > 0:
            backoff_delay = min(2 ** attempts, 300)
            logger.info(f"Attempting to reconnect to {rtsp_url} (attempt #{attempts}, backoff: {backoff_delay}s)")
        
        try:
            # Try with optimized settings first
            logger.debug(f"Opening RTSP stream: {rtsp_url}")
            
            # Try using more reliable transport options
            stream = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            stream.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Reduce buffer size for lower latency
            
            if not stream.isOpened():
                logger.warning("Failed to open stream with FFMPEG, trying native capture")
                stream = cv2.VideoCapture(rtsp_url)
                
            if stream.isOpened():
                # Cache the stream
                stream_cache[rtsp_url] = {
                    'stream': stream,
                    'last_access': current_time,
                    'health': 100,  # Stream health indicator (0-100)
                    'frames_read': 0,
                    'failed_reads': 0
                }
                logger.info("Stream opened successfully")
                
                # Reset reconnection attempts on successful connection
                reconnection_tracker[rtsp_url] = {
                    'attempts': 0,
                    'last_attempt': current_time,
                    'last_success': current_time
                }
            else:
                logger.error("Failed to open stream with OpenCV")
                return None
        except Exception as e:
            logger.error(f"Error opening stream: {e}")
            return None
    else:
        # Update last access time
        stream_cache[rtsp_url]['last_access'] = current_time
    
    return stream

def call_ai_server(endpoint, method='get', data=None, json_data=None, params=None, retry=1, timeout=5, files=None):
    """
    Helper function to call AI server with better error handling and retries
    
    Args:
        endpoint (str): API endpoint path (without base URL)
        method (str): HTTP method to use ('get', 'post', etc.)
        data (bytes): Binary data to send
        json_data (dict): JSON data to send
        params (dict): URL parameters 
        retry (int): Number of retry attempts
        timeout (int): Timeout in seconds
        files (dict): Files to send in multipart/form-data format
        
    Returns:
        tuple: (success, result) where result is response or error message
    """
    global ai_server_status
    
    config = load_config()
    if not config['ai_server']['enabled']:
        return False, "AI server is disabled"
        
    ai_server_url = config['ai_server']['url']
    
    # If URL doesn't start with http, add it
    if not ai_server_url.startswith('http'):
        ai_server_url = 'http://' + ai_server_url
        
    full_url = f"{ai_server_url}/{endpoint.lstrip('/')}"
    
    # Skip additional calls if we know the server is down (check every 30 seconds)
    current_time = time.time()
    if not ai_server_status['available'] and \
       current_time - ai_server_status['last_check'] < ai_server_status['status_cache_time'] and \
       ai_server_status['last_check'] > 0:
        return False, f"AI server is unreachable: {ai_server_status['last_error']}"
    
    for attempt in range(retry):
        try:
            headers = {}
            
            # Set appropriate content type headers based on request type
            # Note: Don't set Content-Type when using files parameter, as requests will set it automatically
            if data and not files:
                headers['Content-Type'] = 'image/jpeg'
            elif json_data:
                headers['Content-Type'] = 'application/json'
                
            # Debug log to see what's being sent
            logger.debug(f"AI server request to {full_url}, method={method}, headers={headers}")
            if params:
                logger.debug(f"Request params: {params}")
            
            # Make the request based on the method
            if method.lower() == 'get':
                response = requests.get(full_url, params=params, headers=headers, timeout=timeout)
            elif method.lower() == 'post':
                if files:
                    # When sending files, let requests handle the Content-Type header
                    response = requests.post(
                        full_url, 
                        files=files,
                        params=params,
                        timeout=timeout
                    )
                else:
                    response = requests.post(
                        full_url, 
                        data=data, 
                        json=json_data,
                        params=params,
                        headers=headers,
                        timeout=timeout
                    )
            else:
                return False, f"Unsupported HTTP method: {method}"
            
            # Log response info for debugging
            logger.debug(f"AI server response: {response.status_code}")
            if response.status_code != 200:
                logger.debug(f"AI server error response: {response.text}")
                
            # Update AI server status
            ai_server_status['last_check'] = current_time
            ai_server_status['available'] = True
            ai_server_status['last_error'] = None
            
            if response.status_code == 200:
                return True, response
            else:
                error_msg = f"AI server returned error: HTTP {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text}"
                logger.warning(error_msg)
                if attempt + 1 < retry:
                    logger.info(f"Retrying AI server call ({attempt+1}/{retry})")
                    time.sleep(1)  # Wait a second before retrying
                    continue
                return False, error_msg
                
        except requests.exceptions.ConnectionError as e:
            ai_server_status['available'] = False
            ai_server_status['last_error'] = "Connection error"
            logger.warning(f"AI server connection failed: {str(e)}")
        except requests.exceptions.Timeout as e:
            ai_server_status['available'] = False
            ai_server_status['last_error'] = "Timeout"
            logger.warning(f"AI server timeout: {str(e)}")
        except Exception as e:
            ai_server_status['available'] = False
            ai_server_status['last_error'] = str(e)
            logger.error(f"Error calling AI server: {str(e)}")
            
        # Only retry if we haven't tried the max number of times
        if attempt + 1 < retry:
            logger.info(f"Retrying AI server call ({attempt+1}/{retry})")
            time.sleep(1)  # Wait a second before retrying
        else:
            return False, ai_server_status['last_error']
    
    return False, "Max retries exceeded"

def generate_frames(rtsp_url, is_roi_editor=False):
    """Generate video frames with object detection and ROI overlays"""
    # Access global variables needed for tracking state
    global last_count_update, object_counts, stream_cache
    
    # Track reconnection status for this specific stream session
    last_reconnect_attempt = 0
    reconnect_cooldown = 5  # Initial cooldown of 5 seconds
    max_reconnect_cooldown = 30  # Maximum cooldown of 30 seconds
    reconnection_count = 0
    last_log_time = 0  # Track when we last logged a connection error
    
    # Open the stream
    stream = open_stream(rtsp_url)
    if not stream:
        # Return an error image
        error_img = np.zeros((480, 640, 3), np.uint8)
        cv2.putText(error_img, "Error: Could not open stream", (50, 240), 
                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Convert to JPEG
        ret, buffer = cv2.imencode('.jpg', error_img)
        error_frame = buffer.tobytes()
        
        # Yield the error frame once
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
        return
    
    # Get configuration for AI detection
    config = load_config()
    ai_enabled = config['ai_server']['enabled']
    ai_server_url = config['ai_server']['url']
    
    # Load ROIs for this stream if not in ROI editor mode
    rois = {}
    stream_id = None
    
    try:
        # Extract stream ID from RTSP URL if possible
        for s_id, s_info in load_stream_config().items():
            if s_info.get('url') == rtsp_url:
                stream_id = s_id
                break
        
        if stream_id and not is_roi_editor:
            roi_file = os.path.join(ROI_CONFIG_DIR, f"{stream_id}.json")
            if os.path.exists(roi_file):
                with open(roi_file, 'r') as f:
                    rois = json.load(f)
    except Exception as e:
        logger.error(f"Error loading ROIs: {e}")
    
    # Process frames
    frame_count = 0
    last_detection_time = time.time()
    detection_interval = 0.5  # Detect every 0.5 seconds
    
    # Create a default error image once
    error_img = np.zeros((480, 640, 3), np.uint8)
    
    while True:
        success = False
        current_time = time.time()
        
        # Try to read a frame
        try:
            if stream is not None:
                success, frame = stream.read()
                
                # Update stream health metrics if stream exists in cache
                if rtsp_url in stream_cache:
                    if success:
                        stream_cache[rtsp_url]['frames_read'] += 1
                        # Reset failed reads counter on successful read
                        if stream_cache[rtsp_url]['failed_reads'] > 0:
                            stream_cache[rtsp_url]['failed_reads'] = 0
                    else:
                        stream_cache[rtsp_url]['failed_reads'] += 1
                        # Update health metric
                        failed = stream_cache[rtsp_url]['failed_reads']
                        if failed > 3:  # After 3 failures, start reducing health
                            stream_cache[rtsp_url]['health'] = max(0, 100 - (failed * 10))
        except Exception as e:
            success = False
            logger.error(f"Error reading from stream: {e}")
        
        if not success:
            # Check if we should attempt reconnection
            if current_time - last_reconnect_attempt >= reconnect_cooldown:
                # Only log reconnection message periodically to avoid spamming logs
                if current_time - last_log_time >= 60:  # Only log once per minute
                    logger.warning(f"Lost connection to stream {rtsp_url}, attempting to reconnect...")
                    last_log_time = current_time
                
                # Update reconnection tracking
                last_reconnect_attempt = current_time
                reconnection_count += 1
                
                # Try to reconnect
                if stream is not None:
                    try:
                        stream.release()
                    except:
                        pass
                
                stream = open_stream(rtsp_url)
                
                # Increase cooldown period exponentially up to max_reconnect_cooldown
                reconnect_cooldown = min(max_reconnect_cooldown, 2 ** min(reconnection_count, 4))
            
            # Show reconnecting message
            cv2.putText(error_img, "Connection lost. Reconnecting...", (50, 240), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Add some status info
            status_text = f"Next attempt in {int(reconnect_cooldown - (current_time - last_reconnect_attempt))}s"
            cv2.putText(error_img, status_text, (50, 280), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 1)
            
            ret, buffer = cv2.imencode('.jpg', error_img)
            error_frame = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
            
            # Wait before trying again to avoid CPU thrashing
            time.sleep(0.5)
            continue
        
        # We have a valid frame - reset reconnection count on success
        reconnection_count = 0
        reconnect_cooldown = 5  # Reset to initial cooldown
        
        frame_count += 1
        
        # Make a copy of the frame for overlays
        display_frame = frame.copy()
        
        # Draw ROIs on the frame
        if SHOW_ROIS and not is_roi_editor and rois:
            for roi_id, roi_info in rois.items():
                points = roi_info.get('points', [])
                if points and len(points) > 2:
                    # Convert points to numpy array for OpenCV
                    pts = np.array(points, np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    
                    # Use different color for active ROIs
                    color = ROI_ACTIVE_COLOR if roi_info.get('enabled', True) else ROI_COLOR
                    
                    # Draw polygon
                    cv2.polylines(display_frame, [pts], True, color, ROI_THICKNESS)
                    
                    # Draw label if available
                    if 'name' in roi_info:
                        # Find top-left point for text placement
                        min_x = min(p[0] for p in points)
                        min_y = min(p[1] for p in points)
                        
                        # Draw semi-transparent background for text
                        text_size = cv2.getTextSize(roi_info['name'], cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
                        cv2.rectangle(display_frame, 
                                     (min_x, min_y - 20), 
                                     (min_x + text_size[0], min_y), 
                                     color, -1)
                        
                        # Draw text
                        cv2.putText(display_frame, roi_info['name'], 
                                   (min_x, min_y - 5), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Do object detection if AI is enabled and it's time for detection
        # Skip detection in ROI editor mode
        if ai_enabled and not is_roi_editor and current_time - last_detection_time >= detection_interval:
            try:
                # Use higher quality for detection frames
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                _, img_encoded = cv2.imencode('.jpg', frame, encode_param)
                img_bytes = img_encoded.tobytes()
                
                # Get stream ID for the request
                request_stream_id = stream_id if stream_id else str(hash(rtsp_url))
                
                # Debug info for troubleshooting
                logger.debug(f"Sending frame from stream {request_stream_id} to AI server for processing")
                
                # Save the image to a temporary file first - this ensures proper image format
                temp_img_path = os.path.join('/tmp', f"frame_{request_stream_id}_{int(time.time())}.jpg")
                with open(temp_img_path, 'wb') as f:
                    f.write(img_bytes)
                
                # Send the image file to the AI server using multipart/form-data
                try:
                    with open(temp_img_path, 'rb') as img_file:
                        files = {'image': ('image.jpg', img_file, 'image/jpeg')}
                        
                        # The AI server expects 'stream_id' as a parameter
                        params = {'stream_id': request_stream_id}
                        if rois and len(rois) > 0:
                            params['check_roi'] = 'true'
                        
                        logger.debug(f"Sending image to AI server with params: {params}")
                        
                        # Use the call_ai_server helper function instead of direct request
                        success, response = call_ai_server(
                            endpoint="predict",
                            method="post",
                            files=files,
                            params=params,
                            timeout=2
                        )
                        
                        # Process predictions if successful
                        if success:
                            try:
                                response_data = response.json()
                                logger.debug(f"Received response from AI server: {response_data}")
                                
                                # Handle different response formats - check if the response is a nested structure
                                if isinstance(response_data, dict) and 'detections' in response_data:
                                    # Extract the detections array from the nested structure
                                    predictions = response_data['detections']
                                    logger.debug(f"Extracted {len(predictions)} detections from nested response")
                                else:
                                    # Use the response directly if it's already an array
                                    predictions = response_data
                                
                                # Update prediction cache
                                prediction_cache[rtsp_url] = {
                                    'time': current_time,
                                    'predictions': predictions
                                }
                                
                                # Process object counts
                                if current_time - last_count_update >= COUNT_UPDATE_INTERVAL:
                                    for pred in predictions:
                                        if isinstance(pred, dict):
                                            label = pred.get('label', 'unknown')
                                            object_counts[label] += 1
                                    
                                    # Update the last count update time
                                    last_count_update = current_time
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse AI server response as JSON: {e}")
                                logger.debug(f"Response content: {response.text}")
                        else:
                            logger.warning(f"AI prediction failed: {response}")
                    
                    # Clean up temporary file
                    try:
                        os.unlink(temp_img_path)
                    except:
                        pass
                        
                except requests.RequestException as e:
                    logger.error(f"Request to AI server failed: {e}")
                
            except Exception as e:
                logger.error(f"AI prediction error: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
            
            # Reset detection timer
            last_detection_time = current_time
        
        # Draw cached predictions if available and recent
        if rtsp_url in prediction_cache:
            cache_data = prediction_cache[rtsp_url]
            cache_age = current_time - cache_data['time']
            
            # Only show predictions for a limited time
            if cache_age < PREDICTION_CACHE_DURATION:
                predictions = cache_data['predictions']
                
                # Draw each prediction
                for pred in predictions:
                    if isinstance(pred, dict) and 'bbox' in pred and 'label' in pred:
                        try:
                            x1, y1, x2, y2 = map(int, pred['bbox'])
                            label = pred['label']
                            # Look for 'score' first, then fall back to 'confidence' if not found
                            confidence = pred.get('score', pred.get('confidence', 0))
                            
                            # Get color for this object type
                            color = get_color(label)
                            
                            # Draw bounding box
                            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                            
                            # Draw label background
                            text = f"{label} {confidence*100:.0f}%"
                            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                            cv2.rectangle(display_frame, 
                                         (x1, y1 - 20), 
                                         (x1 + text_size[0], y1), 
                                         color, -1)
                            
                            # Draw label text
                            cv2.putText(display_frame, text, 
                                       (x1, y1 - 5), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        except (ValueError, TypeError) as e:
                            logger.error(f"Error drawing prediction: {e}, pred: {pred}")
        
        # Add timestamp and system info to the frame
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(display_frame, current_datetime, 
                   (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Convert to JPEG for streaming
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]  # Lower quality for streaming
        ret, buffer = cv2.imencode('.jpg', display_frame, encode_param)
        frame_bytes = buffer.tobytes()
        
        # Yield the frame in multipart response
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Control frame rate to reduce CPU usage
        time.sleep(0.03)  # ~30 FPS

@app.route('/health', methods=['GET'])
def health():
    """Check health of AI server and NVR app"""
    config = load_config()
    
    if config['ai_server']['enabled']:
        success, result = call_ai_server(endpoint="health", timeout=2)
        if success:
            ai_status = result.json()
        else:
            ai_status = {"status": "DOWN", "error": str(result)}
    else:
        ai_status = {"status": "DISABLED"}
        
    return jsonify({
        "ai_server": ai_status, 
        "nvr_app": {"status": "UP"},
        "timestamp": datetime.now().isoformat()
    })

@app.route('/video_feed')
@login_required
def video_feed():
    """Stream video with overlaid detections and ROIs"""
    rtsp_url = request.args.get('rtsp_url')
    if not rtsp_url:
        return "Error: No RTSP URL provided", 400
        
    is_roi_editor = request.args.get('roi_editor', 'false').lower() == 'true'
    return Response(
        generate_frames(rtsp_url, is_roi_editor),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        success, result = verify_user(username, password)
        if success:
            session['user'] = username
            session['is_admin'] = result.get('is_admin', False)
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next', url_for('dashboard'))
            return redirect(next_page)
        else:
            flash(result, "danger")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.pop('user', None)
    session.pop('is_admin', None)
    flash("You have been logged out", "success")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    # Check if any users exist, first user becomes admin
    users = get_users()
    is_first_user = len(users) == 0
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not password:
            flash("Username and password are required", "danger")
        elif password != confirm_password:
            flash("Passwords do not match", "danger")
        else:
            success, message = add_user(username, password, is_admin=is_first_user)
            if success:
                flash("Registration successful. Please login.", "success")
                return redirect(url_for('login'))
            else:
                flash(message, "danger")
    
    return render_template('register.html', is_first_user=is_first_user)

# Main application routes
@app.route('/')
def home():
    """Home page - redirects to login or dashboard"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with all camera streams"""
    streams = load_stream_config()
    return render_template('dashboard.html', streams=streams)

@app.route('/settings')
@login_required
def settings():
    """Settings page"""
    config = load_config()
    return render_template('settings.html', config=config)

@app.route('/settings/general', methods=['POST'])
@login_required
def settings_general():
    """Update general settings"""
    config = load_config()
    
    # Update system name
    if 'system_name' in request.form:
        config['system']['name'] = request.form['system_name']
        save_config(config)
    flash("Settings updated successfully", "success")
    return redirect(url_for('settings'))

@app.route('/settings/ai', methods=['POST'])
@login_required
def settings_ai():
    """Update AI server settings"""
    config = load_config()
    
    # Update AI server URL
    if 'ai_server_url' in request.form:
        config['ai_server']['url'] = request.form['ai_server_url']
    # Update enabled status
    config['ai_server']['enabled'] = 'ai_server_enabled' in request.form
    
    save_config(config)
    flash("AI settings updated successfully", "success")
    return redirect(url_for('settings'))

@app.route('/settings/recording', methods=['POST'])
@login_required
def settings_recording():
    """Update recording settings"""
    config = load_config()
    
    # Update recording path
    if 'recording_path' in request.form:
        new_path = request.form['recording_path']
        if os.path.exists(new_path) or os.access(os.path.dirname(new_path), os.W_OK):
            config['recording']['path'] = new_path
            os.makedirs(new_path, exist_ok=True)
        else:
            flash(f"Invalid recording path: {new_path}", "danger")
            return redirect(url_for('settings'))
    
    # Update retention days
    if 'retention_days' in request.form:
        try:
            days = int(request.form['retention_days'])
            if days > 0:
                config['recording']['retention_days'] = days
        except ValueError:
            flash("Retention days must be a positive number", "danger")
            return redirect(url_for('settings'))
    
    # Update max storage space
    if 'max_space_gb' in request.form:
        try:
            space = float(request.form['max_space_gb'])
            if space > 0:
                config['recording']['max_space_gb'] = space
        except ValueError:
            flash("Max space must be a positive number", "danger")
            return redirect(url_for('settings'))
    
    # Update storage mode
    if 'storage_mode' in request.form:
        storage_mode = request.form['storage_mode']
        if storage_mode in ['file', 'hybrid', 'database']:
            config['recording']['storage_mode'] = storage_mode
    
    save_config(config)
    flash("Recording settings updated successfully", "success")
    return redirect(url_for('settings'))

@app.route('/streams')
@login_required
def manage_streams():
    """Stream management page"""
    streams = load_stream_config()
    return render_template('streams.html', streams=streams)

@app.route('/stream', methods=['POST'])
@login_required
def add_stream():
    """Add or update a stream"""
    data = request.form
    
    if not data or 'name' not in data or 'url' not in data:
        flash("Missing required fields", "danger")
        return redirect(url_for('manage_streams'))
    
    # Generate ID if new stream
    stream_id = data.get('id', str(uuid.uuid4()))
    
    # Update stream config
    streams = load_stream_config()
    streams[stream_id] = {
        "id": stream_id,
        "name": data['name'],
        "url": data['url'],
        "enabled": data.get('enabled', 'on') == 'on',
        "added": data.get('added', datetime.now().isoformat()),
        "roi_enabled": data.get('roi_enabled', 'on') == 'on'
    }
    
    save_stream_config(streams)
    flash(f"Stream '{data['name']}' saved successfully", "success")
    
    # Redirect back to the appropriate page
    if 'source' in data and data['source'] == 'dashboard':
        return redirect(url_for('dashboard'))
    return redirect(url_for('manage_streams'))

@app.route('/stream/<stream_id>', methods=['DELETE'])
@login_required
def delete_stream(stream_id):
    """Delete a stream"""
    streams = load_stream_config()
    if stream_id in streams:
        stream_name = streams[stream_id]['name']
        stream_url = streams[stream_id]['url']
        
        # 1. Delete stream from config
        del streams[stream_id]
        save_stream_config(streams)
        
        # 2. Delete ROI configuration if exists
        roi_file = os.path.join(ROI_CONFIG_DIR, f"{stream_id}.json")
        if os.path.exists(roi_file):
            try:
                os.remove(roi_file)
                logger.info(f"Deleted ROI configuration for stream {stream_name}")
            except Exception as e:
                logger.error(f"Failed to delete ROI file for stream {stream_id}: {e}")
        
        # 3. Release stream from cache if present
        if stream_url in stream_cache:
            try:
                stream_cache[stream_url]['stream'].release()
                del stream_cache[stream_url]
                logger.info(f"Released stream {stream_name} from cache")
            except Exception as e:
                logger.error(f"Error releasing stream {stream_name} from cache: {e}")
        
        # 4. Clean up database entries related to this stream
        config = load_config()
        if config['recording']['storage_mode'] in ['database', 'hybrid']:
            try:
                session = get_session()
                try:
                    # Delete recordings associated with this stream
                    recordings = session.query(Recording).filter(Recording.stream_id == stream_id).all()
                    for recording in recordings:
                        # Delete file if exists
                        if recording.has_file and recording.path and os.path.exists(recording.path):
                            try:
                                os.remove(recording.path)
                                logger.info(f"Deleted recording file: {recording.path}")
                            except Exception as e:
                                logger.error(f"Failed to delete recording file: {e}")
                        
                        # Delete database entry
                        session.delete(recording)
                    
                    session.commit()
                    logger.info(f"Deleted database entries for stream {stream_name}")
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error deleting database entries for stream {stream_id}: {e}")
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Database error when deleting stream {stream_id}: {e}")
                
        return jsonify({"status": "success", "message": f"Stream '{stream_name}' and associated resources deleted successfully"})
    
    return jsonify({"error": "Stream not found"}), 404

@app.route('/monitor')
@login_required
def system_monitor():
    """System monitoring page"""
    stats = get_system_stats()
    return render_template('monitor.html', stats=stats)

@app.route('/api/system/stats')
@login_required
def api_system_stats():
    """API endpoint for system stats"""
    return jsonify(get_system_stats())

@app.route('/api/streams/status')
@login_required
def api_streams_status():
    """API endpoint to get status of all streams"""
    streams = load_stream_config()
    status_data = {}
    
    for stream_id, stream_info in streams.items():
        # Check if the stream is in the stream cache and accessible
        stream_url = stream_info.get('url', '')
        is_connected = False
        
        if stream_url in stream_cache:
            last_access = stream_cache[stream_url]['last_access']
            stream_obj = stream_cache[stream_url]['stream']
            # If accessed in the last minute and stream is open, consider it connected
            if time.time() - last_access < 60 and stream_obj and stream_obj.isOpened():
                is_connected = True
        
        # Get predictions if available
        has_detections = False
        detections = []
        
        if stream_url in prediction_cache:
            cache_data = prediction_cache[stream_url]
            cache_age = time.time() - cache_data['time']
            
            # Only use recent predictions
            if cache_age < 10:  # Predictions not older than 10 seconds
                has_detections = len(cache_data['predictions']) > 0
                detections = cache_data['predictions']
                
        # Get ROIs if available
        roi_file = os.path.join(ROI_CONFIG_DIR, f"{stream_id}.json")
        has_rois = os.path.exists(roi_file)
        
        status_data[stream_id] = {
            'connected': is_connected,
            'enabled': stream_info.get('enabled', True),
            'has_detections': has_detections,
            'detections': detections,
            'has_rois': has_rois,
            'last_updated': datetime.now().isoformat()
        }
    
    return jsonify(status_data)

@app.route('/playback')
@login_required
def playback():
    """Recording playback page"""
    config = load_config()
    rec_path = config["recording"]["path"]
    
    # Add streams data to fix the template error
    streams = load_stream_config()
    
    # Get all recordings, organized by date
    recordings = []
    
    if os.path.exists(rec_path):
        # Get recordings from all subdirectories
        for root, dirs, files in os.walk(rec_path):
            for file in files:
                if file.endswith('.mp4'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, rec_path)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    # Extract camera name and timestamp from filename if possible
                    camera_name = "Unknown"
                    timestamp = file_mtime
                    
                    # Try to parse filename like "camera1_20230215_153045.mp4"
                    match = re.match(r'(.+)_(\d{8})_(\d{6})\.mp4', file)
                    if match:
                        camera_name = match.group(1).replace('_', ' ').title()
                        try:
                            date_str = match.group(2)
                            time_str = match.group(3)
                            timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                        except ValueError:
                            pass
                    
                    recordings.append({
                        'path': rel_path,
                        'camera': camera_name,
                        'timestamp': timestamp.isoformat(),
                        'date': timestamp.strftime("%Y-%m-%d"),
                        'time': timestamp.strftime("%H:%M:%S"),
                        'size': os.path.getsize(file_path)
                    })
    
    # Group recordings by date
    recordings_by_date = {}
    for rec in recordings:
        date = rec['date']
        if date not in recordings_by_date:
            recordings_by_date[date] = []
        recordings_by_date[date].append(rec)
    
    # Sort each date's recordings by timestamp
    for date in recordings_by_date:
        recordings_by_date[date].sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Sort dates
    sorted_dates = sorted(recordings_by_date.keys(), reverse=True)
    
    return render_template('playback.html',
                           recordings_by_date=recordings_by_date,
                           sorted_dates=sorted_dates,
                           streams=streams)

@app.route('/playback/recordings')
@login_required
def get_recordings_by_date():
    """API endpoint to get recordings for a specific date"""
    date = request.args.get('date')
    config = load_config()
    rec_path = config["recording"]["path"]
    
    # Handle null date case
    if date == 'null' or not date:
        today = datetime.now().strftime('%Y-%m-%d')
        date = today
    
    # Get camera filter if provided
    camera_id = request.args.get('camera', 'all')
    
    # Get all recordings for the specified date
    recordings = []
    
    if os.path.exists(rec_path):
        # Get recordings from all subdirectories
        for root, dirs, files in os.walk(rec_path):
            for file in files:
                if file.endswith('.mp4'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, rec_path)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    # Extract camera name and timestamp from filename if possible
                    camera_name = "Unknown"
                    timestamp = file_mtime
                    
                    # Try to parse filename like "camera1_20230215_153045.mp4"
                    match = re.match(r'(.+)_(\d{8})_(\d{6})\.mp4', file)
                    if match:
                        camera_name = match.group(1).replace('_', ' ').title()
                        try:
                            date_str = match.group(2)
                            time_str = match.group(3)
                            timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                        except ValueError:
                            pass
                    
                    # Check if recording matches the requested date
                    recording_date = timestamp.strftime("%Y-%m-%d")
                    if recording_date == date:
                        # Add recording to list
                        rec = {
                            'path': rel_path,
                            'camera': camera_name,
                            'timestamp': timestamp.isoformat(),
                            'date': recording_date,
                            'time': timestamp.strftime("%H:%M:%S"),
                            'size': os.path.getsize(file_path)
                        }
                        
                        # Filter by camera if specified and not 'all'
                        if camera_id == 'all' or camera_name.lower() == camera_id.lower():
                            recordings.append(rec)
    
    # Sort recordings by timestamp (newest first)
    recordings.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({
        'date': date,
        'recordings': recordings
    })

@app.route('/recordings/<path:filename>')
@login_required
def recording_file(filename):
    """Serve a recording file"""
    config = load_config()
    rec_path = config["recording"]["path"]
    return send_from_directory(rec_path, filename)

@app.route('/roi/<stream_id>')
@login_required
def roi_editor(stream_id):
    """ROI editor for a specific stream"""
    streams = load_stream_config()
    if stream_id not in streams:
        flash("Stream not found", "danger")
        return redirect(url_for('manage_streams'))
    
    stream = streams[stream_id]
    # Get ROIs for this stream
    roi_file = os.path.join(ROI_CONFIG_DIR, f"{stream_id}.json")
    rois = {}
    
    if os.path.exists(roi_file):
        try:
            with open(roi_file, 'r') as f:
                rois = json.load(f)
        except Exception as e:
            logger.error(f"Error loading ROIs for stream {stream_id}: {e}")
    
    return render_template('roi_editor.html', stream=stream, rois=rois)

@app.route('/roi/<stream_id>/save', methods=['POST'])
@login_required
def save_roi(stream_id):
    """Save ROIs for a stream"""
    data = request.json
    if not data:
        return jsonify({"error": "No ROI data provided"}), 400
    
    # Validate stream ID exists to prevent directory traversal attacks
    streams = load_stream_config()
    if stream_id not in streams:
        logger.warning(f"Attempt to save ROI for non-existent stream: {stream_id}")
        return jsonify({"error": "Invalid stream ID"}), 404
    
    # Validate ROI data structure
    try:
        for roi_id, roi_info in data.items():
            # Check required fields
            if 'points' not in roi_info or not isinstance(roi_info['points'], list):
                return jsonify({"error": f"Invalid ROI data format for {roi_id}: missing or invalid points"}), 400
            
            # Check points data
            for point in roi_info['points']:
                if not isinstance(point, list) or len(point) != 2:
                    return jsonify({"error": f"Invalid point format in ROI {roi_id}"}), 400
    except Exception as e:
        logger.error(f"Error validating ROI data: {e}")
        return jsonify({"error": "Invalid ROI data structure"}), 400
    
    # Save ROIs to file
    roi_file = os.path.join(ROI_CONFIG_DIR, f"{stream_id}.json")
    
    try:
        # Ensure directory exists before saving
        os.makedirs(os.path.dirname(roi_file), exist_ok=True)
        
        with open(roi_file, 'w') as f:
            json.dump(data, f, indent=4)
        
        # Send ROIs to AI server if enabled
        config = load_config()
        if config['ai_server']['enabled']:
            # Add stream ID to the data so AI server knows which stream these ROIs are for
            roi_data = {
                'stream_id': stream_id,
                'rois': data
            }
            
            success, response = call_ai_server(
                endpoint="roi", 
                method="post", 
                json_data=roi_data, 
                retry=3,
                timeout=5
            )
            
            if not success:
                logger.warning(f"Failed to send ROIs to AI server: {response}")
                # Still return success to the user since we saved the ROIs locally
                return jsonify({
                    "status": "partial_success", 
                    "message": "ROIs saved locally but failed to sync with AI server. AI detection may not work correctly.",
                    "ai_error": str(response)
                })
        
        # Add a debug log to confirm save was successful
        logger.info(f"ROIs saved successfully for stream {stream_id}")
        return jsonify({"status": "success", "message": "ROIs saved successfully"})
    except Exception as e:
        logger.error(f"Error saving ROIs: {e}")
        return jsonify({"error": f"Failed to save ROIs: {str(e)}"}), 500

@app.route('/roi/<stream_id>/get')
@login_required
def get_roi(stream_id):
    """Get ROIs for a stream"""
    roi_file = os.path.join(ROI_CONFIG_DIR, f"{stream_id}.json")
    
    if os.path.exists(roi_file):
        try:
            with open(roi_file, 'r') as f:
                rois = json.load(f)
            return jsonify(rois)
        except Exception as e:
            logger.error(f"Error loading ROIs for stream {stream_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({})

@app.route('/events')
@login_required
def events():
    """Events page displaying detected events and alerts"""
    # Get streams for context
    streams = load_stream_config()
    
    # In a future implementation, this would load actual events from a database
    # For now, just render an empty events page
    return render_template('events.html', streams=streams)

@app.route('/api/users')
@login_required
def api_users():
    """API endpoint to get information about users"""
    # Only return limited information for security
    users = get_users()
    safe_users = {}
    
    for username, user_data in users.items():
        safe_users[username] = {
            "is_admin": user_data.get("is_admin", False),
            "created_at": user_data.get("created_at", ""),
            # Don't include password hash in response
        }
    
    # Include current user info
    current_user = session.get('user')
    
    return jsonify({
        "users": safe_users,
        "current_user": current_user,
        "is_admin": session.get('is_admin', False)
    })

# Run scheduled tasks in background
def run_scheduled_tasks():
    """Run periodic tasks like cleaning old recordings"""
    while True:
        try:
            manage_recordings()
        except Exception as e:
            logger.error(f"Error in scheduled tasks: {e}")
        
        # Run once every hour
        time.sleep(3600)

# Initialize system
# @app.before_first_request  # Deprecated in Flask 2.x
def initialize_system():
    """Initialize the system"""
    setup_directories()
    
    # Check if first run and create admin user
    users = get_users()
    if not users:
        # Create default admin user on first run
        add_user('admin', 'admin123', is_admin=True)
        logger.info("Created default admin user 'admin' with password 'admin123'")

# Register the initialize_system function with Flask 2.x compatible approach
with app.app_context():
    initialize_system()

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'), exist_ok=True)
    
    # Initialize database
    init_db()
    
    # Start the scheduled tasks thread (only once)
    task_thread = threading.Thread(target=run_scheduled_tasks)
    task_thread.daemon = True
    task_thread.start()
    
    # Run the Flask application
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
