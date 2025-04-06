#!/bin/bash

# SmartNVR Installation Script
# This script installs all dependencies required for SmartNVR to run properly

# Text colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print header
echo -e "\n${BLUE}================================================${NC}"
echo -e "${BLUE}       SmartNVR Installation Script${NC}"
echo -e "${BLUE}================================================${NC}\n"

# Check if script is run with sudo or as root
if [ "$EUID" -ne 0 ]
  then echo -e "${RED}Please run this script as root or with sudo${NC}"
  exit 1
fi

# Make script exit on any error
set -e

# Function to print status messages
print_status() {
  echo -e "${YELLOW}>> $1${NC}"
}

# Function to print success messages
print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Function to create directory if it doesn't exist
ensure_directory() {
  if [ ! -d "$1" ]; then
    mkdir -p "$1"
    print_success "Created directory: $1"
  else
    echo "Directory exists: $1"
  fi
}

# Detect OS distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
else
    OS=$(uname -s)
    VER=$(uname -r)
fi

print_status "Detected operating system: $OS $VER"

# Update package lists
print_status "Updating package lists..."
apt-get update
print_success "Package lists updated"

# Install system dependencies
print_status "Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    git \
    build-essential \
    wget \
    curl \
    unzip

print_success "System dependencies installed"

# Setup Python virtual environment (optional)
VENV_DIR="/home/proxpc/SmartNVR/venv"

if [ ! -d "$VENV_DIR" ]; then
    print_status "Setting up Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    print_success "Python virtual environment created at $VENV_DIR"
    
    echo "To activate the virtual environment, use:"
    echo "source $VENV_DIR/bin/activate"
else
    print_status "Virtual environment already exists at $VENV_DIR"
fi

# Function to install Python packages
install_python_packages() {
    if [ -d "$VENV_DIR" ] && [ "$USE_VENV" = true ]; then
        print_status "Installing Python packages in virtual environment..."
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip
        pip install -r "/home/proxpc/SmartNVR/requirements.txt"
        deactivate
    else
        print_status "Installing Python packages system-wide..."
        pip3 install --upgrade pip
        pip3 install -r "/home/proxpc/SmartNVR/requirements.txt"
    fi
    
    print_success "Python packages installed"
}

# Create requirements.txt file if it doesn't exist
REQ_FILE="/home/proxpc/SmartNVR/requirements.txt"

if [ ! -f "$REQ_FILE" ]; then
    print_status "Creating requirements.txt file..."
    cat > "$REQ_FILE" << EOF
# Web framework
Flask>=2.0.1

# Database
SQLAlchemy>=1.4.23

# Image and video processing
opencv-python>=4.5.3
numpy>=1.21.2
Pillow>=9.0.0

# System monitoring
psutil>=5.8.0

# HTTP requests
requests>=2.26.0

# Security
Werkzeug>=2.0.1

# Additional utilities
python-dateutil>=2.8.2
EOF

    print_success "Created requirements.txt file"
fi

# Ask if the user wants to use the virtual environment for installing packages
USE_VENV=false
read -p "Do you want to install Python packages in a virtual environment? (y/N): " choice
case "$choice" in 
  y|Y ) USE_VENV=true;;
  * ) USE_VENV=false;;
esac

# Install Python packages
install_python_packages

# Ensure required directories exist
print_status "Checking required directories..."
DIRECTORIES=(
    "/home/proxpc/SmartNVR/config"
    "/home/proxpc/SmartNVR/config/streams"
    "/home/proxpc/SmartNVR/config/roi"
    "/home/proxpc/SmartNVR/database"
    "/home/proxpc/SmartNVR/recordings"
    "/home/proxpc/SmartNVR/static"
    "/home/proxpc/SmartNVR/templates"
)

for dir in "${DIRECTORIES[@]}"; do
    ensure_directory "$dir"
done

# Set correct permissions
print_status "Setting correct permissions..."
chown -R proxpc:proxpc /home/proxpc/SmartNVR
chmod -R 755 /home/proxpc/SmartNVR
print_success "Permissions set"

