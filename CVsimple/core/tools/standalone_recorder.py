"""
Standalone Training Data Recorder
Niezależna aplikacja do nagrywania gameplay'u gracza dla treningu ML modelu
"""
import time
import pickle
import json
import cv2
import numpy as np
import threading
import keyboard
import mouse
import win32gui
import win32ui
import win32con
import win32api
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import queue
import psutil
from PIL import Image, ImageTk
import sys

@dataclass
class InputSnapshot:
    """Snapshot inputu gracza w danej chwili"""
    # Movement keys
    w: bool = False
    a: bool = False
    s: bool = False
    d: bool = False

    # Action keys
    space: bool = False
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    tab: bool = False

    # Number keys (skills)
    key_1: bool = False
    key_2: bool = False
    key_3: bool = False
    key_4: bool = False
    key_5: bool = False
    key_6: bool = False
    key_7: bool = False
    key_8: bool = False
    key_9: bool = False
    key_0: bool = False

    # Function keys
    f1: bool = False
    f2: bool = False
    f3: bool = False
    f4: bool = False

    # Mouse
    mouse_left: bool = False
    mouse_right: bool = False
    mouse_middle: bool = False
    mouse_x: int = 0
    mouse_y: int = 0

@dataclass
class GameFrame:
    """Pojedyncza ramka z gameplay'u"""
    timestamp: float
    frame_id: int
    screenshot: np.ndarray
    input_state: InputSnapshot
    session_name: str

    # Opcjonalne - wykrywanie z obrazu
    detected_hp_percent: Optional[float] = None
    detected_mana_percent: Optional[float] = None
    detected_objects: Optional[List[Dict]] = None

class SimpleHPManaDetector:
    """Prosty detektor HP/Mana na podstawie kolorów"""

    def __init__(self):
        # Domyślne pozycje pasków (można dostosować)
        self.hp_area = (50, 50, 200, 20)  # x, y, width, height
        self.mana_area = (50, 80, 200, 20)

        # Kolory pasków
        self.hp_color_range = {
            'lower': np.array([0, 100, 100]),    # Czerwony/zielony HSV
            'upper': np.array([60, 255, 255])
        }

        self.mana_color_range = {
            'lower': np.array([100, 100, 100]),  # Niebieski HSV
            'upper': np.array([130, 255, 255])
        }

    def detect_hp_mana(self, screenshot: np.ndarray) -> tuple:
        """Wykryj HP i mana z screenshota"""
        try:
            # Konwertuj do HSV
            hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)

            # Wytnij obszary pasków
            hp_region = self._crop_region(hsv, self.hp_area)
            mana_region = self._crop_region(hsv, self.mana_area)

            # Wykryj procenty
            hp_percent = self._analyze_bar_region(hp_region, self.hp_color_range)
            mana_percent = self._analyze_bar_region(mana_region, self.mana_color_range)

            return hp_percent, mana_percent

        except Exception as e:
            return None, None

    def _crop_region(self, image: np.ndarray, area: tuple) -> np.ndarray:
        """Wytnij region z obrazu"""
        x, y, w, h = area
        return image[y:y+h, x:x+w]

    def _analyze_bar_region(self, region: np.ndarray, color_range: dict) -> Optional[float]:
        """Analizuj region paska i zwróć procent"""
        if region.size == 0:
            return None

        # Stwórz maskę koloru
        mask = cv2.inRange(region, color_range['lower'], color_range['upper'])

        # Policz piksele koloru
        colored_pixels = cv2.countNonZero(mask)
        total_pixels = region.shape[0] * region.shape[1]

        if total_pixels > 0:
            return (colored_pixels / total_pixels) * 100.0
        return None

