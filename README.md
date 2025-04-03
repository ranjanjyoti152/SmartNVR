# Smart NVR

A smart Network Video Recorder (NVR) system with AI-powered detection capabilities, built with FastAPI and modern web technologies.

## Features

- **User Authentication**
  - Secure registration and login system
  - Session-based authentication
  - Password hashing with bcrypt

- **Camera Management**
  - RTSP stream support
  - Multiple camera support with same RTSP URL
  - Real-time video feed display
  - AI detection toggle per camera
  - Camera status monitoring
  - Automatic stream recovery
  - Frame buffering and error handling

- **AI Detection**
  - Motion detection
  - Person detection
  - AI processing toggle per camera
  - Real-time detection indicators

- **System Monitoring**
  - CPU usage tracking
  - Memory usage monitoring
  - Disk space management
  - Recording storage metrics
  - Camera health monitoring

- **Modern UI**
  - Responsive design with Tailwind CSS
  - Real-time system status updates
  - Clean and intuitive interface
  - Mobile-friendly layout

## Tech Stack

- **Backend**
  - FastAPI (Python web framework)
  - SQLAlchemy (ORM)
  - SQLite (Database)
  - OpenCV (Video processing)
  - bcrypt (Password hashing)

- **Frontend**
  - Tailwind CSS
  - JavaScript
  - HTML5
  - Font Awesome icons

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ranjanjyoti152/smart-nvr.git
cd smart-nvr
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Initialize the database:
```bash
python init_db.py
```

4. Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Usage

1. Register a new account at `/register`
2. Log in at `/login`
3. Add cameras through the dashboard interface:
   - Each camera requires a unique name
   - Multiple cameras can use the same RTSP URL
   - Enable/disable AI detection per camera
4. Monitor camera feeds and system status
5. View camera health and stream status

## API Endpoints

- `/api/register` - User registration
- `/api/login` - User authentication
- `/api/cameras` - Camera management
- `/api/cameras/{camera_id}/status` - Camera status
- `/api/cameras/{camera_id}/ai_toggle` - Toggle AI detection
- `/api/system/status` - System metrics
- `/api/system/storage` - Storage information
- `/video_feed/{camera_id}` - Camera stream

## Recent Improvements

- Added support for multiple cameras with same RTSP URL
- Implemented camera health monitoring
- Added automatic stream recovery
- Enhanced error handling and reconnection logic
- Added frame buffering for smoother playback
- Improved camera status monitoring
- Added individual AI detection toggle
- Enhanced stream timeout detection
- Added camera events logging

## Roadmap

### Phase 1: Enhanced Security
- [ ] Implement JWT authentication
- [ ] Add HTTPS support
- [ ] Implement rate limiting
- [ ] Add two-factor authentication
- [ ] Add API key management
- [ ] Implement IP whitelisting

### Phase 2: Advanced Camera Features
- [ ] Add motion zone configuration
- [ ] Implement object tracking
- [ ] Add face detection/recognition
- [ ] Support for PTZ cameras
- [ ] Add camera groups
- [ ] Implement video playback timeline

### Phase 3: Recording Management
- [ ] Add scheduled recording
- [ ] Implement event-based recording
- [ ] Add cloud storage support
- [ ] Implement video compression
- [ ] Add recording retention policies
- [ ] Support for video exports

### Phase 4: AI Enhancements
- [ ] Add custom object detection
- [ ] Implement behavior analysis
- [ ] Add anomaly detection
- [ ] Support for multiple AI models
- [ ] Add AI training interface
- [ ] Implement scene analysis

### Phase 5: User Experience
- [ ] Add dark mode support
- [ ] Implement multi-language support
- [ ] Add mobile app
- [ ] Implement push notifications
- [ ] Add customizable dashboard
- [ ] Support for camera layouts

### Phase 6: Integration & APIs
- [ ] Add REST API documentation
- [ ] Implement WebSocket support
- [ ] Add webhook support
- [ ] Support for third-party integrations
- [ ] Add ONVIF support
- [ ] Implement MQTT support

### Phase 7: System Administration
- [ ] Add user roles and permissions
- [ ] Implement audit logging
- [ ] Add system backup/restore
- [ ] Implement clustering support
- [ ] Add performance optimization
- [ ] Support for distributed deployment

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
# SmartNVR
