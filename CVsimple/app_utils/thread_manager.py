"""
Thread Manager and Queue Management System for CVsimple

Central coordination system for multi-threaded YOLO pipeline architecture.
Manages communication between capture, inference, combat, and GUI threads.
"""

import threading
import queue
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging


class QueueType(Enum):
    """Queue types for different stages of the pipeline"""
    FRAME_QUEUE = "frame_queue"
    INFERENCE_QUEUE = "inference_queue"
    RESULTS_QUEUE = "results_queue"
    COMBAT_QUEUE = "combat_queue"
    ACTION_QUEUE = "action_queue"


class ThreadStatus(Enum):
    """Thread status enumeration"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class QueueMetrics:
    """Metrics for a specific queue"""
    name: str
    size: int = 0
    capacity: int = 0
    utilization: float = 0.0
    total_items: int = 0
    dropped_items: int = 0
    overflow_count: int = 0
    underflow_count: int = 0
    avg_wait_time_ms: float = 0.0
    max_wait_time_ms: float = 0.0


@dataclass
class ThreadMetrics:
    """Metrics for a specific thread"""
    name: str
    status: ThreadStatus = ThreadStatus.STOPPED
    uptime: float = 0.0
    items_processed: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    avg_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    start_time: Optional[float] = None


class ManagedQueue:
    """Thread-safe managed queue with metrics and overflow handling"""

    def __init__(self, name: str, maxsize: int = 0, drop_policy: str = "oldest"):
        self.name = name
        self.maxsize = maxsize
        self.drop_policy = drop_policy  # "oldest", "newest", "block", "drop_new"

        self.queue = queue.Queue(maxsize=maxsize)
        self.metrics = QueueMetrics(name=name, capacity=maxsize)

        # Timing metrics
        self.wait_times = []
        self.max_wait_samples = 100

        # Threading safety
        self.metrics_lock = threading.Lock()

        # Callbacks
        self.overflow_callback = None
        self.underflow_callback = None

    def put(self, item, block: bool = False, timeout: Optional[float] = None) -> bool:
        """Put item in queue with metrics tracking"""
        start_time = time.perf_counter()
        success = False

        try:
            if block:
                self.queue.put(item, timeout=timeout)
            else:
                self.queue.put_nowait(item)

            success = True
            wait_time = (time.perf_counter() - start_time) * 1000

            # Update metrics
            with self.metrics_lock:
                self.metrics.total_items += 1
                self._update_wait_time(wait_time)

        except queue.Full:
            with self.metrics_lock:
                self.metrics.overflow_count += 1

            # Handle overflow based on policy
            success = self._handle_overflow(item)

        except Exception as e:
            logging.error(f"Queue put error in {self.name}: {str(e)}")

        return success

    def get(self, block: bool = False, timeout: Optional[float] = None) -> Any:
        """Get item from queue with metrics tracking"""
        start_time = time.perf_counter()
        item = None

        try:
            if block:
                item = self.queue.get(timeout=timeout)
            else:
                item = self.queue.get_nowait()

            wait_time = (time.perf_counter() - start_time) * 1000

            # Update metrics
            with self.metrics_lock:
                self._update_wait_time(wait_time)

        except queue.Empty:
            with self.metrics_lock:
                self.metrics.underflow_count += 1

            # Handle underflow
            item = self._handle_underflow()

        except Exception as e:
            logging.error(f"Queue get error in {self.name}: {str(e)}")

        return item

    def _handle_overflow(self, item) -> bool:
        """Handle queue overflow based on drop policy"""
        if self.drop_policy == "oldest":
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(item)
                return True
            except:
                return False

        elif self.drop_policy == "newest":
            # Drop the new item
            return False

        elif self.drop_policy == "drop_new":
            return False

        else:  # "block" or default
            return False

    def _handle_underflow(self):
        """Handle queue underflow"""
        if self.underflow_callback:
            try:
                return self.underflow_callback()
            except:
                pass
        return None

    def _update_wait_time(self, wait_time: float):
        """Update wait time metrics"""
        self.wait_times.append(wait_time)

        # Keep only recent samples
        if len(self.wait_times) > self.max_wait_samples:
            self.wait_times = self.wait_times[-self.max_wait_samples]

        # Update metrics
        self.metrics.avg_wait_time_ms = sum(self.wait_times) / len(self.wait_times)
        self.metrics.max_wait_time_ms = max(self.wait_times)

    def update_metrics(self):
        """Update queue size and utilization metrics"""
        with self.metrics_lock:
            self.metrics.size = self.queue.qsize()

            if self.metrics.capacity > 0:
                self.metrics.utilization = (self.metrics.size / self.metrics.capacity) * 100

    def clear(self) -> int:
        """Clear all items from queue"""
        cleared = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                cleared += 1
            except:
                break
        return cleared

    def qsize(self) -> int:
        """Get current queue size"""
        return self.queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty"""
        return self.queue.empty()

    def full(self) -> bool:
        """Check if queue is full"""
        return self.queue.full()


