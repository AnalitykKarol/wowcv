# Plan Optymalizacji Performance'u YOLO: Multi-Threading & CPU Optimization

## Executive Summary

**Cel:** Zwiększenie wydajności przetwarzania z 20 FPS do 30+ FPS przy rozdzielczości Full HD przez implementację architektury wielowątkowej i optymalizację CPU.

**Hardware:** RTX 3060 Ti - pełne wykorzystanie potencjału GPU i CPU

**Szacowany zysk:**
- Faza 1 (Multi-Threading): +8-12 FPS
- Faza 2 (CPU Optimization): +3-5 FPS
- **Razem: 20→30+ FPS (50%+ improvement)**

---

## 1. Analiza Obecnej Architektury

### 1.1 Current Bottleneck

Obecny system działa w pojedynczym wątku w `main_window.py:1888-1978`:

```python
# Synchronous processing pipeline
while self.is_detecting:
    # 1. Window Capture (CPU) - 10-15ms
    frame = self.window_capture.capture_window_screenshot(hwnd)

    # 2. Preprocessing (CPU) - 5-10ms
    # BGR→RGB conversion, resize

    # 3. YOLO Inference (GPU) - 40-60ms
    detections = self.yolo_detector.detect(frame, confidence_threshold)

    # 4. Combat Logic (CPU) - 5-10ms
    self.combat_controller.update(hwnd, detections)

    # 5. GUI Update (CPU) - 5-10ms
    self.update_gui(detections)

    time.sleep(1/30)  # Target 30 FPS
```

**Problemy:**
- **CPU czeka na GPU** podczas inference
- **GPU czeka na CPU** podczas capture i preprocessing
- **Sekwencyjny bottleneck** - sumaryczny czas = wszystkie operacje
- **Niewykorzystany potencjał wielordzeniowy CPU**

### 1.2 Performance Metrics

- **Current Performance:** ~20 FPS
- **Target Performance:** 30+ FPS
- **Bottleneck Components:** Window capture, preprocessing, inference serialization
- **Key Files:** `main_window.py`, `yolo_detector.py`, `window_capture.py`, `combat_controller.py`

---

## 2. Projekt Architektury Multi-Threadingowej

### 2.1 4-Wątkowa Architektura

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│   Main      │    │   Capture    │    │  Inference  │    │   Combat    │
│   Thread    │    │   Thread     │    │   Thread    │    │   Thread    │
│             │    │              │    │             │    │             │
│ • GUI       │◄──►│ • Screen     │◄──►│ • YOLO      │◄──►│ • Logic     │
│ • Events    │    │   Capture    │    │   Model     │    │ • Results   │
│ • Display   │    │ • Preprocess │    │ • GPU       │    │ • Actions   │
│ • Control   │    │ • Queuing    │    │ • Async     │    │ • State     │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
       │                    │                    │                    │
       └────────────────────┼────────────────────┼────────────────────┘
                            │                    │
                    ┌──────────────┐    ┌─────────────┐
                    │ Frame Queue  │    │ Results     │
                    │ (Bounded)    │    │ Queue       │
                    └──────────────┘    └─────────────┘
```

### 2.2 Komunikacja Między Wątkami

**Queue-based Architecture:**
- **Frame Queue**: Capture → Inference (max 5 frames)
- **Results Queue**: Inference → Combat (max 10 results)
- **Combat Queue**: Combat → GUI (max 5 updates)
- **Status Queue**: All threads → Main (monitoring)

**Thread Safety:**
- Thread-safe counters dla statystyk
- Lock-free queues przez `queue.Queue`
- Atomic operations przez `threading.Lock`

---

## 3. Faza 1: Multi-Threading Infrastructure (+8-12 FPS)

### 3.1 Krok 1: Performance Monitor Module

**Plik:** `app_utils/performance_monitor.py`

```python
import time
import threading
import psutil
from queue import Queue
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class PerformanceMetrics:
    fps: float
    capture_latency: float
    inference_latency: float
    combat_latency: float
    gpu_utilization: float
    cpu_utilization: float
    memory_usage: float
    queue_sizes: Dict[str, int]

