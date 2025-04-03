# Build stage
FROM python:3.10-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /build

# Copy requirements first for better cache utilization
COPY requirements.txt .

# Install dependencies into /build
RUN pip install --no-cache-dir --prefix=/build -r requirements.txt

# Download YOLOv5 model
RUN mkdir -p /build/models && \
    wget https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5n.pt -P /build/models/

# Runtime stage
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    netcat \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/data /app/recordings /app/models

# Create a non-root user
RUN useradd -m -u 1000 smartnvr && \
    chown -R smartnvr:smartnvr /app

# Copy Python packages and model from builder stage
COPY --from=builder /build/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /build/models/yolov5n.pt /app/models/

# Copy the entrypoint script
COPY --chown=smartnvr:smartnvr docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copy the application code
COPY --chown=smartnvr:smartnvr . .

# Switch to non-root user
USER smartnvr

# Expose ports
EXPOSE 8000 5053

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Set default command (will be passed to entrypoint)
CMD ["main.py"]