"""
Action Playback System - Replays recorded user actions
POPRAWIONY - precyzyjny timing i naprawiona randomizacja
"""
import win32api
import win32con
import win32gui
import time
import json
import threading
import random
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import os


class ActionPlayback:
    """POPRAWIONA główna klasa playback z precyzyjnym timingiem"""

    def __init__(self, logger=None):
        self.logger = logger

        # Playback state
        self.playing = False
        self.paused = False
        self.actions: List[Dict[str, Any]] = []
        self.metadata: Optional[Dict[str, Any]] = None

        # Playback control
        self.playback_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

        # NOWE: Loop control
        self.loop_enabled = False
        self.loop_delay_min = 1  # minimum delay in seconds
        self.loop_delay_max = 5  # maximum delay in seconds
        self.current_loop_iteration = 0
        self.max_loop_iterations = 0  # 0 = infinite

        # Settings
        self.playback_speed = 1.0  # 1.0 = normal speed, 2.0 = 2x speed, 0.5 = half speed
        self.target_hwnd: Optional[int] = None
        self.target_window_rect: Optional[tuple] = None
        self.use_relative_coords = True  # Use relative coordinates if target window is set

        # POPRAWKA 1: Jasna kontrola randomizacji - domyślnie wyłączona
        self.enable_randomization = False
        self.timing_variance = 0.0
        self.mouse_variance = 0
        self.key_timing_variance = 0.0
        self.click_timing_variance = 0.0

        # Statistics
        self.stats = {
            'total_actions': 0,
            'current_action': 0,
            'playback_duration': 0,
            'actions_executed': 0,
            'mouse_moves': 0,
            'mouse_clicks': 0,
            'key_presses': 0,
            'errors': 0,
            'loop_iteration': 0,
            'total_loop_time': 0
        }

        # Callbacks
        self.progress_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None

    def log(self, message: str):
        """Log message if logger available"""
        if self.logger:
            safe_message = message.encode('ascii', 'ignore').decode('ascii')
            self.logger.info(safe_message)
        else:
            print(f"[ActionPlayback] {message}")

    def configure_loop(self, enabled: bool = False, delay_min: int = 1, delay_max: int = 5, max_iterations: int = 0):
        """Configure loop settings

        Args:
            enabled: Enable/disable looping
            delay_min: Minimum delay between loops (seconds)
            delay_max: Maximum delay between loops (seconds)
            max_iterations: Maximum iterations (0 = infinite)
        """
        self.loop_enabled = enabled
        self.loop_delay_min = max(1, delay_min)
        self.loop_delay_max = max(delay_min, delay_max)
        self.max_loop_iterations = max(0, max_iterations)

        if enabled:
            iterations_text = f"{max_iterations} times" if max_iterations > 0 else "infinitely"
            self.log(f"Loop enabled: {delay_min}-{delay_max}s delay, repeat {iterations_text}")
        else:
            self.log("Loop disabled")

    def get_loop_status(self) -> Dict[str, Any]:
        """Get current loop settings and status"""
        return {
            'enabled': self.loop_enabled,
            'delay_min': self.loop_delay_min,
            'delay_max': self.loop_delay_max,
            'max_iterations': self.max_loop_iterations,
            'current_iteration': self.current_loop_iteration,
            'infinite': self.max_loop_iterations == 0
        }

    def load_recording(self, filepath: str) -> bool:
        """Load recording from JSON file"""
        try:
            if not os.path.exists(filepath):
                self.log(f"Recording file not found: {filepath}")
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate structure
            if 'actions' not in data or 'metadata' not in data:
                self.log("Invalid recording file format")
                return False

            self.actions = data['actions']
            self.metadata = data['metadata']

            # Reset stats
            self.stats['total_actions'] = len(self.actions)
            self.stats['current_action'] = 0
            self.stats['actions_executed'] = 0
            self.stats['mouse_moves'] = 0
            self.stats['mouse_clicks'] = 0
            self.stats['key_presses'] = 0
            self.stats['errors'] = 0

            # Log info
            duration = self.metadata.get('duration', 0)
            window_title = self.metadata.get('window_title', 'Unknown')
            precision_version = self.metadata.get('precision_version', '1.0')

            self.log(f"Loaded recording: {len(self.actions)} actions, {duration:.3f}s duration")
            self.log(f"Original window: {window_title}")
            self.log(f"Recording precision: {precision_version}")

            return True

        except Exception as e:
            self.log(f"Error loading recording: {e}")
            return False

    def set_target_window(self, hwnd: int) -> bool:
        """Set target window for coordinate translation"""
        try:
            if not win32gui.IsWindow(hwnd):
                self.log(f"Invalid window handle: {hwnd}")
                return False

            window_title = win32gui.GetWindowText(hwnd)
            window_rect = win32gui.GetWindowRect(hwnd)

            self.target_hwnd = hwnd
            self.target_window_rect = window_rect

            self.log(f"Target window set: '{window_title}'")
            return True

        except Exception as e:
            self.log(f"Error setting target window: {e}")
            return False

    def clear_target_window(self):
        """Clear target window (use global coordinates)"""
        self.target_hwnd = None
        self.target_window_rect = None
        self.log("Target window cleared - using global coordinates")

    def convert_coordinates(self, rel_x: int, rel_y: int) -> tuple:
        """Convert relative coordinates to absolute"""
        if not self.use_relative_coords or not self.target_window_rect:
            return (rel_x, rel_y)

        abs_x = self.target_window_rect[0] + rel_x
        abs_y = self.target_window_rect[1] + rel_y
        return (abs_x, abs_y)

    def configure_randomization(self, enabled: bool = False, timing_variance: float = 0.0,
                              mouse_variance: int = 0, key_timing_variance: float = 0.0,
                              click_timing_variance: float = 0.0):
        """POPRAWKA: Jasne ustawienie randomizacji"""
        self.enable_randomization = enabled

        if enabled:
            self.timing_variance = max(0.0, min(1.0, timing_variance))
            self.mouse_variance = max(0, min(10, mouse_variance))
            self.key_timing_variance = max(0.0, min(0.2, key_timing_variance))
            self.click_timing_variance = max(0.0, min(0.1, click_timing_variance))
        else:
            # POPRAWKA: Gdy wyłączone, ustaw wszystko na zero
            self.timing_variance = 0.0
            self.mouse_variance = 0
            self.key_timing_variance = 0.0
            self.click_timing_variance = 0.0

        status = "enabled" if enabled else "disabled"
        self.log(f"Randomization {status}: timing={self.timing_variance:.3f}, "
                f"mouse={self.mouse_variance}px, key={self.key_timing_variance:.3f}")

    def set_randomization_from_percentages(self, enabled: bool = False,
                                           timing_percent: float = 0.0,
                                           mouse_pixels: int = 0,
                                           key_timing_percent: float = 0.0,
                                           click_timing_percent: float = 0.0):
        """POPRAWKA: Ustaw randomizację z procentów - tylko gdy włączona"""
        if enabled:
            timing_variance = timing_percent / 100.0
            key_timing_variance = key_timing_percent / 100.0
            click_timing_variance = click_timing_percent / 100.0
        else:
            timing_variance = 0.0
            key_timing_variance = 0.0
            click_timing_variance = 0.0
            mouse_pixels = 0

        self.configure_randomization(
            enabled=enabled,
            timing_variance=timing_variance,
            mouse_variance=mouse_pixels,
            key_timing_variance=key_timing_variance,
            click_timing_variance=click_timing_variance
        )

    def get_randomization_info(self) -> str:
        """Get human-readable randomization info"""
        if not self.enable_randomization:
            return "Randomization: Disabled"

        return (f"Randomization: Enabled\n"
                f"  • Timing: ±{self.timing_variance:.1%}\n"
                f"  • Mouse: ±{self.mouse_variance}px\n"
                f"  • Key timing: ±{self.key_timing_variance:.1%}\n"
                f"  • Click timing: ±{self.click_timing_variance:.1%}")

    def apply_timing_randomization(self, base_delay: float) -> float:
        """POPRAWKA: Randomizacja tylko gdy włączona"""
        if not self.enable_randomization or base_delay <= 0 or self.timing_variance == 0.0:
            return base_delay

        variance = base_delay * self.timing_variance
        random_offset = random.uniform(-variance, variance)
        randomized_delay = max(0.0001, base_delay + random_offset)  # Minimum 0.1ms delay

        return randomized_delay

    def apply_mouse_randomization(self, x: int, y: int) -> tuple:
        """POPRAWKA: Randomizacja myszy tylko gdy włączona"""
        if not self.enable_randomization or self.mouse_variance == 0:
            return (x, y)

        x_offset = random.randint(-self.mouse_variance, self.mouse_variance)
        y_offset = random.randint(-self.mouse_variance, self.mouse_variance)

        randomized_x = max(0, x + x_offset)
        randomized_y = max(0, y + y_offset)

        return (randomized_x, randomized_y)

    def apply_key_timing_randomization(self) -> float:
        """POPRAWKA: Randomizacja klawiszy tylko gdy włączona"""
        if not self.enable_randomization or self.key_timing_variance == 0.0:
            return 0.0

        # Small random delay between 0-5ms for key events
        max_delay = 0.005 * self.key_timing_variance * 100
        return random.uniform(0, max_delay)

    def apply_click_timing_randomization(self) -> float:
        """POPRAWKA: Randomizacja clicków tylko gdy włączona"""
        if not self.enable_randomization or self.click_timing_variance == 0.0:
            return 0.0

        # Small random delay between 0-2ms for click events
        max_delay = 0.002 * self.click_timing_variance * 100
        return random.uniform(0, max_delay)

    def get_randomization_status(self) -> Dict[str, Any]:
        """Get current randomization settings"""
        return {
            'enabled': self.enable_randomization,
            'timing_variance': self.timing_variance,
            'mouse_variance': self.mouse_variance,
            'key_timing_variance': self.key_timing_variance,
            'click_timing_variance': self.click_timing_variance
        }

    def simulate_key_event(self, key_code: int, state: str):
        """POPRAWKA: Precyzyjne symulowanie klawiatury"""
        try:
            # Dodaj opóźnienie tylko gdy randomizacja jest włączona
            random_delay = self.apply_key_timing_randomization()
            if random_delay > 0:
                time.sleep(random_delay)

            if state == 'down':
                win32api.keybd_event(key_code, 0, 0, 0)
            elif state == 'up':
                win32api.keybd_event(key_code, 0, win32con.KEYEVENTF_KEYUP, 0)

            self.stats['key_presses'] += 1

        except Exception as e:
            self.log(f"Error simulating key event: {e}")
            self.stats['errors'] += 1

    def simulate_mouse_move(self, x: int, y: int):
        """POPRAWKA: Precyzyjne ruchy myszy"""
        try:
            # Randomizacja tylko gdy włączona
            final_x, final_y = self.apply_mouse_randomization(x, y)
            abs_x, abs_y = self.convert_coordinates(final_x, final_y)

            win32api.SetCursorPos((abs_x, abs_y))
            self.stats['mouse_moves'] += 1

        except Exception as e:
            self.log(f"Error simulating mouse move: {e}")
            self.stats['errors'] += 1

    def simulate_mouse_click(self, x: int, y: int, button: str, state: str):
        """POPRAWKA: Precyzyjne kliknięcia myszy bez przypadkowej randomizacji"""
        try:
            # POPRAWKA: Randomizacja tylko gdy włączona explicite
            final_x, final_y = self.apply_mouse_randomization(x, y)
            abs_x, abs_y = self.convert_coordinates(final_x, final_y)

            # POPRAWKA: Używaj win32api konsistentnie
            win32api.SetCursorPos((abs_x, abs_y))

            # Dodaj mikro-opóźnienie dla clicków gdy randomizacja włączona
            click_delay = self.apply_click_timing_randomization()
            if click_delay > 0:
                time.sleep(click_delay)

            # Button mapping
            if button == 'left':
                if state == 'down':
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, abs_x, abs_y, 0, 0)
                else:
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, abs_x, abs_y, 0, 0)
            elif button == 'right':
                if state == 'down':
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, abs_x, abs_y, 0, 0)
                else:
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, abs_x, abs_y, 0, 0)
            elif button == 'middle':
                if state == 'down':
                    win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, abs_x, abs_y, 0, 0)
                else:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, abs_x, abs_y, 0, 0)

            if state == 'down':
                self.stats['mouse_clicks'] += 1

        except Exception as e:
            self.log(f"Error simulating mouse click: {e}")
            self.stats['errors'] += 1

    def execute_action(self, action: Dict[str, Any]):
        """Execute a single action"""
        try:
            action_type = action.get('type')
            data = action.get('data', {})

            if action_type == 'key':
                key_code = data.get('key_code')
                state = data.get('state')
                if key_code and state:
                    self.simulate_key_event(key_code, state)

            elif action_type == 'mouse_move':
                x = data.get('x')
                y = data.get('y')
                if x is not None and y is not None:
                    self.simulate_mouse_move(x, y)

            elif action_type == 'mouse_click':
                x = data.get('x')
                y = data.get('y')
                button = data.get('button')
                state = data.get('state')
                if all(v is not None for v in [x, y, button, state]):
                    self.simulate_mouse_click(x, y, button, state)

            self.stats['actions_executed'] += 1

        except Exception as e:
            self.log(f"Error executing action: {e}")
            self.stats['errors'] += 1

    def playback_loop(self):
        """POPRAWKA: Główna pętla z precyzyjnym timingiem i LOOPING"""
        if not self.actions:
            self.log("No actions to play")
            return

        loop_start_time = time.perf_counter()
        self.current_loop_iteration = 0

        # Main loop - może się powtarzać jeśli loop enabled
        while True:
            self.current_loop_iteration += 1
            self.stats['loop_iteration'] = self.current_loop_iteration

            iteration_text = f"iteration {self.current_loop_iteration}"
            if self.max_loop_iterations > 0:
                iteration_text += f"/{self.max_loop_iterations}"

            self.log(f"Starting playback: {len(self.actions)} actions at {self.playback_speed}x speed ({iteration_text})")
            self.log(f"Randomization: {'enabled' if self.enable_randomization else 'DISABLED'}")

            # POPRAWKA: Użyj perf_counter dla precyzyjnego timingu
            start_time = time.perf_counter()
            last_timestamp = 0

            try:
                # Execute all actions in this iteration
                for i, action in enumerate(self.actions):
                    # Check for stop signal
                    if self.stop_event.is_set():
                        self.log("Playback stopped by user")
                        return

                    # Check for pause
                    while self.pause_event.is_set() and not self.stop_event.is_set():
                        time.sleep(0.01)

                    if self.stop_event.is_set():
                        return

                    # Update current action
                    self.stats['current_action'] = i

                    # POPRAWKA: Precyzyjny timing
                    current_timestamp = action.get('timestamp', 0)
                    if i > 0:  # Skip timing for first action
                        base_time_diff = (current_timestamp - last_timestamp) / self.playback_speed
                        if base_time_diff > 0:
                            # Apply timing randomization only if enabled
                            final_delay = self.apply_timing_randomization(base_time_diff)

                            # POPRAWKA: Używaj perf_counter dla precyzyjnego opóźnienia
                            target_time = time.perf_counter() + final_delay
                            while time.perf_counter() < target_time:
                                if self.stop_event.is_set():
                                    return
                                time.sleep(0.0001)  # Bardzo krótkie sprawdzenia

                    # Execute action
                    self.execute_action(action)
                    last_timestamp = current_timestamp

                    # Update progress callback
                    if self.progress_callback:
                        progress = (i + 1) / len(self.actions) * 100
                        self.progress_callback(progress, self.stats.copy())

                    # Minimal delay to prevent system overload
                    time.sleep(0.0001)

                # Calculate stats for this iteration
                iteration_duration = time.perf_counter() - start_time
                self.stats['playback_duration'] = iteration_duration

                if not self.stop_event.is_set():
                    self.log(f"Iteration {self.current_loop_iteration} completed in {iteration_duration:.3f}s")
                    self.log(f"Actions executed: {self.stats['actions_executed']}, Errors: {self.stats['errors']}")

            except Exception as e:
                self.log(f"Error in playback loop: {e}")
                self.stats['errors'] += 1

            # Check if we should continue looping
            if not self.loop_enabled:
                # Single playback mode
                if not self.stop_event.is_set() and self.completion_callback:
                    self.completion_callback(self.stats.copy())
                break

            # Check max iterations
            if self.max_loop_iterations > 0 and self.current_loop_iteration >= self.max_loop_iterations:
                self.log(f"Completed all {self.max_loop_iterations} iterations")
                if self.completion_callback:
                    self.completion_callback(self.stats.copy())
                break

            # Check for stop before delay
            if self.stop_event.is_set():
                break

            # Random delay between iterations
            delay = random.uniform(self.loop_delay_min, self.loop_delay_max)
            self.log(f"Waiting {delay:.1f}s before next iteration...")

            # Sleep with stop checking
            delay_start = time.perf_counter()
            while time.perf_counter() - delay_start < delay:
                if self.stop_event.is_set():
                    self.log("Loop stopped during delay")
                    return
                time.sleep(0.1)

            # Reset stats for next iteration (keep loop counter)
            loop_iteration = self.stats['loop_iteration']
            self.stats['current_action'] = 0
            self.stats['actions_executed'] = 0
            self.stats['mouse_moves'] = 0
            self.stats['mouse_clicks'] = 0
            self.stats['key_presses'] = 0
            self.stats['loop_iteration'] = loop_iteration

        # Final stats
        self.stats['total_loop_time'] = time.perf_counter() - loop_start_time

        if not self.stop_event.is_set():
            if self.loop_enabled:
                self.log(f"All loops completed! Total time: {self.stats['total_loop_time']:.1f}s")
            else:
                self.log(f"Playback completed successfully in {self.stats['playback_duration']:.3f}s")

        self.playing = False
        self.paused = False

    def start_playback(self) -> bool:
        """Start playback with optional looping"""
        if self.playing:
            self.log("Playback already in progress")
            return False

        if not self.actions:
            self.log("No recording loaded")
            return False

        try:
            # Reset state
            self.stop_event.clear()
            self.pause_event.clear()
            self.current_loop_iteration = 0
            self.stats['current_action'] = 0
            self.stats['actions_executed'] = 0
            self.stats['mouse_moves'] = 0
            self.stats['mouse_clicks'] = 0
            self.stats['key_presses'] = 0
            self.stats['errors'] = 0
            self.stats['loop_iteration'] = 0
            self.stats['total_loop_time'] = 0

            # Start playback thread
            self.playback_thread = threading.Thread(target=self.playback_loop, daemon=True)
            self.playback_thread.start()
            self.playing = True

            loop_info = ""
            if self.loop_enabled:
                if self.max_loop_iterations > 0:
                    loop_info = f" (looping {self.max_loop_iterations} times)"
                else:
                    loop_info = " (looping infinitely)"

            self.log(f"Playback started{loop_info}")
            return True

        except Exception as e:
            self.log(f"Error starting playback: {e}")
            return False

    def stop_playback(self):
        """Stop playback"""
        if not self.playing:
            self.log("No playback in progress")
            return

        self.stop_event.set()
        if self.playback_thread:
            self.playback_thread.join(timeout=2.0)

        self.playing = False
        self.paused = False
        self.log("Playback stopped")

    def pause_playback(self):
        """Pause playback"""
        if not self.playing:
            self.log("No playback in progress")
            return

        if self.paused:
            self.log("Playback already paused")
            return

        self.pause_event.set()
        self.paused = True
        self.log("Playback paused")

    def resume_playback(self):
        """Resume playback"""
        if not self.playing:
            self.log("No playback in progress")
            return

        if not self.paused:
            self.log("Playback not paused")
            return

        self.pause_event.clear()
        self.paused = False
        self.log("Playback resumed")

    def set_playback_speed(self, speed: float):
        """Set playback speed multiplier"""
        if speed <= 0:
            self.log("Invalid playback speed")
            return

        self.playback_speed = speed
        self.log(f"Playback speed set to {speed}x")

    def set_progress_callback(self, callback: Callable[[float, Dict], None]):
        """Set progress update callback"""
        self.progress_callback = callback

    def set_completion_callback(self, callback: Callable[[Dict], None]):
        """Set completion callback"""
        self.completion_callback = callback

    def get_available_recordings(self, directory: str = "runs") -> List[Dict[str, Any]]:
        """Get list of available recordings"""
        recordings = []

        if not os.path.exists(directory):
            return recordings

        try:
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(directory, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        if 'metadata' in data and 'actions' in data:
                            metadata = data['metadata']
                            recordings.append({
                                'filename': filename,
                                'filepath': filepath,
                                'name': metadata.get('run_name', filename),
                                'recorded_at': metadata.get('recorded_at', 'Unknown'),
                                'duration': metadata.get('duration', 0),
                                'total_actions': len(data['actions']),
                                'window_title': metadata.get('window_title', 'Unknown'),
                                'file_size': os.path.getsize(filepath),
                                'precision_version': metadata.get('precision_version', '1.0')
                            })
                    except:
                        # Skip invalid files
                        continue

            # Sort by recorded date (newest first)
            recordings.sort(key=lambda r: r['recorded_at'], reverse=True)

        except Exception as e:
            self.log(f"Error scanning recordings: {e}")

        return recordings

    def get_recording_info(self) -> Optional[Dict[str, Any]]:
        """Get information about currently loaded recording"""
        if not self.metadata or not self.actions:
            return None

        return {
            'metadata': self.metadata.copy(),
            'total_actions': len(self.actions),
            'action_breakdown': self._get_action_breakdown(),
            'estimated_duration': self._get_estimated_duration()
        }

    def _get_action_breakdown(self) -> Dict[str, int]:
        """Get breakdown of action types"""
        breakdown = {'key': 0, 'mouse_move': 0, 'mouse_click': 0, 'other': 0}

        for action in self.actions:
            action_type = action.get('type', 'other')
            if action_type in breakdown:
                breakdown[action_type] += 1
            else:
                breakdown['other'] += 1

        return breakdown

    def _get_estimated_duration(self) -> float:
        """Get estimated playback duration at current speed"""
        if not self.actions:
            return 0

        last_timestamp = self.actions[-1].get('timestamp', 0)
        return last_timestamp / self.playback_speed

    def get_playback_status(self) -> Dict[str, Any]:
        """Get current playback status including loop info"""
        return {
            'playing': self.playing,
            'paused': self.paused,
            'playback_speed': self.playback_speed,
            'use_relative_coords': self.use_relative_coords,
            'target_window': self.target_hwnd,
            'randomization': self.get_randomization_status(),
            'loop': self.get_loop_status(),
            'stats': self.stats.copy(),
            'progress_percent': (self.stats['current_action'] / max(1, self.stats['total_actions'])) * 100
        }


# Test/example usage
if __name__ == "__main__":
    import logging

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    logger = logging.getLogger()

    # Create playback system
    playback = ActionPlayback(logger)

    def progress_callback(progress, stats):
        print(f"Progress: {progress:.1f}% - Actions: {stats['actions_executed']}/{stats['total_actions']}")

    def completion_callback(stats):
        print(f"Playback completed! Duration: {stats['playback_duration']:.3f}s, Errors: {stats['errors']}")

    playback.set_progress_callback(progress_callback)
    playback.set_completion_callback(completion_callback)

    # List available recordings
    recordings = playback.get_available_recordings()
    if recordings:
        print("=== IMPROVED Action Playback System ===")
        print("Available recordings:")
        for i, recording in enumerate(recordings):
            precision = recording.get('precision_version', '1.0')
            print(f"{i+1}. {recording['name']} - {recording['total_actions']} actions, "
                  f"{recording['duration']:.3f}s (v{precision})")

        # Load first recording
        if playback.load_recording(recordings[0]['filepath']):
            print(f"Loaded: {recordings[0]['name']}")

            # POPRAWKA: Upewnij się że randomizacja jest wyłączona
            playback.configure_randomization(enabled=False)
            print("Randomization: DISABLED for 1:1 playback")

            # NOWE: Konfiguruj loop
            playback.configure_loop(enabled=True, delay_min=1, delay_max=5, max_iterations=3)
            print("Loop: ENABLED - 3 iterations with 1-5s random delay")

            # Get recording info
            info = playback.get_recording_info()
            if info:
                breakdown = info['action_breakdown']
                print(f"Actions: {breakdown['key']} keys, {breakdown['mouse_click']} clicks, {breakdown['mouse_move']} moves")

            print("Starting looped playback in 3 seconds...")
            time.sleep(3)

            # Start playback
            playback.start_playback()

            # Monitor playback
            while playback.playing:
                time.sleep(1)
                status = playback.get_playback_status()
                randomization_status = "enabled" if status['randomization']['enabled'] else "disabled"
                loop_info = f"Loop {status['loop']['current_iteration']}/{status['loop']['max_iterations']}" if status['loop']['enabled'] else "Single run"
                print(f"Playing: {status['progress_percent']:.1f}% (randomization: {randomization_status}, {loop_info})")

    else:
        print("No recordings found in 'runs' directory")