class PerformanceMonitor:
    def __init__(self):
        self.metrics_lock = threading.Lock()
        self.frame_times = Queue(maxsize=100)
        self.component_latencies = {}
        self.start_time = time.time()

    def record_frame_time(self, latency: float):
        self.frame_times.put(latency)
        if self.frame_times.qsize() > 100:
            self.frame_times.get()

    def calculate_fps(self) -> float:
        if self.frame_times.qsize() < 10:
            return 0.0
        times = list(self.frame_times.queue)
        avg_latency = sum(times) / len(times)
        return 1000.0 / avg_latency if avg_latency > 0 else 0.0
```

**Implementacja:**
1. Utworzenie modułu monitoringu wydajności
2. Integracja z istniejącymi komponentami
3. Real-time metrics display w GUI

### 3.2 Krok 2: Thread-Safe Window Capture

**Modyfikacja pliku:** `core/window_capture.py`

```python
import threading
import queue
import time
from typing import Optional, Tuple, Dict

class ThreadSafeWindowCapture(WindowCapture):
    def __init__(self, window_title: str, target_fps: int = 60):
        super().__init__(window_title)
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps

        # Threading components
        self.capture_thread = None
        self.frame_queue = queue.Queue(maxsize=5)
        self.stats_lock = threading.Lock()
        self.is_capturing = False

        # Performance tracking
        self.capture_times = queue.Queue(maxsize=100)
        self.frame_count = 0
        self.dropped_frames = 0

    def start_capture(self):
        if self.capture_thread and self.capture_thread.is_alive():
            return

        self.is_capturing = True
        self.capture_thread = threading.Thread(
            target=self._capture_worker,
            name="WindowCaptureThread",
            daemon=True
        )
        self.capture_thread.start()

    def _capture_worker(self):
        """Dedicated capture thread running at target_fps"""
        while self.is_capturing:
            start_time = time.perf_counter()

            try:
                # Capture frame
                frame = self.capture_window_screenshot()
                if frame is not None:
                    timestamp = time.time()
                    frame_metadata = {
                        'frame': frame,
                        'timestamp': timestamp,
                        'frame_id': self.frame_count
                    }

                    # Add to queue (drop if full)
                    try:
                        self.frame_queue.put_nowait(frame_metadata)
                    except queue.Full:
                        self.dropped_frames += 1

                    self.frame_count += 1

            except Exception as e:
                print(f"Capture error: {e}")

            # Maintain target FPS
            capture_time = (time.perf_counter() - start_time) * 1000
            sleep_time = max(0, self.frame_interval - capture_time / 1000.0)
            time.sleep(sleep_time)

    def get_latest_frame(self) -> Optional[Dict]:
        """Get latest frame from queue (non-blocking)"""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
```

**Kluczowe zmiany:**
1. Oddzielny wątek capture działający z docelowym 60 FPS
2. Bounded queue (max 5 frames) dla kontroli pamięci
3. Frame dropping przy pełnej kolejce
4. Performance tracking i statystyki

### 3.3 Krok 3: Multi-Threaded YOLO Detector

**Modyfikacja pliku:** `core/yolo_detector.py`

```python
import threading
import queue
import time
from typing import List, Dict, Optional
from ultralytics import YOLO

