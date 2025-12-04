#!/usr/bin/env python3
"""
Performance Bottleneck Test Script
Diagnoses RAM and CPU usage issues in CVsimple framework
"""
import time
import psutil
import threading
import numpy as np
from collections import deque
from typing import Dict, List, Tuple
import os
import sys

# Optional matplotlib for plotting (not required)
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("ℹ️  matplotlib not available - plotting disabled")

class PerformanceProfiler:
    """Comprehensive resource usage profiler"""

    def __init__(self):
        self.monitoring = False
        self.monitor_thread = None

        # Data storage
        self.cpu_history = deque(maxlen=200)  # 200 samples = ~100 seconds
        self.ram_history = deque(maxlen=200)
        self.gpu_history = deque(maxlen=200)
        self.timestamps = deque(maxlen=200)

        # Process handle
        self.process = psutil.Process()

        print("🔍 Performance Profiler initialized")

    def start_monitoring(self):
        """Start background monitoring"""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("📊 Started performance monitoring")

    def stop_monitoring(self):
        """Stop monitoring and return results"""
        if not self.monitoring:
            return {}

        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

        return self._analyze_results()

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                # CPU usage (non-blocking, per-process)
                cpu_percent = self.process.cpu_percent()

                # Memory usage
                memory_info = self.process.memory_info()
                ram_mb = memory_info.rss / 1024 / 1024
                ram_percent = self.process.memory_percent()

                # Try to get GPU info if available
                gpu_usage = self._get_gpu_usage()

                # Store data
                timestamp = time.time()
                self.cpu_history.append(cpu_percent)
                self.ram_history.append(ram_mb)
                self.gpu_history.append(gpu_usage)
                self.timestamps.append(timestamp)

                # Print real-time stats every 5 seconds
                if len(self.timestamps) % 50 == 0:  # Every 5 seconds (10Hz sampling)
                    print(f"📈 CPU: {cpu_percent:5.1f}% | RAM: {ram_mb:6.1f}MB ({ram_percent:5.1f}%) | GPU: {gpu_usage:5.1f}%")

                time.sleep(0.1)  # 10Hz sampling

            except Exception as e:
                print(f"❌ Monitoring error: {e}")
                time.sleep(0.5)

    def _get_gpu_usage(self):
        """Try to get GPU usage (fallback to 0 if not available)"""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.utilization()
        except:
            pass
        return 0.0

    def _analyze_results(self) -> Dict:
        """Analyze collected data"""
        if not self.cpu_history:
            return {"error": "No data collected"}

        # Convert to numpy for analysis
        cpu_data = np.array(list(self.cpu_history))
        ram_data = np.array(list(self.ram_history))

        analysis = {
            "duration_seconds": len(self.timestamps) * 0.1,
            "sample_count": len(self.cpu_history),

            # CPU Analysis
            "cpu": {
                "mean": np.mean(cpu_data),
                "max": np.max(cpu_data),
                "min": np.min(cpu_data),
                "std": np.std(cpu_data),
                "percentile_95": np.percentile(cpu_data, 95)
            },

            # RAM Analysis
            "ram": {
                "mean_mb": np.mean(ram_data),
                "max_mb": np.max(ram_data),
                "min_mb": np.min(ram_data),
                "mean_percent": np.mean(ram_data) * 100 / (16 * 1024),  # Assuming 16GB RAM
                "peak_mb": np.max(ram_data)
            },

            # Bottleneck Detection
            "bottlenecks": self._detect_bottlenecks(cpu_data, ram_data)
        }

        return analysis

    def _detect_bottlenecks(self, cpu_data: np.ndarray, ram_data: np.ndarray) -> List[str]:
        """Detect performance bottlenecks"""
        bottlenecks = []

        # CPU bottlenecks
        if np.mean(cpu_data) > 70:
            bottlenecks.append(f"🔥 High CPU usage: {np.mean(cpu_data):.1f}% (target < 50%)")

        if np.max(cpu_data) > 90:
            bottlenecks.append(f"⚠️ CPU spikes detected: {np.max(cpu_data):.1f}%")

        # RAM bottlenecks
        ram_peak_mb = np.max(ram_data)
        if ram_peak_mb > 2000:  # > 2GB
            bottlenecks.append(f"💾 High RAM usage: {ram_peak_mb:.0f}MB")

        if np.std(ram_data) > 200:  # High variability = memory pressure
            bottlenecks.append(f"📊 Unstable RAM usage: std={np.std(ram_data):.0f}MB")

        return bottlenecks

    def generate_report(self, results: Dict):
        """Generate human-readable report"""
        if "error" in results:
            print(f"❌ {results['error']}")
            return

        print("\n" + "="*60)
        print("📊 PERFORMANCE ANALYSIS REPORT")
        print("="*60)

        print(f"\n⏱️  Duration: {results['duration_seconds']:.1f} seconds ({results['sample_count']} samples)")

        # CPU Section
        cpu = results["cpu"]
        print(f"\n🖥️  CPU USAGE:")
        print(f"   Average: {cpu['mean']:5.1f}%")
        print(f"   Maximum: {cpu['max']:5.1f}%")
        print(f"   Minimum: {cpu['min']:5.1f}%")
        print(f"   95th percentile: {cpu['percentile_95']:5.1f}%")

        # RAM Section
        ram = results["ram"]
        print(f"\n💾 MEMORY USAGE:")
        print(f"   Average: {ram['mean_mb']:6.1f}MB ({ram['mean_percent']:5.1f}%)")
        print(f"   Peak:    {ram['max_mb']:6.1f}MB")
        print(f"   Minimum: {ram['min_mb']:6.1f}MB")

        # Bottlenecks
        print(f"\n🚨 BOTTLENECKS DETECTED:")
        if results["bottlenecks"]:
            for bottleneck in results["bottlenecks"]:
                print(f"   {bottleneck}")
        else:
            print("   ✅ No critical bottlenecks detected")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if cpu["mean"] > 70:
            print("   - Reduce FPS or add frame skipping")
            print("   - Optimize image processing pipeline")

        if ram["max_mb"] > 1000:
            print("   - Reduce queue sizes in frame pipeline")
            print("   - Add explicit memory cleanup")

        if not results["bottlenecks"]:
            print("   - System performance looks good!")

        print("\n" + "="*60)