class KeyboardMouseTracker:
    """Tracker inputu klawiatury i myszy"""

    def __init__(self):
        self.current_state = InputSnapshot()
        self.tracking = False

        # Mapowanie klawiszy
        self.key_mapping = {
            'w': 'w', 'a': 'a', 's': 's', 'd': 'd',
            'space': 'space', 'shift': 'shift', 'ctrl': 'ctrl', 'alt': 'alt', 'tab': 'tab',
            '1': 'key_1', '2': 'key_2', '3': 'key_3', '4': 'key_4', '5': 'key_5',
            '6': 'key_6', '7': 'key_7', '8': 'key_8', '9': 'key_9', '0': 'key_0',
            'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4'
        }

    def start_tracking(self):
        """Rozpocznij śledzenie inputu"""
        if self.tracking:
            return

        self.tracking = True

        # Keyboard hooks
        for key_name, attr_name in self.key_mapping.items():
            keyboard.on_press_key(key_name, lambda e, attr=attr_name: self._key_down(attr))
            keyboard.on_release_key(key_name, lambda e, attr=attr_name: self._key_up(attr))

        # Mouse hooks
        mouse.on_button('left', self._mouse_left, args=())
        mouse.on_button('right', self._mouse_right, args=())
        mouse.on_button('middle', self._mouse_middle, args=())

        print("🎮 Input tracking started")

    def stop_tracking(self):
        """Zatrzymaj śledzenie inputu"""
        if not self.tracking:
            return

        self.tracking = False

        # Unhook wszystkie klawisze
        keyboard.unhook_all()
        mouse.unhook_all()

        print("🎮 Input tracking stopped")

    def _key_down(self, key_attr: str):
        """Handler wciśnięcia klawisza"""
        if hasattr(self.current_state, key_attr):
            setattr(self.current_state, key_attr, True)

    def _key_up(self, key_attr: str):
        """Handler puszczenia klawisza"""
        if hasattr(self.current_state, key_attr):
            setattr(self.current_state, key_attr, False)

    def _mouse_left(self):
        """Handler lewego przycisku myszy"""
        self.current_state.mouse_left = not self.current_state.mouse_left

    def _mouse_right(self):
        """Handler prawego przycisku myszy"""
        self.current_state.mouse_right = not self.current_state.mouse_right

    def _mouse_middle(self):
        """Handler środkowego przycisku myszy"""
        self.current_state.mouse_middle = not self.current_state.mouse_middle

    def get_current_state(self) -> InputSnapshot:
        """Pobierz aktualny stan inputu"""
        # Update mouse position
        pos = mouse.get_position()
        self.current_state.mouse_x = pos[0]
        self.current_state.mouse_y = pos[1]

        # Return copy
        return InputSnapshot(**asdict(self.current_state))

class WindowCapture:
    """Przechwytywanie konkretnego okna"""

    def __init__(self):
        self.target_window = None
        self.hwnd = None

    def find_game_window(self, window_title_fragment: str) -> List[tuple]:
        """Znajdź okna gry"""
        windows = []

        def enum_handler(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd)
                if window_title_fragment.lower() in window_text.lower() and len(window_text) > 3:
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    windows.append((hwnd, window_text, width, height))
            return True

        win32gui.EnumWindows(enum_handler, windows)
        return windows

    def set_target_window(self, hwnd: int, title: str):
        """Ustaw okno docelowe"""
        self.hwnd = hwnd
        self.target_window = title
        print(f"🎯 Target window set: {title}")

    def capture_window(self) -> Optional[np.ndarray]:
        """Przechwyć screenshot okna"""
        if not self.hwnd:
            return None

        try:
            # Get window dimensions
            rect = win32gui.GetWindowRect(self.hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            if width <= 0 or height <= 0:
                return None

            # Capture window
            hwndDC = win32gui.GetWindowDC(self.hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # Copy window content
            saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)

            # Convert to numpy array
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            img = np.frombuffer(bmpstr, dtype='uint8')
            img.shape = (height, width, 4)
            img = img[..., :3]  # Remove alpha channel
            img = np.ascontiguousarray(img)

            # Cleanup
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwndDC)

            return img

        except Exception as e:
            print(f"❌ Screenshot error: {e}")
            return None