class MultiThreadedYOLODetector(OptimizedYOLODetector):
    def __init__(self, model_path: str, device: str = 'auto'):
        super().__init__(model_path, device)

        # Threading components
        self.inference_thread = None
        self.inference_queue = queue.Queue(maxsize=3)
        self.results_queue = queue.Queue(maxsize=10)
        self.model_lock = threading.Lock()
        self.is_running = False

        # Performance tracking
        self.inference_times = queue.Queue(maxsize=100)
        self.inference_count = 0

    def start_inference(self):
        if self.inference_thread and self.inference_thread.is_alive():
            return

        self.is_running = True
        self.inference_thread = threading.Thread(
            target=self._inference_worker,
            name="YOLOInferenceThread",
            daemon=True
        )
        self.inference_thread.start()

    def _inference_worker(self):
        """Dedicated inference thread"""
        while self.is_running:
            try:
                # Get frame from queue (blocking with timeout)
                frame_data = self.inference_queue.get(timeout=0.1)

                start_time = time.perf_counter()

                # Perform inference with model lock
                with self.model_lock:
                    results = self.model(
                        frame_data['frame'],
                        conf=frame_data['confidence'],
                        verbose=False,
                        device=self.device
                    )

                # Process results
                detections = self._process_results(results, frame_data['frame_id'])

                # Queue results
                result_data = {
                    'detections': detections,
                    'frame_id': frame_data['frame_id'],
                    'timestamp': frame_data['timestamp'],
                    'inference_time': (time.perf_counter() - start_time) * 1000
                }

                self.results_queue.put_nowait(result_data)
                self.inference_count += 1

                # Track performance
                self.inference_times.put(result_data['inference_time'])
                if self.inference_times.qsize() > 100:
                    self.inference_times.get()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Inference error: {e}")

    def queue_frame(self, frame: np.ndarray, confidence: float,
                   frame_id: int, timestamp: float):
        """Queue frame for inference"""
        frame_data = {
            'frame': frame,
            'confidence': confidence,
            'frame_id': frame_id,
            'timestamp': timestamp
        }

        try:
            self.inference_queue.put_nowait(frame_data)
        except queue.Full:
            # Drop frame if queue is full
            pass

    def get_latest_results(self) -> Optional[Dict]:
        """Get latest inference results"""
        try:
            return self.results_queue.get_nowait()
        except queue.Empty:
            return None
```

**Kluczowe funkcje:**
1. Oddzielony inference thread
2. Thread-safe dostęp do modelu przez lock
3. Bounded queues dla kontroli pamięci
4. Performance tracking inference latency

### 3.4 Krok 4: Async Combat Controller

**Modyfikacja pliku:** `core/combat_controller.py`

```python
import threading
import queue
import time
from typing import Dict, List, Optional

class AsyncCombatController(CombatController):
    def __init__(self):
        super().__init__()

        # Threading components
        self.combat_thread = None
        self.combat_queue = queue.Queue(maxsize=5)
        self.action_queue = queue.Queue(maxsize=10)
        self.is_processing = False

        # Performance tracking
        self.combat_times = queue.Queue(maxsize=100)

    def start_processing(self):
        if self.combat_thread and self.combat_thread.is_alive():
            return

        self.is_processing = True
        self.combat_thread = threading.Thread(
            target=self._combat_worker,
            name="CombatLogicThread",
            daemon=True
        )
        self.combat_thread.start()

    def _combat_worker(self):
        """Dedicated combat logic thread"""
        while self.is_processing:
            try:
                # Get detection results
                detection_data = self.combat_queue.get(timeout=0.1)

                start_time = time.perf_counter()

                # Process combat logic
                actions = self.process_combat_logic(
                    detection_data['detections'],
                    detection_data['hwnd'],
                    detection_data['frame_id']
                )

                # Queue actions for main thread
                action_data = {
                    'actions': actions,
                    'frame_id': detection_data['frame_id'],
                    'processing_time': (time.perf_counter() - start_time) * 1000,
                    'timestamp': detection_data['timestamp']
                }

                self.action_queue.put_nowait(action_data)

                # Track performance
                self.combat_times.put(action_data['processing_time'])
                if self.combat_times.qsize() > 100:
                    self.combat_times.get()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Combat processing error: {e}")

    def queue_detections(self, detections: Dict, hwnd: int,
                        frame_id: int, timestamp: float):
        """Queue detection results for combat processing"""
        detection_data = {
            'detections': detections,
            'hwnd': hwnd,
            'frame_id': frame_id,
            'timestamp': timestamp
        }

        try:
            self.combat_queue.put_nowait(detection_data)
        except queue.Full:
            # Skip if combat thread is overloaded
            pass
```

### 3.5 Krok 5: Main Window Coordination

**Modyfikacja pliku:** `gui/main_window.py`

```python
import threading
import queue
import time