def test_frame_processing():
    """Test frame processing performance"""
    print("🧪 Testing frame processing performance...")

    # Simulate frame processing
    frame_count = 100
    frame_size = (1920, 1080, 3)

    processing_times = []

    for i in range(frame_count):
        start = time.perf_counter()

        # Simulate frame operations
        frame = np.random.randint(0, 255, frame_size, dtype=np.uint8)

        # Simulate format conversions (the expensive operations)
        frame_bgr = frame[:, :, ::-1]  # RGB -> BGR
        frame_resized = cv2.resize(frame, (640, 640))  # Resize for YOLO
        frame_normalized = frame_resized.astype(np.float32) / 255.0

        processing_time = (time.perf_counter() - start) * 1000
        processing_times.append(processing_time)

        if i % 20 == 0:
            print(f"   Frame {i}: {processing_time:.1f}ms")

    avg_time = np.mean(processing_times)
    max_time = np.max(processing_times)
    theoretical_fps = 1000.0 / avg_time

    print(f"\n📈 Frame Processing Results:")
    print(f"   Average time: {avg_time:.2f}ms")
    print(f"   Maximum time: {max_time:.2f}ms")
    print(f"   Theoretical FPS: {theoretical_fps:.1f}")

    return {
        "avg_processing_time_ms": avg_time,
        "max_processing_time_ms": max_time,
        "theoretical_fps": theoretical_fps
    }

def main():
    """Main test function"""
    print("🚀 Starting CVsimple Performance Bottleneck Test")
    print("="*60)

    # Initialize profiler
    profiler = PerformanceProfiler()

    # Test 1: Frame processing performance
    frame_results = test_frame_processing()

    print("\n" + "="*60)
    print("📡 NOW MONITORING SYSTEM PERFORMANCE...")
    print("   Run your CVsimple application now")
    print("   Press Ctrl+C to stop monitoring and see results")
    print("="*60)

    # Start monitoring
    profiler.start_monitoring()

    try:
        # Monitor for specified time or until user stops
        monitor_time = 10  # Demo: 10 seconds for quick test
        print(f"⏰ Monitoring for {monitor_time} seconds...")

        for i in range(monitor_time):
            time.sleep(1)
            remaining = monitor_time - i
            if remaining % 10 == 0:
                print(f"   {remaining} seconds remaining...")

    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")

    # Stop and get results
    results = profiler.stop_monitoring()

    # Generate comprehensive report
    profiler.generate_report(results)

    # Compare with frame processing results
    if frame_results["theoretical_fps"] < 30:
        print(f"\n⚠️  Frame processing is a bottleneck!")
        print(f"    Theoretical max FPS: {frame_results['theoretical_fps']:.1f}")
        print(f"    Consider optimizing image operations")

if __name__ == "__main__":
    # Try to import OpenCV for realistic testing
    try:
        import cv2
    except ImportError:
        print("⚠️  OpenCV not available - using numpy only for frame test")
        def cv2_resize(*args, **kwargs):
            return np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        cv2 = type('cv2', (), {})()
        cv2.resize = cv2_resize

    main()