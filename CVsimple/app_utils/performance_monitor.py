"""
Performance Monitor Module for CVsimple

Provides real-time performance monitoring and metrics collection
for YOLO detection pipeline optimization.
"""

import time
import threading
import psutil
import queue
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import deque
import numpy as np


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    fps: float = 0.0
    capture_latency: float = 0.0
    inference_latency: float = 0.0
    combat_latency: float = 0.0
    total_latency: float = 0.0

    # System metrics
    cpu_utilization: float = 0.0
    gpu_utilization: float = 0.0
    memory_usage: float = 0.0
    gpu_memory_usage: float = 0.0

    # Queue metrics
    queue_sizes: Dict[str, int] = field(default_factory=dict)

    # Frame statistics
    frames_processed: int = 0
    frames_dropped: int = 0
    frame_drops_rate: float = 0.0

    # Timestamp
    timestamp: float = field(default_factory=time.time)


class PerformanceMonitor:
    """
    Real-time performance monitoring system for CVsimple
    """

    def __init__(self, history_size: int = 100, update_interval: float = 0.1):
        self.history_size = history_size
        self.update_interval = update_interval

        # Thread safety
        self.metrics_lock = threading.RLock()

        # Performance data storage
        self.frame_times = deque(maxlen=history_size)
        self.capture_latencies = deque(maxlen=history_size)
        self.inference_latencies = deque(maxlen=history_size)
        self.combat_latencies = deque(maxlen=history_size)

        # System metrics history
        self.cpu_history = deque(maxlen=history_size)
        self.memory_history = deque(maxlen=history_size)

        # Queue size tracking
        self.queue_sizes = {}

        # Frame statistics
        self.frames_processed = 0
        self.frames_dropped = 0
        self.start_time = time.time()

        # Monitoring thread
        self.is_monitoring = False
        self.monitor_thread = None

        # GPU monitoring
        self.gpu_available = self._check_gpu_availability()

        # Metrics cache
        self._cached_metrics = PerformanceMetrics()
        self._last_metrics_update = 0
        self._cache_ttl = 0.05  # Cache for 50ms

    def _check_gpu_availability(self) -> bool:
        """Check if GPU monitoring is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def start_monitoring(self):
        """Start performance monitoring thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_worker,
            name="PerformanceMonitorThread",
            daemon=True
        )
        self.monitor_thread.start()
        print("🔍 Performance monitoring started")

    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
        print("🛑 Performance monitoring stopped")

    def _monitoring_worker(self):
        """Background monitoring thread"""
        while self.is_monitoring:
            try:
                # Update system metrics
                self._update_system_metrics()

                # Sleep for interval
                time.sleep(self.update_interval)

            except Exception as e:
                print(f"❌ Performance monitoring error: {e}")
                time.sleep(self.update_interval)

    def _update_system_metrics(self):
        """Update system-level metrics"""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent()
            memory_info = psutil.virtual_memory()

            with self.metrics_lock:
                self.cpu_history.append(cpu_percent)
                self.memory_history.append(memory_info.percent)

        except Exception as e:
            print(f"⚠️ System metrics update failed: {e}")

    def record_frame_time(self, latency: float):
        """Record frame processing time"""
        with self.metrics_lock:
            self.frame_times.append(latency)
            self.frames_processed += 1

    def record_capture_latency(self, latency: float):
        """Record window capture latency"""
        with self.metrics_lock:
            self.capture_latencies.append(latency)

    def record_inference_latency(self, latency: float):
        """Record YOLO inference latency"""
        with self.metrics_lock:
            self.inference_latencies.append(latency)

    def record_combat_latency(self, latency: float):
        """Record combat processing latency"""
        with self.metrics_lock:
            self.combat_latencies.append(latency)

    def record_dropped_frame(self):
        """Record a dropped frame"""
        with self.metrics_lock:
            self.frames_dropped += 1

    def update_queue_size(self, queue_name: str, size: int):
        """Update queue size for monitoring"""
        with self.metrics_lock:
            self.queue_sizes[queue_name] = size

    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        current_time = time.time()

        # Use cached metrics if recent
        if (current_time - self._last_metrics_update < self._cache_ttl and
            self._cached_metrics.fps > 0):
            return self._cached_metrics

        with self.metrics_lock:
            metrics = PerformanceMetrics()

            # Calculate FPS
            if len(self.frame_times) >= 10:
                avg_frame_time = np.mean(list(self.frame_times))
                metrics.fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0.0

            # Average latencies
            if self.capture_latencies:
                metrics.capture_latency = np.mean(list(self.capture_latencies))

            if self.inference_latencies:
                metrics.inference_latency = np.mean(list(self.inference_latencies))

            if self.combat_latencies:
                metrics.combat_latency = np.mean(list(self.combat_latencies))

            # Total latency
            metrics.total_latency = (metrics.capture_latency +
                                   metrics.inference_latency +
                                   metrics.combat_latency)

            # System metrics
            if self.cpu_history:
                metrics.cpu_utilization = np.mean(list(self.cpu_history))
            else:
                metrics.cpu_utilization = psutil.cpu_percent()

            if self.memory_history:
                metrics.memory_usage = np.mean(list(self.memory_history))
            else:
                memory_info = psutil.virtual_memory()
                metrics.memory_usage = memory_info.percent

            # GPU metrics if available
            if self.gpu_available:
                try:
                    import torch
                    if torch.cuda.is_available():
                        allocated = torch.cuda.memory_allocated()
                        cached = torch.cuda.memory_reserved()
                        total = torch.cuda.get_device_properties(0).total_memory
                        metrics.gpu_memory_usage = (allocated / total) * 100

                        # GPU utilization (simplified)
                        metrics.gpu_utilization = min(100, (allocated / total) * 120)
                except:
                    pass

            # Queue sizes
            metrics.queue_sizes = self.queue_sizes.copy()

            # Frame statistics
            metrics.frames_processed = self.frames_processed
            metrics.frames_dropped = self.frames_dropped
            total_frames = metrics.frames_processed + metrics.frames_dropped
            metrics.frame_drops_rate = (metrics.frames_dropped / total_frames * 100) if total_frames > 0 else 0.0

            # Timestamp
            metrics.timestamp = current_time

        # Update cache
        self._cached_metrics = metrics
        self._last_metrics_update = current_time

        return metrics

    def get_average_metrics(self, window_size: int = 30) -> PerformanceMetrics:
        """Get average metrics over a time window"""
        with self.metrics_lock:
            metrics = PerformanceMetrics()

            # Calculate averages from recent history
            frame_times_slice = list(self.frame_times)[-window_size:]
            if frame_times_slice:
                avg_frame_time = np.mean(frame_times_slice)
                metrics.fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0.0

            capture_slice = list(self.capture_latencies)[-window_size:]
            if capture_slice:
                metrics.capture_latency = np.mean(capture_slice)

            inference_slice = list(self.inference_latencies)[-window_size:]
            if inference_slice:
                metrics.inference_latency = np.mean(inference_slice)

            combat_slice = list(self.combat_latencies)[-window_size:]
            if combat_slice:
                metrics.combat_latency = np.mean(combat_slice)

            metrics.total_latency = (metrics.capture_latency +
                                   metrics.inference_latency +
                                   metrics.combat_latency)

            return metrics

    def reset_metrics(self):
        """Reset all metrics and counters"""
        with self.metrics_lock:
            self.frame_times.clear()
            self.capture_latencies.clear()
            self.inference_latencies.clear()
            self.combat_latencies.clear()
            self.cpu_history.clear()
            self.memory_history.clear()

            self.frames_processed = 0
            self.frames_dropped = 0
            self.start_time = time.time()

            self.queue_sizes.clear()

    def get_performance_report(self) -> str:
        """Generate formatted performance report"""
        metrics = self.get_current_metrics()

        report = f"""
📊 Performance Report ({time.strftime('%H:%M:%S')})
═══════════════════════════════════════════════════════════

🎯 Performance Metrics:
  • FPS: {metrics.fps:.1f}
  • Frame Drops: {metrics.frame_drops_rate:.1f}%
  • Total Latency: {metrics.total_latency:.1f}ms

⏱️ Latency Breakdown:
  • Capture: {metrics.capture_latency:.1f}ms
  • Inference: {metrics.inference_latency:.1f}ms
  • Combat: {metrics.combat_latency:.1f}ms

💻 System Resources:
  • CPU: {metrics.cpu_utilization:.1f}%
  • Memory: {metrics.memory_usage:.1f}%
  • GPU Memory: {metrics.gpu_memory_usage:.1f}%

📦 Queue Status:
"""

        for queue_name, size in metrics.queue_sizes.items():
            report += f"  • {queue_name}: {size} items\n"

        report += f"""
📈 Statistics:
  • Frames Processed: {metrics.frames_processed:,}
  • Frames Dropped: {metrics.frames_dropped:,}
  • Runtime: {time.time() - self.start_time:.1f}s
"""

        return report

    def check_performance_alerts(self) -> List[str]:
        """Check for performance issues and return alerts"""
        alerts = []
        metrics = self.get_current_metrics()

        # FPS alerts
        if metrics.fps < 15:
            alerts.append("🚨 Low FPS detected (< 15 FPS)")
        elif metrics.fps < 25:
            alerts.append("⚠️ Suboptimal FPS (< 25 FPS)")

        # Latency alerts
        if metrics.inference_latency > 80:
            alerts.append("⚠️ High inference latency (> 80ms)")

        if metrics.total_latency > 120:
            alerts.append("⚠️ High total latency (> 120ms)")

        # Resource alerts
        if metrics.cpu_utilization > 90:
            alerts.append("⚠️ High CPU usage (> 90%)")

        if metrics.memory_usage > 85:
            alerts.append("⚠️ High memory usage (> 85%)")

        # Frame drop alerts
        if metrics.frame_drops_rate > 5:
            alerts.append("⚠️ High frame drop rate (> 5%)")

        # Queue alerts
        for queue_name, size in metrics.queue_sizes.items():
            if size > 8:
                alerts.append(f"⚠️ Large queue: {queue_name} ({size} items)")

        return alerts

    def export_metrics(self, filename: str) -> bool:
        """Export metrics to CSV file"""
        try:
            import csv

            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['timestamp', 'fps', 'capture_latency', 'inference_latency',
                            'combat_latency', 'cpu_utilization', 'memory_usage',
                            'frames_processed', 'frames_dropped']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()

                # Write current snapshot
                metrics = self.get_current_metrics()
                writer.writerow({
                    'timestamp': metrics.timestamp,
                    'fps': metrics.fps,
                    'capture_latency': metrics.capture_latency,
                    'inference_latency': metrics.inference_latency,
                    'combat_latency': metrics.combat_latency,
                    'cpu_utilization': metrics.cpu_utilization,
                    'memory_usage': metrics.memory_usage,
                    'frames_processed': metrics.frames_processed,
                    'frames_dropped': metrics.frames_dropped
                })

            print(f"✅ Metrics exported to {filename}")
            return True

        except Exception as e:
            print(f"❌ Failed to export metrics: {e}")
            return False