class MainWindow:
    def __init__(self):
        # ... existing initialization ...

        # Multi-threading components
        self.frame_queue = queue.Queue(maxsize=5)
        self.results_queue = queue.Queue(maxsize=10)
        self.combat_queue = queue.Queue(maxsize=5)

        # Thread management
        self.threads = []
        self.is_running = False

        # Performance monitoring
        self.performance_monitor = PerformanceMonitor()

    def start_detection_threaded(self):
        """Start multi-threaded detection"""
        if self.is_running:
            return

        self.is_running = True

        # Start all worker threads
        self.window_capture.start_capture()
        self.yolo_detector.start_inference()
        self.combat_controller.start_processing()

        # Start coordination thread
        coordination_thread = threading.Thread(
            target=self._coordination_worker,
            name="CoordinationThread",
            daemon=True
        )
        coordination_thread.start()
        self.threads.append(coordination_thread)

    def _coordination_worker(self):
        """Main coordination thread"""
        last_gui_update = 0
        gui_update_interval = 1.0 / 30  # 30 FPS GUI updates

        while self.is_running:
            try:
                # Get latest frame from capture
                frame_data = self.window_capture.get_latest_frame()
                if frame_data:
                    # Queue for inference
                    self.yolo_detector.queue_frame(
                        frame_data['frame'],
                        self.confidence_threshold,
                        frame_data['frame_id'],
                        frame_data['timestamp']
                    )

                    # Update performance metrics
                    capture_latency = (time.time() - frame_data['timestamp']) * 1000
                    self.performance_monitor.record_frame_time(capture_latency)

                # Get latest inference results
                results = self.yolo_detector.get_latest_results()
                if results:
                    # Queue for combat processing
                    self.combat_controller.queue_detections(
                        results['detections'],
                        self.selected_window['hwnd'],
                        results['frame_id'],
                        results['timestamp']
                    )

                # Get combat actions (non-blocking)
                try:
                    actions = self.combat_controller.action_queue.get_nowait()
                    # Execute actions in main thread
                    self.execute_combat_actions(actions['actions'])
                except queue.Empty:
                    pass

                # Update GUI at limited rate
                current_time = time.time()
                if current_time - last_gui_update > gui_update_interval:
                    self.update_performance_display()
                    last_gui_update = current_time

            except Exception as e:
                print(f"Coordination error: {e}")
                time.sleep(0.01)  # Prevent tight loop

    def stop_detection_threaded(self):
        """Graceful shutdown of all threads"""
        self.is_running = False

        # Stop all components
        self.window_capture.stop_capture()
        self.yolo_detector.stop_inference()
        self.combat_controller.stop_processing()

        # Wait for threads to finish
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1.0)

    def update_performance_display(self):
        """Update GUI with performance metrics"""
        metrics = self.performance_monitor.get_current_metrics()

        # Update GUI elements
        self.fps_label.config(text=f"FPS: {metrics.fps:.1f}")
        self.inference_time_label.config(text=f"Inference: {metrics.inference_latency:.1f}ms")

        # Update queue sizes
        self.frame_queue_size.set(self.window_capture.frame_queue.qsize())
        self.results_queue_size.set(self.yolo_detector.results_queue.qsize())
```

---

## 4. Faza 2: CPU Optimization (+3-5 FPS)

### 4.1 Krok 6: Model Optimization

**Modyfikacja pliku:** `core/yolo_detector.py`

```python
import torch
from ultralytics import YOLO

class OptimizedYOLODetector(MultiThreadedYOLODetector):
    def __init__(self, model_path: str, device: str = 'auto'):
        super().__init__(model_path, device)
        self.optimize_model()

    def optimize_model(self):
        """Apply various optimizations to the model"""
        # Compile with TorchScript for better performance
        try:
            self.model = torch.jit.script(self.model.model)
            print("Model compiled with TorchScript")
        except Exception as e:
            print(f"TorchScript compilation failed: {e}")

        # Enable mixed precision if supported
        if self.device.startswith('cuda') and torch.cuda.is_available():
            self.model = self.model.half()
            print("Enabled FP16 inference")

        # Optimize for inference
        self.model.eval()

        # Set optimal thread count for CPU
        if self.device == 'cpu':
            torch.set_num_threads(min(4, os.cpu_count()))
            print(f"CPU threads set to: {torch.get_num_threads()}")
