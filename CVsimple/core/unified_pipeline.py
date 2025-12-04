"""
Unified High-Performance Pipeline
Single-threaded design with configurable FPS and direct component integration
Eliminates dual-system complexity and resource competition
"""
import time
import numpy as np
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from queue import Queue, Empty
import cv2

# Import our optimized components
from .dx_window_capture import DXWindowCapture
from .yolo_detector import MultiThreadedYOLODetector
from .combat_controller import AsyncCombatController

@dataclass
class PipelineResult:
    """Result from single pipeline execution"""
    frame: Optional[np.ndarray]
    detections: Optional[List[Dict[str, Any]]]
    actions: Optional[Dict[str, Any]]
    timestamp: float
    processing_time_ms: float
    capture_time_ms: float
    inference_time_ms: float
    combat_time_ms: float

class UnifiedPipeline:
    """
    Unified capture → inference → combat pipeline
    Single-threaded design for maximum performance and maintainability
    """

    def __init__(self, logger=None, target_fps=60):
        self.logger = logger or print
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps

        # Core components - optimized single instances
        self.dx_capture = None
        self.yolo_detector = None
        self.combat_controller = None

        # Pipeline state
        self.is_running = False
        self.current_hwnd = None
        self.frame_count = 0
        self.frames_processed = 0

        # Performance metrics
        self.performance_metrics = {
            'avg_processing_time_ms': 0,
            'avg_capture_time_ms': 0,
            'avg_inference_time_ms': 0,
            'avg_combat_time_ms': 0,
            'actual_fps': 0,
            'frames_dropped': 0,
            'total_frames': 0
        }

        # Result queues (for external consumption)
        self.result_queue = Queue(maxsize=5)  # Keep only latest 5 results
        self.stats_lock = threading.Lock()

        # Initialize components
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all pipeline components"""
        try:
            # Initialize dxcam for high-performance capture
            self.dx_capture = DXWindowCapture(output_color="RGB")
            self.log("✅ dxcam initialized")

            # Test dxcam functionality immediately
            import win32gui
            test_hwnd = win32gui.GetForegroundWindow()
            test_frame = self.dx_capture.capture_window_screenshot(test_hwnd)
            if test_frame is not None:
                self.log(f"✅ dxcam test successful: {test_frame.shape}")
            else:
                self.log("⚠️ dxcam test failed - will use fallback")
                self.dx_capture = None

        except Exception as e:
            self.log(f"⚠️ dxcam initialization failed: {e}")
            self.dx_capture = None

        try:
            # Initialize YOLO detector
            self.yolo_detector = MultiThreadedYOLODetector(logger=self.log)
            # Test YOLO functionality
            if hasattr(self.yolo_detector, 'model') and self.yolo_detector.model is not None:
                self.log("✅ YOLO detector initialized")
            else:
                self.log("⚠️ YOLO model not loaded - will try to load")

        except Exception as e:
            self.log(f"⚠️ YOLO initialization failed: {e}")
            self.yolo_detector = None

        try:
            # Initialize combat controller
            self.combat_controller = AsyncCombatController(logger=self.log)
            self.log("✅ Combat controller initialized")

        except Exception as e:
            self.log(f"⚠️ Combat controller initialization failed: {e}")
            self.combat_controller = None

    def start_pipeline(self, hwnd: int) -> bool:
        """Start the unified pipeline"""
        if self.is_running:
            self.log("⚠️ Pipeline already running")
            return False

        # Validate window
        try:
            import win32gui
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                self.log(f"❌ Invalid window handle: {hwnd}")
                return False
            window_title = win32gui.GetWindowText(hwnd)
            self.log(f"🎯 Target window: {window_title}")
        except Exception as e:
            self.log(f"❌ Window validation failed: {e}")
            return False

        self.current_hwnd = hwnd
        self.is_running = True
        self.frame_count = 0
        self.frames_processed = 0

        self.log(f"🚀 Starting unified pipeline at {self.target_fps} FPS")
        return True

    def stop_pipeline(self):
        """Stop the unified pipeline gracefully"""
        self.is_running = False
        self.log("🛑 Unified pipeline stopped")

    def process_frame(self) -> Optional[PipelineResult]:
        """
        Process a single frame through the entire pipeline
        This is the core unified processing function
        """
        if not self.is_running or not self.current_hwnd:
            return None

        start_time = time.perf_counter()

        try:
            # Step 1: Capture Frame
            capture_start = time.perf_counter()
            frame = self._capture_frame()
            capture_time = (time.perf_counter() - capture_start) * 1000

            if frame is None:
                return PipelineResult(
                    frame=None, detections=None, actions=None,
                    timestamp=start_time, processing_time_ms=0,
                    capture_time_ms=0, inference_time_ms=0, combat_time_ms=0
                )

            # Step 2: YOLO Inference
            inference_start = time.perf_counter()
            detections = self._run_inference(frame)
            inference_time = (time.perf_counter() - inference_start) * 1000

            # Step 3: Combat Processing
            combat_start = time.perf_counter()
            actions = self._process_combat(detections)
            combat_time = (time.perf_counter() - combat_start) * 1000

            # Calculate total processing time
            processing_time = (time.perf_counter() - start_time) * 1000

            # Create result
            result = PipelineResult(
                frame=frame,
                detections=detections,
                actions=actions,
                timestamp=start_time,
                processing_time_ms=processing_time,
                capture_time_ms=capture_time,
                inference_time_ms=inference_time,
                combat_time_ms=combat_time
            )

            # Update metrics
            self._update_metrics(result)

            # Add to result queue
            try:
                self.result_queue.put_nowait(result)
            except:
                # Queue full - clear old results
                while not self.result_queue.empty():
                    try:
                        self.result_queue.get_nowait()
                    except Empty:
                        break
                self.result_queue.put_nowait(result)

            return result

        except Exception as e:
            self.log(f"❌ Pipeline processing error: {e}")
            return PipelineResult(
                frame=None, detections=None, actions=None,
                timestamp=start_time, processing_time_ms=0,
                capture_time_ms=0, inference_time_ms=0, combat_time_ms=0
            )

    def _capture_frame(self) -> Optional[np.ndarray]:
        """Capture frame using available method"""
        if self.dx_capture:
            frame = self.dx_capture.capture_window_screenshot(self.current_hwnd)
            if frame is not None:
                return frame

        # Fallback to traditional capture
        try:
            from .window_capture import WindowCapture
            legacy_capture = WindowCapture(logger=self.log)
            frame = legacy_capture.capture_window_screenshot(self.current_hwnd)
            return frame
        except Exception as e:
            self.log(f"❌ All capture methods failed: {e}")
            return None

    def _run_inference(self, frame: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """Run YOLO inference"""
        if not self.yolo_detector:
            return None

        try:
            # Try to get latest results from multi-threaded detector
            if hasattr(self.yolo_detector, 'get_latest_results'):
                results = self.yolo_detector.get_latest_results(block=False)
                if results and 'detections' in results:
                    return results['detections']

            # Fallback to direct inference
            if hasattr(self.yolo_detector, 'detect'):
                detections = self.yolo_detector.detect(
                    frame, confidence=0.5, classes=[0]  # class 0 = mob
                )
                return detections

        except Exception as e:
            self.log(f"❌ Inference error: {e}")
            return None

    def _process_combat(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Process combat based on detections"""
        if not self.combat_controller or not detections:
            return None

        try:
            # Queue detections for async processing
            if hasattr(self.combat_controller, 'queue_detections'):
                success = self.combat_controller.queue_detections(
                    detections, self.current_hwnd
                )

                # Get latest actions
                if hasattr(self.combat_controller, 'get_latest_actions'):
                    actions = self.combat_controller.get_latest_actions(block=False)
                    return actions

        except Exception as e:
            self.log(f"❌ Combat processing error: {e}")
            return None

    def _update_metrics(self, result: PipelineResult):
        """Update performance metrics"""
        with self.stats_lock:
            # Update frame counters
            self.frames_processed += 1
            self.total_frames += 1

            # Update times
            if self.frames_processed == 1:
                # Initialize with first values
                self.performance_metrics['avg_processing_time_ms'] = result.processing_time_ms
                self.performance_metrics['avg_capture_time_ms'] = result.capture_time_ms
                self.performance_metrics['avg_inference_time_ms'] = result.inference_time_ms
                self.performance_metrics['avg_combat_time_ms'] = result.combat_time_ms
            else:
                # Calculate running averages
                alpha = 0.1  # Smoothing factor
                self.performance_metrics['avg_processing_time_ms'] = (
                    alpha * result.processing_time_ms +
                    (1 - alpha) * self.performance_metrics['avg_processing_time_ms']
                )
                self.performance_metrics['avg_capture_time_ms'] = (
                    alpha * result.capture_time_ms +
                    (1 - alpha) * self.performance_metrics['avg_capture_time_ms']
                )
                self.performance_metrics['avg_inference_time_ms'] = (
                    alpha * result.inference_time_ms +
                    (1 - alpha) * self.performance_metrics['avg_inference_time_ms']
                )
                self.performance_metrics['avg_combat_time_ms'] = (
                    alpha * result.combat_time_ms +
                    (1 - alpha) * self.performance_metrics['avg_combat_time_ms']
                )

            # Calculate actual FPS
            if self.frames_processed % 10 == 0:
                elapsed = time.time() - self.start_time if hasattr(self, 'start_time') else 1
                if elapsed > 0:
                    self.performance_metrics['actual_fps'] = self.frames_processed / elapsed

    def get_latest_result(self) -> Optional[PipelineResult]:
        """Get the latest pipeline result"""
        try:
            return self.result_queue.get_nowait()
        except Empty:
            return None

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        with self.stats_lock:
            metrics = self.performance_metrics.copy()
            metrics.update({
                'is_running': self.is_running,
                'total_frames': self.total_frames,
                'frames_processed': self.frames_processed,
                'target_fps': self.target_fps,
                'capture_method': 'dxcam' if self.dx_capture else 'PrintWindow'
            })
            return metrics

    def set_target_fps(self, fps: int):
        """Change target FPS dynamically"""
        if 1 <= fps <= 120:
            old_fps = self.target_fps
            self.target_fps = fps
            self.frame_interval = 1.0 / fps
            self.log(f"🔄 Target FPS changed: {old_fps} → {fps}")

    def log(self, message: str):
        """Log message"""
        if self.logger:
            self.logger(message)

# Convenience function for quick setup
def create_unified_pipeline(target_fps: int = 60, logger=None):
    """
    Create a unified pipeline with optimized settings

    Args:
        target_fps: Target frames per second
        logger: Optional logger function

    Returns:
        UnifiedPipeline instance
    """
    return UnifiedPipeline(logger=logger, target_fps=target_fps)

if __name__ == "__main__":
    # Test the unified pipeline
    print("🎯 Testing Unified Pipeline")
    pipeline = create_unified_pipeline(target_fps=60)

    print(f"📊 Initial metrics: {pipeline.get_performance_metrics()}")