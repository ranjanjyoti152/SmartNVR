#!/bin/bash
set -e

# Constants
MAX_RETRIES=30
RETRY_INTERVAL=2
DB_PATH="/app/data/smartnvr.db"
LOG_FILE="/app/data/entrypoint.log"

# Function to log messages with timestamp
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to wait for AI service with timeout
wait_for_ai() {
    local retries=0
    log "Waiting for AI service..."
    
    while ! nc -z ai 5053; do
        retries=$((retries + 1))
        if [ $retries -ge $MAX_RETRIES ]; then
            log "ERROR: AI service not available after $MAX_RETRIES attempts"
            return 1
        fi
        log "Attempt $retries/$MAX_RETRIES: AI service not ready, waiting..."
        sleep $RETRY_INTERVAL
    done
    
    log "AI service is up and running!"
    return 0
}

# Function to initialize database
init_database() {
    if [ ! -f "$DB_PATH" ]; then
        log "Database not found. Initializing..."
        if python3 init_db.py; then
            log "Database initialized successfully"
        else
            log "ERROR: Database initialization failed"
            return 1
        fi
    else
        log "Database already exists"
    fi
    return 0
}

# Function to check system resources
check_resources() {
    log "Checking system resources..."
    
    # Check available memory
    local total_mem=$(free -m | awk '/^Mem:/{print $2}')
    local avail_mem=$(free -m | awk '/^Mem:/{print $7}')
    log "Memory - Total: ${total_mem}MB, Available: ${avail_mem}MB"
    
    # Check CPU cores
    local cpu_cores=$(nproc)
    log "CPU cores available: $cpu_cores"
    
    # Check GPU if NVIDIA runtime is available
    if command -v nvidia-smi &> /dev/null; then
        log "GPU information:"
        nvidia-smi --query-gpu=gpu_name,memory.total,memory.free --format=csv,noheader
    else
        log "No NVIDIA GPU detected"
    fi
}

# Main execution flow
main() {
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting entrypoint script..."
    
    # Check system resources
    check_resources
    
    # Initialize database
    if ! init_database; then
        log "FATAL: Database initialization failed"
        exit 1
    fi
    
    # Handle different service types
    case "$1" in
        "main.py")
            log "Preparing to start NVR service..."
            if ! wait_for_ai; then
                log "FATAL: Could not connect to AI service"
                exit 1
            fi
            log "Starting NVR service..."
            exec python3 "$@"
            ;;
            
        "ai_detection.py")
            log "Starting AI detection service..."
            exec python3 "$@"
            ;;
            
        *)
            log "Unknown command: $1"
            exec "$@"
            ;;
    esac
}

# Trap signals
trap 'log "Received SIGTERM/SIGINT, shutting down..."; exit 0' TERM INT

# Execute main function
main "$@"