```

### 4.2 Krok 7: Memory Optimization

**Nowy plik:** `app_utils/memory_optimizer.py`

```python
import gc
import threading
import time
import psutil
from queue import Queue

class MemoryOptimizer:
    def __init__(self, check_interval: float = 5.0):
        self.check_interval = check_interval
        self.is_monitoring = False
        self.monitor_thread = None

    def start_monitoring(self):
        if self.monitor_thread and self.monitor_thread.is_alive():
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_memory,
            name="MemoryOptimizerThread",
            daemon=True
        )
        self.monitor_thread.start()

    def _monitor_memory(self):
        """Monitor memory usage and perform cleanup"""
        while self.is_monitoring:
            try:
                memory_percent = psutil.virtual_memory().percent

                if memory_percent > 80:  # Critical threshold
                    print(f"High memory usage: {memory_percent}%")
                    self.perform_cleanup()

                # Cleanup GPU memory if using CUDA
                if torch.cuda.is_available():
                    gpu_memory = torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated()
                    if gpu_memory > 0.8:  # 80% GPU memory usage
                        torch.cuda.empty_cache()

                time.sleep(self.check_interval)

            except Exception as e:
                print(f"Memory monitoring error: {e}")
                time.sleep(self.check_interval)

    def perform_cleanup(self):
        """Perform memory cleanup"""
        # Clear queues
        gc.collect()

        # Clear PyTorch cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
```

### 4.3 Krok 8: Preprocessing Optimization

**Modyfikacja pliku:** `core/window_capture.py`

```python
import cv2
import numpy as np
from numba import jit

@jit(nopython=True)
def bgr_to_rgb_numba(image):
    """Fast BGR to RGB conversion using Numba"""
    rgb_image = np.empty_like(image)
    rgb_image[:, :, 0] = image[:, :, 2]
    rgb_image[:, :, 1] = image[:, :, 1]
    rgb_image[:, :, 2] = image[:, :, 0]
    return rgb_image

class OptimizedWindowCapture(ThreadSafeWindowCapture):
    def __init__(self, window_title: str, target_fps: int = 60):
        super().__init__(window_title, target_fps)
        self.enable_numba_optimization = True

    def preprocess_frame(self, frame: np.ndarray,
                        target_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
        """Optimized frame preprocessing"""
        processed_frame = frame.copy()

        # Fast BGR to RGB conversion
        if self.enable_numba_optimization:
            processed_frame = bgr_to_rgb_numba(processed_frame)
        else:
            processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)

        # Resize if needed
        if target_size:
            processed_frame = cv2.resize(processed_frame, target_size,
                                       interpolation=cv2.INTER_LINEAR)

        return processed_frame
```

---

## 5. Thread Communication Design

### 5.1 Queue Architecture

```python
# Thread-safe bounded queues
class ThreadSafeQueues:
    def __init__(self):
        # Frame processing pipeline
        self.capture_to_inference = queue.Queue(maxsize=5)    # Frames
        self.inference_to_combat = queue.Queue(maxsize=10)    # Detection results
        self.combat_to_gui = queue.Queue(maxsize=5)          # Combat actions

        # Status and monitoring
        self.status_updates = queue.Queue(maxsize=20)        # Thread status
        self.performance_metrics = queue.Queue(maxsize=100)  # Performance data
```

### 5.2 Error Handling & Recovery

```python
class ThreadHealthMonitor:
    def __init__(self):
        self.thread_status = {}
        self.last_heartbeat = {}
        self.health_check_interval = 1.0

    def register_thread(self, thread_name: str):
        self.thread_status[thread_name] = 'running'
        self.last_heartbeat[thread_name] = time.time()

    def update_heartbeat(self, thread_name: str):
        self.last_heartbeat[thread_name] = time.time()

    def check_thread_health(self):
        """Check if all threads are responsive"""
        current_time = time.time()
        for thread_name, last_time in self.last_heartbeat.items():
            if current_time - last_time > 5.0:  # 5 second timeout
                print(f"Thread {thread_name} appears to be stuck!")
                # Restart thread or take recovery action
