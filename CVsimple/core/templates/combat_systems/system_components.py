"""
System Components - HP Recovery, Button Sequence, Camera
Wydzielone z combat_controller.py dla modularności
"""
import time
import random
import math
from typing import Optional, Dict, Any
from .input_handler import InputHandler


class HPRecoverySystem:
    """
    HP Recovery System - Automatyczne używanie mikstury życia
    Wydzielony z ReactiveCombatController
    """

    def __init__(self, input_handler: InputHandler, logger=None):
        self.input_handler = input_handler
        self.logger = logger

        # VK codes
        vk_codes = input_handler.get_vk_codes()
        self.VK_4 = vk_codes['4']

        # HP Recovery System state
        self.hp_recovery_active = False
        self.hp_recovery_start_time = 0
        self.hp_recovery_wait_duration = 1.0  # seconds between potions
        self.hp_recovery_key = self.VK_4  # Key for health potion
        self.last_hp_potion_time = 0
        self.waiting_for_hp_recovery = False

        # Player status tracking
        self.player_hp = 100.0
        self.player_hp_event = None
        self.player_mana = 100.0
        self.player_mana_event = None

        # Statistics
        self.stats = {
            'hp_recovery_sessions': 0,
            'health_potions_used': 0,
            'hp_recovery_time_total': 0.0,
            'hp_recovery_average_time': 0.0
        }

    def log(self, message: str):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)

    def get_current_hp_from_gui(self) -> float:
        """Get current HP from GUI data (not from screenshot)"""
        # This would need to be connected to bars analyzer
        return self.player_hp  # Fallback to last known value

    def handle_hp_event(self, event_type: str, hp_percentage: float):
        """Handle HP events from PlayerBarsAnalyzer"""
        self.player_hp = hp_percentage
        self.player_hp_event = event_type

        if event_type == "hp_critical" or event_type == "hp_warning":
            self.trigger_hp_recovery(hp_percentage)
        elif event_type == "hp_critical_recovered":
            self.on_hp_recovery_success(hp_percentage)
        elif event_type == "hp_warning":
            self.log(f"⚠️ HP Warning: {hp_percentage:.1f}%")
        elif event_type == "hp_warning_recovered":
            self.log(f"✅ HP Warning cleared: {hp_percentage:.1f}%")

    def handle_mana_event(self, event_type: str, mana_percentage: float):
        """Handle Mana events from PlayerBarsAnalyzer (for future use)"""
        self.player_mana = mana_percentage
        self.player_mana_event = event_type

        if event_type == "mana_critical":
            self.log(f"🚨 CRITICAL MANA: {mana_percentage:.1f}%")
        elif event_type == "mana_recovered":
            self.log(f"✅ Mana recovered: {mana_percentage:.1f}%")

    def trigger_hp_recovery(self, hp_percentage: float):
        """Start HP recovery mode - CRITICAL HP detected"""
        if self.hp_recovery_active:
            self.log(f"🔄 HP Recovery already active, current HP: {hp_percentage:.1f}%")
            return

        self.hp_recovery_active = True
        self.waiting_for_hp_recovery = True
        self.hp_recovery_start_time = time.time()
        self.last_hp_potion_time = 0  # Reset timer to use potion immediately

        # Update statistics
        self.stats['hp_recovery_sessions'] += 1

        self.log(f"🚨 HP RECOVERY STARTED: {hp_percentage:.1f}% - EMERGENCY MODE ACTIVATED")

    def on_hp_recovery_success(self, hp_percentage: float):
        """HP recovery completed - return to normal combat"""
        if not self.hp_recovery_active:
            self.log(f"✅ HP Recovery callback received but not active: {hp_percentage:.1f}%")
            return

        # Calculate recovery time
        recovery_time = time.time() - self.hp_recovery_start_time
        self.stats['hp_recovery_time_total'] += recovery_time

        # Calculate average recovery time
        if self.stats['hp_recovery_sessions'] > 0:
            self.stats['hp_recovery_average_time'] = (
                    self.stats['hp_recovery_time_total'] / self.stats['hp_recovery_sessions']
            )

        self.hp_recovery_active = False
        self.waiting_for_hp_recovery = False

        self.log(f"✅ HP RECOVERED: {hp_percentage:.1f}% - recovery took {recovery_time:.1f}s - returning to combat")

    def update(self, hwnd: int) -> bool:
        """Update HP recovery system - returns True if recovery is active"""
        current_time = time.time()

        # Check if recovery should end based on HP level
        if self.hp_recovery_active:
            current_hp = self.get_current_hp_from_gui()
            if current_hp > 80.0:
                self.log(f"✅ Manual HP check ended recovery at {current_hp:.1f}%")
                self.on_hp_recovery_success(current_hp)
                return False

        if not self.hp_recovery_active:
            return False

        # Check if it's time to use another health potion
        if current_time - self.last_hp_potion_time >= self.hp_recovery_wait_duration:
            # Use health potion
            if self.input_handler.send_key_press(hwnd, self.hp_recovery_key):
                self.last_hp_potion_time = current_time
                self.stats['health_potions_used'] += 1

                recovery_elapsed = current_time - self.hp_recovery_start_time
                self.log(f"💊 Health potion used (#{self.stats['health_potions_used']}) - "
                         f"recovery time: {recovery_elapsed:.1f}s - waiting {self.hp_recovery_wait_duration:.1f}s...")
            else:
                self.log("❌ FAILED to use health potion - trying again in 0.5s")
                self.last_hp_potion_time = current_time - self.hp_recovery_wait_duration + 0.5

        return True

    def is_active(self) -> bool:
        """Check if HP recovery is currently active"""
        return self.hp_recovery_active

    def get_status(self) -> str:
        """Get current HP recovery status for display"""
        if not self.hp_recovery_active:
            return ""

        current_time = time.time()
        recovery_elapsed = current_time - self.hp_recovery_start_time
        next_potion_in = self.hp_recovery_wait_duration - (current_time - self.last_hp_potion_time)

        if next_potion_in <= 0:
            return f"💊 HP RECOVERY ({recovery_elapsed:.1f}s) - POTION READY"
        else:
            return f"💊 HP RECOVERY ({recovery_elapsed:.1f}s) - next potion in {next_potion_in:.1f}s"

    def configure(self, potion_key: int = None, wait_duration: float = 2.0):
        """Configure HP recovery system"""
        if potion_key is not None:
            self.hp_recovery_key = potion_key
            self.log(f"💊 HP Recovery key set to: {potion_key} (VK code)")

        self.hp_recovery_wait_duration = wait_duration
        self.log(f"⏱️ HP Recovery wait duration: {wait_duration}s between potions")

    def emergency_stop(self):
        """Emergency stop HP recovery"""
        if self.hp_recovery_active:
            self.hp_recovery_active = False
            self.waiting_for_hp_recovery = False
            self.log("🚨 EMERGENCY STOP: HP Recovery aborted")

    def get_stats(self) -> Dict[str, Any]:
        """Get HP recovery statistics"""
        return {
            'hp_recovery_active': self.hp_recovery_active,
            'hp_recovery_sessions': self.stats['hp_recovery_sessions'],
            'health_potions_used': self.stats['health_potions_used'],
            'hp_recovery_time_total': self.stats['hp_recovery_time_total'],
            'hp_recovery_average_time': self.stats['hp_recovery_average_time'],
            'current_player_hp': self.player_hp,
            'current_player_mana': self.player_mana,
            'last_hp_event': self.player_hp_event,
            'last_mana_event': self.player_mana_event,
        }


