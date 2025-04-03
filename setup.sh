#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Smart NVR system...${NC}"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10.0"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then 
    echo -e "${GREEN}Python version $python_version is compatible${NC}"
else
    echo -e "${RED}Error: Python version $python_version is not compatible. Please install Python 3.10 or higher${NC}"
    exit 1
fi

# Create virtual environment
echo -e "\n${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo -e "\n${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Check CUDA availability
echo -e "\n${YELLOW}Checking CUDA availability...${NC}"
python3 - <<EOF
import torch
if torch.cuda.is_available():
    print("\033[0;32mCUDA is available! GPU acceleration enabled.\033[0m")
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"GPU Device: {torch.cuda.get_device_name(0)}")
else:
    print("\033[1;33mWarning: CUDA is not available. Running in CPU mode.\033[0m")
EOF

# Download YOLOv5 model
echo -e "\n${YELLOW}Downloading YOLOv5 model...${NC}"
if [ ! -f "yolov5n.pt" ]; then
    wget https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5n.pt
else
    echo -e "${GREEN}YOLOv5 model already exists${NC}"
fi

# Initialize database
echo -e "\n${YELLOW}Initializing database...${NC}"
python3 init_db.py

echo -e "\n${GREEN}Setup completed successfully!${NC}"
echo -e "\nTo start the system:"
echo -e "1. Start the AI server:   ${YELLOW}python3 custom_ml_studio.py --port 5053 --debug --model yolov5n.pt${NC}"
echo -e "2. Start the NVR server:  ${YELLOW}python3 main.py${NC}"
echo -e "\nAccess the web interface at: ${YELLOW}http://localhost:8000${NC}"