```

---

## 6. Performance Considerations

### 6.1 Memory Management

- **Bounded Queues**: Prevent memory leaks through queue size limits
- **Frame Pool**: Reuse numpy arrays to reduce allocation overhead
- **Garbage Collection**: Periodic cleanup of unused objects
- **GPU Memory**: Active management of CUDA memory allocation

### 6.2 CPU Optimization

- **Thread Affinity**: Pin threads to specific CPU cores
- **Vectorization**: Use Numba/NumPy for fast array operations
- **Cache Optimization**: Minimize memory access patterns
- **Async I/O**: Non-blocking operations where possible

### 6.3 Synchronization Overhead

- **Lock-Free Queues**: Use Python's built-in `queue.Queue`
- **Atomic Operations**: Minimize lock contention
- **Batch Processing**: Process multiple items when possible
- **Minimize Shared State**: Reduce thread communication needs

---

## 7. Testing Strategy

### 7.1 Performance Benchmarking

```python
class PerformanceBenchmark:
    def __init__(self):
        self.baseline_fps = 0
        self.optimized_fps = 0

    def run_baseline_test(self):
        """Test current single-threaded performance"""
        # Run existing code and measure FPS
        pass

    def run_optimized_test(self):
        """Test new multi-threaded performance"""
        # Run optimized code and measure FPS
        pass

    def generate_report(self):
        """Generate performance comparison report"""
        improvement = (self.optimized_fps / self.baseline_fps - 1) * 100
        print(f"Performance improvement: {improvement:.1f}%")
```

### 7.2 Thread Safety Validation

- **Stress Testing**: High-load scenarios with rapid queue operations
- **Race Condition Detection**: Tools like `threading` module debugging
- **Memory Leak Detection**: Long-running tests monitoring memory usage
- **Deadlock Detection**: Timeout-based detection of stuck threads

### 7.3 Integration Testing

- **End-to-End Workflow**: Complete capture→inference→combat pipeline
- **GUI Responsiveness**: Ensure UI remains responsive under load
- **Error Recovery**: Test graceful handling of thread failures
- **Resource Limits**: Test behavior under memory/CPU constraints

---

## 8. Rollback Plan

### 8.1 Version Control Strategy

```python
# Feature flags for gradual rollout
FEATURE_MULTI_THREADING = False
FEATURE_CPU_OPTIMIZATION = False

def create_detector():
    if FEATURE_MULTI_THREADING:
        return MultiThreadedYOLODetector(model_path)
    else:
        return OptimizedYOLODetector(model_path)
