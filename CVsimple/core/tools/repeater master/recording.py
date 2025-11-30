"""
Action Recording System - Complete Recording Module
Handles all recording functionality: mouse, keyboard, hotkeys
POPRAWIONY - zwiększona precyzja i lepsze próbkowanie
"""
import win32api
import win32con
import win32gui
import time
import json
import threading
import ctypes
import ctypes.wintypes
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime
import os


class GlobalHotkeyManager:
    """Manages global hotkeys for recording control"""

    def __init__(self, logger=None):
        self.logger = logger
        self.hotkeys = {}
        self.hotkey_thread = None
        self.stop_event = threading.Event()
        self.callback_map = {}

    def register_hotkey(self, key_code: int, modifiers: int, callback: Callable, name: str = None):
        """Register a global hotkey"""
        try:
            hotkey_id = len(self.hotkeys) + 1
            success = ctypes.windll.user32.RegisterHotKeyW(None, hotkey_id, modifiers, key_code)

            if success:
                self.hotkeys[hotkey_id] = {
                    'key_code': key_code,
                    'modifiers': modifiers,
                    'name': name or f"Hotkey_{hotkey_id}"
                }
                self.callback_map[hotkey_id] = callback
                self.log(f"Registered global hotkey: {name or key_code} (ID: {hotkey_id})")
                return hotkey_id
            else:
                self.log(f"Failed to register hotkey: {name or key_code}")
                return None

        except Exception as e:
            self.log(f"Error registering hotkey: {e}")
            return None

    def start_listening(self):
        """Start listening for hotkey messages"""
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            return

        self.stop_event.clear()
        self.hotkey_thread = threading.Thread(target=self._hotkey_listener, daemon=True)
        self.hotkey_thread.start()
        self.log("Global hotkey listener started")

    def _hotkey_listener(self):
        """Hotkey message loop"""
        msg = ctypes.wintypes.MSG()

        while not self.stop_event.is_set():
            try:
                # Get message with timeout
                result = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)

                if result == -1:  # Error
                    break
                elif result == 0:  # WM_QUIT
                    break

                if msg.message == win32con.WM_HOTKEY:
                    hotkey_id = msg.wParam
                    if hotkey_id in self.callback_map:
                        try:
                            self.callback_map[hotkey_id]()
                        except Exception as e:
                            self.log(f"Error in hotkey callback: {e}")

                # Small sleep to prevent busy waiting
                time.sleep(0.01)

            except Exception as e:
                self.log(f"Error in hotkey listener: {e}")
                time.sleep(0.1)

    def stop_listening(self):
        """Stop hotkey listener"""
        self.stop_event.set()
        if self.hotkey_thread:
            self.hotkey_thread.join(timeout=1.0)

    def unregister_all(self):
        """Unregister all hotkeys"""
        for hotkey_id in self.hotkeys:
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        self.hotkeys.clear()
        self.callback_map.clear()
        self.log("All hotkeys unregistered")

    def log(self, message: str):
        if self.logger:
            # Remove emoji for Windows compatibility
            safe_message = message.encode('ascii', 'ignore').decode('ascii')
            self.logger.info(safe_message)
        else:
            print(f"[GlobalHotkeyManager] {message}")


