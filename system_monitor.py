import psutil
import os
from typing import Dict, Optional

class SystemMonitor:
    def __init__(self):
        self._cpu_percent = 0
        self._memory_percent = 0
        self._disk_percent = 0
        self._update_interval = 5  # seconds

    def get_cpu_percent(self) -> float:
        """Get CPU usage percentage."""
        try:
            self._cpu_percent = psutil.cpu_percent(interval=1)
        except Exception:
            pass
        return self._cpu_percent

    def get_memory_percent(self) -> float:
        """Get memory usage percentage."""
        try:
            memory = psutil.virtual_memory()
            self._memory_percent = memory.percent
        except Exception:
            pass
        return self._memory_percent

    def get_disk_percent(self) -> float:
        """Get disk usage percentage."""
        try:
            disk = psutil.disk_usage('/')
            self._disk_percent = disk.percent
        except Exception:
            pass
        return self._disk_percent

    def get_total_space_gb(self) -> float:
        """Get total disk space in GB."""
        try:
            disk = psutil.disk_usage('/')
            return disk.total / (1024 * 1024 * 1024)  # Convert bytes to GB
        except Exception:
            return 0.0

    def get_system_info(self) -> Dict[str, float]:
        """Get all system metrics."""
        return {
            'cpu_percent': self.get_cpu_percent(),
            'memory_percent': self.get_memory_percent(),
            'disk_percent': self.get_disk_percent(),
            'total_space_gb': self.get_total_space_gb()
        }

# Create a global instance
system_monitor = SystemMonitor()