class DataRecorder:
    """Główny recorder danych"""

    def __init__(self):
        self.window_capture = WindowCapture()
        self.input_tracker = KeyboardMouseTracker()
        self.hp_mana_detector = SimpleHPManaDetector()

        # Recording state
        self.recording = False
        self.session_name = ""
        self.frame_count = 0
        self.recorded_frames = []

        # Settings
        self.target_fps = 10
        self.frame_interval = 1.0 / self.target_fps

        # Threads
        self.record_thread = None
        self.stop_event = threading.Event()

        # Data storage
        self.output_dir = Path("recorded_sessions")
        self.output_dir.mkdir(exist_ok=True)

        # Stats
        self.start_time = 0
        self.bytes_recorded = 0

    def start_recording(self, session_name: str):
        """Rozpocznij nagrywanie sesji"""
        if self.recording:
            return False

        if not self.window_capture.hwnd:
            print("❌ No target window selected!")
            return False

        self.session_name = session_name
        self.recording = True
        self.frame_count = 0
        self.recorded_frames = []
        self.start_time = time.time()
        self.stop_event.clear()

        # Start input tracking
        self.input_tracker.start_tracking()

        # Start recording thread
        self.record_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.record_thread.start()

        print(f"🔴 RECORDING STARTED: {session_name}")
        return True

    def stop_recording(self):
        """Zatrzymaj nagrywanie"""
        if not self.recording:
            return

        print("🔴 STOPPING RECORDING...")
        self.recording = False
        self.stop_event.set()

        # Stop input tracking
        self.input_tracker.stop_tracking()

        # Wait for thread
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=5)

        # Save data
        if self.recorded_frames:
            self._save_session()

        duration = time.time() - self.start_time
        print(f"✅ RECORDING COMPLETED")
        print(f"📊 Duration: {duration:.1f}s")
        print(f"📊 Frames: {len(self.recorded_frames)}")
        print(f"📊 Size: {self.bytes_recorded / 1024 / 1024:.1f}MB")

    def _recording_loop(self):
        """Główna pętla nagrywania"""
        last_frame_time = 0

        while self.recording and not self.stop_event.is_set():
            current_time = time.time()

            # FPS control
            if current_time - last_frame_time < self.frame_interval:
                time.sleep(0.01)
                continue

            try:
                # Capture screenshot
                screenshot = self.window_capture.capture_window()
                if screenshot is None:
                    continue

                # Get input state
                input_state = self.input_tracker.get_current_state()

                # Detect HP/Mana (optional)
                hp_percent, mana_percent = self.hp_mana_detector.detect_hp_mana(screenshot)

                # Create frame
                frame = GameFrame(
                    timestamp=current_time,
                    frame_id=self.frame_count,
                    screenshot=screenshot,
                    input_state=input_state,
                    session_name=self.session_name,
                    detected_hp_percent=hp_percent,
                    detected_mana_percent=mana_percent
                )

                self.recorded_frames.append(frame)
                self.frame_count += 1
                self.bytes_recorded += screenshot.nbytes

                last_frame_time = current_time

        
            except Exception as e:
                time.sleep(0.1)

    def _save_session(self):
        """Zapisz sesję do pliku"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.session_name}_{timestamp}"

        # Save binary data
        data_file = self.output_dir / f"{filename}.pkl"
        with open(data_file, 'wb') as f:
            pickle.dump(self.recorded_frames, f, protocol=pickle.HIGHEST_PROTOCOL)

        # Save metadata
        metadata = {
            'session_name': self.session_name,
            'timestamp': timestamp,
            'frame_count': len(self.recorded_frames),
            'duration_seconds': self.recorded_frames[-1].timestamp - self.recorded_frames[0].timestamp,
            'target_fps': self.target_fps,
            'file_size_mb': self.bytes_recorded / 1024 / 1024,
            'target_window': self.window_capture.target_window
        }

        metadata_file = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"💾 Session saved: {data_file}")
        print(f"📄 Metadata: {metadata_file}")

class RecorderGUI:
    """GUI dla recordera"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎮 Gaming Session Recorder for ML Training")
        self.root.geometry("800x600")

        self.recorder = DataRecorder()

        # GUI state
        self.recording_var = tk.BooleanVar()
        self.fps_var = tk.IntVar(value=10)
        self.session_name_var = tk.StringVar(value="deadmines")
        self.auto_increment_var = tk.BooleanVar(value=True)
        self.current_run_var = tk.IntVar(value=1)

        # Session management
        self.completed_runs = []
        self.session_stats = {
            'total_runs': 0,
            'total_duration': 0,
            'last_session': None
        }

        self.setup_gui()
        self.update_loop()
        self.update_session_preview()

        # Load previous session stats
        self.load_session_stats()

    def setup_gui(self):
        """Ustaw interfejs"""
        # Main title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill='x', padx=10, pady=10)

        title_label = ttk.Label(title_frame, text="🎮 Gaming Session Recorder",
                               font=('Arial', 16, 'bold'))
        title_label.pack()

        subtitle_label = ttk.Label(title_frame, text="Record your gameplay for ML bot training",
                                  font=('Arial', 10))
        subtitle_label.pack()

        # Window selection
        window_frame = ttk.LabelFrame(self.root, text="🪟 Select Game Window", padding=10)
        window_frame.pack(fill='x', padx=10, pady=5)

        window_search_frame = ttk.Frame(window_frame)
        window_search_frame.pack(fill='x')

        ttk.Label(window_search_frame, text="Window title contains:").pack(side='left')
        self.window_search_var = tk.StringVar(value="World of Warcraft")
        ttk.Entry(window_search_frame, textvariable=self.window_search_var, width=30).pack(side='left', padx=5)
        ttk.Button(window_search_frame, text="🔍 Find Windows",
                  command=self.find_windows).pack(side='left', padx=5)

        # Window list
        self.window_listbox = tk.Listbox(window_frame, height=4)
        self.window_listbox.pack(fill='x', pady=5)

        ttk.Button(window_frame, text="✅ Select Window",
                  command=self.select_window).pack()

        self.selected_window_label = ttk.Label(window_frame, text="❌ No window selected",
                                              foreground='red')
        self.selected_window_label.pack(pady=5)

        # Recording settings
        settings_frame = ttk.LabelFrame(self.root, text="⚙️ Recording Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=5)

        # Session name with auto-increment
        name_frame = ttk.Frame(settings_frame)
        name_frame.pack(fill='x', pady=2)
        ttk.Label(name_frame, text="Base session name:").pack(side='left')
        ttk.Entry(name_frame, textvariable=self.session_name_var, width=20).pack(side='left', padx=5)

        # Auto-increment controls
        self.auto_increment_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(name_frame, text="Auto-increment run number",
                       variable=self.auto_increment_var).pack(side='left', padx=10)

        self.current_run_var = tk.IntVar(value=1)
        ttk.Label(name_frame, text="Run #:").pack(side='left', padx=(10,0))
        run_spinbox = ttk.Spinbox(name_frame, from_=1, to=999, width=5,
                                 textvariable=self.current_run_var)
        run_spinbox.pack(side='left', padx=5)

        # Preview of full session name
        self.session_preview_label = ttk.Label(name_frame, text="",
                                              font=('Arial', 9), foreground='blue')
        self.session_preview_label.pack(side='left', padx=10)

        # Quick session templates
        template_frame = ttk.Frame(settings_frame)
        template_frame.pack(fill='x', pady=5)
        ttk.Label(template_frame, text="Quick templates:").pack(side='left')

        templates = [
            ("Deadmines", "deadmines"),
            ("Wailing Caverns", "wc"),
            ("Stockade", "stockade"),
            ("Scarlet Monastery", "sm"),
            ("Custom", "custom")
        ]

        for display_name, base_name in templates:
            ttk.Button(template_frame, text=display_name, width=12,
                      command=lambda name=base_name: self.set_session_template(name)).pack(side='left', padx=2)

        # FPS setting
        fps_frame = ttk.Frame(settings_frame)
        fps_frame.pack(fill='x', pady=2)
        ttk.Label(fps_frame, text="Recording FPS:").pack(side='left')
        fps_scale = ttk.Scale(fps_frame, from_=5, to=30, variable=self.fps_var,
                             orient='horizontal', length=200)
        fps_scale.pack(side='left', padx=5)
        ttk.Label(fps_frame, textvariable=self.fps_var).pack(side='left')

        # Recording controls
        control_frame = ttk.LabelFrame(self.root, text="🎬 Recording Controls", padding=10)
        control_frame.pack(fill='x', padx=10, pady=5)

        button_frame = ttk.Frame(control_frame)
        button_frame.pack()

        self.record_button = ttk.Button(button_frame, text="🔴 Start Recording",
                                       command=self.toggle_recording)
        self.record_button.pack(side='left', padx=5)

        ttk.Button(button_frame, text="📁 Open Output Folder",
                  command=self.open_output_folder).pack(side='left', padx=5)

        ttk.Button(button_frame, text="📊 Session Summary",
                  command=self.show_session_summary).pack(side='left', padx=5)

        ttk.Button(button_frame, text="🔄 Refresh Runs",
                  command=self.refresh_run_detection).pack(side='left', padx=5)

        # Session progress
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(fill='x', pady=5)

        self.progress_label = ttk.Label(progress_frame, text="No runs completed yet")
        self.progress_label.pack(side='left')

        # Progress bar for target (e.g., 50 runs)
        self.target_runs_var = tk.IntVar(value=50)
        ttk.Label(progress_frame, text="Target runs:").pack(side='right', padx=(20,5))
        ttk.Spinbox(progress_frame, from_=10, to=200, width=5,
                   textvariable=self.target_runs_var).pack(side='right')

        self.progress_bar = ttk.Progressbar(progress_frame, length=200, mode='determinate')
        self.progress_bar.pack(side='right', padx=10)

        # Hotkey info
        hotkey_label = ttk.Label(control_frame,
                                text="Hotkeys: F10 = Start/Stop Recording, F11 = Emergency Stop",
                                font=('Arial', 9), foreground='blue')
        hotkey_label.pack(pady=5)

        # Status
        status_frame = ttk.LabelFrame(self.root, text="📊 Status", padding=10)
        status_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.status_text = tk.Text(status_frame, height=15, wrap='word', font=('Consolas', 9))
        status_scrollbar = ttk.Scrollbar(status_frame, orient='vertical', command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scrollbar.set)

        self.status_text.pack(side='left', fill='both', expand=True)
        status_scrollbar.pack(side='right', fill='y')

        # Setup hotkeys
        keyboard.add_hotkey('f10', self.toggle_recording)
        keyboard.add_hotkey('f11', self.emergency_stop)

        # Bind events for auto-preview update
        self.session_name_var.trace('w', lambda *args: self.update_session_preview())
        self.current_run_var.trace('w', lambda *args: self.update_session_preview())
        self.auto_increment_var.trace('w', lambda *args: self.update_session_preview())

        # Also auto-detect when base name changes
        self.session_name_var.trace('w', lambda *args: self.auto_detect_on_name_change())

        self.log_status("🚀 Recorder initialized. Find and select your game window to start.")

    def auto_detect_on_name_change(self):
        """Auto-wykryj run number gdy zmienia się base name"""
        base_name = self.session_name_var.get()
        if base_name and self.auto_increment_var.get():
            # Small delay to avoid rapid updates during typing
            self.root.after(500, lambda: self.delayed_auto_detect(base_name))

    def delayed_auto_detect(self, base_name: str):
        """Opóźnione auto-wykrywanie (żeby nie spam podczas pisania)"""
        # Only update if name hasn't changed during delay
        if self.session_name_var.get() == base_name:
            next_run = self.detect_next_run_number(base_name)
            current_run = self.current_run_var.get()

            # Only update if it would be different (avoid infinite loops)
            if next_run != current_run:
                self.current_run_var.set(next_run)

                existing_count = len(self.find_existing_runs(base_name))
                if existing_count > 0:
                    self.log_status(f"🔄 Auto-detected: {base_name} has {existing_count} runs, continuing from run_{next_run:02d}")

    def find_windows(self):
        """Znajdź okna gry"""
        search_term = self.window_search_var.get()
        windows = self.recorder.window_capture.find_game_window(search_term)

        self.window_listbox.delete(0, tk.END)
        self.window_data = {}

        for hwnd, title, width, height in windows:
            display_text = f"{title} ({width}x{height})"
            self.window_listbox.insert(tk.END, display_text)
            self.window_data[display_text] = (hwnd, title)

        self.log_status(f"🔍 Found {len(windows)} windows matching '{search_term}'")

    def set_session_template(self, template_name: str):
        """Ustaw szablon sesji i auto-wykryj następny run number"""
        self.session_name_var.set(template_name)

        # Auto-detect next run number
        next_run = self.detect_next_run_number(template_name)
        self.current_run_var.set(next_run)

        self.update_session_preview()
        self.log_status(f"📋 Template set: {template_name}")

        # Show existing runs info
        existing_runs = self.find_existing_runs(template_name)
        if existing_runs:
            self.log_status(f"📊 Found {len(existing_runs)} existing runs. Next: run_{next_run:02d}")
        else:
            self.log_status(f"🆕 New session started. First run: run_{next_run:02d}")

    def detect_next_run_number(self, base_name: str) -> int:
        """Wykryj następny numer runu na podstawie istniejących plików"""
        existing_runs = self.find_existing_runs(base_name)

        if not existing_runs:
            return 1  # First run

        # Return next number after highest existing
        return max(existing_runs) + 1

    def update_session_preview(self):
        """Aktualizuj podgląd nazwy sesji"""
        base_name = self.session_name_var.get()

        if self.auto_increment_var.get():
            run_number = self.current_run_var.get()
            full_name = f"{base_name}_run_{run_number:02d}"
        else:
            full_name = base_name

        self.session_preview_label.config(text=f"→ {full_name}")

        # Also update existing runs count
        if base_name:
            existing_count = len(self.find_existing_runs(base_name))
            if existing_count > 0:
                self.session_preview_label.config(
                    text=f"→ {full_name} (continuing from {existing_count} existing)"
                )

    def get_current_session_name(self) -> str:
        """Pobierz aktualną nazwę sesji"""
        base_name = self.session_name_var.get()

        if self.auto_increment_var.get():
            run_number = self.current_run_var.get()
            return f"{base_name}_run_{run_number:02d}"
        else:
            return base_name

    def load_session_stats(self):
        """Wczytaj statystyki poprzednich sesji i auto-wykryj run number"""
        stats_file = self.recorder.output_dir / "session_stats.json"

        if stats_file.exists():
            try:
                with open(stats_file, 'r') as f:
                    self.session_stats = json.load(f)
                self.log_status(f"📊 Loaded stats: {self.session_stats['total_runs']} total runs")
            except Exception as e:
                self.log_status(f"⚠️ Could not load session stats: {e}")

        # Auto-detect next run for current base name
        base_name = self.session_name_var.get()
        if base_name:
            next_run = self.detect_next_run_number(base_name)
            self.current_run_var.set(next_run)

            existing_runs = self.find_existing_runs(base_name)
            if existing_runs:
                self.log_status(f"🔄 Resuming '{base_name}': found {len(existing_runs)} existing runs")
                self.log_status(f"🎯 Next run will be: run_{next_run:02d}")

    def save_session_stats(self):
        """Zapisz statystyki sesji"""
        stats_file = self.recorder.output_dir / "session_stats.json"

        try:
            with open(stats_file, 'w') as f:
                json.dump(self.session_stats, f, indent=2)
        except Exception as e:
            self.log_status(f"⚠️ Could not save session stats: {e}")

    def find_existing_runs(self, base_name: str) -> List[int]:
        """Znajdź istniejące runy dla danej bazy nazwy"""
        if not base_name.strip():
            return []

        existing_runs = []

        # Search for both .pkl and _metadata.json files
        search_patterns = [
            f"{base_name}_run_*_*.pkl",
            f"{base_name}_run_*_*_metadata.json"
        ]

        found_numbers = set()

        for pattern in search_patterns:
            for file in self.recorder.output_dir.glob(pattern):
                try:
                    # Extract run number from filename
                    # Format: base_name_run_XX_YYYYMMDD_HHMMSS.pkl
                    filename = file.stem.replace('_metadata', '')

                    # Find pattern "run_XX"
                    import re
                    match = re.search(r'run_(\d+)', filename)
                    if match:
                        run_num = int(match.group(1))
                        found_numbers.add(run_num)

                except (ValueError, IndexError) as e:
                    continue

        return sorted(list(found_numbers))

    def refresh_run_detection(self):
        """Ręczne odświeżenie wykrywania runów (dla debug)"""
        base_name = self.session_name_var.get()
        if base_name:
            existing_runs = self.find_existing_runs(base_name)
            next_run = self.detect_next_run_number(base_name)
            self.current_run_var.set(next_run)
            self.update_session_preview()

            self.log_status(f"🔄 Refreshed: found {len(existing_runs)} runs, next: {next_run}")
            if existing_runs:
                self.log_status(f"   Existing runs: {existing_runs}")
        else:
            self.log_status("⚠️ Enter base session name first")
        """Znajdź okna gry"""
        search_term = self.window_search_var.get()
        windows = self.recorder.window_capture.find_game_window(search_term)

        self.window_listbox.delete(0, tk.END)
        self.window_data = {}

        for hwnd, title, width, height in windows:
            display_text = f"{title} ({width}x{height})"
            self.window_listbox.insert(tk.END, display_text)
            self.window_data[display_text] = (hwnd, title)

        self.log_status(f"🔍 Found {len(windows)} windows matching '{search_term}'")

    def select_window(self):
        """Wybierz okno do nagrywania"""
        selection = self.window_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a window from the list")
            return

        selected_text = self.window_listbox.get(selection[0])
        hwnd, title = self.window_data[selected_text]

        self.recorder.window_capture.set_target_window(hwnd, title)
        self.selected_window_label.config(text=f"✅ Selected: {title}", foreground='green')

        self.log_status(f"🎯 Target window selected: {title}")

    def toggle_recording(self):
        """Przełącz nagrywanie"""
        if self.recorder.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Rozpocznij nagrywanie"""
        if not self.recorder.window_capture.hwnd:
            messagebox.showerror("Error", "Please select a game window first!")
            return

        session_name = self.get_current_session_name()

        # Check if session already exists
        existing_files = list(self.recorder.output_dir.glob(f"{session_name}_*.pkl"))
        if existing_files:
            response = messagebox.askyesno(
                "Session Exists",
                f"Session '{session_name}' already exists.\n\nOverwrite?",
                default='no'
            )
            if not response:
                return

        # Update settings
        self.recorder.target_fps = self.fps_var.get()
        self.recorder.frame_interval = 1.0 / self.recorder.target_fps

        success = self.recorder.start_recording(session_name)
        if success:
            self.record_button.config(text="⏹️ Stop Recording")
            self.log_status(f"🔴 Recording started: {session_name}")
            self.log_status("🎮 Play your game normally. Press F10 or the button to stop.")

            # Update run tracking
            self.session_stats['last_session'] = session_name

    def stop_recording(self):
        """Zatrzymaj nagrywanie"""
        if not self.recorder.recording:
            return

        session_name = self.recorder.session_name
        duration = time.time() - self.recorder.start_time if self.recorder.start_time > 0 else 0

        self.recorder.stop_recording()
        self.record_button.config(text="🔴 Start Recording")

        # Update session stats
        self.session_stats['total_runs'] += 1
        self.session_stats['total_duration'] += duration
        self.completed_runs.append({
            'name': session_name,
            'duration': duration,
            'frames': self.recorder.frame_count,
            'timestamp': datetime.now().isoformat()
        })

        # Auto-increment run number if enabled
        if self.auto_increment_var.get():
            current_run = self.current_run_var.get()
            self.current_run_var.set(current_run + 1)
            self.update_session_preview()

        # Save stats
        self.save_session_stats()

        # Show completion summary
        completion_msg = f"✅ Run completed: {session_name}\n"
        completion_msg += f"📊 Duration: {duration:.1f}s\n"
        completion_msg += f"📊 Frames: {self.recorder.frame_count}\n"
        completion_msg += f"📊 Total runs this session: {len(self.completed_runs)}"

        self.log_status("⏹️ Recording stopped and saved.")
        self.log_status(completion_msg)

        # Auto-suggest next action
        if self.auto_increment_var.get():
            next_session = self.get_current_session_name()
            self.log_status(f"🎯 Next run ready: {next_session}")
            self.log_status("   Press F10 to start next recording!")

    def show_session_summary(self):
        """Pokaż podsumowanie sesji nagrywania"""
        base_name = self.session_name_var.get()

        # Get all existing runs for this base name
        all_existing_runs = self.find_existing_runs(base_name)

        # Get runs completed in current session
        current_session_runs = self.completed_runs

        if not all_existing_runs and not current_session_runs:
            messagebox.showinfo("Session Summary", f"No runs found for '{base_name}'.")
            return

        # Calculate totals
        current_session_duration = sum(run['duration'] for run in current_session_runs)
        current_session_frames = sum(run['frames'] for run in current_session_runs)

        summary = f"📊 SESSION SUMMARY: {base_name}\n\n"

        # Overall stats
        summary += f"📁 Total runs on disk: {len(all_existing_runs)}\n"
        if all_existing_runs:
            summary += f"   Run numbers: {min(all_existing_runs)} - {max(all_existing_runs)}\n"

        summary += f"🎬 Current session runs: {len(current_session_runs)}\n"

        if current_session_runs:
            avg_duration = current_session_duration / len(current_session_runs)
            summary += f"   Total duration: {current_session_duration/60:.1f} minutes\n"
            summary += f"   Average run time: {avg_duration:.1f} seconds\n"
            summary += f"   Total frames: {current_session_frames:,}\n"
            summary += f"   Data size estimate: {(current_session_frames * 2) / 1024:.1f} MB\n\n"

            summary += "Recent runs this session:\n"
            for run in current_session_runs[-5:]:  # Last 5 runs
                summary += f"  • {run['name']}: {run['duration']:.1f}s ({run['frames']} frames)\n"

        # Next run info
        next_run = self.detect_next_run_number(base_name)
        summary += f"\n🎯 Next run: {base_name}_run_{next_run:02d}"

        messagebox.showinfo("Session Summary", summary)

    def emergency_stop(self):
        """Awaryjne zatrzymanie"""
        if self.recorder.recording:
            self.recorder.stop_recording()
            self.record_button.config(text="🔴 Start Recording")
            self.log_status("🚨 EMERGENCY STOP - Recording terminated!")

    def open_output_folder(self):
        """Otwórz folder z nagraniami"""
        import os
        import subprocess

        path = self.recorder.output_dir.absolute()
        if path.exists():
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        else:
            messagebox.showinfo("Info", f"Output folder will be created at:\n{path}")

    def log_status(self, message: str):
        """Dodaj wiadomość do statusu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        self.status_text.insert(tk.END, log_message)
        self.status_text.see(tk.END)

        # Keep only last 1000 lines
        lines = self.status_text.get(1.0, tk.END).split('\n')
        if len(lines) > 1000:
            self.status_text.delete(1.0, f"{len(lines) - 1000}.0")

        print(log_message.strip())

    def update_loop(self):
        """Pętla aktualizacji GUI"""
        try:
            # Update recording status
            if self.recorder.recording:
                elapsed = time.time() - self.recorder.start_time
                fps = self.recorder.frame_count / elapsed if elapsed > 0 else 0
                size_mb = self.recorder.bytes_recorded / 1024 / 1024

                status = f"🔴 RECORDING | Frames: {self.recorder.frame_count} | "
                status += f"Time: {elapsed:.0f}s | FPS: {fps:.1f} | Size: {size_mb:.1f}MB"

                self.root.title(f"Gaming Session Recorder - {status}")
            else:
                self.root.title("🎮 Gaming Session Recorder")

            # Update progress
            completed_count = len(self.completed_runs)
            target_count = self.target_runs_var.get()

            if completed_count > 0:
                progress_text = f"Completed: {completed_count}/{target_count} runs"
                if completed_count >= target_count:
                    progress_text += " ✅ TARGET REACHED!"
                self.progress_label.config(text=progress_text)

                # Update progress bar
                progress_percent = min(100, (completed_count / target_count) * 100)
                self.progress_bar['value'] = progress_percent
            else:
                self.progress_label.config(text="No runs completed yet")
                self.progress_bar['value'] = 0

        except Exception as e:
            self.log_status(f"❌ Update error: {e}")

        # Schedule next update
        self.root.after(1000, self.update_loop)

    def run(self):
        """Uruchom aplikację"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
        finally:
            # Cleanup
            if self.recorder.recording:
                self.recorder.stop_recording()
            keyboard.unhook_all()

def main():
    """Główna funkcja"""
    print("🎮 Starting Gaming Session Recorder...")
    print("This application will record your gameplay for ML training.")
    print("\nControls:")
    print("F10 - Start/Stop recording")
    print("F11 - Emergency stop")
    print("\nMake sure to:")
    print("1. Select your game window")
    print("2. Enter a descriptive session name")
    print("3. Play normally while recording")

    app = RecorderGUI()
    app.run()

if __name__ == "__main__":
    main()