class InputPolling:
    """POPRAWIONA klasa - Input capture using polling z wysoką precyzją"""

    def __init__(self, logger=None):
        self.logger = logger
        self.recording = False
        self.action_callback: Optional[Callable] = None

        # Polling state
        self.poll_thread: Optional[threading.Thread] = None
        self.stop_polling = threading.Event()

        # POPRAWKA 1: Zwiększona częstotliwość próbkowania do 1000 FPS
        self.poll_interval = 0.001  # 1ms = 1000 FPS zamiast 0.002 (500Hz)

        # Key state tracking
        self.key_states = {}  # Track key down/up states
        self.mouse_states = {}  # Track mouse button states

        # POPRAWKA 2: Precyzyjny timer do timestampów
        self.start_time = None

        # POPRAWKA 3: Rozszerzona lista monitorowanych klawiszy
        self.monitored_keys = [
            # Letters A-Z
            0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A,
            0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x50, 0x51, 0x52, 0x53, 0x54,
            0x55, 0x56, 0x57, 0x58, 0x59, 0x5A,
            # Numbers 0-9
            0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
            # Function keys F1-F12
            0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79,
            0x7A, 0x7B,
            # Special keys
            0x20,  # Space
            0x0D,  # Enter
            0x1B,  # Escape
            0x09,  # Tab
            0x08,  # Backspace
            0x2E,  # Delete
            0x24,  # Home
            0x23,  # End
            0x21,  # Page Up
            0x22,  # Page Down
            0x25,  # Left Arrow
            0x26,  # Up Arrow
            0x27,  # Right Arrow
            0x28,  # Down Arrow
            # Modifier keys
            0x10,  # Shift
            0x11,  # Ctrl
            0x12,  # Alt
            0x5B,  # Left Windows key
            0x5C,  # Right Windows key
            # Numpad
            0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
            0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
        ]

        # Mouse button codes
        self.mouse_buttons = {
            0x01: 'left',    # Left mouse button
            0x02: 'right',   # Right mouse button
            0x04: 'middle'   # Middle mouse button
        }

    def set_action_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Set callback function for captured actions"""
        self.action_callback = callback

    def is_key_pressed(self, vk_code: int) -> bool:
        """Check if key is currently pressed using GetAsyncKeyState"""
        try:
            state = ctypes.windll.user32.GetAsyncKeyState(vk_code)
            return (state & 0x8000) != 0  # Check if key is down
        except:
            return False

    def poll_input_loop(self):
        """POPRAWIONA główna pętla polling z wysoką precyzją"""
        self.log("Input polling started with 1000 FPS precision")
        self.start_time = time.perf_counter()  # POPRAWKA: Użyj perf_counter dla precyzji

        while not self.stop_polling.is_set():
            try:
                if not self.recording:
                    time.sleep(0.01)
                    continue

                current_time = time.perf_counter()

                # POPRAWKA 4: Dokładniejsze próbkowanie klawiatury
                for vk_code in self.monitored_keys:
                    current_state = self.is_key_pressed(vk_code)
                    previous_state = self.key_states.get(vk_code, False)

                    if current_state != previous_state:
                        state = 'down' if current_state else 'up'
                        if self.action_callback:
                            # POPRAWKA: Dodaj precyzyjny timestamp
                            timestamp = current_time - self.start_time
                            self.action_callback('key', {
                                'key_code': vk_code,
                                'state': state,
                                'precise_time': timestamp  # Precyzyjny czas
                            })
                        self.key_states[vk_code] = current_state

                # Poll mouse buttons
                for vk_code, button_name in self.mouse_buttons.items():
                    current_state = self.is_key_pressed(vk_code)
                    previous_state = self.mouse_states.get(vk_code, False)

                    if current_state != previous_state:
                        state = 'down' if current_state else 'up'
                        if self.action_callback:
                            # Get mouse position
                            try:
                                cursor_pos = win32gui.GetCursorPos()
                                timestamp = current_time - self.start_time
                                self.action_callback('mouse_click', {
                                    'x': cursor_pos[0],
                                    'y': cursor_pos[1],
                                    'button': button_name,
                                    'state': state,
                                    'precise_time': timestamp
                                })
                            except:
                                pass
                        self.mouse_states[vk_code] = current_state

                # POPRAWKA 5: Precyzyjne opóźnienie
                sleep_time = self.poll_interval - (time.perf_counter() - current_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                self.log(f"Error in polling loop: {e}")
                time.sleep(0.001)

        self.log("Input polling stopped")

    def start_capture(self):
        """Start input capture using polling"""
        if self.poll_thread and self.poll_thread.is_alive():
            return True

        try:
            self.stop_polling.clear()
            # POPRAWKA: Reset state tracking
            self.key_states.clear()
            self.mouse_states.clear()

            self.poll_thread = threading.Thread(target=self.poll_input_loop, daemon=True)
            self.poll_thread.start()
            self.recording = True
            self.log("Input polling capture started (1000 FPS precision)")
            return True
        except Exception as e:
            self.log(f"Failed to start polling: {e}")
            return False

    def stop_capture(self):
        """Stop input capture"""
        self.recording = False
        self.log("Input polling capture stopped")

    def initialize(self):
        """Initialize polling system"""
        self.log("High-precision polling system initialized (1000 FPS)")
        return True

    def cleanup(self):
        """Stop polling system"""
        self.stop_polling.set()
        if self.poll_thread:
            self.poll_thread.join(timeout=2.0)
        self.log("Polling system stopped")

    def log(self, message: str):
        if self.logger:
            safe_message = message.encode('ascii', 'ignore').decode('ascii')
            self.logger.info(safe_message)


class ActionRecorder:
    """POPRAWIONA główna klasa recording z precyzyjnym timingiem"""

    def __init__(self, logger=None):
        self.logger = logger

        # Recording state
        self.recording = False
        self.target_hwnd: Optional[int] = None
        self.target_window_rect: Optional[Tuple[int, int, int, int]] = None
        self.actions: List[Dict[str, Any]] = []

        # POPRAWKA: Użyj perf_counter dla precyzyjnych timestampów
        self.start_time: Optional[float] = None

        # Components
        self.hotkey_manager = GlobalHotkeyManager(logger)
        self.input_polling = InputPolling(logger)

        # Mouse tracking optimization - zwiększona precyzja
        self.mouse_poll_interval = 1/120  # 120 FPS dla myszy
        self.last_mouse_pos: Optional[Tuple[int, int]] = None
        self.mouse_movement_threshold = 1
        self.mouse_tracking_thread: Optional[threading.Thread] = None
        self.stop_mouse_tracking = threading.Event()

        # Setup callbacks
        self.input_polling.set_action_callback(self.record_input_action)

        # Statistics
        self.stats = {
            'total_actions': 0,
            'mouse_moves': 0,
            'mouse_clicks': 0,
            'key_presses': 0,
            'recording_duration': 0,
            'mouse_positions_saved': 0,
            'mouse_positions_skipped': 0
        }

    def log(self, message: str):
        """Log message if logger available"""
        if self.logger:
            # Remove emoji for Windows compatibility
            safe_message = message.encode('ascii', 'ignore').decode('ascii')
            self.logger.info(safe_message)
        else:
            print(f"[ActionRecorder] {message}")

    def initialize(self):
        """Initialize all components"""
        try:
            # Initialize input polling
            if not self.input_polling.initialize():
                return False

            # Register F10 hotkey for toggle recording
            self.hotkey_manager.register_hotkey(
                key_code=0x79,  # F10
                modifiers=0,    # No modifiers
                callback=self.toggle_recording,
                name="F10_Toggle_Recording"
            )

            # Start hotkey listener
            self.hotkey_manager.start_listening()

            self.log("ActionRecorder initialized successfully")
            return True

        except Exception as e:
            self.log(f"Error initializing ActionRecorder: {e}")
            return False

    def cleanup(self):
        """Clean up all components"""
        self.stop_recording()
        self.input_polling.cleanup()
        self.hotkey_manager.stop_listening()
        self.hotkey_manager.unregister_all()
        self.log("ActionRecorder cleanup completed")

    def get_available_windows(self) -> List[Dict[str, Any]]:
        """Get list of visible windows for selection"""
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

    def set_target_window(self, hwnd: int) -> bool:
        """Set target window for recording"""
        try:
            if not win32gui.IsWindow(hwnd):
                self.log(f"Invalid window handle: {hwnd}")
                return False

            window_title = win32gui.GetWindowText(hwnd)
            window_rect = win32gui.GetWindowRect(hwnd)

            self.target_hwnd = hwnd
            self.target_window_rect = window_rect

            self.log(f"Target window set: '{window_title}' ({window_rect[2]-window_rect[0]}x{window_rect[3]-window_rect[1]})")
            return True

        except Exception as e:
            self.log(f"Error setting target window: {e}")
            return False

    def get_relative_mouse_position(self) -> Optional[Tuple[int, int]]:
        """Get mouse position relative to target window"""
        if not self.target_hwnd or not self.target_window_rect:
            return None

        try:
            cursor_pos = win32gui.GetCursorPos()
            rel_x = cursor_pos[0] - self.target_window_rect[0]
            rel_y = cursor_pos[1] - self.target_window_rect[1]
            return (rel_x, rel_y)

        except Exception as e:
            return None

    def should_record_mouse_position(self, current_pos: Tuple[int, int]) -> bool:
        """Determine if mouse position should be recorded"""
        if self.last_mouse_pos is None:
            return True

        dx = abs(current_pos[0] - self.last_mouse_pos[0])
        dy = abs(current_pos[1] - self.last_mouse_pos[1])
        distance = max(dx, dy)

        return distance >= self.mouse_movement_threshold

    def record_action(self, action_type: str, data: Dict[str, Any]):
        """POPRAWIONA metoda record action z precyzyjnym timestampem"""
        if not self.recording or self.start_time is None:
            return

        # POPRAWKA: Użyj precise_time jeśli dostępne, inaczej oblicz z perf_counter
        if 'precise_time' in data:
            relative_time = data['precise_time']
            del data['precise_time']  # Usuń z danych akcji aby nie zapisywać w JSON
        else:
            current_time = time.perf_counter()
            relative_time = current_time - self.start_time

        action = {
            'timestamp': round(relative_time, 6),  # POPRAWKA: Zwiększ precyzję do mikrosekund
            'type': action_type,
            'data': data
        }

        self.actions.append(action)
        self.stats['total_actions'] += 1

        if action_type == 'mouse_move':
            self.stats['mouse_moves'] += 1
        elif action_type == 'mouse_click':
            self.stats['mouse_clicks'] += 1
        elif action_type == 'key':
            self.stats['key_presses'] += 1

    def record_input_action(self, action_type: str, data: Dict[str, Any]):
        """Callback for input capture events"""
        if action_type == 'mouse_click':
            # Convert absolute coordinates to relative
            if self.target_window_rect:
                abs_x, abs_y = data['x'], data['y']
                rel_x = abs_x - self.target_window_rect[0]
                rel_y = abs_y - self.target_window_rect[1]
                data['x'] = rel_x
                data['y'] = rel_y

        self.record_action(action_type, data)

    def mouse_tracking_loop(self):
        """Mouse position tracking loop z wyższą precyzją"""
        while not self.stop_mouse_tracking.is_set():
            try:
                mouse_pos = self.get_relative_mouse_position()

                if mouse_pos and self.should_record_mouse_position(mouse_pos):
                    self.record_action('mouse_move', {
                        'x': mouse_pos[0],
                        'y': mouse_pos[1]
                    })

                    self.last_mouse_pos = mouse_pos
                    self.stats['mouse_positions_saved'] += 1
                else:
                    if mouse_pos:  # Only count as skipped if we have valid position
                        self.stats['mouse_positions_skipped'] += 1

                time.sleep(self.mouse_poll_interval)

            except Exception as e:
                self.log(f"Error in mouse tracking: {e}")
                time.sleep(0.1)

    def start_recording(self) -> bool:
        """POPRAWIONE rozpoczęcie nagrywania z precyzyjnym timerem"""
        if self.recording:
            self.log("Recording already in progress")
            return False

        if not self.target_hwnd:
            self.log("No target window set")
            return False

        try:
            # Reset state
            self.actions.clear()
            self.start_time = time.perf_counter()  # POPRAWKA: Precyzyjny timer
            self.last_mouse_pos = None
            self.stop_mouse_tracking.clear()

            # Reset stats
            for key in self.stats:
                if key != 'recording_duration':
                    self.stats[key] = 0

            # Start input polling
            self.input_polling.start_capture()

            # Start mouse tracking thread
            self.mouse_tracking_thread = threading.Thread(target=self.mouse_tracking_loop, daemon=True)
            self.mouse_tracking_thread.start()

            self.recording = True
            self.log("Recording STARTED with high precision timing")
            return True

        except Exception as e:
            self.log(f"Error starting recording: {e}")
            return False

    def stop_recording(self) -> bool:
        """Stop recording user actions"""
        if not self.recording:
            self.log("No recording in progress")
            return False

        try:
            # Stop input polling
            self.input_polling.stop_capture()

            # Stop mouse tracking
            self.stop_mouse_tracking.set()
            if self.mouse_tracking_thread:
                self.mouse_tracking_thread.join(timeout=2.0)

            # Calculate duration
            if self.start_time:
                self.stats['recording_duration'] = time.perf_counter() - self.start_time

            self.recording = False

            # Log statistics
            duration = self.stats['recording_duration']
            total_actions = self.stats['total_actions']
            mouse_saved = self.stats['mouse_positions_saved']
            mouse_skipped = self.stats['mouse_positions_skipped']
            compression_ratio = (mouse_skipped / max(1, mouse_saved + mouse_skipped)) * 100

            self.log("Recording STOPPED")
            self.log(f"Duration: {duration:.3f}s, Actions: {total_actions}")
            self.log(f"Mouse: {mouse_saved} saved, {mouse_skipped} skipped ({compression_ratio:.1f}% compression)")

            return True

        except Exception as e:
            self.log(f"Error stopping recording: {e}")
            return False

    def toggle_recording(self):
        """Toggle recording state (F10 hotkey callback)"""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def save_run(self, filepath: str, run_name: str = None) -> bool:
        """Save recorded run to JSON file"""
        if not self.actions:
            self.log("No actions to save")
            return False

        try:
            window_title = win32gui.GetWindowText(self.target_hwnd) if self.target_hwnd else "Unknown"
            window_size = None
            if self.target_window_rect:
                window_size = [
                    self.target_window_rect[2] - self.target_window_rect[0],
                    self.target_window_rect[3] - self.target_window_rect[1]
                ]

            run_data = {
                'metadata': {
                    'run_name': run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'recorded_at': datetime.now().isoformat(),
                    'window_title': window_title,
                    'window_size': window_size,
                    'duration': self.stats['recording_duration'],
                    'total_actions': self.stats['total_actions'],
                    'mouse_positions_saved': self.stats['mouse_positions_saved'],
                    'mouse_positions_skipped': self.stats['mouse_positions_skipped'],
                    'compression_ratio': (self.stats['mouse_positions_skipped'] /
                                        max(1, self.stats['mouse_positions_saved'] + self.stats['mouse_positions_skipped'])) * 100,
                    'precision_version': '1.1'  # POPRAWKA: Oznacz wersję z lepszą precyzją
                },
                'actions': self.actions,
                'statistics': self.stats.copy()
            }

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(run_data, f, indent=2, ensure_ascii=False)

            file_size = os.path.getsize(filepath) / 1024
            self.log(f"Run saved: {filepath} ({file_size:.1f} KB)")
            return True

        except Exception as e:
            self.log(f"Error saving run: {e}")
            return False

    def get_input_system_status(self) -> str:
        """Get current input system status"""
        return "High-precision polling system active (1000 FPS input monitoring)"

    def get_recording_status(self) -> Dict[str, Any]:
        """Get current recording status and statistics"""
        status = {
            'recording': self.recording,
            'target_window': None,
            'current_duration': 0,
            'stats': self.stats.copy()
        }

        if self.target_hwnd:
            try:
                status['target_window'] = {
                    'title': win32gui.GetWindowText(self.target_hwnd),
                    'size': None
                }
                if self.target_window_rect:
                    status['target_window']['size'] = [
                        self.target_window_rect[2] - self.target_window_rect[0],
                        self.target_window_rect[3] - self.target_window_rect[1]
                    ]
            except:
                status['target_window'] = {'title': 'Error getting window info', 'size': None}

        if self.recording and self.start_time:
            status['current_duration'] = time.perf_counter() - self.start_time

        return status

    def configure_mouse_tracking(self, fps: int = 120, movement_threshold: int = 1):
        """Configure mouse tracking parameters - zwiększona domyślna wartość FPS"""
        self.mouse_poll_interval = 1 / fps
        self.mouse_movement_threshold = movement_threshold
        self.log(f"Mouse tracking configured: {fps} FPS, {movement_threshold}px threshold")


# Test/example usage
if __name__ == "__main__":
    import logging
    import signal
    import sys

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    logger = logging.getLogger()

    # Create recorder
    recorder = ActionRecorder(logger)

    def signal_handler(sig, frame):
        print("\nShutting down...")
        recorder.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Initialize
    if not recorder.initialize():
        print("Failed to initialize recorder")
        sys.exit(1)

    print("=== IMPROVED Action Recording System ===")
    print("1. Select a target window")
    print("2. Press F10 to start/stop recording")
    print("3. Use Ctrl+C to exit")
    print("IMPROVEMENTS: 1000 FPS precision, better timing")
    print()

    # Show available windows
    windows = recorder.get_available_windows()
    print("Available windows:")
    for i, window in enumerate(windows[:10]):
        print(f"{i+1}. {window['title']} ({window['size']})")

    try:
        choice = int(input("\nSelect window (number): ")) - 1
        if 0 <= choice < len(windows):
            recorder.set_target_window(windows[choice]['hwnd'])
            print("Ready! Press F10 to start recording...")

            # Keep alive
            while True:
                time.sleep(1)
        else:
            print("Invalid selection")

    except (ValueError, KeyboardInterrupt):
        pass
    finally:
        recorder.cleanup()