```

### 8.2 Emergency Rollback

- **Configuration Toggle**: Simple flag to disable multi-threading
- **Backup Implementation**: Keep original code as fallback
- **Graceful Degradation**: System should function even if threads fail
- **Monitoring Integration**: Automated alerts for performance regressions

### 8.3 Gradual Deployment

1. **Phase 1**: Deploy with feature flag disabled
2. **Phase 2**: Enable for testing windows only
3. **Phase 3**: Enable for all windows with monitoring
4. **Phase 4**: Full rollout after validation

---

## 9. Implementation Timeline

### Week 1: Foundation
- **Day 1-2**: Performance monitor module
- **Day 3-4**: Thread-safe window capture
- **Day 5**: Queue system implementation

### Week 2: Core Threading
- **Day 1-2**: Multi-threaded YOLO detector
- **Day 3-4**: Async combat controller
- **Day 5**: Thread health monitoring

### Week 3: Integration
- **Day 1-2**: Main window coordination
- **Day 3-4**: Performance display integration
- **Day 5**: Error handling and recovery

### Week 4: Optimization & Testing
- **Day 1-2**: CPU optimizations (TorchScript, FP16)
- **Day 3**: Memory optimization
- **Day 4-5**: Performance benchmarking

### Week 5: Deployment
- **Day 1-2**: Feature flags and rollback procedures
- **Day 3**: Testing on production data
- **Day 4-5**: Documentation and knowledge transfer

---

## 10. Success Metrics & KPIs

### 10.1 Performance Targets

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Average FPS | 20 FPS | 30+ FPS | Real-time monitoring |
| Capture Latency | 15ms | 10ms | Timestamp tracking |
| Inference Latency | 50ms | 35ms | Model timing |
| Memory Usage | <2GB | <1GB | System monitoring |
| CPU Utilization | 60% | 80%+ | Per-thread metrics |

### 10.2 Stability Metrics

- **Thread Uptime**: >99% (minimal crashes/restarts)
- **Error Rate**: <1% (failed operations)
- **Queue Overflow**: <0.1% (dropped frames)
- **Memory Leaks**: 0 (no continuous growth)

### 10.3 Quality Metrics

- **Detection Accuracy**: No degradation (<5% loss)
- **Response Latency**: Combat actions <100ms
- **GUI Responsiveness**: <16ms (60Hz display)
- **System Stability**: 24+ hours continuous operation

---

## 11. Risk Assessment & Mitigation

### 11.1 High Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Thread Deadlocks | System freeze | Timeout detection, watchdog threads |
| Memory Leaks | System crash | Bounded queues, periodic cleanup |
| GPU Context Issues | Inference failure | Proper CUDA context management |

### 11.2 Medium Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance Regression | Slower operation | Feature flags, gradual rollout |
| Thread Race Conditions | Inconsistent results | Thread-safe data structures |
| CPU Affinity Issues | Suboptimal performance | Configurable thread pinning |

### 11.3 Low Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| GUI Updates Throttling | Slight UI lag | Rate limiting, async updates |
| Queue Size Tuning | Memory/CPU tradeoff | Configurable parameters |
| Debugging Complexity | Harder troubleshooting | Comprehensive logging |

---

## 12. Next Steps

### 12.1 Immediate Actions

1. **Setup Development Environment**: Ensure all dependencies available
2. **Create Feature Branch**: Isolate multi-threading changes
3. **Baseline Performance**: Document current performance metrics
4. **Backup Current Code**: Ensure rollback capability

### 12.2 Implementation Order

1. **Start with Performance Monitor** - Foundation for measurement
2. **Implement Thread-Safe Capture** - Most critical bottleneck
3. **Add Multi-Threaded YOLO** - Main inference optimization
4. **Integrate Async Combat** - Complete pipeline parallelization
5. **CPU Optimizations** - Fine-tuning and performance gains

### 12.3 Success Criteria

- **Performance**: 30+ FPS sustained average
- **Stability**: 99%+ thread uptime over 24 hours
- **Quality**: No significant detection accuracy loss
- **Maintainability**: Clean, well-documented thread-safe code

---

## Appendix

### A. Configuration Parameters

```python
# Threading configuration
THREAD_CONFIG = {
    'capture_fps': 60,           # Capture thread target FPS
    'inference_queue_size': 3,   # Max queued frames for inference
    'results_queue_size': 10,    # Max queued results
    'combat_queue_size': 5,      # Max queued combat updates
    'gui_update_fps': 30,        # GUI refresh rate
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    'target_fps': 30.0,
    'min_fps': 25.0,
    'max_memory_mb': 1024,
    'max_cpu_percent': 90,
    'thread_timeout_seconds': 5.0,
}
```

### B. Debugging Tools

```python
# Thread debugging utilities
def dump_thread_info():
    """Print current thread information"""
    for thread in threading.enumerate():
        print(f"Thread: {thread.name}, Alive: {thread.is_alive()}")

def dump_queue_sizes():
    """Print current queue sizes"""
    print(f"Capture queue: {capture_queue.qsize()}")
    print(f"Results queue: {results_queue.qsize()}")
```

### C. Performance Monitoring Commands

```bash
# System monitoring
htop                    # CPU and memory usage
nvidia-smi -l 1        # GPU utilization
iotop                   # I/O monitoring

# Python profiling
python -m cscript      # CPU profiling
memory_profiler        # Memory usage analysis
py-spy                 # Production profiling
```

---

*Document Version: 1.0*
*Last Updated: 2025-12-03*
*Author: Claude Code Assistant*