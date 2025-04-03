#!/bin/bash

# Constants
COMPOSE_FILE="docker-compose.yml"
LOG_FILE="docker-manage.log"
SERVICES="nvr ai"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    local message=$2
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

# Check if docker and docker-compose are installed
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        log "ERROR" "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log "ERROR" "Docker Compose is not installed"
        exit 1
    fi
}

# Check NVIDIA GPU availability
check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        log "INFO" "NVIDIA GPU detected"
        nvidia-smi --query-gpu=gpu_name,memory.total,memory.free --format=csv,noheader
    else
        log "WARNING" "No NVIDIA GPU detected - AI service may run slower on CPU"
    fi
}

# Build containers
build() {
    log "INFO" "Building containers..."
    docker-compose -f $COMPOSE_FILE build --pull
}

# Start services
start() {
    log "INFO" "Starting services..."
    check_gpu
    docker-compose -f $COMPOSE_FILE up -d
    
    # Wait for services to be healthy
    for service in $SERVICES; do
        wait_for_healthy $service
    done
}

# Stop services
stop() {
    log "INFO" "Stopping services..."
    docker-compose -f $COMPOSE_FILE down
}

# Restart services
restart() {
    stop
    start
}

# Show service logs
logs() {
    local service=$1
    if [ -z "$service" ]; then
        docker-compose -f $COMPOSE_FILE logs --tail=100 -f
    else
        docker-compose -f $COMPOSE_FILE logs --tail=100 -f $service
    fi
}

# Check service health
wait_for_healthy() {
    local service=$1
    local retries=30
    local delay=2

    echo -n "Waiting for $service to be healthy"
    while [ $retries -gt 0 ]; do
        if docker-compose -f $COMPOSE_FILE ps $service | grep -q "healthy"; then
            echo -e "\n${GREEN}$service is healthy${NC}"
            return 0
        fi
        echo -n "."
        sleep $delay
        retries=$((retries - 1))
    done
    echo -e "\n${RED}$service failed to become healthy${NC}"
    return 1
}

# Show container status
status() {
    echo -e "${YELLOW}Container Status:${NC}"
    docker-compose -f $COMPOSE_FILE ps

    echo -e "\n${YELLOW}Resource Usage:${NC}"
    docker stats --no-stream $(docker-compose -f $COMPOSE_FILE ps -q)
}

# Clean up unused resources
cleanup() {
    log "INFO" "Cleaning up unused Docker resources..."
    docker-compose -f $COMPOSE_FILE down --remove-orphans
    docker system prune -f
}

# Show help message
show_help() {
    echo -e "${YELLOW}SmartNVR Docker Management Script${NC}"
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build    - Build or rebuild services"
    echo "  start    - Start services"
    echo "  stop     - Stop services"
    echo "  restart  - Restart services"
    echo "  status   - Show service status and resource usage"
    echo "  logs     - Show service logs (use 'logs nvr' or 'logs ai' for specific service)"
    echo "  cleanup  - Remove unused Docker resources"
    echo "  help     - Show this help message"
}

# Main script execution
check_dependencies

case "$1" in
    "build")
        build
        ;;
    "start")
        start
        ;;
    "stop")
        stop
        ;;
    "restart")
        restart
        ;;
    "status")
        status
        ;;
    "logs")
        logs $2
        ;;
    "cleanup")
        cleanup
        ;;
    "help"|"")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac