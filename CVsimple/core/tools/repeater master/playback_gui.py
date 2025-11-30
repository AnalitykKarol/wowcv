"""
Playback GUI - Interface for playing back recorded actions
ZAKTUALIZOWANY - dodano funkcję zapętlania z losowym delay
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
from datetime import datetime
import logging

# Import the playback system
from playback import ActionPlayback

# Import window enumeration from recording
try:
    from recording import ActionRecorder

    def get_available_windows():
        """Get available windows using ActionRecorder"""
        recorder = ActionRecorder()
        return recorder.get_available_windows()

except ImportError:
    # Fallback window enumeration
    import win32gui
    def get_available_windows():
        windows = []
        def enum_window_callback(hwnd, windows_list):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd)
                if window_text.strip():
                    rect = win32gui.GetWindowRect(hwnd)
                    windows_list.append({
                        'hwnd': hwnd,
                        'title': window_text,
                        'rect': rect,
                        'size': f"{rect[2]-rect[0]}x{rect[3]-rect[1]}"
                    })
        win32gui.EnumWindows(enum_window_callback, windows)
        return sorted(windows, key=lambda w: w['title'].lower())


class PlaybackGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Action Playback System")
        self.root.geometry("900x750")  # Zwiększono wysokość dla nowych kontrolek
        self.root.resizable(True, True)

        # Setup logging
        self.setup_logging()

        # Create playback system
        self.playback = ActionPlayback(self.logger)
        self.playback.set_progress_callback(self.on_progress_update)
        self.playback.set_completion_callback(self.on_playback_complete)

        # GUI state
        self.recordings = []
        self.selected_recording = None
        self.update_thread = None
        self.running = True

        # Create GUI elements
        self.create_widgets()
        self.setup_layout()

        # Start status updates
        self.start_status_updates()

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.log("Playback GUI started successfully")

    def setup_logging(self):
        """Setup logging to both file and GUI"""
        os.makedirs("logs", exist_ok=True)

        log_filename = f"logs/playback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        self.logger = logging.getLogger('playback')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, message: str):
        """Log message and update GUI log display"""
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        if safe_message.strip():
            self.logger.info(safe_message)

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

            lines = self.log_text.get("1.0", tk.END).split('\n')
            if len(lines) > 100:
                self.log_text.delete("1.0", f"{len(lines)-100}.0")
        except Exception:
            pass

    def create_widgets(self):
        """Create all GUI widgets"""

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)

        # === TAB 1: Playback Control ===
        self.playback_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.playback_frame, text="Playback")

        # Recording selection frame
        recording_frame = ttk.LabelFrame(self.playback_frame, text="1. Select Recording")

        # Recording list
        self.recording_listbox = tk.Listbox(recording_frame, height=6)
        self.recording_scrollbar = ttk.Scrollbar(recording_frame, orient="vertical", command=self.recording_listbox.yview)
        self.recording_listbox.configure(yscrollcommand=self.recording_scrollbar.set)

        # Recording control buttons
        recording_btn_frame = ttk.Frame(recording_frame)
        self.refresh_recordings_btn = ttk.Button(recording_btn_frame, text="Refresh List", command=self.refresh_recordings)
        self.load_recording_btn = ttk.Button(recording_btn_frame, text="Load Recording", command=self.load_selected_recording)
        self.load_file_btn = ttk.Button(recording_btn_frame, text="Load File...", command=self.load_recording_file)

        # Recording info frame
        info_frame = ttk.LabelFrame(self.playback_frame, text="Recording Information")

        self.info_text = tk.Text(info_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.info_scrollbar = ttk.Scrollbar(info_frame, orient="vertical", command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=self.info_scrollbar.set)

        # Target window frame
        window_frame = ttk.LabelFrame(self.playback_frame, text="2. Target Window (Optional)")

        # Window selection
        window_select_frame = ttk.Frame(window_frame)
        self.window_listbox = tk.Listbox(window_select_frame, height=3)
        self.window_scrollbar = ttk.Scrollbar(window_select_frame, orient="vertical", command=self.window_listbox.yview)
        self.window_listbox.configure(yscrollcommand=self.window_scrollbar.set)

        window_btn_frame = ttk.Frame(window_frame)
        self.refresh_windows_btn = ttk.Button(window_btn_frame, text="Refresh Windows", command=self.refresh_windows)
        self.select_window_btn = ttk.Button(window_btn_frame, text="Select Window", command=self.select_target_window)
        self.clear_window_btn = ttk.Button(window_btn_frame, text="Clear (Global)", command=self.clear_target_window)

        # Playback control frame
        control_frame = ttk.LabelFrame(self.playback_frame, text="3. Playback Control")

        # Status display
        self.status_var = tk.StringVar(value="Ready - No recording loaded")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, font=("Arial", 10, "bold"))

        # Control buttons
        control_btn_frame = ttk.Frame(control_frame)
        self.play_btn = ttk.Button(control_btn_frame, text="Play", command=self.play_recording, state="disabled")
        self.pause_btn = ttk.Button(control_btn_frame, text="Pause", command=self.pause_recording, state="disabled")
        self.stop_btn = ttk.Button(control_btn_frame, text="Stop", command=self.stop_recording, state="disabled")

        # Progress frame
        progress_frame = ttk.LabelFrame(control_frame, text="Progress")

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)

        self.progress_text_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_text_var)

        # === TAB 2: Settings ===
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")

        # Playback settings
        playback_settings_frame = ttk.LabelFrame(self.settings_frame, text="Playback Settings")

        ttk.Label(playback_settings_frame, text="Speed:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.speed_var = tk.StringVar(value="1.0")
        self.speed_spinbox = ttk.Spinbox(playback_settings_frame, from_=0.1, to=5.0, increment=0.1,
                                   textvariable=self.speed_var, width=10)
        self.speed_spinbox.grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(playback_settings_frame, text="(1.0 = normal, 2.0 = 2x speed)").grid(row=0, column=2, sticky="w", padx=5)

        self.relative_coords_var = tk.BooleanVar(value=True)
        self.coords_checkbox = ttk.Checkbutton(playback_settings_frame, text="Use relative coordinates (when target window set)",
                                         variable=self.relative_coords_var, command=self.update_coord_mode)
        self.coords_checkbox.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        self.apply_settings_btn = ttk.Button(playback_settings_frame, text="Apply Settings", command=self.apply_settings)
        self.apply_settings_btn.grid(row=2, column=0, columnspan=3, pady=10)

        # NOWE: Loop settings frame
        loop_frame = ttk.LabelFrame(self.settings_frame, text="🔄 Loop Settings")

        self.enable_loop_var = tk.BooleanVar(value=False)
        self.loop_checkbox = ttk.Checkbutton(loop_frame, text="Enable looping",
                                            variable=self.enable_loop_var, command=self.update_loop_settings)
        self.loop_checkbox.grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        ttk.Label(loop_frame, text="Delay min (s):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.loop_delay_min_var = tk.StringVar(value="1")
        loop_min_spinbox = ttk.Spinbox(loop_frame, from_=1, to=60, increment=1,
                                     textvariable=self.loop_delay_min_var, width=10)
        loop_min_spinbox.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(loop_frame, text="Delay max (s):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.loop_delay_max_var = tk.StringVar(value="5")
        loop_max_spinbox = ttk.Spinbox(loop_frame, from_=1, to=60, increment=1,
                                     textvariable=self.loop_delay_max_var, width=10)
        loop_max_spinbox.grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(loop_frame, text="Max iterations:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.loop_max_iterations_var = tk.StringVar(value="0")
        loop_iterations_spinbox = ttk.Spinbox(loop_frame, from_=0, to=100, increment=1,
                                            textvariable=self.loop_max_iterations_var, width=10)
        loop_iterations_spinbox.grid(row=3, column=1, padx=5, pady=2)
        ttk.Label(loop_frame, text="(0 = infinite)").grid(row=3, column=2, sticky="w", padx=5)

        apply_loop_btn = ttk.Button(loop_frame, text="Apply Loop Settings", command=self.apply_loop_settings)
        apply_loop_btn.grid(row=4, column=0, columnspan=3, pady=10)

        self.loop_info = ttk.Label(loop_frame, text="Loop: Disabled", font=("Arial", 8), foreground="gray")
        self.loop_info.grid(row=5, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        # Randomization settings
        randomization_frame = ttk.LabelFrame(self.settings_frame, text="Micro-Randomization (Anti-Detection)")

        self.enable_randomization_var = tk.BooleanVar(value=False)
        self.randomization_checkbox = ttk.Checkbutton(randomization_frame,
                                                     text="Enable micro-randomization",
                                                     variable=self.enable_randomization_var,
                                                     command=self.update_randomization)
        self.randomization_checkbox.grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        ttk.Label(randomization_frame, text="Timing variance (%):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.timing_variance_var = tk.StringVar(value="2.0")
        timing_spinbox = ttk.Spinbox(randomization_frame, from_=0.0, to=50.0, increment=1.0,
                                   textvariable=self.timing_variance_var, width=10)
        timing_spinbox.grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(randomization_frame, text="(±% of original timing)").grid(row=1, column=2, sticky="w", padx=5)

        ttk.Label(randomization_frame, text="Mouse variance (px):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.mouse_variance_var = tk.StringVar(value="2")
        mouse_spinbox = ttk.Spinbox(randomization_frame, from_=0, to=10, increment=1,
                                  textvariable=self.mouse_variance_var, width=10)
        mouse_spinbox.grid(row=2, column=1, padx=5, pady=2)
        ttk.Label(randomization_frame, text="(±pixels in X/Y)").grid(row=2, column=2, sticky="w", padx=5)

        ttk.Label(randomization_frame, text="Key timing (%):").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.key_timing_var = tk.StringVar(value="1.0")
        key_timing_spinbox = ttk.Spinbox(randomization_frame, from_=0.0, to=20.0, increment=0.5,
                                       textvariable=self.key_timing_var, width=10)
        key_timing_spinbox.grid(row=3, column=1, padx=5, pady=2)
        ttk.Label(randomization_frame, text="(±% extra delay)").grid(row=3, column=2, sticky="w", padx=5)

        apply_randomization_btn = ttk.Button(randomization_frame, text="Apply Randomization",
                                           command=self.apply_randomization_settings)
        apply_randomization_btn.grid(row=4, column=0, columnspan=3, pady=10)

        # Randomization info
        self.randomization_info = ttk.Label(randomization_frame, text="Randomization: Disabled",
                                          font=("Arial", 8), foreground="gray")
        self.randomization_info.grid(row=5, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        # Statistics frame
        stats_frame = ttk.LabelFrame(self.settings_frame, text="Current Session Statistics")

        self.stats_text = tk.Text(stats_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.stats_scrollbar = ttk.Scrollbar(stats_frame, orient="vertical", command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=self.stats_scrollbar.set)

        # === TAB 3: Log ===
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Log")

        # Log display
        log_display_frame = ttk.Frame(self.log_frame)
        self.log_text = tk.Text(log_display_frame, height=20, wrap=tk.WORD)
        self.log_scrollbar = ttk.Scrollbar(log_display_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scrollbar.set)

        # Log control buttons
        log_btn_frame = ttk.Frame(self.log_frame)
        self.clear_log_btn = ttk.Button(log_btn_frame, text="Clear Log", command=self.clear_log)
        self.save_log_btn = ttk.Button(log_btn_frame, text="Save Log", command=self.save_log)

        # Store references for layout
        self.recording_frame = recording_frame
        self.recording_btn_frame = recording_btn_frame
        self.info_frame = info_frame
        self.window_frame = window_frame
        self.window_select_frame = window_select_frame
        self.window_btn_frame = window_btn_frame
        self.control_frame = control_frame
        self.control_btn_frame = control_btn_frame
        self.progress_frame = progress_frame
        self.playback_settings_frame = playback_settings_frame
        self.loop_frame = loop_frame
        self.randomization_frame = randomization_frame
        self.stats_frame = stats_frame
        self.log_display_frame = log_display_frame
        self.log_btn_frame = log_btn_frame

    def setup_layout(self):
        """Setup widget layout"""

        # Main notebook
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # === Playback Tab Layout ===

        # Recording selection
        self.recording_frame.pack(fill="x", pady=(0, 10))

        list_frame = ttk.Frame(self.recording_frame)
        list_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.recording_listbox.pack(side="left", fill="both", expand=True)
        self.recording_scrollbar.pack(side="right", fill="y")

        self.recording_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.refresh_recordings_btn.pack(side="left", padx=(0, 5))
        self.load_recording_btn.pack(side="left", padx=(0, 5))
        self.load_file_btn.pack(side="left")

        # Recording info
        self.info_frame.pack(fill="x", pady=(0, 10))
        info_content_frame = ttk.Frame(self.info_frame)
        info_content_frame.pack(fill="x", padx=10, pady=10)
        self.info_text.pack(side="left", fill="both", expand=True)
        self.info_scrollbar.pack(side="right", fill="y")

        # Target window
        self.window_frame.pack(fill="x", pady=(0, 10))

        self.window_select_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.window_listbox.pack(side="left", fill="both", expand=True)
        self.window_scrollbar.pack(side="right", fill="y")

        self.window_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.refresh_windows_btn.pack(side="left", padx=(0, 5))
        self.select_window_btn.pack(side="left", padx=(0, 5))
        self.clear_window_btn.pack(side="left")

        # Playback control
        self.control_frame.pack(fill="x")
        self.status_label.pack(pady=(10, 5))

        self.control_btn_frame.pack(fill="x", pady=(0, 10))
        self.play_btn.pack(side="left", padx=(0, 5))
        self.pause_btn.pack(side="left", padx=(0, 5))
        self.stop_btn.pack(side="left")

        self.progress_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.progress_bar.pack(fill="x", padx=10, pady=(10, 5))
        self.progress_label.pack(pady=(0, 10))

        # === Settings Tab Layout ===
        self.playback_settings_frame.pack(fill="x", padx=10, pady=10)
        self.loop_frame.pack(fill="x", padx=10, pady=(0, 10))  # NOWE: Loop frame
        self.randomization_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.stats_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        stats_content_frame = ttk.Frame(self.stats_frame)
        stats_content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.stats_text.pack(side="left", fill="both", expand=True)
        self.stats_scrollbar.pack(side="right", fill="y")

        # === Log Tab Layout ===
        self.log_display_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_scrollbar.pack(side="right", fill="y")

        self.log_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.clear_log_btn.pack(side="left", padx=(0, 5))
        self.save_log_btn.pack(side="left")

    # NOWE: Loop methods
    def update_loop_settings(self):
        """Update loop settings based on checkbox"""
        try:
            enabled = self.enable_loop_var.get()
            if enabled:
                self.apply_loop_settings()
            else:
                self.playback.configure_loop(enabled=False)
                self.loop_info.config(text="Loop: Disabled")
                self.log("Loop disabled")
        except Exception as e:
            self.log(f"Error updating loop settings: {e}")

    def apply_loop_settings(self):
        """Apply loop settings"""
        try:
            enabled = self.enable_loop_var.get()
            delay_min = int(self.loop_delay_min_var.get())
            delay_max = int(self.loop_delay_max_var.get())
            max_iterations = int(self.loop_max_iterations_var.get())

            # Validate settings
            if delay_min > delay_max:
                delay_max = delay_min
                self.loop_delay_max_var.set(str(delay_max))

            self.playback.configure_loop(
                enabled=enabled,
                delay_min=delay_min,
                delay_max=delay_max,
                max_iterations=max_iterations
            )

            # Update info display
            if enabled:
                iterations_text = f"{max_iterations} times" if max_iterations > 0 else "infinitely"
                info_text = f"Loop: Enabled ({delay_min}-{delay_max}s delay, {iterations_text})"
            else:
                info_text = "Loop: Disabled"

            self.loop_info.config(text=info_text)
            self.log(f"Loop settings applied: enabled={enabled}, delay={delay_min}-{delay_max}s")

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid loop values: {e}")
        except Exception as e:
            self.log(f"Error applying loop settings: {e}")
            messagebox.showerror("Error", f"Failed to apply loop settings: {e}")

    # Reszta metod pozostaje bez zmian, ale dodaję aktualizacje do update_stats_display

    def update_stats_display(self, stats: dict):
        """Update statistics display with loop info"""
        try:
            # Get randomization and loop status
            status = self.playback.get_playback_status()
            randomization = status.get('randomization', {})
            loop = status.get('loop', {})

            loop_info = ""
            if loop.get('enabled', False):
                current_iter = loop.get('current_iteration', 0)
                max_iter = loop.get('max_iterations', 0)
                if max_iter > 0:
                    loop_info = f"Loop {current_iter}/{max_iter}"
                else:
                    loop_info = f"Loop {current_iter}/∞"
            else:
                loop_info = "Single run"

            stats_text = f"""Current Session Statistics:

{loop_info}
Actions Executed: {stats.get('actions_executed', 0)} / {stats.get('total_actions', 0)}
Mouse Movements: {stats.get('mouse_moves', 0)}
Mouse Clicks: {stats.get('mouse_clicks', 0)}
Key Presses: {stats.get('key_presses', 0)}
Errors: {stats.get('errors', 0)}
Playback Duration: {stats.get('playback_duration', 0):.1f} seconds
Total Loop Time: {stats.get('total_loop_time', 0):.1f} seconds

Randomization Status:
Enabled: {'Yes' if randomization.get('enabled', False) else 'No'}
Timing Variance: ±{randomization.get('timing_variance', 0):.1%}
Mouse Variance: ±{randomization.get('mouse_variance', 0)}px
Key Timing Variance: ±{randomization.get('key_timing_variance', 0):.1%}

Progress: {(stats.get('current_action', 0) / max(1, stats.get('total_actions', 1))) * 100:.1f}%"""

            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", stats_text)
            self.stats_text.config(state=tk.DISABLED)

        except Exception as e:
            self.log(f"Error updating stats display: {e}")

    # Pozostałe metody (refresh_recordings, load_recording, etc.) pozostają bez zmian
    # Ale trzeba dodać aktualizację progress display dla loop info

    def _update_progress_display(self, progress: float, stats: dict):
        """Update progress display with loop info"""
        try:
            self.progress_var.set(progress)
            current = stats.get('current_action', 0)
            total = stats.get('total_actions', 0)

            # Add loop info to progress text
            loop_iteration = stats.get('loop_iteration', 0)
            if loop_iteration > 0:
                progress_text = f"Loop {loop_iteration} - Action {current}/{total} ({progress:.1f}%)"
            else:
                progress_text = f"Action {current}/{total} ({progress:.1f}%)"

            self.progress_text_var.set(progress_text)

            # Update stats display
            self.update_stats_display(stats)

        except Exception as e:
            self.log(f"Error updating progress display: {e}")

    # Wszystkie pozostałe metody z oryginalnego playback_gui.py...
    # (refresh_recordings, load_selected_recording, load_recording_file, etc.)
    # Zachowuję je wszystkie bez zmian, więc nie będę ich przepisywać tutaj
    # Tylko dodałem nowe funkcje loop i zaktualizowałem kilka metod display

    def refresh_recordings(self):
        """Refresh the list of available recordings"""
        try:
            self.recordings = self.playback.get_available_recordings()

            self.recording_listbox.delete(0, tk.END)

            for recording in self.recordings:
                duration = recording['duration']
                actions = recording['total_actions']
                size_kb = recording['file_size'] / 1024
                display_text = f"{recording['name']} - {actions} actions, {duration:.1f}s ({size_kb:.1f} KB)"
                self.recording_listbox.insert(tk.END, display_text)

            self.log(f"Found {len(self.recordings)} recordings")

        except Exception as e:
            self.log(f"Error refreshing recordings: {e}")
            messagebox.showerror("Error", f"Failed to refresh recordings: {e}")

    def load_selected_recording(self):
        """Load the selected recording"""
        try:
            selection = self.recording_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a recording first")
                return

            recording_index = selection[0]
            if recording_index >= len(self.recordings):
                messagebox.showerror("Error", "Invalid recording selection")
                return

            recording = self.recordings[recording_index]
            self.load_recording(recording['filepath'])

        except Exception as e:
            self.log(f"Error loading selected recording: {e}")
            messagebox.showerror("Error", f"Failed to load recording: {e}")

    def load_recording_file(self):
        """Load recording from file dialog"""
        try:
            filename = filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir="runs",
                title="Select Recording File"
            )

            if filename:
                self.load_recording(filename)

        except Exception as e:
            self.log(f"Error loading recording file: {e}")
            messagebox.showerror("Error", f"Failed to load recording: {e}")

    def load_recording(self, filepath: str):
        """Load a recording file"""
        try:
            if self.playback.load_recording(filepath):
                self.selected_recording = filepath
                self.play_btn.config(state="normal")
                self.status_var.set("Recording loaded - Ready to play")

                # Update info display
                self.update_recording_info()

                self.log(f"Loaded recording: {os.path.basename(filepath)}")
            else:
                messagebox.showerror("Error", "Failed to load recording file")

        except Exception as e:
            self.log(f"Error loading recording: {e}")
            messagebox.showerror("Error", f"Failed to load recording: {e}")

    def update_recording_info(self):
        """Update the recording information display"""
        try:
            info = self.playback.get_recording_info()
            if not info:
                self.info_text.config(state=tk.NORMAL)
                self.info_text.delete("1.0", tk.END)
                self.info_text.insert("1.0", "No recording loaded")
                self.info_text.config(state=tk.DISABLED)
                return

            metadata = info['metadata']
            breakdown = info['action_breakdown']

            info_text = f"""Recording: {metadata.get('run_name', 'Unknown')}