# Global performance monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor instance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def start_global_monitoring():
    """Start global performance monitoring"""
    monitor = get_performance_monitor()
    monitor.start_monitoring()


def stop_global_monitoring():
    """Stop global performance monitoring"""
    monitor = get_performance_monitor()
    monitor.stop_monitoring()


def record_frame_latency(latency: float):
    """Record frame processing time in global monitor"""
    monitor = get_performance_monitor()
    monitor.record_frame_time(latency)


def record_inference_latency(latency: float):
    """Record inference latency in global monitor"""
    monitor = get_performance_monitor()
    monitor.record_inference_latency(latency)


def update_queue_status(queue_name: str, size: int):
    """Update queue status in global monitor"""
    monitor = get_performance_monitor()
    monitor.update_queue_size(queue_name, size)


if __name__ == "__main__":
    # Test performance monitor
    monitor = PerformanceMonitor()
    monitor.start_monitoring()

    print("🧪 Testing Performance Monitor...")

    # Simulate some metrics
    for i in range(50):
        monitor.record_frame_time(33.3 + np.random.normal(0, 5))
        monitor.record_inference_latency(45.0 + np.random.normal(0, 10))
        monitor.record_capture_latency(12.0 + np.random.normal(0, 3))
        time.sleep(0.05)

    # Generate report
    print(monitor.get_performance_report())

    # Check alerts
    alerts = monitor.check_performance_alerts()
    if alerts:
        print("⚠️ Performance Alerts:")
        for alert in alerts:
            print(f"  • {alert}")

    monitor.stop_monitoring()
    print("✅ Performance monitor test completed")