# Create a startup script
print_status "Creating startup script..."
cat > "/home/proxpc/SmartNVR/start.sh" << EOF
#!/bin/bash
# Startup script for SmartNVR

# Change to the SmartNVR directory
cd "\$(dirname "\$0")"

# Check if we should use the virtual environment
if [ -d "./venv" ]; then
    echo "Activating virtual environment..."
    source ./venv/bin/activate
fi

# Start the application
echo "Starting SmartNVR..."
python3 nvr-app.py
EOF

chmod +x "/home/proxpc/SmartNVR/start.sh"
print_success "Startup script created"

# Optional: Create a systemd service
print_status "Do you want to create a systemd service to run SmartNVR at startup? (y/N): "
read -p "" setup_service

if [[ "$setup_service" =~ ^[Yy]$ ]]; then
    print_status "Creating systemd service..."
    cat > "/etc/systemd/system/smartnvr.service" << EOF
[Unit]
Description=SmartNVR Security Camera System
After=network.target

[Service]
User=proxpc
WorkingDirectory=/home/proxpc/SmartNVR
ExecStart=/bin/bash /home/proxpc/SmartNVR/start.sh
Restart=on-failure
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=smartnvr

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable smartnvr.service
    print_success "Systemd service created and enabled"
    
    print_status "You can now start SmartNVR with: systemctl start smartnvr"
    print_status "Check status with: systemctl status smartnvr"
fi

# Final instructions
echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}       SmartNVR Setup Complete${NC}"
echo -e "${GREEN}============================================${NC}\n"

echo -e "You can start SmartNVR by running:"
echo -e "  ${BLUE}cd /home/proxpc/SmartNVR && ./start.sh${NC}"
echo ""

if [ "$USE_VENV" = true ]; then
    echo -e "Or manually with:"
    echo -e "  ${BLUE}cd /home/proxpc/SmartNVR${NC}"
    echo -e "  ${BLUE}source venv/bin/activate${NC}"
    echo -e "  ${BLUE}python3 nvr-app.py${NC}"
else
    echo -e "Or manually with:"
    echo -e "  ${BLUE}cd /home/proxpc/SmartNVR${NC}"
    echo -e "  ${BLUE}python3 nvr-app.py${NC}"
fi

echo -e "\nAccess the web interface at: ${BLUE}http://localhost:5000${NC}"
echo -e "Default login: ${BLUE}admin / admin123${NC} (change this after first login!)"

# If we have ffmpeg, offer to install RTSP server components
if command_exists ffmpeg; then
    echo -e "\n${YELLOW}Additional Feature:${NC}"
    echo -e "Would you like to install RTSP server components for streaming local cameras?"
    read -p "Install RTSP components? (y/N): " install_rtsp
    
    if [[ "$install_rtsp" =~ ^[Yy]$ ]]; then
        print_status "Installing RTSP server components..."
        apt-get install -y v4l-utils
        pip3 install rtsp-simple-server
        print_success "RTSP components installed"
        
        echo -e "\nYou can now use local cameras with:"
        echo -e "  ${BLUE}rtsp-simple-server${NC}"
    fi
fi

# Check for GPU and offer to install AI acceleration
if lspci | grep -i "vga.*nvidia" > /dev/null; then
    echo -e "\n${YELLOW}NVIDIA GPU Detected:${NC}"
    echo -e "Would you like to install NVIDIA CUDA support for AI acceleration?"
    read -p "Install CUDA support? (y/N): " install_cuda
    
    if [[ "$install_cuda" =~ ^[Yy]$ ]]; then
        print_status "Please visit: https://developer.nvidia.com/cuda-downloads"
        print_status "And follow the instructions for your specific OS version"
        
        print_status "After installing CUDA, you may need to install additional packages:"
        echo -e "  ${BLUE}pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu116${NC}"
    fi
fi

exit 0