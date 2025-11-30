"""
Action Recording GUI - Simple Interface
Basic GUI for window selection and recording control
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
from datetime import datetime
import logging

# Import the recording system
from recording import ActionRecorder


class RecordingGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Action Recording System")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        # Setup logging
        self.setup_logging()

        # Create recorder
        self.recorder = ActionRecorder(self.logger)

        # GUI state
        self.selected_window = None
        self.update_thread = None
        self.running = True

        # Create GUI elements
        self.create_widgets()
        self.setup_layout()

        # Initialize recorder
        self.recorder_initialized = False

        try:
            if self.recorder.initialize():
                self.recorder_initialized = True
                self.log("Recording system initialized successfully")
            else:
                self.log("Failed to initialize recording system")
                messagebox.showerror("Error", "Failed to initialize recording system!")
                self.root.destroy()
                return
        except Exception as e:
            self.log(f"Initialization error: {e}")
            messagebox.showerror("Error", f"Initialization failed: {e}")
            self.root.destroy()
            return

        # Start status update thread
        self.start_status_updates()

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.log("Recording GUI started successfully")

    def setup_logging(self):
        """Setup logging to both file and GUI"""
        # Create logs directory
        os.makedirs("logs", exist_ok=True)

        # Setup file logging with UTF-8 encoding
        log_filename = f"logs/recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # File handler with UTF-8 encoding
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(formatter)

        # Console handler with safe encoding
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # Setup logger
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, message: str):
        """Log message and update GUI log display"""
        # Remove emoji for console compatibility but keep for GUI
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        if safe_message.strip():  # Only log if message is not empty after emoji removal
            self.logger.info(safe_message)

        # Update GUI log (thread-safe) - keep original message with emoji
        if hasattr(self, 'log_text') and self.log_text and self.log_text.winfo_exists():
            self.root.after(0, lambda: self.update_log_display(message))

    def update_log_display(self, message: str):
        """Update the log display in GUI"""
        try:
            if not hasattr(self, 'log_text') or not self.log_text or not self.log_text.winfo_exists():
                return

            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}\n"

            self.log_text.insert(tk.END, formatted_message)
            self.log_text.see(tk.END)

            # Keep only last 100 lines
            lines = self.log_text.get("1.0", tk.END).split('\n')
            if len(lines) > 100:
                self.log_text.delete("1.0", f"{len(lines)-100}.0")
        except Exception:
            # Silently ignore errors in log display update
            pass

    def create_widgets(self):
        """Create all GUI widgets"""

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)

        # === TAB 1: Recording Control ===
        self.recording_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.recording_frame, text="Recording")

        # Window selection frame
        window_frame = ttk.LabelFrame(self.recording_frame, text="1. Select Target Window")

        # Window list
        self.window_listbox = tk.Listbox(window_frame, height=8)
        self.window_scrollbar = ttk.Scrollbar(window_frame, orient="vertical", command=self.window_listbox.yview)
        self.window_listbox.configure(yscrollcommand=self.window_scrollbar.set)

        # Window control buttons
        window_btn_frame = ttk.Frame(window_frame)
        self.refresh_btn = ttk.Button(window_btn_frame, text="Refresh Windows", command=self.refresh_windows)
        self.select_btn = ttk.Button(window_btn_frame, text="Select Window", command=self.select_window)

        # Recording control frame
        recording_frame = ttk.LabelFrame(self.recording_frame, text="2. Recording Control")

        # Status display
        self.status_var = tk.StringVar(value="Ready - No window selected")
        self.status_label = ttk.Label(recording_frame, textvariable=self.status_var, font=("Arial", 10, "bold"))

        # Recording buttons
        recording_btn_frame = ttk.Frame(recording_frame)
        self.start_btn = ttk.Button(recording_btn_frame, text="Start Recording", command=self.start_recording, state="disabled")
        self.stop_btn = ttk.Button(recording_btn_frame, text="Stop Recording", command=self.stop_recording, state="disabled")

        # Progress frame
        progress_frame = ttk.LabelFrame(recording_frame, text="Current Session")

        self.duration_var = tk.StringVar(value="Duration: 0.0s")
        self.duration_label = ttk.Label(progress_frame, textvariable=self.duration_var)

        self.actions_var = tk.StringVar(value="Actions: 0")
        self.actions_label = ttk.Label(progress_frame, textvariable=self.actions_var)

        self.compression_var = tk.StringVar(value="Mouse compression: 0%")
        self.compression_label = ttk.Label(progress_frame, textvariable=self.compression_var)

        # Save frame
        save_frame = ttk.LabelFrame(self.recording_frame, text="3. Save Recording")

        save_input_frame = ttk.Frame(save_frame)
        ttk.Label(save_input_frame, text="Run name:").pack(side="left")
        self.run_name_var = tk.StringVar(value=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.run_name_entry = ttk.Entry(save_input_frame, textvariable=self.run_name_var, width=30)
        self.run_name_entry.pack(side="left", padx=(5, 0))

        save_btn_frame = ttk.Frame(save_frame)
        self.save_btn = ttk.Button(save_btn_frame, text="Save Run", command=self.save_run, state="disabled")
        self.save_as_btn = ttk.Button(save_btn_frame, text="Save As...", command=self.save_run_as, state="disabled")

        # === TAB 2: Settings ===
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")

        # Mouse tracking settings
        mouse_frame = ttk.LabelFrame(self.settings_frame, text="Mouse Tracking")

        ttk.Label(mouse_frame, text="FPS:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.fps_var = tk.StringVar(value="30")
        fps_spinbox = ttk.Spinbox(mouse_frame, from_=10, to=60, textvariable=self.fps_var, width=10)
        fps_spinbox.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(mouse_frame, text="Movement threshold (px):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.threshold_var = tk.StringVar(value="1")
        threshold_spinbox = ttk.Spinbox(mouse_frame, from_=1, to=10, textvariable=self.threshold_var, width=10)
        threshold_spinbox.grid(row=1, column=1, padx=5, pady=2)

        apply_settings_btn = ttk.Button(mouse_frame, text="Apply Settings", command=self.apply_settings)
        apply_settings_btn.grid(row=2, column=0, columnspan=2, pady=10)

        # System info
        system_frame = ttk.LabelFrame(self.settings_frame, text="System Information")

        # System status
        self.system_status_var = tk.StringVar()
        self.system_status_label = ttk.Label(system_frame, textvariable=self.system_status_var,
                                            font=("Arial", 9))

        # System info
        self.system_info = ttk.Label(system_frame,
                              text="Input Method: Polling (50 FPS keyboard/mouse monitoring)",
                              font=("Arial", 8), foreground="gray")

        # Control info
        self.control_info = ttk.Label(system_frame,
                              text="Recording Control: Use GUI buttons or F10 hotkey",
                              font=("Arial", 8), foreground="gray")

        # === TAB 3: Log ===
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Log")

        # Log display
        log_display_frame = ttk.Frame(self.log_frame)
        self.log_text = tk.Text(log_display_frame, height=20, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_display_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        # Log control buttons
        log_btn_frame = ttk.Frame(self.log_frame)
        clear_log_btn = ttk.Button(log_btn_frame, text="Clear Log", command=self.clear_log)
        save_log_btn = ttk.Button(log_btn_frame, text="Save Log", command=self.save_log)

        # Store references for layout
        self.window_frame = window_frame
        self.window_btn_frame = window_btn_frame
        self.recording_control_frame = recording_frame
        self.recording_btn_frame = recording_btn_frame
        self.progress_frame = progress_frame
        self.save_frame = save_frame
        self.save_input_frame = save_input_frame
        self.save_btn_frame = save_btn_frame
        self.mouse_frame = mouse_frame
        self.system_frame = system_frame
        self.log_display_frame = log_display_frame
        self.log_btn_frame = log_btn_frame

    def setup_layout(self):
        """Setup widget layout"""

        # Main notebook
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # === Recording Tab Layout ===

        # Window selection
        self.window_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Window list and scrollbar
        self.window_listbox.pack(side="left", fill="both", expand=True)
        self.window_scrollbar.pack(side="right", fill="y")

        # Window buttons
        self.window_btn_frame.pack(fill="x", pady=(10, 0))
        self.refresh_btn.pack(side="left", padx=(0, 5))
        self.select_btn.pack(side="left")

        # Recording control
        self.recording_control_frame.pack(fill="x", pady=(0, 10))

        # Status
        self.status_label.pack(pady=(10, 5))

        # Recording buttons
        self.recording_btn_frame.pack(fill="x", pady=(0, 10))
        self.start_btn.pack(side="left", padx=(0, 5))
        self.stop_btn.pack(side="left")

        # Progress info
        self.progress_frame.pack(fill="x", pady=(0, 10))
        self.duration_label.pack(anchor="w", padx=10, pady=2)
        self.actions_label.pack(anchor="w", padx=10, pady=2)
        self.compression_label.pack(anchor="w", padx=10, pady=2)

        # Save controls
        self.save_frame.pack(fill="x")
        self.save_input_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.save_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.save_btn.pack(side="left", padx=(0, 5))
        self.save_as_btn.pack(side="left")

        # === Settings Tab Layout ===
        self.mouse_frame.pack(fill="x", padx=10, pady=10)
        self.system_frame.pack(fill="x", padx=10, pady=(0, 10))

        # System frame layout
        self.system_status_label.pack(anchor="w", padx=10, pady=(10, 5))
        self.system_info.pack(anchor="w", padx=10, pady=2)
        self.control_info.pack(anchor="w", padx=10, pady=(0, 10))

        # === Log Tab Layout ===
        self.log_display_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar = ttk.Scrollbar(self.log_display_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.log_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        clear_log_btn = ttk.Button(self.log_btn_frame, text="Clear Log", command=self.clear_log)
        save_log_btn = ttk.Button(self.log_btn_frame, text="Save Log", command=self.save_log)
        clear_log_btn.pack(side="left", padx=(0, 5))
        save_log_btn.pack(side="left")

    def refresh_windows(self):
        """Refresh the list of available windows"""
        try:
            # Check if widgets exist before using them
            if not hasattr(self, 'window_listbox') or not self.window_listbox or not self.window_listbox.winfo_exists():
                self.log("Window list widget not ready yet")
                return

            windows = self.recorder.get_available_windows()

            # Clear current list
            self.window_listbox.delete(0, tk.END)

            # Add windows to list
            for window in windows:
                display_text = f"{window['title']} ({window['size']})"
                self.window_listbox.insert(tk.END, display_text)

            # Store window data for selection
            self.windows_data = windows

            self.log(f"Refreshed window list - {len(windows)} windows found")

        except Exception as e:
            self.log(f"Error refreshing windows: {e}")
            # Don't show messagebox here as it might be called during initialization

    def select_window(self):
        """Select the currently highlighted window"""
        try:
            selection = self.window_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a window first")
                return

            window_index = selection[0]
            if not hasattr(self, 'windows_data') or window_index >= len(self.windows_data):
                messagebox.showerror("Error", "Invalid window selection")
                return

            selected_window = self.windows_data[window_index]

            if self.recorder.set_target_window(selected_window['hwnd']):
                self.selected_window = selected_window
                self.start_btn.config(state="normal")
                self.status_var.set(f"Target: {selected_window['title']}")
                self.log(f"Selected window: {selected_window['title']}")
            else:
                messagebox.showerror("Error", "Failed to set target window")

        except Exception as e:
            self.log(f"Error selecting window: {e}")
            messagebox.showerror("Error", f"Failed to select window: {e}")

    def start_recording(self):
        """Start recording"""
        try:
            if self.recorder.start_recording():
                self.start_btn.config(state="disabled")
                self.stop_btn.config(state="normal")
                self.status_var.set("Recording...")
                self.log("Recording started")
            else:
                messagebox.showerror("Error", "Failed to start recording")

        except Exception as e:
            self.log(f"Error starting recording: {e}")
            messagebox.showerror("Error", f"Failed to start recording: {e}")

    def stop_recording(self):
        """Stop recording"""
        try:
            if self.recorder.stop_recording():
                self.start_btn.config(state="normal")
                self.stop_btn.config(state="disabled")
                self.save_btn.config(state="normal")
                self.save_as_btn.config(state="normal")
                self.status_var.set("Recording stopped - Ready to save")
                self.log("Recording stopped")
            else:
                messagebox.showerror("Error", "Failed to stop recording")

        except Exception as e:
            self.log(f"Error stopping recording: {e}")
            messagebox.showerror("Error", f"Failed to stop recording: {e}")

    def save_run(self):
        """Save run with default name"""
        try:
            if not self.recorder.actions:
                messagebox.showwarning("Warning", "No actions to save")
                return

            # Create runs directory
            os.makedirs("runs", exist_ok=True)

            run_name = self.run_name_var.get().strip()
            if not run_name:
                run_name = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            filepath = f"runs/{run_name}.json"

            if self.recorder.save_run(filepath, run_name):
                self.save_btn.config(state="disabled")
                self.save_as_btn.config(state="disabled")
                messagebox.showinfo("Success", f"Run saved as: {filepath}")
            else:
                messagebox.showerror("Error", "Failed to save run")

        except Exception as e:
            self.log(f"Error saving run: {e}")
            messagebox.showerror("Error", f"Failed to save run: {e}")

    def save_run_as(self):
        """Save run with file dialog"""
        try:
            if not self.recorder.actions:
                messagebox.showwarning("Warning", "No actions to save")
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir="runs",
                initialname=self.run_name_var.get()
            )

            if filename:
                run_name = os.path.splitext(os.path.basename(filename))[0]
                if self.recorder.save_run(filename, run_name):
                    self.save_btn.config(state="disabled")
                    self.save_as_btn.config(state="disabled")
                    messagebox.showinfo("Success", f"Run saved as: {filename}")
                else:
                    messagebox.showerror("Error", "Failed to save run")

        except Exception as e:
            self.log(f"Error saving run: {e}")
            messagebox.showerror("Error", f"Failed to save run: {e}")

    def apply_settings(self):
        """Apply mouse tracking settings"""
        try:
            fps = int(self.fps_var.get())
            threshold = int(self.threshold_var.get())

            self.recorder.configure_mouse_tracking(fps, threshold)
            self.log(f"Settings applied: {fps} FPS, {threshold}px threshold")
            messagebox.showinfo("Success", "Settings applied successfully")

        except ValueError:
            messagebox.showerror("Error", "Invalid settings values")
        except Exception as e:
            self.log(f"Error applying settings: {e}")
            messagebox.showerror("Error", f"Failed to apply settings: {e}")

    def clear_log(self):
        """Clear the log display"""
        self.log_text.delete("1.0", tk.END)

    def save_log(self):
        """Save log to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialdir="logs",
                initialname=f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get("1.0", tk.END))
                messagebox.showinfo("Success", f"Log saved as: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save log: {e}")

    def start_status_updates(self):
        """Start the status update thread"""
        self.update_thread = threading.Thread(target=self.status_update_loop, daemon=True)
        self.update_thread.start()

    def status_update_loop(self):
        """Update status information periodically"""
        while self.running:
            try:
                if self.recorder:
                    status = self.recorder.get_recording_status()

                    # Update GUI in main thread
                    self.root.after(0, lambda: self.update_status_display(status))

                time.sleep(0.5)  # Update every 500ms

            except Exception as e:
                self.log(f"Error in status update: {e}")
                time.sleep(1)

    def update_status_display(self, status):
        """Update the status display (called from main thread)"""
        try:
            # Update system status
            if self.recorder_initialized:
                input_system = self.recorder.get_input_system_status()
                self.system_status_var.set(f"Status: {input_system}")
            else:
                self.system_status_var.set("Status: Not initialized")

            if status['recording']:
                duration = status.get('current_duration', 0)
                self.duration_var.set(f"Duration: {duration:.1f}s")

                stats = status.get('stats', {})
                total_actions = stats.get('total_actions', 0)
                self.actions_var.set(f"Actions: {total_actions}")

                mouse_saved = stats.get('mouse_positions_saved', 0)
                mouse_skipped = stats.get('mouse_positions_skipped', 0)
                if mouse_saved + mouse_skipped > 0:
                    compression = (mouse_skipped / (mouse_saved + mouse_skipped)) * 100
                    self.compression_var.set(f"Mouse compression: {compression:.1f}%")
                else:
                    self.compression_var.set("Mouse compression: 0%")

                # Update run name with current timestamp
                if not self.run_name_entry.get() or "run_" in self.run_name_entry.get():
                    new_name = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    self.run_name_var.set(new_name)

        except Exception as e:
            self.log(f"Error updating status display: {e}")

    def on_closing(self):
        """Handle window closing"""
        try:
            self.running = False

            if self.recorder.recording:
                result = messagebox.askyesno("Recording Active",
                                           "Recording is still active. Stop recording and save before closing?")
                if result:
                    self.recorder.stop_recording()
                    # Give user chance to save
                    if self.recorder.actions:
                        save_result = messagebox.askyesno("Save Recording",
                                                        "Save the current recording?")
                        if save_result:
                            self.save_run()

            self.recorder.cleanup()
            self.root.destroy()

        except Exception as e:
            self.log(f"Error during cleanup: {e}")
            self.root.destroy()

    def run(self):
        """Start the GUI main loop"""
        # Auto-refresh windows on startup
        self.refresh_windows()

        self.log("GUI ready - Select a window and start recording!")
        self.root.mainloop()


def main():
    """Main entry point"""
    try:
        app = RecordingGUI()
        app.run()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()