class ButtonSequenceSystem:
    """
    Button Sequence System - Automatyczne naciskanie "-" i "="
    Wydzielony z ReactiveCombatController
    """

    def __init__(self, input_handler: InputHandler, logger=None):
        self.input_handler = input_handler
        self.logger = logger

        # VK codes
        vk_codes = input_handler.get_vk_codes()
        self.VK_MINUS, self.VK_EQUALS = vk_codes['MINUS'], vk_codes['EQUALS']

        # Button sequence system
        self.enabled = True
        self.interval_base = 30 * 60  # 30 minutes
        self.interval_variance = 5 * 60  # ±5 minutes
        self.hold_duration = (0.05, 0.15)
        self.delay = (1.0, 1.3)
        self.last_cycle = 0
        self.next_cycle = 0
        self.active = False
        self.step = 0
        self.next_time = 0

        # Statistics
        self.stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'total_presses': 0,
            'last_cycle_time': 0,
            'next_cycle_in': 0
        }

        # Schedule first cycle
        self._schedule_first_cycle()

    def log(self, message: str):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)

    def _schedule_first_cycle(self):
        """Schedule the first button cycle with a short delay"""
        current_time = time.time()
        first_delay = random.uniform(1.0, 2.0)
        self.next_cycle = current_time + first_delay
        self.stats['next_cycle_in'] = first_delay
        self.log(f"📅 First '-' + '=' cycle in {first_delay:.1f} seconds")

    def _schedule_next_cycle(self):
        """Schedule the next button cycle"""
        current_time = time.time()
        random_variance = random.uniform(-self.interval_variance, self.interval_variance)
        interval = self.interval_base + random_variance
        self.next_cycle = current_time + interval
        self.stats['next_cycle_in'] = interval
        self.log(f"📅 Next '-' + '=' cycle scheduled in {interval / 60:.1f} minutes")

    def _press_button_single(self, hwnd: int, vk_code: int, button_name: str) -> bool:
        """Press a single button with proper timing"""
        try:
            hold_duration = random.uniform(*self.hold_duration)
            success1 = self.input_handler.send_key_down(hwnd, vk_code)
            if not success1:
                return False
            time.sleep(hold_duration)
            success2 = self.input_handler.send_key_up(hwnd, vk_code)

            if success1 and success2:
                self.stats['total_presses'] += 1
                self.log(f"📋 Pressed '{button_name}' (held {hold_duration:.2f}s)")
                return True
            return False
        except Exception as e:
            self.log(f"❌ Error pressing button '{button_name}': {e}")
            return False

    def update(self, hwnd: int):
        """Update the button sequence system"""
        current_time = time.time()

        # Start new cycle
        if (not self.active and
                current_time >= self.next_cycle and
                self.enabled):

            self.active = True
            self.step = 1

            if self._press_button_single(hwnd, self.VK_MINUS, "-"):
                delay = random.uniform(*self.delay)
                self.next_time = current_time + delay
                self.log(f"🔄 '-' cycle started - '=' in {delay:.2f}s")
            else:
                self.active = False
                self.step = 0
                self.stats['failed_cycles'] += 1
                self._schedule_next_cycle()

        # Continue sequence (second click "=")
        elif (self.active and self.step == 1 and
              current_time >= self.next_time):

            if self._press_button_single(hwnd, self.VK_EQUALS, "="):
                self.stats['successful_cycles'] += 1
                self.log("✅ '-' + '=' cycle completed successfully")
            else:
                self.stats['failed_cycles'] += 1
                self.log("❌ Second '=' click failed")

            self.active = False
            self.step = 0
            self.stats['total_cycles'] += 1
            self.stats['last_cycle_time'] = current_time
            self.last_cycle = current_time
            self._schedule_next_cycle()

    def get_status(self) -> str:
        """Get current status of button sequence system"""
        if not self.enabled:
            return "⏸️ DISABLED"

        current_time = time.time()

        if self.active:
            if self.step == 1:
                time_until_second = self.next_time - current_time
                if time_until_second <= 0:
                    return "⏰ '=' READY"
                else:
                    return f"🔄 '=' IN {time_until_second:.1f}s"
            else:
                return "🔄 ACTIVE"

        time_until_next = self.next_cycle - current_time

        if time_until_next <= 0:
            return "⏰ READY"
        elif time_until_next < 60:
            return f"⏱️ {time_until_next:.0f}s"
        elif time_until_next < 3600:
            return f"⏱️ {time_until_next / 60:.1f}min"
        else:
            return f"⏱️ {time_until_next / 3600:.1f}h"

    def configure(self, enabled: bool = True, interval_minutes: int = 30, variance_minutes: int = 5):
        """Configure button sequence system"""
        self.enabled = enabled
        self.interval_base = interval_minutes * 60
        self.interval_variance = variance_minutes * 60

        if enabled:
            if self.stats['total_cycles'] == 0:
                self._schedule_first_cycle()
            else:
                self._schedule_next_cycle()
            self.log(f"📋 Buttons '-' and '=': ENABLED (interval: {interval_minutes}±{variance_minutes}min)")
        else:
            self.log("📋 Buttons '-' and '=': DISABLED")

    def get_stats(self) -> Dict[str, Any]:
        """Get detailed button sequence statistics"""
        current_time = time.time()
        time_until_next = max(0, self.next_cycle - current_time)
        time_since_last = current_time - self.last_cycle if self.last_cycle > 0 else 0

        return {
            'enabled': self.enabled,
            'total_cycles': self.stats['total_cycles'],
            'successful_cycles': self.stats['successful_cycles'],
            'failed_cycles': self.stats['failed_cycles'],
            'total_presses': self.stats['total_presses'],
            'cycle_success_rate': (self.stats['successful_cycles'] / max(1, self.stats['total_cycles'])) * 100,
            'sequence_active': self.active,
            'sequence_step': self.step,
            'time_until_next_cycle': time_until_next,
            'time_since_last_cycle': time_since_last,
            'next_cycle_formatted': self.get_status(),
            'interval_minutes': self.interval_base / 60,
            'variance_minutes': self.interval_variance / 60
        }