class ThreadManager:
    """
    Central thread management and coordination system
    """

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

        # Thread management
        self.threads: Dict[str, threading.Thread] = {}
        self.thread_metrics: Dict[str, ThreadMetrics] = {}
        self.thread_stop_flags: Dict[str, threading.Event] = {}

        # Queue management
        self.queues: Dict[str, ManagedQueue] = {}

        # System state
        self.is_running = False
        self.start_time = time.time()

        # Performance monitoring
        self.metrics_lock = threading.Lock()
        self.health_check_interval = 1.0
        self.health_check_thread = None

        # Error handling
        self.error_callbacks: List[Callable] = []

        self.logger.info("ThreadManager initialized")

    def create_queue(self, name: str, maxsize: int = 0, drop_policy: str = "oldest") -> ManagedQueue:
        """Create a managed queue"""
        if name in self.queues:
            self.logger.warning(f"Queue {name} already exists, returning existing queue")
            return self.queues[name]

        queue = ManagedQueue(name, maxsize, drop_policy)
        self.queues[name] = queue

        self.logger.info(f"Created queue: {name} (maxsize={maxsize}, policy={drop_policy})")
        return queue

    def get_queue(self, name: str) -> Optional[ManagedQueue]:
        """Get a managed queue by name"""
        return self.queues.get(name)

    def create_thread(self, name: str, target: Callable, *args, daemon: bool = True, **kwargs) -> bool:
        """Create and register a thread"""
        if name in self.threads and self.threads[name].is_alive():
            self.logger.warning(f"Thread {name} already running")
            return False

        # Create stop event
        if name not in self.thread_stop_flags:
            self.thread_stop_flags[name] = threading.Event()

        # Create thread
        stop_flag = self.thread_stop_flags[name]
        thread = threading.Thread(
            target=self._thread_wrapper,
            name=name,
            args=(stop_flag, target) + args,
            kwargs=kwargs,
            daemon=daemon
        )

        # Initialize metrics
        self.thread_metrics[name] = ThreadMetrics(name=name)

        self.threads[name] = thread
        self.logger.info(f"Created thread: {name}")
        return True

    def start_thread(self, name: str) -> bool:
        """Start a registered thread"""
        if name not in self.threads:
            self.logger.error(f"Thread {name} not found")
            return False

        if self.threads[name].is_alive():
            self.logger.warning(f"Thread {name} already running")
            return True

        try:
            # Reset stop flag
            self.thread_stop_flags[name].clear()

            # Update metrics
            with self.metrics_lock:
                self.thread_metrics[name].status = ThreadStatus.STARTING
                self.thread_metrics[name].start_time = time.time()

            # Start thread
            self.threads[name].start()
            self.logger.info(f"Started thread: {name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start thread {name}: {str(e)}")
            with self.metrics_lock:
                self.thread_metrics[name].status = ThreadStatus.ERROR
                self.thread_metrics[name].last_error = str(e)
            return False

    def stop_thread(self, name: str, timeout: float = 5.0) -> bool:
        """Stop a thread gracefully"""
        if name not in self.threads:
            self.logger.warning(f"Thread {name} not found")
            return False

        if not self.threads[name].is_alive():
            self.logger.info(f"Thread {name} already stopped")
            return True

        try:
            # Signal stop
            self.thread_stop_flags[name].set()

            # Update metrics
            with self.metrics_lock:
                self.thread_metrics[name].status = ThreadStatus.STOPPING

            # Wait for thread to stop
            self.threads[name].join(timeout)

            if self.threads[name].is_alive():
                self.logger.warning(f"Thread {name} did not stop gracefully within {timeout}s")
                return False
            else:
                self.logger.info(f"Thread {name} stopped gracefully")
                with self.metrics_lock:
                    self.thread_metrics[name].status = ThreadStatus.STOPPED
                return True

        except Exception as e:
            self.logger.error(f"Error stopping thread {name}: {str(e)}")
            return False

    def stop_all_threads(self, timeout: float = 5.0) -> Dict[str, bool]:
        """Stop all threads"""
        results = {}

        for name in list(self.threads.keys()):
            results[name] = self.stop_thread(name, timeout)

        return results

    def _thread_wrapper(self, stop_flag: threading.Event, target: Callable, *args, **kwargs):
        """Wrapper for thread execution with error handling and metrics"""
        thread_name = threading.current_thread().name

        try:
            # Update status
            with self.metrics_lock:
                self.thread_metrics[thread_name].status = ThreadStatus.RUNNING

            # Execute target
            target(stop_flag, *args, **kwargs)

        except Exception as e:
            self.logger.error(f"Thread {thread_name} error: {str(e)}")
            with self.metrics_lock:
                self.thread_metrics[thread_name].status = ThreadStatus.ERROR
                self.thread_metrics[thread_name].last_error = str(e)
                self.thread_metrics[thread_name].error_count += 1

            # Call error callbacks
            for callback in self.error_callbacks:
                try:
                    callback(thread_name, e)
                except:
                    pass

        finally:
            # Update status
            with self.metrics_lock:
                if self.thread_metrics[thread_name].status != ThreadStatus.ERROR:
                    self.thread_metrics[thread_name].status = ThreadStatus.STOPPED

                if self.thread_metrics[thread_name].start_time:
                    self.thread_metrics[thread_name].uptime = (
                        time.time() - self.thread_metrics[thread_name].start_time
                    )

    def get_thread_status(self, name: str) -> Optional[ThreadMetrics]:
        """Get metrics for a specific thread"""
        return self.thread_metrics.get(name)

    def get_queue_metrics(self, name: str) -> Optional[QueueMetrics]:
        """Get metrics for a specific queue"""
        queue = self.queues.get(name)
        if queue:
            queue.update_metrics()
            return queue.metrics
        return None

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics"""
        with self.metrics_lock:
            # Thread metrics
            thread_metrics = {}
            for name, metrics in self.thread_metrics.items():
                thread_metrics[name] = {
                    'status': metrics.status.value,
                    'uptime': metrics.uptime,
                    'items_processed': metrics.items_processed,
                    'error_count': metrics.error_count,
                    'last_error': metrics.last_error,
                    'avg_processing_time_ms': metrics.avg_processing_time_ms,
                    'max_processing_time_ms': metrics.max_processing_time_ms
                }

            # Queue metrics
            queue_metrics = {}
            for name, queue in self.queues.items():
                queue.update_metrics()
                metrics = queue.metrics
                queue_metrics[name] = {
                    'size': metrics.size,
                    'capacity': metrics.capacity,
                    'utilization': metrics.utilization,
                    'total_items': metrics.total_items,
                    'dropped_items': metrics.dropped_items,
                    'overflow_count': metrics.overflow_count,
                    'underflow_count': metrics.underflow_count,
                    'avg_wait_time_ms': metrics.avg_wait_time_ms,
                    'max_wait_time_ms': metrics.max_wait_time_ms
                }

            # System metrics
            system_metrics = {
                'uptime': time.time() - self.start_time,
                'thread_count': len(self.threads),
                'queue_count': len(self.queues),
                'active_threads': sum(1 for t in self.threads.values() if t.is_alive()),
                'error_threads': sum(1 for m in self.thread_metrics.values() if m.status == ThreadStatus.ERROR)
            }

            return {
                'system': system_metrics,
                'threads': thread_metrics,
                'queues': queue_metrics
            }

    def start_health_monitoring(self):
        """Start background health monitoring"""
        if self.health_check_thread and self.health_check_thread.is_alive():
            return

        self.is_running = True
        self.health_check_thread = threading.Thread(
            target=self._health_monitor_worker,
            name="HealthMonitorThread",
            daemon=True
        )
        self.health_check_thread.start()
        self.logger.info("Health monitoring started")

    def stop_health_monitoring(self):
        """Stop health monitoring"""
        self.is_running = False
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=2.0)
        self.logger.info("Health monitoring stopped")

    def _health_monitor_worker(self):
        """Background health monitoring worker"""
        while self.is_running:
            try:
                # Update all queue metrics
                for queue in self.queues.values():
                    queue.update_metrics()

                # Check for stuck threads
                current_time = time.time()
                for name, thread in self.threads.items():
                    if thread.is_alive():
                        metrics = self.thread_metrics.get(name)
                        if metrics and metrics.start_time:
                            uptime = current_time - metrics.start_time
                            if uptime > 300 and metrics.items_processed == 0:  # 5 minutes with no activity
                                self.logger.warning(f"Thread {name} may be stuck (uptime: {uptime:.1f}s, no activity)")

                time.sleep(self.health_check_interval)

            except Exception as e:
                self.logger.error(f"Health monitoring error: {str(e)}")
                time.sleep(self.health_check_interval)

    def add_error_callback(self, callback: Callable):
        """Add error callback"""
        self.error_callbacks.append(callback)

    def shutdown(self):
        """Graceful shutdown of thread manager"""
        self.logger.info("Shutting down ThreadManager")

        # Stop health monitoring
        self.stop_health_monitoring()

        # Stop all threads
        self.stop_all_threads()

        # Clear queues
        for queue in self.queues.values():
            queue.clear()

        self.logger.info("ThreadManager shutdown complete")

    def __del__(self):
        """Cleanup"""
        try:
            self.shutdown()
        except:
            pass


# Global thread manager instance
_global_thread_manager: Optional[ThreadManager] = None


def get_thread_manager() -> ThreadManager:
    """Get or create global thread manager instance"""
    global _global_thread_manager
    if _global_thread_manager is None:
        _global_thread_manager = ThreadManager()
    return _global_thread_manager


def initialize_thread_manager(logger=None) -> ThreadManager:
    """Initialize global thread manager"""
    global _global_thread_manager
    _global_thread_manager = ThreadManager(logger)
    _global_thread_manager.start_health_monitoring()
    return _global_thread_manager


def shutdown_thread_manager():
    """Shutdown global thread manager"""
    global _global_thread_manager
    if _global_thread_manager:
        _global_thread_manager.shutdown()
        _global_thread_manager = None