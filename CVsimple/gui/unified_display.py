"""
Unified Display System
Replaces separate preview and analysis systems with single configurable display
"""
import tkinter as tk
from tkinter import ttk, Canvas
import cv2
import numpy as np
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from PIL import Image, ImageTk

# Import our unified pipeline
from ..core.unified_pipeline import UnifiedPipeline, PipelineResult

class UnifiedDisplay:
    """
    Unified display system for CVsimple
    Replaces dual preview/analysis with single configurable interface
    """

    def __init__(self, root: tk.Tk, logger=None):
        self.root = root
        self.logger = logger or print
        self.pipeline = None
        self.is_running = False

        # Display settings
        self.display_modes = {
            'debug': {
                'name': 'Debug Mode',
                'fps': 30,
                'show_boxes': True,
                'show_metrics': True,
                'show_grid': True
            },
            'performance': {
                'name': 'Performance Mode',
                'fps': 60,
                'show_boxes': False,
                'show_metrics': True,
                'show_grid': False
            },
            'minimal': {
                'name': 'Minimal Mode',
                'fps': 90,
                'show_boxes': False,
                'show_metrics': False,
                'show_grid': False
            },
            'custom': {
                'name': 'Custom Mode',
                'fps': 60,
                'show_boxes': True,
                'show_metrics': True,
                'show_grid': False
            }
        }

        self.current_mode = 'debug'
        self.show_boxes = True
        self.show_metrics = True

        # UI State
        self.canvas_width = 800
        self.canvas_height = 600
        self.photo_image = None
        self.detections_ovals = []

        # Performance tracking
        self.last_result = None
        self.fps_counter = 0
        self.fps_start_time = time.time()

        # Setup UI
        self._setup_ui()
        self._start_display_loop()

    def _setup_ui(self):
        """Setup the unified display interface"""
        # Control Panel
        control_frame = ttk.LabelFrame(self.root, text="🎮 Control Panel")
        control_frame.pack(fill='x', padx=10, pady=5)

        # Start/Stop controls
        controls_row1 = ttk.Frame(control_frame)
        controls_row1.pack(fill='x', padx=5, pady=2)

        self.start_btn = ttk.Button(
            controls_row1, text="▶️ Start Pipeline",
            command=self.start_pipeline,
            width=20
        )
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = ttk.Button(
            controls_row1, text="⏹️ Stop Pipeline",
            command=self.stop_pipeline,
            width=20,
            state='disabled'
        )
        self.stop_btn.pack(side='left', padx=5)

        # Display Mode Controls
        controls_row2 = ttk.Frame(control_frame)
        controls_row2.pack(fill='x', padx=5, pady=2)

        ttk.Label(controls_row2, text="Display Mode:").pack(side='left')
        self.mode_var = tk.StringVar(value='debug')
        mode_combo = ttk.Combobox(
            controls_row2,
            textvariable=self.mode_var,
            values=list(self.display_modes.keys()),
            state='readonly',
            width=15
        )
        mode_combo.pack(side='left', padx=5)
        mode_combo.bind('<<ComboboxSelected>>', self.on_mode_changed)

        # FPS Slider
        controls_row3 = ttk.Frame(control_frame)
        controls_row3.pack(fill='x', padx=5, pady=2)

        ttk.Label(controls_row3, text="FPS:").pack(side='left')
        self.fps_var = tk.IntVar(value=30)
        fps_scale = ttk.Scale(
            controls_row3,
            from_=1, to=120,
            orient='horizontal',
            variable=self.fps_var,
            command=self.on_fps_changed
        )
        fps_scale.pack(side='left', padx=5, expand=True, fill='x')

        self.fps_label = ttk.Label(controls_row3, text="30 FPS")
        self.fps_label.pack(side='left')

        # Display Options
        options_frame = ttk.LabelFrame(control_frame, text="🎛 Display Options")
        options_frame.pack(fill='x', padx=10, pady=5)

        self.show_boxes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, text="Show Detection Boxes",
            variable=self.show_boxes_var,
            command=self.update_display_options
        ).pack(side='left', padx=5)

        self.show_metrics_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, text="Show Metrics Overlay",
            variable=self.show_metrics_var,
            command=self.update_display_options
        ).pack(side='left', padx=5)

        # Canvas (Main Display)
        canvas_frame = ttk.LabelFrame(self.root, text="🖼️ Live Display")
        canvas_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.canvas = Canvas(
            canvas_frame,
            width=self.canvas_width,
            height=self.canvas_height,
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)

        # Status Bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill='x', padx=10, pady=5)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side='left')

        self.mode_label = ttk.Label(status_frame, text="")
        self.mode_label.pack(side='left', padx=(20, 5))

        self.fps_actual_label = ttk.Label(status_frame, text="0 FPS")
        self.fps_actual_label.pack(side='left', padx=(20, 5))

    def on_mode_changed(self, event=None):
        """Handle display mode change"""
        mode = self.mode_var.get()
        if mode in self.display_modes:
            self.current_mode = mode
            mode_config = self.display_modes[mode]

            # Update FPS
            self.fps_var.set(mode_config['fps'])
            self.fps_label.config(text=f"{mode_config['fps']} FPS")

            # Update display options
            self.show_boxes_var.set(mode_config['show_boxes'])
            self.show_metrics_var.set(mode_config['show_metrics'])

            self.update_display_options()
            self.log(f"🎮 Display mode changed to: {mode_config['name']}")

    def on_fps_changed(self, value=None):
        """Handle FPS slider change"""
        fps = self.fps_var.get()
        self.fps_label.config(text=f"{fps} FPS")

        if self.pipeline:
            self.pipeline.set_target_fps(fps)
            self.log(f"🎯 Target FPS changed to: {fps}")

    def update_display_options(self):
        """Update display options based on current settings"""
        self.show_boxes = self.show_boxes_var.get()
        self.show_metrics = self.show_metrics_var.get()

    def start_pipeline(self):
        """Start the unified pipeline"""
        if self.is_running:
            self.log("⚠️ Pipeline already running")
            return

        # Get window handle
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            self.log(f"🎯 Starting pipeline for: {title}")
        except Exception as e:
            self.log(f"❌ Failed to get window handle: {e}")
            return

        # Create pipeline
        try:
            target_fps = self.fps_var.get()
            self.pipeline = UnifiedPipeline(logger=self.log, target_fps=target_fps)

            # Start pipeline
            if self.pipeline.start_pipeline(hwnd):
                self.is_running = True
                self.start_btn.config(state='disabled')
                self.stop_btn.config(state='normal')
                self.status_var.set("🟢 Running")
                self.log("🚀 Pipeline started successfully")
            else:
                self.log("❌ Failed to start pipeline")
        except Exception as e:
            self.log(f"❌ Pipeline creation failed: {e}")

    def stop_pipeline(self):
        """Stop the unified pipeline"""
        if not self.is_running:
            self.log("⚠️ Pipeline not running")
            return

        try:
            if self.pipeline:
                self.pipeline.stop_pipeline()
            self.is_running = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.status_var.set("🛑 Stopped")
            self.log("🛑 Pipeline stopped")
        except Exception as e:
            self.log(f"❌ Error stopping pipeline: {e}")

    def _start_display_loop(self):
        """Start the main display loop"""
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()
        self.log("🖼️ Display loop started")

    def _display_loop(self):
        """Main display processing loop"""
        last_time = time.time()
        frame_count = 0
        fps_update_interval = 1.0  # Update FPS every second

        while True:
            try:
                # Get latest result from pipeline
                result = self.pipeline.get_latest_result() if self.pipeline else None

                if result and result.frame is not None:
                    # Calculate FPS
                    current_time = time.time()
                    frame_count += 1

                    if current_time - last_time >= fps_update_interval:
                        actual_fps = frame_count / fps_update_interval
                        self.fps_actual_label.config(text=f"{actual_fps:.1f} FPS")
                        frame_count = 0
                        last_time = current_time

                    # Update display
                    self._update_display(result)
                    self.last_result = result

                # Control loop timing
                target_interval = 1.0 / self.fps_var.get()
                sleep_time = max(0.001, target_interval - 0.001)  # Minimum 1ms sleep

                time.sleep(sleep_time)

            except Exception as e:
                self.log(f"❌ Display loop error: {e}")
                time.sleep(0.1)  # Brief pause before retry

    def _update_display(self, result: PipelineResult):
        """Update the display with pipeline result"""
        if not result.frame is not None:
            try:
                # Convert frame for Tkinter
                frame_rgb = result.frame.astype(np.uint8)

                # Resize if needed
                if frame_rgb.shape[:2] != (self.canvas_height, self.canvas_width):
                    frame_rgb = cv2.resize(frame_rgb, (self.canvas_width, self.canvas_height))

                # Convert to PIL Image then to PhotoImage
                pil_image = Image.fromarray(frame_rgb)
                self.photo_image = ImageTk.PhotoImage(pil_image)

                # Update canvas
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, self.photo_image, anchor='nw')

                # Draw overlays if enabled
                if self.show_boxes and result.detections:
                    self._draw_detections(result.detections)

                if self.show_metrics:
                    self._draw_metrics(result)

            except Exception as e:
                self.log(f"❌ Display update error: {e}")

    def _draw_detections(self, detections: List[Dict[str, Any]]):
        """Draw detection boxes on canvas"""
        try:
            # Clear previous ovals
            self.canvas.delete("detection")

            # Convert canvas coordinates
            canvas_width = self.canvas_width
            canvas_height = self.canvas_height

            for detection in detections:
                if 'center_x' in detection and 'center_y' in detection:
                    # Convert relative coordinates to canvas coordinates
                    x = (detection['center_x'] / 1920) * canvas_width
                    y = (detection['center_y'] / 1080) * canvas_height

                    # Get bounding box if available
                    width = detection.get('width', 100)
                    height = detection.get('height', 80)

                    # Calculate bounding box coordinates
                    x1 = x - width // 2
                    y1 = y - height // 2
                    x2 = x + width // 2
                    y2 = y + height // 2

                    # Draw rectangle
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2,
                        outline='red', width=2, tags="detection"
                    )

                    # Draw center point
                    self.canvas.create_oval(
                        x-2, y-2, x+2, y+2,
                        fill='', outline='red', width=1, tags="detection"
                    )

                    # Draw confidence
                    confidence = detection.get('confidence', 0.0)
                    if confidence > 0:
                        self.canvas.create_text(
                            x+5, y+5, f"{confidence:.2f}",
                            fill='yellow', font=('Arial', 10),
                            anchor='nw', tags="detection"
                        )

        except Exception as e:
            self.log(f"❌ Detection drawing error: {e}")

    def _draw_metrics(self, result: PipelineResult):
        """Draw performance metrics on canvas"""
        try:
            # Draw in top-right corner
            text_lines = [
                f"Capture: {result.capture_time_ms:.1f}ms",
                f"Inference: {result.inference_time_ms:.1f}ms",
                f"Combat: {result.combat_time_ms:.1f}ms",
                f"Total: {result.processing_time_ms:.1f}ms"
            ]

            y_pos = 10
            for line in text_lines:
                self.canvas.create_text(
                    self.canvas_width - 5, y_pos, line,
                    fill='lime', font=('Arial', 10),
                    anchor='e', tags="metrics"
                )
                y_pos += 15

        except Exception as e:
            self.log(f"❌ Metrics drawing error: {e}")

    def log(self, message: str):
        """Log message to display"""
        self.status_var.set(message)
        print(f"🖥️ Display: {message}")

    def get_status(self) -> Dict[str, Any]:
        """Get current display status"""
        status = {
            'is_running': self.is_running,
            'current_mode': self.current_mode,
            'show_boxes': self.show_boxes,
            'show_metrics': self.metrics,
            'target_fps': self.fps_var.get(),
            'canvas_size': (self.canvas_width, self.canvas_height)
        }

        if self.pipeline:
            status.update(self.pipeline.get_performance_metrics())

        return status

# Convenience function for quick setup
def create_unified_display(root: tk.Tk, logger=None) -> UnifiedDisplay:
    """
    Create unified display system

    Args:
        root: Tkinter root window
        logger: Optional logger function

    Returns:
        UnifiedDisplay instance
    """
    return UnifiedDisplay(root, logger=logger)

if __name__ == "__main__":
    # Test the unified display
    root = tk.Tk()
    root.title("🎯 Unified Display - CVsimple")

    display = create_unified_display(root)
    root.geometry("900x700")

    root.mainloop()