class CameraSystem:
    """
    Camera System - Zarządzanie kamerą i pozycjonowaniem
    Wydzielony z ReactiveCombatController
    """

    def __init__(self, input_handler: InputHandler, logger=None):
        self.input_handler = input_handler
        self.logger = logger

        # VK codes
        vk_codes = input_handler.get_vk_codes()
        self.VK_A, self.VK_D = vk_codes['A'], vk_codes['D']

        # Screen configuration - defaults
        self.screen_width = 1920
        self.screen_height = 1080
        self.screen_center_x = 960
        self.screen_center_y = 540

        # Camera trapezoid system
        self.trapez_bottom_width = 192  # 10% of 1920
        self.trapez_top_width = 576  # 30% of 1920
        self.trapez_height = 520  # 50% of 1080
        self.trapez_bottom_y = self.screen_center_y
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        # Micro camera movements
        self.micro_camera_duration = random.uniform(0.002, 0.02)
        self.micro_camera_cooldown = random.uniform(0.8, 1.1)
        self.last_camera_adjustment = 0
        self.camera_adjusting = False
        self.camera_key_pressed: Optional[int] = None
        self.camera_key_start_time = 0

        # Statistics
        self.stats = {
            'camera_adjustments': 0
        }

    def log(self, message: str):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)

    def configure_screen_size(self, window_width: int, window_height: int):
        """Configure screen size and recalculate all proportional values"""
        self.screen_width = window_width
        self.screen_height = window_height
        self.screen_center_x = window_width // 2
        self.screen_center_y = window_height // 2

        # Configure trapezoid with new proportions
        self.trapez_bottom_width = int(window_width * 0.1)  # 10% at bottom
        self.trapez_top_width = int(window_width * 0.3)  # 30% at top
        self.trapez_height = int(window_height * 0.51)  # height 30% upward

        self.trapez_bottom_y = self.screen_center_y
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        self.log(f"🖥️ Screen configured: {window_width}x{window_height}")
        self.log(
            f"📐 Trapezoid: bottom {self.trapez_bottom_width}px, top {self.trapez_top_width}px, height {self.trapez_height}px")

    def is_enemy_in_trapezoid(self, enemy_x: float, enemy_y: float) -> bool:
        """Check if enemy is within the camera trapezoid"""
        if enemy_y > self.trapez_bottom_y or enemy_y < self.trapez_top_y:
            return False

        # Calculate trapezoid width at enemy's height
        y_ratio = (self.trapez_bottom_y - enemy_y) / self.trapez_height
        width_at_y = self.trapez_bottom_width + (self.trapez_top_width - self.trapez_bottom_width) * y_ratio

        left_bound = self.screen_center_x - width_at_y / 2
        right_bound = self.screen_center_x + width_at_y / 2

        return left_bound <= enemy_x <= right_bound

    def get_camera_adjustment_direction(self, enemy_x: float, enemy_y: float) -> str:
        """Get direction for camera adjustment"""
        return "left" if enemy_x < self.screen_center_x else "right"

    def micro_camera_adjust(self, hwnd: int, direction: str) -> bool:
        """Perform micro camera adjustment"""
        current_time = time.time()
        if current_time - self.last_camera_adjustment < self.micro_camera_cooldown:
            return False

        key = self.VK_A if direction == "left" else self.VK_D
        if not self.input_handler.send_key_down(hwnd, key):
            return False

        self.camera_adjusting = True
        self.camera_key_pressed = key
        self.camera_key_start_time = current_time
        self.last_camera_adjustment = current_time
        self.stats['camera_adjustments'] += 1

        if self.stats['camera_adjustments'] % 3 == 0:
            self.log(f"📹 Micro camera move: {direction}")
        return True

    def update(self, hwnd: int):
        """Update ongoing camera adjustment"""
        if not self.camera_adjusting:
            return

        current_time = time.time()
        if current_time - self.camera_key_start_time >= self.micro_camera_duration:
            if self.camera_key_pressed:
                self.input_handler.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_adjusting = False
            self.camera_key_pressed = None

    def emergency_stop(self, hwnd: int):
        """Emergency stop camera movements"""
        if self.camera_key_pressed:
            self.input_handler.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_adjusting = False
            self.camera_key_pressed = None

    def get_stats(self) -> Dict[str, Any]:
        """Get camera system statistics"""
        return {
            'camera_adjustments': self.stats['camera_adjustments'],
            'camera_adjusting': self.camera_adjusting,
            'screen_width': self.screen_width,
            'screen_height': self.screen_height,
            'trapez_bottom_width': self.trapez_bottom_width,
            'trapez_top_width': self.trapez_top_width,
            'trapez_height': self.trapez_height
        }