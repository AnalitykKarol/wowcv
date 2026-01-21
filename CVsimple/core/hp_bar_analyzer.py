"""
Enhanced Player Bars Analyzer - Simplified HP and Mana Analysis + Color Triggers
Analyzes green (HP), blue (Mana) bars, and custom color triggers with manual positioning
UPDATED: Added Color Trigger System for automatic key pressing
"""
import cv2
import numpy as np
import time
import win32api
import win32con
from typing import List, Dict, Optional, Tuple, Any, Callable

# GPU acceleration imports
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# === COLOR TRIGGER CONFIGURATION ===
TRIGGER_POINTS = [
    {
        "x": 1033,
        "y": 870,
        "color": (np.int64(104), np.int64(103), np.int64(119)),
        "key": 0x39,  # Klawisz '9' - zmień jeśli potrzebujesz
        "tolerance": 15,
        "name": "trigger_1",
        "enabled": True
    },
]

# Ustawienia Color Triggers
COLOR_TRIGGER_REGION_SIZE = 3  # Rozmiar regionu do sprawdzania (5x5 pikseli)
COLOR_TRIGGER_COOLDOWN = 1.0   # Cooldown między triggerami tego samego typu (sekundy)


class PlayerBarsAnalyzer:
    def __init__(self, logger=None):
        self.logger = logger

        # === HP SYSTEM (GREEN) ===
        self.hp_enabled = False
        self.hp_position = {'x': 0, 'y': 0, 'width': 0, 'height': 0}
        self.hp_critical_threshold = 25.0
        self.hp_change_callbacks: List[Callable[[str, float], None]] = []
        self.last_hp_critical_warning = 0
        self.hp_critical_warning_cooldown = 2.0

        # HP thresholds with hysteresis
        self.hp_warning_threshold = 50.0
        self.hp_warning_recovery_threshold = 80.0
        self.hp_critical_threshold = 25.0  # FIXED: Critical at 25% HP (not 80%!)
        self.hp_critical_recovery_threshold = 85.0  # Recovery when back to 85% HP

        # HP threshold state tracking
        self.hp_above_50 = True
        self.hp_above_25 = True

        # Green HSV thresholds for HP
        self.green_hsv_lower = np.array([50, 100, 100])
        self.green_hsv_upper = np.array([80, 255, 255])

        # HP Statistics
        self.hp_stats = {
            'total_analyses': 0,
            'successful_detections': 0,
            'avg_analysis_time_ms': 0.0,
            'last_hp_value': 0.0,
            'critical_warnings': 0
        }
        self.hp_analysis_times = []

        # === MANA SYSTEM (BLUE) ===
        self.mana_enabled = False
        self.mana_position = {'x': 0, 'y': 0, 'width': 0, 'height': 0}
        self.mana_critical_threshold = 15.0
        self.mana_change_callbacks: List[Callable[[str, float], None]] = []
        self.last_mana_critical_warning = 0
        self.mana_critical_warning_cooldown = 2.0

        # Mana thresholds with hysteresis
        self.mana_critical_threshold = 10.0
        self.mana_recovery_threshold = 100.0

        # Mana threshold state tracking
        self.mana_above_10 = True

        # Blue HSV thresholds for Mana
        self.blue_hsv_lower = np.array([100, 80, 80])
        self.blue_hsv_upper = np.array([130, 255, 255])

        # Mana Statistics
        self.mana_stats = {
            'total_analyses': 0,
            'successful_detections': 0,
            'avg_analysis_time_ms': 0.0,
            'last_mana_value': 0.0,
            'critical_warnings': 0
        }
        self.mana_analysis_times = []

        # === NEW: COLOR TRIGGER SYSTEM ===
        self.color_triggers_enabled = False
        self.trigger_points = []
        self.color_trigger_callbacks: List[Callable[[str, Dict], None]] = []
        self.last_trigger_times = {}  # Cooldown tracking per trigger

        # Color Trigger Statistics
        self.color_trigger_stats = {
            'total_checks': 0,
            'successful_triggers': 0,
            'total_trigger_activations': 0,
            'triggers_by_name': {}
        }

        # Load default trigger points
        self.load_trigger_points(TRIGGER_POINTS)

        # === GENERAL SETTINGS ===
        self.max_time_samples = 30
        self.min_percentage_threshold = 5.0  # Minimum % to consider valid

    def log(self, message: str, level: str = "info"):
        """Helper for logging"""
        if self.logger:
            if level == "debug":
                self.logger.debug(message)
            elif level == "warning":
                self.logger.warning(message)
            elif level == "error":
                self.logger.error(message)
            else:
                self.logger.info(message)
        else:
            print(f"[{level.upper()}] BARS_ANALYZER: {message}")

    # === HP SYSTEM CONFIGURATION (unchanged) ===
    def enable_hp_analysis(self, enabled: bool = True):
        """Enable or disable HP analysis"""
        self.hp_enabled = enabled
        self.log(f"💚 HP Analysis: {'ENABLED' if enabled else 'DISABLED'}")

    def set_hp_position_px(self, x: int, y: int, width: int, height: int):
        """Set HP bar position in pixels"""
        self.hp_position = {'x': x, 'y': y, 'width': width, 'height': height}
        self.log(f"💚 HP Position: ({x}, {y}) {width}x{height}px")

    def set_hp_thresholds(self, warning: float = 50.0, warning_recovery: float = 80.0,
                         critical: float = 25.0, critical_recovery: float = 80.0):
        """Set HP thresholds with hysteresis"""
        self.hp_warning_threshold = warning
        self.hp_warning_recovery_threshold = warning_recovery
        self.hp_critical_threshold = critical
        self.hp_critical_recovery_threshold = critical_recovery
        self.log(f"💚 HP Thresholds: Warning {warning}%→{warning_recovery}%, Critical {critical}%→{critical_recovery}%")

    def add_hp_change_callback(self, callback: Callable[[str, float], None]):
        """Add callback for HP threshold changes"""
        self.hp_change_callbacks.append(callback)
        self.log(f"💚 HP Callback added (total: {len(self.hp_change_callbacks)})")

    def configure_hp_hsv(self, lower_hsv: List[int], upper_hsv: List[int]):
        """Configure HP green HSV thresholds"""
        self.green_hsv_lower = np.array(lower_hsv)
        self.green_hsv_upper = np.array(upper_hsv)
        self.log(f"💚 HP HSV: {lower_hsv} - {upper_hsv}")

    # === MANA SYSTEM CONFIGURATION (unchanged) ===
    def enable_mana_analysis(self, enabled: bool = True):
        """Enable or disable Mana analysis"""
        self.mana_enabled = enabled
        self.log(f"💙 Mana Analysis: {'ENABLED' if enabled else 'DISABLED'}")

    def set_mana_position_px(self, x: int, y: int, width: int, height: int):
        """Set Mana bar position in pixels"""
        self.mana_position = {'x': x, 'y': y, 'width': width, 'height': height}
        self.log(f"💙 Mana Position: ({x}, {y}) {width}x{height}px")

    # NOWE: Funkcje dla względnych współrzędnych
    def set_hp_position_relative(self, x_percent: float, y_percent: float, w_percent: float, h_percent: float):
        """Set HP bar position using relative coordinates (percentage of screen)"""
        self.hp_position = {'x': x_percent, 'y': y_percent, 'width': w_percent, 'height': h_percent, 'relative': True}
        self.log(f"💚 HP Relative Position: ({x_percent:.1f}%, {y_percent:.1f}%) {w_percent:.1f}%x{h_percent:.1f}%")

    def set_mana_position_relative(self, x_percent: float, y_percent: float, w_percent: float, h_percent: float):
        """Set Mana bar position using relative coordinates (percentage of screen)"""
        self.mana_position = {'x': x_percent, 'y': y_percent, 'width': w_percent, 'height': h_percent, 'relative': True}
        self.log(f"💙 Mana Relative Position: ({x_percent:.1f}%, {y_percent:.1f}%) {w_percent:.1f}%x{h_percent:.1f}%")

    def get_hp_absolute_position(self, screen_width: int, screen_height: int) -> dict:
        """Convert relative HP coordinates to absolute pixels"""
        if self.hp_position.get('relative', False):
            x = int(screen_width * self.hp_position['x'] / 100.0)
            y = int(screen_height * self.hp_position['y'] / 100.0)
            w = int(screen_width * self.hp_position['width'] / 100.0)
            h = int(screen_height * self.hp_position['height'] / 100.0)
            return {'x': x, 'y': y, 'width': w, 'height': h}
        else:
            return self.hp_position.copy()

    def get_mana_absolute_position(self, screen_width: int, screen_height: int) -> dict:
        """Convert relative Mana coordinates to absolute pixels"""
        if self.mana_position.get('relative', False):
            x = int(screen_width * self.mana_position['x'] / 100.0)
            y = int(screen_height * self.mana_position['y'] / 100.0)
            w = int(screen_width * self.mana_position['width'] / 100.0)
            h = int(screen_height * self.mana_position['height'] / 100.0)
            return {'x': x, 'y': y, 'width': w, 'height': h}
        else:
            return self.mana_position.copy()

    def load_preset_config(self, preset_data: dict):
        """Load preset configuration from preset data"""
        try:
            # Load HP configuration if available
            if 'relative_coords' in preset_data and 'hp' in preset_data['relative_coords']:
                hp_coords = preset_data['relative_coords']['hp']
                self.set_hp_position_relative(hp_coords['x'], hp_coords['y'], hp_coords['w'], hp_coords['h'])
                self.log(f"✅ Loaded HP preset: {preset_data.get('name', 'Unknown')}")

            # Load Mana configuration if available
            if 'relative_coords' in preset_data and 'mana' in preset_data['relative_coords']:
                mana_coords = preset_data['relative_coords']['mana']
                self.set_mana_position_relative(mana_coords['x'], mana_coords['y'], mana_coords['w'], mana_coords['h'])
                self.log(f"✅ Loaded Mana preset: {preset_data.get('name', 'Unknown')}")

            # Fallback to legacy absolute coordinates if available
            elif 'legacy_absolute' in preset_data:
                legacy = preset_data['legacy_absolute']
                if 'hp' in legacy:
                    hp_pos = legacy['hp']
                    self.set_hp_position_px(hp_pos['x'], hp_pos['y'], hp_pos['w'], hp_pos['h'])
                if 'mana' in legacy:
                    mana_pos = legacy['mana']
                    self.set_mana_position_px(mana_pos['x'], mana_pos['y'], mana_pos['w'], mana_pos['h'])
                self.log(f"⚠️ Loaded legacy preset: {preset_data.get('name', 'Unknown')}")

            # Load color configuration if available
            if 'colors' in preset_data:
                colors = preset_data['colors']
                if 'hp' in colors:
                    hp_colors = colors['hp']
                    self.configure_hp_hsv([hp_colors.get('h_min', 50), hp_colors.get('h_max', 80)],
                                      [hp_colors.get('s_min', 100), 255], [hp_colors.get('v_min', 100), 255])
                if 'mana' in colors:
                    mana_colors = colors['mana']
                    # Update mana color thresholds (similar to HP method)
                    self.log(f"✅ Loaded color configuration from preset")

        except Exception as e:
            self.log(f"❌ Error loading preset configuration: {str(e)}")

    def set_mana_critical_threshold(self, threshold: float):
        """Set Mana critical threshold percentage"""
        self.mana_critical_threshold = threshold
        self.log(f"💙 Mana Critical threshold: {threshold}%")

    def add_mana_change_callback(self, callback: Callable[[str, float], None]):
        """Add callback for Mana threshold changes"""
        self.mana_change_callbacks.append(callback)
        self.log(f"💙 Mana Callback added (total: {len(self.mana_change_callbacks)})")

    def configure_mana_hsv(self, lower_hsv: List[int], upper_hsv: List[int]):
        """Configure Mana blue HSV thresholds"""
        self.blue_hsv_lower = np.array(lower_hsv)
        self.blue_hsv_upper = np.array(upper_hsv)
        self.log(f"💙 Mana HSV: {lower_hsv} - {upper_hsv}")

    def set_mana_thresholds(self, critical: float = 10.0, recovery: float = 100.0):
        """Set Mana thresholds with hysteresis"""
        self.mana_critical_threshold = critical
        self.mana_recovery_threshold = recovery
        self.log(f"💙 Mana Thresholds: Critical {critical}%→{recovery}%")

    # === NEW: COLOR TRIGGER SYSTEM ===
    def enable_color_triggers(self, enabled: bool = True):
        """Enable or disable Color Trigger analysis"""
        self.color_triggers_enabled = enabled
        self.log(f"🎯 Color Triggers: {'ENABLED' if enabled else 'DISABLED'}")

    def load_trigger_points(self, trigger_points: List[Dict]):
        """Load trigger points configuration"""
        self.trigger_points = []
        self.last_trigger_times = {}

        for trigger_config in trigger_points:
            # Convert numpy types to regular Python types
            trigger = {
                'x': int(trigger_config['x']),
                'y': int(trigger_config['y']),
                'color': tuple(int(c) for c in trigger_config['color']),  # Convert np.int64 to int
                'key': int(trigger_config['key']),
                'tolerance': float(trigger_config['tolerance']),
                'name': str(trigger_config['name']),
                'enabled': bool(trigger_config['enabled']),
                'region_size': trigger_config.get('region_size', COLOR_TRIGGER_REGION_SIZE),
                'cooldown': trigger_config.get('cooldown', COLOR_TRIGGER_COOLDOWN)
            }

            self.trigger_points.append(trigger)
            self.last_trigger_times[trigger['name']] = 0

            # Initialize stats for this trigger
            self.color_trigger_stats['triggers_by_name'][trigger['name']] = {
                'checks': 0,
                'activations': 0,
                'last_activation': 0
            }

        enabled_count = len([t for t in self.trigger_points if t['enabled']])
        self.log(f"🎯 Loaded {len(self.trigger_points)} color triggers ({enabled_count} enabled)")

        # Debug log trigger details
        for trigger in self.trigger_points:
            if trigger['enabled']:
                self.log(f"  🎯 {trigger['name']}: ({trigger['x']}, {trigger['y']}) → {trigger['color']} → Key {self._vk_to_key_name(trigger['key'])}")

    def add_color_trigger_callback(self, callback: Callable[[str, Dict], None]):
        """Add callback for color trigger activations"""
        self.color_trigger_callbacks.append(callback)
        self.log(f"🎯 Color Trigger Callback added (total: {len(self.color_trigger_callbacks)})")

    def analyze_color_triggers(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze all color triggers"""
        if not self.color_triggers_enabled or not self.trigger_points:
            return {'triggers_checked': 0, 'triggers_activated': 0}

        current_time = time.time()
        self.color_trigger_stats['total_checks'] += 1

        triggers_checked = 0
        triggers_activated = 0

        for trigger in self.trigger_points:
            if not trigger['enabled']:
                continue

            triggers_checked += 1
            trigger_name = trigger['name']

            # Update per-trigger stats
            self.color_trigger_stats['triggers_by_name'][trigger_name]['checks'] += 1

            # Check cooldown
            if current_time - self.last_trigger_times[trigger_name] < trigger['cooldown']:
                continue

            # Check if color matches at position
            if self._check_color_trigger_match(image, trigger):
                # Activate trigger
                if self._activate_color_trigger(trigger):
                    triggers_activated += 1
                    self.last_trigger_times[trigger_name] = current_time

                    # Update stats
                    self.color_trigger_stats['successful_triggers'] += 1
                    self.color_trigger_stats['total_trigger_activations'] += 1
                    self.color_trigger_stats['triggers_by_name'][trigger_name]['activations'] += 1
                    self.color_trigger_stats['triggers_by_name'][trigger_name]['last_activation'] = current_time

                    self.log(f"🎯 TRIGGERED: {trigger_name} at ({trigger['x']}, {trigger['y']}) → Key {self._vk_to_key_name(trigger['key'])}")

                    # Call callbacks
                    self._call_color_trigger_callbacks(trigger_name, trigger)

        return {
            'triggers_checked': triggers_checked,
            'triggers_activated': triggers_activated,
            'total_enabled': len([t for t in self.trigger_points if t['enabled']])
        }

    def _check_color_trigger_match(self, image: np.ndarray, trigger: Dict) -> bool:
        """Check if color at trigger position matches target"""
        try:
            img_height, img_width = image.shape[:2]
            x, y = trigger['x'], trigger['y']
            region_size = trigger['region_size']
            half_size = region_size // 2

            # Check if position is within image bounds
            if x < 0 or y < 0 or x >= img_width or y >= img_height:
                return False

            # Calculate region bounds
            x1 = max(0, x - half_size)
            y1 = max(0, y - half_size)
            x2 = min(img_width, x + half_size + 1)
            y2 = min(img_height, y + half_size + 1)

            # Extract region
            region = image[y1:y2, x1:x2]

            if region.size == 0:
                return False

            # Calculate average color of region
            avg_color_rgb = np.mean(region, axis=(0, 1)).astype(int)
            target_rgb = np.array(trigger['color'])

            # Check color difference using RGB distance
            color_diff = np.sqrt(np.sum((avg_color_rgb - target_rgb) ** 2))
            tolerance = trigger['tolerance']

            # Scale tolerance for RGB space (max distance is ~441 for RGB)
            max_distance = tolerance * 441 / 100  # Convert percentage to actual distance

            return color_diff <= max_distance

        except Exception as e:
            self.log(f"❌ Error checking color trigger {trigger['name']}: {str(e)}", "error")
            return False

    def _activate_color_trigger(self, trigger: Dict) -> bool:
        """Use PostMessage like combat controller"""
        try:
            key_code = trigger['key']

            if hasattr(self, '_current_hwnd') and self._current_hwnd:
                # PostMessage - identyczna metoda jak w combat_controller
                success1 = win32api.PostMessage(self._current_hwnd, win32con.WM_KEYDOWN, key_code, 0)
                time.sleep(0.05)
                success2 = win32api.PostMessage(self._current_hwnd, win32con.WM_KEYUP, key_code, 0)

                if success1 and success2:
                    self.log(f"🎯 ✅ PostMessage key: {self._vk_to_key_name(key_code)}")
                    return True

            return False
        except Exception as e:
            self.log(f"❌ Error: {str(e)}", "error")
            return False

    def _call_color_trigger_callbacks(self, trigger_name: str, trigger: Dict):
        """Call all color trigger callbacks"""
        for callback in self.color_trigger_callbacks:
            try:
                callback(trigger_name, trigger)
            except Exception as e:
                self.log(f"❌ Color trigger callback error: {str(e)}", "error")

    def _vk_to_key_name(self, vk_code: int) -> str:
        """Convert VK code to key name"""
        key_names = {
            0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4', 0x35: '5',
            0x36: '6', 0x37: '7', 0x38: '8', 0x39: '9', 0x30: '0',
            0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
            0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
            0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O',
            0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
            0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
            0x5A: 'Z', 0x20: 'SPACE', 0x0D: 'ENTER', 0x1B: 'ESC'
        }
        return key_names.get(vk_code, f'VK_{vk_code:02X}')

    # === CORE ANALYSIS FUNCTIONS (unchanged) ===
    def extract_color_percentage(self, image_crop: np.ndarray, lower_hsv: np.ndarray, upper_hsv: np.ndarray) -> Dict[str, float]:
        """Extract color percentage from image crop - REVERTED to working CPU version"""
        try:
            if image_crop is None or image_crop.size == 0:
                return {'colored_pixels': 0, 'total_pixels': 0, 'percentage': 0.0}

            # Keep it simple and working on CPU
            # Convert to HSV
            hsv = cv2.cvtColor(image_crop, cv2.COLOR_RGB2HSV)
            total_pixels = hsv.shape[0] * hsv.shape[1]

            # Create mask for target color
            color_mask = cv2.inRange(hsv, lower_hsv, upper_hsv)

            # Count colored pixels
            colored_pixels = np.count_nonzero(color_mask)
            percentage = (colored_pixels / total_pixels) * 100

            return {
                'colored_pixels': colored_pixels,
                'total_pixels': total_pixels,
                'percentage': round(percentage, 2)
            }

        except Exception as e:
            self.log(f"❌ Color extraction error: {str(e)}", "error")
            return {'colored_pixels': 0, 'total_pixels': 0, 'percentage': 0.0}

    def calculate_bar_percentage(self, color_data: Dict[str, float]) -> float:
        """Calculate bar percentage from color coverage"""
        percentage = color_data['percentage']

        if percentage < self.min_percentage_threshold:
            return 0.0

        # For horizontal bars, color percentage roughly equals bar percentage
        return min(100.0, percentage)

    # === HP ANALYSIS (unchanged) ===
    def analyze_hp(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze HP bar from image"""
        if not self.hp_enabled:
            return {'success': False, 'reason': 'HP analysis disabled', 'hp_percentage': 0.0}

        start_time = time.time()

        try:
            self.hp_stats['total_analyses'] += 1

            # Get HP region
            x = self.hp_position['x']
            y = self.hp_position['y']
            width = self.hp_position['width']
            height = self.hp_position['height']

            if width <= 0 or height <= 0:
                return {'success': False, 'reason': 'Invalid HP position', 'hp_percentage': 0.0}

            # Validate bounds
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(image.shape[1], x + width), min(image.shape[0], y + height)

            if x2 <= x1 or y2 <= y1:
                return {'success': False, 'reason': 'HP region out of bounds', 'hp_percentage': 0.0}

            # Extract HP crop
            hp_crop = image[y1:y2, x1:x2]

            if hp_crop.size == 0:
                return {'success': False, 'reason': 'Empty HP crop', 'hp_percentage': 0.0}

            # Analyze green color
            green_data = self.extract_color_percentage(hp_crop, self.green_hsv_lower, self.green_hsv_upper)
            hp_percentage = self.calculate_bar_percentage(green_data)

            # Check if valid HP detected
            if hp_percentage < self.min_percentage_threshold:
                return {'success': False, 'reason': 'HP percentage too low', 'hp_percentage': 0.0}

            # Update statistics
            analysis_time = (time.time() - start_time) * 1000
            self.hp_analysis_times.append(analysis_time)
            if len(self.hp_analysis_times) > self.max_time_samples:
                self.hp_analysis_times.pop(0)

            avg_time = sum(self.hp_analysis_times) / len(self.hp_analysis_times)
            self.hp_stats['avg_analysis_time_ms'] = avg_time
            self.hp_stats['successful_detections'] += 1
            self.hp_stats['last_hp_value'] = hp_percentage

            # Check critical HP
            is_critical = self._check_hp_critical(hp_percentage)

            # Trigger callbacks
            self._trigger_hp_callbacks(hp_percentage)

            result = {
                'success': True,
                'hp_percentage': round(hp_percentage, 1),
                'critical': is_critical,
                'green_data': green_data,
                'region': (x1, y1, x2, y2),
                'analysis_time_ms': round(analysis_time, 2)
            }

            return result

        except Exception as e:
            self.log(f"❌ HP analysis error: {str(e)}", "error")
            return {'success': False, 'reason': f'Exception: {str(e)}', 'hp_percentage': 0.0}

    def _check_hp_critical(self, hp_percentage: float) -> bool:
        """Check if HP is critical and send warnings"""
        current_time = time.time()
        is_critical = hp_percentage <= self.hp_critical_threshold

        if (is_critical and
            current_time - self.last_hp_critical_warning > self.hp_critical_warning_cooldown):
            self.log(f"🚨 CRITICAL HP: {hp_percentage:.1f}%", "warning")
            self.last_hp_critical_warning = current_time
            self.hp_stats['critical_warnings'] += 1

        return is_critical

    def _trigger_hp_callbacks(self, hp_percentage: float):
        """Trigger HP callbacks only when thresholds are crossed with hysteresis"""
        # Check 50% warning threshold
        if self.hp_above_50 and hp_percentage < self.hp_warning_threshold:
            self.hp_above_50 = False
            self._call_hp_callbacks("hp_warning", hp_percentage)
            self.log(f"⚠️ HP Warning triggered: {hp_percentage:.1f}% (threshold: {self.hp_warning_threshold}%)")
        elif not self.hp_above_50 and hp_percentage >= self.hp_warning_recovery_threshold:
            self.hp_above_50 = True
            self._call_hp_callbacks("hp_warning_recovered", hp_percentage)
            self.log(f"✅ HP Warning recovered: {hp_percentage:.1f}% (recovery: {self.hp_warning_recovery_threshold}%)")

        # Check 25% critical threshold
        if self.hp_above_25 and hp_percentage < self.hp_critical_threshold:
            self.hp_above_25 = False
            self._call_hp_callbacks("hp_critical", hp_percentage)
            self.log(f"🚨 HP Critical triggered: {hp_percentage:.1f}% (threshold: {self.hp_critical_threshold}%)")
        elif not self.hp_above_25 and hp_percentage >= self.hp_critical_recovery_threshold:
            self.hp_above_25 = True
            self._call_hp_callbacks("hp_critical_recovered", hp_percentage)
            self.log(f"✅ HP Critical recovered: {hp_percentage:.1f}% (recovery: {self.hp_critical_recovery_threshold}%)")

    def _call_hp_callbacks(self, event_type: str, hp_percentage: float):
        """Helper to call all HP callbacks with event type"""
        for callback in self.hp_change_callbacks:
            try:
                callback(event_type, hp_percentage)
            except Exception as e:
                self.log(f"❌ HP callback error: {str(e)}", "error")

    # === MANA ANALYSIS (unchanged) ===
    def analyze_mana(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze Mana bar from image"""
        if not self.mana_enabled:
            return {'success': False, 'reason': 'Mana analysis disabled', 'mana_percentage': 0.0}

        start_time = time.time()

        try:
            self.mana_stats['total_analyses'] += 1

            # Get Mana region
            x = self.mana_position['x']
            y = self.mana_position['y']
            width = self.mana_position['width']
            height = self.mana_position['height']

            if width <= 0 or height <= 0:
                return {'success': False, 'reason': 'Invalid Mana position', 'mana_percentage': 0.0}

            # Validate bounds
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(image.shape[1], x + width), min(image.shape[0], y + height)

            if x2 <= x1 or y2 <= y1:
                return {'success': False, 'reason': 'Mana region out of bounds', 'mana_percentage': 0.0}

            # Extract Mana crop
            mana_crop = image[y1:y2, x1:x2]

            if mana_crop.size == 0:
                return {'success': False, 'reason': 'Empty Mana crop', 'mana_percentage': 0.0}

            # Analyze blue color
            blue_data = self.extract_color_percentage(mana_crop, self.blue_hsv_lower, self.blue_hsv_upper)
            mana_percentage = self.calculate_bar_percentage(blue_data)

            # Check if valid Mana detected
            if mana_percentage < self.min_percentage_threshold:
                return {'success': False, 'reason': 'Mana percentage too low', 'mana_percentage': 0.0}

            # Update statistics
            analysis_time = (time.time() - start_time) * 1000
            self.mana_analysis_times.append(analysis_time)
            if len(self.mana_analysis_times) > self.max_time_samples:
                self.mana_analysis_times.pop(0)

            avg_time = sum(self.mana_analysis_times) / len(self.mana_analysis_times)
            self.mana_stats['avg_analysis_time_ms'] = avg_time
            self.mana_stats['successful_detections'] += 1
            self.mana_stats['last_mana_value'] = mana_percentage

            # Check critical Mana
            is_critical = self._check_mana_critical(mana_percentage)

            # Trigger callbacks
            self._trigger_mana_callbacks(mana_percentage)

            result = {
                'success': True,
                'mana_percentage': round(mana_percentage, 1),
                'critical': is_critical,
                'blue_data': blue_data,
                'region': (x1, y1, x2, y2),
                'analysis_time_ms': round(analysis_time, 2)
            }

            return result

        except Exception as e:
            self.log(f"❌ Mana analysis error: {str(e)}", "error")
            return {'success': False, 'reason': f'Exception: {str(e)}', 'mana_percentage': 0.0}

    def _check_mana_critical(self, mana_percentage: float) -> bool:
        """Check if Mana is critical and send warnings"""
        current_time = time.time()
        is_critical = mana_percentage <= self.mana_critical_threshold

        if (is_critical and
            current_time - self.last_mana_critical_warning > self.mana_critical_warning_cooldown):
            self.log(f"🚨 CRITICAL MANA: {mana_percentage:.1f}%", "warning")
            self.last_mana_critical_warning = current_time
            self.mana_stats['critical_warnings'] += 1

        return is_critical

    def _trigger_mana_callbacks(self, mana_percentage: float):
        """Trigger Mana callbacks only when threshold is crossed with hysteresis"""
        # Check 10% threshold with 100% recovery
        if self.mana_above_10 and mana_percentage < self.mana_critical_threshold:
            self.mana_above_10 = False
            self._call_mana_callbacks("mana_critical", mana_percentage)
            self.log(f"🚨 Mana Critical triggered: {mana_percentage:.1f}% (threshold: {self.mana_critical_threshold}%)")
        elif not self.mana_above_10 and mana_percentage >= self.mana_recovery_threshold:
            self.mana_above_10 = True
            self._call_mana_callbacks("mana_recovered", mana_percentage)
            self.log(f"✅ Mana recovered: {mana_percentage:.1f}% (recovery: {self.mana_recovery_threshold}%)")

    def _call_mana_callbacks(self, event_type: str, mana_percentage: float):
        """Helper to call all Mana callbacks with event type"""
        for callback in self.mana_change_callbacks:
            try:
                callback(event_type, mana_percentage)
            except Exception as e:
                self.log(f"❌ Mana callback error: {str(e)}", "error")

    # === COMBINED ANALYSIS - UPDATED WITH COLOR TRIGGERS ===
    def analyze_both(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze HP, Mana, and Color Triggers"""
        hp_result = self.analyze_hp(image) if self.hp_enabled else {'success': False, 'hp_percentage': 0.0}
        mana_result = self.analyze_mana(image) if self.mana_enabled else {'success': False, 'mana_percentage': 0.0}

        # NEW: Add color trigger analysis
        color_trigger_result = self.analyze_color_triggers(image) if self.color_triggers_enabled else {'triggers_checked': 0, 'triggers_activated': 0}

        return {
            'hp_result': hp_result,
            'mana_result': mana_result,
            'color_trigger_result': color_trigger_result,  # NEW
            'both_successful': hp_result.get('success', False) and mana_result.get('success', False),
            'hp_percentage': hp_result.get('hp_percentage', 0.0),
            'mana_percentage': mana_result.get('mana_percentage', 0.0),
            'hp_critical': hp_result.get('critical', False),
            'mana_critical': mana_result.get('critical', False),
            'triggers_activated': color_trigger_result.get('triggers_activated', 0)  # NEW
        }

    # === QUICK ACCESS METHODS ===
    def get_hp_percentage(self, image: np.ndarray) -> float:
        """Quick HP check - returns only percentage"""
        if not self.hp_enabled:
            return 0.0
        result = self.analyze_hp(image)
        return result.get('hp_percentage', 0.0)

    def get_mana_percentage(self, image: np.ndarray) -> float:
        """Quick Mana check - returns only percentage"""
        if not self.mana_enabled:
            return 0.0
        result = self.analyze_mana(image)
        return result.get('mana_percentage', 0.0)

    def is_hp_critical(self, image: np.ndarray) -> bool:
        """Check if HP is critical"""
        hp = self.get_hp_percentage(image)
        return hp > 0 and hp <= self.hp_critical_threshold

    def is_mana_critical(self, image: np.ndarray) -> bool:
        """Check if Mana is critical"""
        mana = self.get_mana_percentage(image)
        return mana > 0 and mana <= self.mana_critical_threshold

    def get_player_stats(self, image: np.ndarray) -> Dict[str, float]:
        """Get both HP and Mana percentages"""
        return {
            'hp': self.get_hp_percentage(image),
            'mana': self.get_mana_percentage(image)
        }

    # === STATISTICS AND DIAGNOSTICS - UPDATED WITH COLOR TRIGGERS ===
    def get_hp_stats(self) -> Dict[str, Any]:
        """Get HP statistics"""
        return self.hp_stats.copy()

    def get_mana_stats(self) -> Dict[str, Any]:
        """Get Mana statistics"""
        return self.mana_stats.copy()

    def get_color_trigger_stats(self) -> Dict[str, Any]:
        """Get Color Trigger statistics"""
        return self.color_trigger_stats.copy()

    def get_combined_stats(self) -> Dict[str, Any]:
        """Get combined statistics"""
        return {
            'hp_stats': self.get_hp_stats(),
            'mana_stats': self.get_mana_stats(),
            'color_trigger_stats': self.get_color_trigger_stats(),  # NEW
            'hp_enabled': self.hp_enabled,
            'mana_enabled': self.mana_enabled,
            'color_triggers_enabled': self.color_triggers_enabled,  # NEW
            'hp_position': self.hp_position.copy(),
            'mana_position': self.mana_position.copy(),
            'trigger_points': self.trigger_points.copy(),  # NEW
            'hp_critical_threshold': self.hp_critical_threshold,
            'mana_critical_threshold': self.mana_critical_threshold,
            'hp_warning_threshold': self.hp_warning_threshold,
            'hp_warning_recovery_threshold': self.hp_warning_recovery_threshold,
            'hp_critical_recovery_threshold': self.hp_critical_recovery_threshold,
            'mana_recovery_threshold': self.mana_recovery_threshold
        }

    def reset_stats(self):
        """Reset all statistics"""
        self.hp_stats = {
            'total_analyses': 0,
            'successful_detections': 0,
            'avg_analysis_time_ms': 0.0,
            'last_hp_value': 0.0,
            'critical_warnings': 0
        }
        self.mana_stats = {
            'total_analyses': 0,
            'successful_detections': 0,
            'avg_analysis_time_ms': 0.0,
            'last_mana_value': 0.0,
            'critical_warnings': 0
        }
        # NEW: Reset color trigger stats
        self.color_trigger_stats = {
            'total_checks': 0,
            'successful_triggers': 0,
            'total_trigger_activations': 0,
            'triggers_by_name': {}
        }
        # Reinitialize per-trigger stats
        for trigger in self.trigger_points:
            self.color_trigger_stats['triggers_by_name'][trigger['name']] = {
                'checks': 0,
                'activations': 0,
                'last_activation': 0
            }

        self.hp_analysis_times.clear()
        self.mana_analysis_times.clear()
        self.log("📊 All statistics reset")

    # === COMBAT CONTROLLER INTEGRATION ===
    def integrate_with_combat_controller(self, combat_controller):
        """Integrate with ReactiveCombatController"""
        def hp_callback(event_type: str, hp_percentage: float):
            """HP threshold callback for combat controller"""
            try:
                if hasattr(combat_controller, 'handle_hp_event'):
                    combat_controller.handle_hp_event(event_type, hp_percentage)
                else:
                    combat_controller.player_hp = hp_percentage
                    combat_controller.player_hp_event = event_type
            except Exception as e:
                self.log(f"❌ HP integration error: {str(e)}", "error")

        def mana_callback(event_type: str, mana_percentage: float):
            """Mana threshold callback for combat controller"""
            try:
                if hasattr(combat_controller, 'handle_mana_event'):
                    combat_controller.handle_mana_event(event_type, mana_percentage)
                else:
                    combat_controller.player_mana = mana_percentage
                    combat_controller.player_mana_event = event_type
            except Exception as e:
                self.log(f"❌ Mana integration error: {str(e)}", "error")

        def color_trigger_callback(trigger_name: str, trigger: Dict):
            """Color trigger callback for combat controller"""
            try:
                # Just log for now - the key press is already handled
                self.log(f"🎯 Color trigger '{trigger_name}' activated in combat controller integration")
            except Exception as e:
                self.log(f"❌ Color trigger integration error: {str(e)}", "error")

        self.add_hp_change_callback(hp_callback)
        self.add_mana_change_callback(mana_callback)
        self.add_color_trigger_callback(color_trigger_callback)  # NEW
        self.log("🔗 Integrated with Combat Controller (HP, Mana, Color Triggers)")

    # === DEBUG AND VISUALIZATION ===
    def create_debug_image(self, image: np.ndarray) -> np.ndarray:
        """Create debug image with HP, Mana regions, and Color Trigger points"""
        debug_image = image.copy()

        try:
            # Draw HP region
            if self.hp_enabled:
                x, y = self.hp_position['x'], self.hp_position['y']
                w, h = self.hp_position['width'], self.hp_position['height']
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(debug_image, "HP", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Draw Mana region
            if self.mana_enabled:
                x, y = self.mana_position['x'], self.mana_position['y']
                w, h = self.mana_position['width'], self.mana_position['height']
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), (255, 0, 0), 2)
                cv2.putText(debug_image, "MANA", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

            # NEW: Draw Color Trigger points
            if self.color_triggers_enabled:
                for i, trigger in enumerate(self.trigger_points):
                    if trigger['enabled']:
                        x, y = trigger['x'], trigger['y']
                        region_size = trigger['region_size']
                        half_size = region_size // 2

                        # Draw trigger region
                        cv2.rectangle(debug_image,
                                    (x - half_size, y - half_size),
                                    (x + half_size, y + half_size),
                                    (255, 255, 0), 2)  # Yellow

                        # Draw center point
                        cv2.circle(debug_image, (x, y), 3, (255, 255, 0), -1)

                        # Draw trigger name
                        cv2.putText(debug_image, trigger['name'],
                                  (x + 10, y - 10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

            return debug_image

        except Exception as e:
            self.log(f"❌ Debug image error: {str(e)}", "error")
            return debug_image

    def test_analysis(self, image: np.ndarray) -> Dict[str, Any]:
        """Test HP, Mana, and Color Trigger analysis with full diagnostics"""
        return {
            'hp_test': self.analyze_hp(image),
            'mana_test': self.analyze_mana(image),
            'color_trigger_test': self.analyze_color_triggers(image),  # NEW
            'combined_test': self.analyze_both(image),
            'stats': self.get_combined_stats()
        }

    # === NEW: COLOR TRIGGER MANAGEMENT METHODS ===
    def get_color_trigger_status(self) -> str:
        """Get current color trigger status"""
        if not self.color_triggers_enabled:
            return "🎯 COLOR TRIGGERS: DISABLED"

        enabled_triggers = len([t for t in self.trigger_points if t['enabled']])
        if enabled_triggers == 0:
            return "🎯 COLOR TRIGGERS: NO ACTIVE TRIGGERS"

        recent_triggers = 0
        current_time = time.time()

        for trigger_name, stats in self.color_trigger_stats['triggers_by_name'].items():
            if current_time - stats['last_activation'] < 10:  # Last 10 seconds
                recent_triggers += 1

        if recent_triggers > 0:
            return f"🎯 COLOR TRIGGERS: {recent_triggers} RECENT ({enabled_triggers} active)"
        else:
            return f"🎯 COLOR TRIGGERS: MONITORING ({enabled_triggers} active)"

    def enable_trigger_by_name(self, trigger_name: str, enabled: bool = True):
        """Enable/disable specific trigger by name"""
        for trigger in self.trigger_points:
            if trigger['name'] == trigger_name:
                trigger['enabled'] = enabled
                status = "ENABLED" if enabled else "DISABLED"
                self.log(f"🎯 Trigger '{trigger_name}': {status}")
                return True

        self.log(f"❌ Trigger '{trigger_name}' not found", "warning")
        return False

    def test_color_trigger_at_position(self, image: np.ndarray, x: int, y: int, target_color: tuple, tolerance: int = 30) -> Dict[str, Any]:
        """Test color trigger at specific position"""
        try:
            if image is None or image.size == 0:
                return {'success': False, 'reason': 'Invalid image'}

            img_height, img_width = image.shape[:2]

            if x < 0 or y < 0 or x >= img_width or y >= img_height:
                return {'success': False, 'reason': 'Position out of bounds'}

            # Create test trigger
            test_trigger = {
                'x': x, 'y': y,
                'color': target_color,
                'tolerance': tolerance,
                'region_size': COLOR_TRIGGER_REGION_SIZE
            }

            # Check color match
            match = self._check_color_trigger_match(image, test_trigger)

            # Get actual color at position for comparison
            half_size = COLOR_TRIGGER_REGION_SIZE // 2
            x1, y1 = max(0, x - half_size), max(0, y - half_size)
            x2, y2 = min(img_width, x + half_size + 1), min(img_height, y + half_size + 1)

            region = image[y1:y2, x1:x2]
            actual_color = tuple(np.mean(region, axis=(0, 1)).astype(int))

            return {
                'success': True,
                'match': match,
                'actual_color': actual_color,
                'target_color': target_color,
                'tolerance': tolerance,
                'position': (x, y),
                'region_bounds': (x1, y1, x2, y2)
            }

        except Exception as e:
            return {'success': False, 'reason': f'Exception: {str(e)}'}


# === EXAMPLE USAGE ===
if __name__ == "__main__":
    # Create enhanced analyzer
    analyzer = PlayerBarsAnalyzer()

    # Enable all systems
    analyzer.enable_hp_analysis(True)
    analyzer.enable_mana_analysis(True)
    analyzer.enable_color_triggers(True)  # NEW

    # Set positions (example coordinates)
    analyzer.set_hp_position_px(100, 50, 200, 15)    # HP bar
    analyzer.set_mana_position_px(100, 70, 200, 15)  # Mana bar below HP

    # Set critical thresholds
    analyzer.set_hp_critical_threshold(25.0)   # 25% HP
    analyzer.set_mana_critical_threshold(15.0) # 15% Mana

    # Color triggers are automatically loaded from TRIGGER_POINTS

    # Test with dummy image
    test_image = np.random.randint(0, 255, (900, 1200, 3), dtype=np.uint8)

    # Add test HP bar (green)
    test_image[50:65, 100:250] = [0, 255, 0]  # Full green HP bar

    # Add test Mana bar (blue) - partial
    test_image[70:85, 100:175] = [0, 0, 255]  # Half blue Mana bar

    # Add test color trigger
    test_image[845:853, 1049:1055] = [124, 125, 160]  # Your trigger color

    # Test analysis
    results = analyzer.analyze_both(test_image)
    print(f"HP: {results['hp_percentage']:.1f}%")
    print(f"Mana: {results['mana_percentage']:.1f}%")
    print(f"Triggers activated: {results['triggers_activated']}")
    print(f"HP Critical: {results['hp_critical']}")
    print(f"Mana Critical: {results['mana_critical']}")

    # Test quick methods
    print(f"Quick HP: {analyzer.get_hp_percentage(test_image):.1f}%")
    print(f"Quick Mana: {analyzer.get_mana_percentage(test_image):.1f}%")

    # Get statistics
    stats = analyzer.get_combined_stats()
    print(f"HP Success Rate: {(stats['hp_stats']['successful_detections']/max(1,stats['hp_stats']['total_analyses']))*100:.1f}%")
    print(f"Mana Success Rate: {(stats['mana_stats']['successful_detections']/max(1,stats['mana_stats']['total_analyses']))*100:.1f}%")
    print(f"Color Triggers: {stats['color_trigger_stats']['successful_triggers']} activations")