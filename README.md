# SmartNVR

SmartNVR is a powerful, AI-enhanced Network Video Recorder application built with Python and Flask. It provides comprehensive camera management, intelligent object detection, and a modern web interface for monitoring and reviewing security footage.

## Features

- **Camera Management**: Add and manage multiple IP cameras using RTSP streams
- **AI-Powered Detection**: Integrate with AI servers to detect and track objects in real-time 
- **Regions of Interest (ROI)**: Define specific areas for monitoring and triggering events
- **Intelligent Recording**: Save disk space with event-based recording
- **User Management**: Multi-user system with admin and regular user roles
- **Modern Dashboard**: Clean, responsive interface for viewing all camera streams
- **Playback System**: Browse and review recordings with intuitive date/time navigation
- **Events Timeline**: Track detected objects and events with detailed information
- **System Monitoring**: Monitor system resources, storage usage and camera health
- **Database Recording Storage**: Store recordings metadata in a database for improved management
- **Timeline Export**: Export recordings based on a specified timeline for backup or external use
- **Multi-client Stream Handling**: View streams in multiple tabs or browsers simultaneously

## Installation

### Automated Installation (Recommended)

The easiest way to install SmartNVR is using the provided setup script:

1. Make the setup script executable:
   ```bash
   chmod +x setup.sh
   ```

2. Run the setup script with sudo:
   ```bash
   sudo ./setup.sh
   ```

3. Follow the prompts to:
   - Install required system dependencies
   - Set up a Python virtual environment (optional)
   - Install Python packages
   - Configure directories and permissions
   - Create a systemd service (optional)
   - Set up RTSP server components (optional)
   - Configure NVIDIA CUDA support for AI acceleration (if available)

4. Start SmartNVR:
   ```bash
   ./start.sh
   ```

### Manual Installation

If you prefer to install manually:

#### Prerequisites

- Python 3.7+ 
- OpenCV and dependencies
- FFmpeg
- SQLAlchemy
- A compatible AI detection server (optional)

#### Setup Steps

1. Install system dependencies:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip python3-dev ffmpeg libsm6 libxext6 libxrender-dev
   ```

2. Install required Python packages:
   ```bash
   pip3 install Flask opencv-python numpy Pillow psutil requests SQLAlchemy Werkzeug
   ```

3. Start the application:
   ```bash
   python3 nvr-app.py
   ```

4. Access the web interface at:
   ```
   http://localhost:5000
   ```

## Configuration

### Recording Path

When using SmartNVR, you can specify your own recording path:

1. On first run, a default recording path will be used
2. Navigate to Settings → Recording to change the path
3. The path should be to an existing directory with sufficient disk space

### Database Storage

SmartNVR uses a database to store recording metadata:

1. Recordings are automatically tracked in the database
2. The database file is stored in the `database` directory
3. You can choose between file system storage or hybrid storage (files + database)

### AI Integration

SmartNVR can work with an external AI detection server:

1. Navigate to Settings → AI
2. Enter the URL of your AI server
3. Enable or disable AI processing as needed

### Running as a Service

If you used the automated installation and chose to create a systemd service:

1. Start the service:
   ```bash
   sudo systemctl start smartnvr
   ```

2. Check service status:
   ```bash
   sudo systemctl status smartnvr
   ```

3. Enable autostart at boot:
   ```bash
   sudo systemctl enable smartnvr
   ```

## Project Structure

```
SmartNVR/
├── nvr-app.py         # Main application file
├── database.py        # Database functionality for recordings
├── setup.sh           # Automated installation script
├── start.sh           # Application startup script
├── requirements.txt   # Python dependencies
├── config/            # Configuration files
│   ├── config.json    # System configuration
│   ├── users.json     # User accounts
│   ├── streams/       # Camera stream configurations
│   └── roi/           # Regions of Interest definitions
├── database/          # Database storage
│   └── smartnvr.db    # SQLite database file
├── recordings/        # Default recording storage location
├── templates/         # HTML templates for the web interface
└── static/            # Static assets (CSS, JS, images)
```

## Usage

### Adding Cameras

1. Navigate to the Cameras page
2. Click "Add Camera"
3. Enter a name and RTSP URL
4. Enable or disable as needed

### Configuring Regions of Interest (ROI)

1. Navigate to the Cameras page
2. Click the "ROI" button for a camera
3. Draw polygons on the camera view to define regions
4. Save your changes

### Viewing Recordings

1. Navigate to the Playback page
2. Select a date from the calendar
3. Browse available recordings
4. Click on a recording to play

### Exporting Timeline Recordings

1. Navigate to the Playback page
2. Click on the "Export" button
3. Select a start and end date/time
4. Choose export format (ZIP or directory)
5. Click "Export" to download the recordings

### Managing Events

1. Navigate to the Events page
2. Filter by camera, object type, or date
3. Click on an event for detailed information
4. Navigate to associated recordings if available

## Default Login

On first run, a default admin user is created:
- Username: `admin`
- Password: `admin123`

**Important:** Change this password immediately after first login.

## Troubleshooting

### Stream Issues

- Make sure your RTSP URL is correct and accessible
- Check if FFmpeg is properly installed
- Verify that your camera supports the RTSP protocol
- Open multiple tabs without interfering with stream connections

### Recording Playback Problems

- Ensure recordings path has proper permissions
- Check that file paths use forward slashes (/)
- Verify that your browser supports the video format

### AI Detection Not Working

- Verify that the AI server URL is correct in settings
- Check if the AI server is running and accessible
- Look for connection errors in the nvr-app.log file

## License

[MIT](LICENSE)

## Credits

SmartNVR uses several open source libraries and frameworks:
- Flask
- OpenCV
- SQLAlchemy
- Bootstrap
- Font Awesome