Recorded: {metadata.get('recorded_at', 'Unknown')}
Original Window: {metadata.get('window_title', 'Unknown')}
Duration: {metadata.get('duration', 0):.1f} seconds
Total Actions: {info['total_actions']}

Action Breakdown:
• Key events: {breakdown['key']}
• Mouse clicks: {breakdown['mouse_click']}
• Mouse movements: {breakdown['mouse_move']}
• Other: {breakdown['other']}

Estimated playback time: {info['estimated_duration']:.1f} seconds"""

            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete("1.0", tk.END)
            self.info_text.insert("1.0", info_text)
            self.info_text.config(state=tk.DISABLED)

        except Exception as e:
            self.log(f"Error updating recording info: {e}")

    def refresh_windows(self):
        """Refresh the list of available windows"""
        try:
            windows = get_available_windows()

            self.window_listbox.delete(0, tk.END)

            for window in windows:
                display_text = f"{window['title']} ({window['size']})"
                self.window_listbox.insert(tk.END, display_text)

            self.windows_data = windows
            self.log(f"Found {len(windows)} windows")

        except Exception as e:
            self.log(f"Error refreshing windows: {e}")

    def select_target_window(self):
        """Select target window for playback"""
        try:
            selection = self.window_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a window first")
                return

            window_index = selection[0]
            if not hasattr(self, 'windows_data') or window_index >= len(self.windows_data):
                messagebox.showerror("Error", "Invalid window selection")
                return

            window = self.windows_data[window_index]

            if self.playback.set_target_window(window['hwnd']):
                self.log(f"Target window set: {window['title']}")
                messagebox.showinfo("Success", f"Target window set to: {window['title']}")
            else:
                messagebox.showerror("Error", "Failed to set target window")

        except Exception as e:
            self.log(f"Error selecting target window: {e}")
            messagebox.showerror("Error", f"Failed to select target window: {e}")

    def clear_target_window(self):
        """Clear target window (use global coordinates)"""
        try:
            self.playback.clear_target_window()
            self.log("Target window cleared - using global coordinates")
            messagebox.showinfo("Success", "Cleared target window - will use global coordinates")

        except Exception as e:
            self.log(f"Error clearing target window: {e}")

    def apply_settings(self):
        """Apply playback settings"""
        try:
            speed = float(self.speed_var.get())
            if speed <= 0:
                raise ValueError("Speed must be positive")

            self.playback.set_playback_speed(speed)
            self.log(f"Playback speed set to {speed}x")

            # Update estimated duration
            self.update_recording_info()

            messagebox.showinfo("Success", f"Settings applied: {speed}x speed")

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid speed value: {e}")
        except Exception as e:
            self.log(f"Error applying settings: {e}")
            messagebox.showerror("Error", f"Failed to apply settings: {e}")

    def play_recording(self):
        """Start playback"""
        try:
            if self.playback.start_playback():
                self.play_btn.config(state="disabled")
                self.pause_btn.config(state="normal")
                self.stop_btn.config(state="normal")

                # Update status with loop info
                loop_status = self.playback.get_loop_status()
                if loop_status['enabled']:
                    if loop_status['infinite']:
                        status_text = "Playing (looping infinitely)..."
                    else:
                        status_text = f"Playing (looping {loop_status['max_iterations']} times)..."
                else:
                    status_text = "Playing..."

                self.status_var.set(status_text)
                self.log("Playback started")
            else:
                messagebox.showerror("Error", "Failed to start playback")

        except Exception as e:
            self.log(f"Error starting playback: {e}")
            messagebox.showerror("Error", f"Failed to start playback: {e}")

    def pause_recording(self):
        """Pause/resume playback"""
        try:
            if self.playback.paused:
                self.playback.resume_playback()
                self.pause_btn.config(text="Pause")
                self.status_var.set("Playing...")
            else:
                self.playback.pause_playback()
                self.pause_btn.config(text="Resume")
                self.status_var.set("Paused")

        except Exception as e:
            self.log(f"Error pausing/resuming playback: {e}")

    def stop_recording(self):
        """Stop playback"""
        try:
            self.playback.stop_playback()
            self.play_btn.config(state="normal")
            self.pause_btn.config(state="disabled", text="Pause")
            self.stop_btn.config(state="disabled")
            self.status_var.set("Stopped")
            self.progress_var.set(0)
            self.progress_text_var.set("Stopped")
            self.log("Playback stopped")

        except Exception as e:
            self.log(f"Error stopping playback: {e}")

    def update_coord_mode(self):
        """Update coordinate mode"""
        try:
            use_relative = self.relative_coords_var.get()
            self.playback.use_relative_coords = use_relative
            mode = "relative" if use_relative else "absolute"
            self.log(f"Coordinate mode set to {mode}")

        except Exception as e:
            self.log(f"Error updating coordinate mode: {e}")

    def update_randomization(self):
        """Update randomization status"""
        try:
            enabled = self.enable_randomization_var.get()
            if enabled:
                self.apply_randomization_settings()
            else:
                self.playback.configure_randomization(enabled=False)
                self.randomization_info.config(text="Randomization: Disabled")
                self.log("Randomization disabled")
        except Exception as e:
            self.log(f"Error updating randomization: {e}")

    def apply_randomization_settings(self):
        """Apply randomization settings"""
        try:
            enabled = self.enable_randomization_var.get()
            timing_percent = float(self.timing_variance_var.get())
            mouse_pixels = int(self.mouse_variance_var.get())
            key_timing_percent = float(self.key_timing_var.get())

            self.playback.set_randomization_from_percentages(
                enabled=enabled,
                timing_percent=timing_percent,
                mouse_pixels=mouse_pixels,
                key_timing_percent=key_timing_percent,
                click_timing_percent=2.0  # Fixed 2% for clicks
            )

            # Update info display
            info_text = self.playback.get_randomization_info()
            self.randomization_info.config(text=info_text.replace('\n', ' | '))

            self.log(f"Randomization settings applied: {timing_percent}% timing, {mouse_pixels}px mouse")

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid randomization values: {e}")
        except Exception as e:
            self.log(f"Error applying randomization settings: {e}")
            messagebox.showerror("Error", f"Failed to apply randomization settings: {e}")

    def on_progress_update(self, progress: float, stats: dict):
        """Handle progress updates from playback"""
        try:
            self.root.after(0, lambda: self._update_progress_display(progress, stats))
        except:
            pass

    def on_playback_complete(self, stats: dict):
        """Handle playback completion"""
        try:
            self.root.after(0, lambda: self._handle_completion(stats))
        except:
            pass

    def _handle_completion(self, stats: dict):
        """Handle playback completion (called from main thread)"""
        try:
            self.play_btn.config(state="normal")
            self.pause_btn.config(state="disabled", text="Pause")
            self.stop_btn.config(state="disabled")
            self.status_var.set("Completed")
            self.progress_var.set(100)

            errors = stats.get('errors', 0)
            duration = stats.get('total_loop_time', stats.get('playback_duration', 0))
            actions = stats.get('actions_executed', 0)
            loop_iterations = stats.get('loop_iteration', 0)

            if errors > 0:
                self.progress_text_var.set(f"Completed with {errors} errors")
                completion_text = f"Playback completed with {errors} errors."
            else:
                self.progress_text_var.set("Completed successfully")
                completion_text = "Playback completed successfully!"

            if loop_iterations > 1:
                completion_text += f"\nCompleted {loop_iterations} iterations in {duration:.1f}s"
            else:
                completion_text += f"\nDuration: {duration:.1f}s, Actions: {actions}"

            if errors > 0:
                messagebox.showwarning("Playback Complete", completion_text)
            else:
                self.log(f"Playback completed: {loop_iterations} iterations, {duration:.1f}s")

        except Exception as e:
            self.log(f"Error handling completion: {e}")

    def start_status_updates(self):
        """Start the status update thread"""
        self.update_thread = threading.Thread(target=self.status_update_loop, daemon=True)
        self.update_thread.start()

    def status_update_loop(self):
        """Update status information periodically"""
        while self.running:
            try:
                status = self.playback.get_playback_status()

                # Only update if something is happening
                if status['playing']:
                    self.root.after(0, lambda s=status: self.update_status_from_thread(s))

                time.sleep(0.5)

            except Exception as e:
                self.log(f"Error in status update: {e}")
                time.sleep(1)

    def update_status_from_thread(self, status):
        """Update status from background thread"""
        try:
            if status['playing'] and not status['paused']:
                progress = status.get('progress_percent', 0)
                if hasattr(self, 'progress_var'):
                    self.progress_var.set(progress)

        except Exception as e:
            self.log(f"Error updating status from thread: {e}")

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
                initialname=f"playback_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get("1.0", tk.END))
                messagebox.showinfo("Success", f"Log saved as: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save log: {e}")

    def on_closing(self):
        """Handle window closing"""
        try:
            self.running = False

            if self.playback.playing:
                result = messagebox.askyesno("Playback Active",
                                           "Playback is still active. Stop playback and close?")
                if result:
                    self.playback.stop_playback()
                else:
                    return

            self.root.destroy()

        except Exception as e:
            self.log(f"Error during cleanup: {e}")
            self.root.destroy()

    def run(self):
        """Start the GUI main loop"""
        # Auto-refresh recordings and windows on startup
        self.refresh_recordings()
        self.refresh_windows()

        self.log("Playback GUI ready - Load a recording and start playing!")
        self.root.mainloop()


def main():
    """Main entry point"""
    try:
        app = PlaybackGUI()
        app.run()
    except Exception as e:
        print(f"Failed to start Playback GUI: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()