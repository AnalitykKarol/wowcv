"""
Reactive Combat Controller - Improved Version
Fixed bugs, improved error handling, and better code organization
"""
import win32api
import win32con
import win32gui
import time
import random
import math
import ctypes
from ctypes import wintypes
from typing import Dict, List, Optional, Tuple, Any


class ReactiveCombatController:
    def __init__(self, logger=None):
        self.logger = logger

        # Virtual key codes
        self.VK_W, self.VK_A, self.VK_S, self.VK_D = 0x57, 0x41, 0x53, 0x44
        self.VK_1, self.VK_2, self.VK_3, self.VK_4 = 0x31, 0x32, 0x33, 0x34
        self.VK_5, self.VK_6, self.VK_7, self.VK_8 = 0x35, 0x36, 0x37, 0x38
        self.VK_MINUS, self.VK_EQUALS = 0xBD, 0xBB

        # Main system state
        self.mode = "exploration"  # exploration, combat, grace_period
        self.last_enemy_position: Optional[Tuple[float, float]] = None
        self.last_enemy_seen_time = 0
        self.grace_period_duration = 6.0
        self.grace_period_start_time = 0

        # Movement system
        self.movement_state = "ready_for_next_move"
        self.current_movement_key: Optional[int] = None
        self.movement_start_time = 0
        self.movement_duration = 0
        self.movement_pause_start_time = 0
        self.movement_pause_duration = random.uniform(0.01, 0.3)

        # Movement durations
        self.micro_movement_duration = random.uniform(0.1, 0.2)
        self.short_movement_duration = random.uniform(0.25, 0.4)
        self.medium_movement_duration = random.uniform(0.6, 2)

        # W+A/D combination system
        self.w_plus_turn_chance = 0.3
        self.turn_key_with_w: Optional[int] = None
        self.turn_key_pressed = False
        self.turn_duration_with_w = 0
        self.turn_start_time_with_w = 0

        # Screen configuration - defaults, will be updated by configure_screen_size()
        self.screen_width = 1920
        self.screen_height = 1080
        self.screen_center_x = 960
        self.screen_center_y = 540

        # Camera trapezoid system
        self.trapez_bottom_width = 192  # 10% of 1920
        self.trapez_top_width = 576     # 30% of 1920
        self.trapez_height = 520        # 50% of 1080
        self.trapez_bottom_y = self.screen_center_y
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        # Micro camera movements
        self.micro_camera_duration = random.uniform(0.005, 0.01)
        self.micro_camera_cooldown = random.uniform(0.8, 1.1)
        self.last_camera_adjustment = 0
        self.camera_adjusting = False
        self.camera_key_pressed: Optional[int] = None
        self.camera_key_start_time = 0

        # Attack system
        self.attack_keys = [self.VK_1, self.VK_2, self.VK_3, self.VK_4,
                           self.VK_5, self.VK_6, self.VK_7]
        self.attack_weights = {
            self.VK_1: 0.25, self.VK_2: 0.25, self.VK_3: 0.2, self.VK_4: 0.1,
            self.VK_5: 0.05, self.VK_6: 0.1, self.VK_7: 0.1
        }
        self.last_attack_time = 0
        self.attack_interval = random.uniform(0.5, 1.5)

        # Emergency backstep system
        self.emergency_distance_threshold = 150
        self.emergency_backstep_duration = random.uniform(0.2, 0.6)
        self.emergency_backstep_cooldown = random.uniform(10, 30)
        self.last_emergency_backstep = 0
        self.emergency_backstep_active = False
        self.emergency_backstep_start_time = 0

        # Clicking system
        self.last_combat_click = 0
        self.last_loot_click = 0
        self.combat_click_cooldown = (1.5, 3.0)
        self.loot_click_cooldown = (0.5, 1)
        self.loot_offset_range = (10, 60)
        self.last_successful_method: Optional[str] = None

        # Button sequence system ("-" and "=" keys)
        self._init_button_sequence_system()

        # Statistics
        self.stats = {
            'combat_sessions': 0,
            'camera_adjustments': 0,
            'emergency_backsteps': 0,
            'position_clicks': 0,
            'successful_clicks': 0,
            'failed_clicks': 0,
            'method_stats': {
                'wow_proven': 0,
                'warcraft_style': 0,
                'evasion_technique': 0,
                'sendinput_admin': 0,
                'hybrid_fallback': 0
            }
        }

    def _init_button_sequence_system(self):
        """Initialize the button sequence system for '-' and '=' keys"""
        self.button_sequence_enabled = True
        self.button_sequence_interval_base = 30 * 60  # 30 minutes
        self.button_sequence_interval_variance = 5 * 60  # ±5 minutes
        self.button_sequence_hold_duration = (0.05, 0.15)
        self.button_sequence_delay = (1.0, 1.3)
        self.button_sequence_last_cycle = 0
        self.button_sequence_next_cycle = 0
        self.button_sequence_active = False
        self.button_sequence_step = 0
        self.button_sequence_next_time = 0

        # Button sequence statistics
        self.button_sequence_stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'total_presses': 0,
            'last_cycle_time': 0,
            'next_cycle_in': 0
        }

        # Schedule first cycle
        self._schedule_first_button_cycle()

    def log(self, message: str):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)

    # === BUTTON SEQUENCE SYSTEM ("-" and "=" keys) ===
    def _schedule_first_button_cycle(self):
        """Schedule the first button cycle with a short delay"""
        current_time = time.time()
        first_delay = random.uniform(1.0, 2.0)
        self.button_sequence_next_cycle = current_time + first_delay
        self.button_sequence_stats['next_cycle_in'] = first_delay
        self.log(f"📅 First '-' + '=' cycle in {first_delay:.1f} seconds")

    def _schedule_next_button_cycle(self):
        """Schedule the next button cycle"""
        current_time = time.time()
        random_variance = random.uniform(-self.button_sequence_interval_variance,
                                       self.button_sequence_interval_variance)
        interval = self.button_sequence_interval_base + random_variance
        self.button_sequence_next_cycle = current_time + interval
        self.button_sequence_stats['next_cycle_in'] = interval
        self.log(f"📅 Next '-' + '=' cycle scheduled in {interval/60:.1f} minutes")

    def _press_button_single(self, hwnd: int, vk_code: int, button_name: str) -> bool:
        """Press a single button with proper timing"""
        try:
            hold_duration = random.uniform(*self.button_sequence_hold_duration)
            success1 = self.send_key_down(hwnd, vk_code)
            if not success1:
                return False
            time.sleep(hold_duration)
            success2 = self.send_key_up(hwnd, vk_code)

            if success1 and success2:
                self.button_sequence_stats['total_presses'] += 1
                self.log(f"📋 Pressed '{button_name}' (held {hold_duration:.2f}s)")
                return True
            return False
        except Exception as e:
            self.log(f"❌ Error pressing button '{button_name}': {e}")
            return False

    def update_button_sequence_system(self, hwnd: int):
        """Update the button sequence system"""
        current_time = time.time()

        # Start new cycle
        if (not self.button_sequence_active and
            current_time >= self.button_sequence_next_cycle and
            self.button_sequence_enabled):

            self.button_sequence_active = True
            self.button_sequence_step = 1

            if self._press_button_single(hwnd, self.VK_MINUS, "-"):
                delay = random.uniform(*self.button_sequence_delay)
                self.button_sequence_next_time = current_time + delay
                self.log(f"🔄 '-' cycle started - '=' in {delay:.2f}s")
            else:
                self.button_sequence_active = False
                self.button_sequence_step = 0
                self.button_sequence_stats['failed_cycles'] += 1
                self._schedule_next_button_cycle()

        # Continue sequence (second click "=")
        elif (self.button_sequence_active and self.button_sequence_step == 1 and
              current_time >= self.button_sequence_next_time):

            if self._press_button_single(hwnd, self.VK_EQUALS, "="):
                self.button_sequence_stats['successful_cycles'] += 1
                self.log("✅ '-' + '=' cycle completed successfully")
            else:
                self.button_sequence_stats['failed_cycles'] += 1
                self.log("❌ Second '=' click failed")

            self.button_sequence_active = False
            self.button_sequence_step = 0
            self.button_sequence_stats['total_cycles'] += 1
            self.button_sequence_stats['last_cycle_time'] = current_time
            self.button_sequence_last_cycle = current_time
            self._schedule_next_button_cycle()

    def get_button_sequence_status(self) -> str:
        """Get current status of button sequence system"""
        if not self.button_sequence_enabled:
            return "⏸️ DISABLED"

        current_time = time.time()

        if self.button_sequence_active:
            if self.button_sequence_step == 1:
                time_until_second = self.button_sequence_next_time - current_time
                if time_until_second <= 0:
                    return "⏰ '=' READY"
                else:
                    return f"🔄 '=' IN {time_until_second:.1f}s"
            else:
                return "🔄 ACTIVE"

        time_until_next = self.button_sequence_next_cycle - current_time

        if time_until_next <= 0:
            return "⏰ READY"
        elif time_until_next < 60:
            return f"⏱️ {time_until_next:.0f}s"
        elif time_until_next < 3600:
            return f"⏱️ {time_until_next/60:.1f}min"
        else:
            return f"⏱️ {time_until_next/3600:.1f}h"

    # === SCREEN CONFIGURATION WITH TRAPEZOID ===
    def configure_screen_size(self, window_width: int, window_height: int):
        """Configure screen size and recalculate all proportional values"""
        self.screen_width = window_width
        self.screen_height = window_height
        self.screen_center_x = window_width // 2
        self.screen_center_y = window_height // 2

        # Configure trapezoid with new proportions
        self.trapez_bottom_width = int(window_width * 0.1)  # 10% at bottom
        self.trapez_top_width = int(window_width * 0.3)     # 30% at top
        self.trapez_height = int(window_height * 0.51)       # height 30% upward

        self.trapez_bottom_y = self.screen_center_y
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        # Adjust other values proportionally
        base_width = 1920
        scale_factor = window_width / base_width
        self.emergency_distance_threshold = int(150 * scale_factor)
        self.loot_offset_range = (int(10 * scale_factor), int(60 * scale_factor))

        self.log(f"🖥️ Screen configured: {window_width}x{window_height}")
        self.log(f"📐 Trapezoid: bottom {self.trapez_bottom_width}px, top {self.trapez_top_width}px, height {self.trapez_height}px")

    # === CAMERA SYSTEM WITH TRAPEZOID ===
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
        if not self.send_key_down(hwnd, key):
            return False

        self.camera_adjusting = True
        self.camera_key_pressed = key
        self.camera_key_start_time = current_time
        self.last_camera_adjustment = current_time
        self.stats['camera_adjustments'] += 1

        if self.stats['camera_adjustments'] % 3 == 0:
            self.log(f"📹 Micro camera move: {direction}")
        return True

    def update_camera_adjustment(self, hwnd: int):
        """Update ongoing camera adjustment"""
        if not self.camera_adjusting:
            return

        current_time = time.time()
        if current_time - self.camera_key_start_time >= self.micro_camera_duration:
            if self.camera_key_pressed:
                self.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_adjusting = False
            self.camera_key_pressed = None

    # === EMERGENCY BACKSTEP SYSTEM ===
    def check_emergency_backstep(self, enemy_x: float, enemy_y: float) -> bool:
        """Check if emergency backstep is needed"""
        dx = enemy_x - self.screen_center_x
        dy = enemy_y - self.screen_center_y
        distance = math.sqrt(dx*dx + dy*dy)
        return distance < self.emergency_distance_threshold

    def start_emergency_backstep(self, hwnd: int) -> bool:
        """Start emergency backstep maneuver"""
        current_time = time.time()
        if current_time - self.last_emergency_backstep < self.emergency_backstep_cooldown:
            return False

        # Add S key without stopping other movements
        if not self.send_key_down(hwnd, self.VK_S):
            return False

        self.emergency_backstep_active = True
        self.emergency_backstep_start_time = current_time
        self.last_emergency_backstep = current_time
        self.stats['emergency_backsteps'] += 1

        self.log(f"🚨 EMERGENCY BACKSTEP! Mob too close (cooldown {self.emergency_backstep_cooldown:.1f}s)")
        return True

    def update_emergency_backstep(self, hwnd: int):
        """Update ongoing emergency backstep"""
        if not self.emergency_backstep_active:
            return

        current_time = time.time()
        if current_time - self.emergency_backstep_start_time >= self.emergency_backstep_duration:
            self.send_key_up(hwnd, self.VK_S)
            self.emergency_backstep_active = False
            self.log("✅ Emergency backstep completed")

    # === CLICKING METHODS ===
    def method_1_wow_proven_postmessage(self, hwnd: int, x: float, y: float) -> bool:
        """Method 1: Proven WoW PostMessage format"""
        try:
            lParam = ((int(y) << 16) | (int(x) & 0xFFFF))

            # DODAJ TO: Poinformuj grę gdzie jest mysz
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
            time.sleep(0.001)  # Krótka pauza

            result1 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, 0, lParam)

            time.sleep(random.uniform(0.005, 0.015))

            result2 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lParam)

            success = bool(result1 and result2)
            return success  # ← TO JEST KLUCZOWE!
        except Exception as e:
            self.log(f"❌ Method 1 (WoW): EXCEPTION - {e}")
            return False

    # === MAIN CLICKING INTERFACE ===
    def perform_right_click(self, hwnd: int, x: float, y: float, is_loot: bool = False) -> bool:
        """Perform right click using the best available method"""
        try:
            if is_loot:
                offset_y = random.randint(*self.loot_offset_range)
                y += offset_y
                click_type = "📦 Loot"
            else:
                click_type = "🔫 Combat"

            methods = [
                ("WoW Proven PostMessage", self.method_1_wow_proven_postmessage)
            ]

            # If we have a last successful method, try it first
            if self.last_successful_method:
                for method_name, method_func in methods:
                    if method_name == self.last_successful_method:
                        if method_func(hwnd, x, y):
                            self.stats['successful_clicks'] += 1
                            self.stats['position_clicks'] += 1
                            self.update_click_timers(is_loot)
                            self.log(f"✅ {click_type} {method_name} at ({x:.0f}, {y:.0f})")
                            return True
                        break

            # Try all methods in order
            for method_name, method_func in methods:
                try:
                    self.log(f"🎯 Trying method: {method_name}")
                    if method_func(hwnd, x, y):
                        self.last_successful_method = method_name
                        self.stats['successful_clicks'] += 1
                        self.stats['position_clicks'] += 1
                        self.update_click_timers(is_loot)
                        self.log(f"✅ {click_type} {method_name} SUCCESS at ({x:.0f}, {y:.0f})")
                        return True

                except Exception as e:
                    self.log(f"❌ {method_name} EXCEPTION: {e}")
                    continue

            self.stats['failed_clicks'] += 1
            return False

        except Exception as e:
            self.log(f"❌ Error in perform_right_click: {str(e)}")
            return False

    def update_click_timers(self, is_loot: bool):
        """Update click timing trackers"""
        current_time = time.time()
        if is_loot:
            self.last_loot_click = current_time
        else:
            self.last_combat_click = current_time

    def can_combat_click(self) -> bool:
        """Check if combat click is off cooldown"""
        current_time = time.time()
        cooldown = random.uniform(*self.combat_click_cooldown)
        return current_time - self.last_combat_click >= cooldown

    def can_loot_click(self) -> bool:
        """Check if loot click is off cooldown"""
        current_time = time.time()
        cooldown = random.uniform(*self.loot_click_cooldown)
        return current_time - self.last_loot_click >= cooldown

    # === MOVEMENT SYSTEM ===
    def stop_movement(self, hwnd: int):
        """Stop all current movement"""
        if self.current_movement_key:
            self.send_key_up(hwnd, self.current_movement_key)
            self.current_movement_key = None

        if self.turn_key_pressed and self.turn_key_with_w:
            self.send_key_up(hwnd, self.turn_key_with_w)
            self.turn_key_with_w = None
            self.turn_key_pressed = False

    def start_movement(self, hwnd: int, movement_key: Optional[int], duration: float, reason: str):
        """Start a new movement with specified duration"""
        self.stop_movement(hwnd)

        if movement_key:
            if not self.send_key_down(hwnd, movement_key):
                self.log(f"❌ Failed to start movement key {movement_key}")
                return

            self.current_movement_key = movement_key
            self.movement_start_time = time.time()
            self.movement_duration = duration
            self.movement_state = "moving"

            # If it's W, randomly add A or D
            if movement_key == self.VK_W and random.random() < self.w_plus_turn_chance:
                turn_key = random.choice([self.VK_A, self.VK_D])
                turn_duration = random.uniform(0.3, 0.8)

                if self.send_key_down(hwnd, turn_key):
                    self.turn_key_with_w = turn_key
                    self.turn_key_pressed = True
                    self.turn_duration_with_w = turn_duration
                    self.turn_start_time_with_w = time.time()

                    turn_name = "A" if turn_key == self.VK_A else "D"
                    self.log(f"🔄 Movement: W+{turn_name} for {duration:.2f}s → {reason}")
                else:
                    self.log(f"❌ Failed to start turn key {turn_key}")
            else:
                key_name = {self.VK_W: "W", self.VK_A: "A", self.VK_S: "S", self.VK_D: "D"}.get(movement_key, "?")
                self.log(f"🔄 Movement: {key_name} for {duration:.2f}s → {reason}")
        else:
            self.movement_state = "waiting_for_next"
            self.movement_pause_start_time = time.time()

    def update_movement_state(self, hwnd: int):
        """Update the current movement state"""
        current_time = time.time()

        if self.movement_state == "moving":
            # Check if we should stop the additional turn
            if (self.turn_key_pressed and
                current_time - self.turn_start_time_with_w >= self.turn_duration_with_w):
                if self.turn_key_with_w:
                    self.send_key_up(hwnd, self.turn_key_with_w)
                self.turn_key_pressed = False
                self.turn_key_with_w = None

            # Check if main movement is finished
            if current_time - self.movement_start_time >= self.movement_duration:
                self.stop_movement(hwnd)
                self.movement_state = "waiting_for_next"
                self.movement_pause_start_time = current_time
                self.movement_pause_duration = random.uniform(0.1, 0.3)

        elif self.movement_state == "waiting_for_next":
            if current_time - self.movement_pause_start_time >= self.movement_pause_duration:
                self.movement_state = "ready_for_next_move"

    def simple_exploration(self, hwnd: int):
        """Simple exploration movement AI"""
        if self.movement_state not in ["ready_for_next_move"]:
            return

        rand = random.random()
        if rand < 0.8:  # 80% forward
            movement_key = self.VK_W
            duration = self.medium_movement_duration
            reason = "Exploration FORWARD"
        elif rand < 0.9:  # 10% left
            movement_key = self.VK_A
            duration = self.micro_movement_duration
            reason = "Exploration LEFT"
        elif rand < 0.95:  # 5% right
            movement_key = self.VK_D
            duration = self.micro_movement_duration
            reason = "Exploration RIGHT"
        else:  # 5% backward
            movement_key = self.VK_S
            duration = self.micro_movement_duration
            reason = "Exploration BACKWARD"

        self.start_movement(hwnd, movement_key, duration, reason)

    # === ATTACK SYSTEM ===
    def simple_attack(self, hwnd: int) -> bool:
        """Perform attack with weighted key selection"""
        current_time = time.time()
        if current_time - self.last_attack_time < self.attack_interval:
            return False

        # Select key based on weights
        rand = random.random()
        cumulative_weight = 0
        attack_key = self.VK_1

        for key, weight in self.attack_weights.items():
            cumulative_weight += weight
            if rand <= cumulative_weight:
                attack_key = key
                break

        if self.send_key_press(hwnd, attack_key):
            self.last_attack_time = current_time
            self.attack_interval = random.uniform(0.8, 1.5)
            key_name = str(attack_key - 0x30)
            self.log(f"⚔️ Attack: {key_name}")
            return True
        return False

    # === BASIC KEY FUNCTIONS ===
    def send_key_down(self, hwnd: int, vk_code: int) -> bool:
        """Send key down message"""
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            return True
        except Exception as e:
            self.log(f"❌ send_key_down failed: {e}")
            return False

    def send_key_up(self, hwnd: int, vk_code: int) -> bool:
        """Send key up message"""
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
            return True
        except Exception as e:
            self.log(f"❌ send_key_up failed: {e}")
            return False

    def send_key_press(self, hwnd: int, vk_code: int) -> bool:
        """Send complete key press (down + up)"""
        try:
            if not self.send_key_down(hwnd, vk_code):
                return False
            time.sleep(0.05)
            return self.send_key_up(hwnd, vk_code)
        except Exception as e:
            self.log(f"❌ send_key_press failed: {e}")
            return False

    # === MAIN UPDATE LOOP ===
    def update(self, hwnd: int, detections: Optional[List[Dict[str, Any]]] = None):
        """Main update loop - call this regularly to run the bot"""
        current_time = time.time()

        # Update all systems
        self.update_button_sequence_system(hwnd)
        self.update_camera_adjustment(hwnd)
        self.update_emergency_backstep(hwnd)
        self.update_movement_state(hwnd)

        # Find enemies
        enemies = []
        if detections:
            for detection in detections:
                name = detection.get('name', '').lower()
                if any(keyword in name for keyword in ['mob', 'enemy', 'monster', 'target', 'health_bar']):
                    enemies.append(detection)

        if enemies:
            # COMBAT MODE
            closest_enemy = min(enemies, key=lambda e:
                abs(e.get('center_x', self.screen_center_x) - self.screen_center_x) +
                abs(e.get('center_y', self.screen_center_y) - self.screen_center_y))

            enemy_x = closest_enemy.get('center_x', self.screen_center_x)
            enemy_y = closest_enemy.get('center_y', self.screen_center_y)

            if self.mode != "combat":
                self.log("🎯 Enemy detected - entering combat")
                self.mode = "combat"
                self.stats['combat_sessions'] += 1
                self.stop_movement(hwnd)

            self.last_enemy_position = (enemy_x, enemy_y)
            self.last_enemy_seen_time = current_time

            # Emergency backstep check - does NOT block other actions
            if self.check_emergency_backstep(enemy_x, enemy_y):
                if not self.emergency_backstep_active:
                    self.start_emergency_backstep(hwnd)
                # NO return - continue normal actions

            # Check camera positioning
            if not self.is_enemy_in_trapezoid(enemy_x, enemy_y):
                if not self.camera_adjusting:
                    direction = self.get_camera_adjustment_direction(enemy_x, enemy_y)
                    self.micro_camera_adjust(hwnd, direction)

            # Combat click on enemy - ALWAYS
            if self.can_combat_click():
                self.perform_right_click(hwnd, enemy_x, enemy_y, is_loot=False)

            # Attack - ALWAYS
            self.simple_attack(hwnd)

        else:
            # NO ENEMIES
            if self.mode == "combat":
                self.log("👻 Enemy disappeared - starting grace period (loot)")
                self.mode = "grace_period"
                self.grace_period_start_time = current_time
                self.stop_movement(hwnd)

            elif self.mode == "grace_period":
                elapsed = current_time - self.grace_period_start_time

                if elapsed >= self.grace_period_duration:
                    self.log("🔄 Grace period ended - returning to exploration")
                    self.mode = "exploration"
                    self.last_enemy_position = None
                else:
                    # During grace period - loot and attack in place
                    remaining = self.grace_period_duration - elapsed

                    # Log every second
                    if int(remaining) != int(remaining + 0.1):
                        self.log(f"📦 Grace period: {remaining:.1f}s remaining")

                    # Loot clicking at last position
                    if self.last_enemy_position and self.can_loot_click():
                        x, y = self.last_enemy_position
                        self.perform_right_click(hwnd, x, y, is_loot=True)

                    # Attack in place during grace period
                    self.simple_attack(hwnd)
                    return

            # EXPLORATION
            if self.mode == "exploration" and not self.emergency_backstep_active:
                self.simple_exploration(hwnd)

    def emergency_stop(self, hwnd: int):
        """Emergency stop all activities"""
        self.stop_movement(hwnd)
        if self.camera_key_pressed:
            self.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_adjusting = False
            self.camera_key_pressed = None
        if self.emergency_backstep_active:
            self.send_key_up(hwnd, self.VK_S)
            self.emergency_backstep_active = False
        self.mode = "exploration"
        self.last_enemy_position = None
        self.log("🚨 EMERGENCY STOP")

    def get_status(self) -> str:
        """Get current status string for display"""
        status_parts = []

        if self.mode == "combat":
            status_parts.append("⚔️ COMBAT")
        elif self.mode == "grace_period":
            remaining = self.grace_period_duration - (time.time() - self.grace_period_start_time)
            status_parts.append(f"📦 GRACE PERIOD ({remaining:.1f}s)")
        elif self.mode == "exploration":
            status_parts.append("🔄 EXPLORATION")

        if self.emergency_backstep_active:
            status_parts.append("🚨 EMERGENCY BACKSTEP")

        if self.current_movement_key:
            key_names = {self.VK_W: "W", self.VK_A: "A", self.VK_S: "S", self.VK_D: "D"}
            current_key = key_names.get(self.current_movement_key, '?')
            remaining_time = self.movement_duration - (time.time() - self.movement_start_time)

            if self.turn_key_pressed and self.turn_key_with_w:
                turn_key_name = "A" if self.turn_key_with_w == self.VK_A else "D"
                status_parts.append(f"[{current_key}+{turn_key_name}: {remaining_time:.2f}s]")
            else:
                status_parts.append(f"[{current_key}: {remaining_time:.2f}s]")

        elif self.movement_state == "waiting_for_next":
            remaining_pause = self.movement_pause_duration - (time.time() - self.movement_pause_start_time)
            status_parts.append(f"[Pause: {remaining_pause:.2f}s]")

        if self.camera_adjusting:
            direction = "←" if self.camera_key_pressed == self.VK_A else "→"
            status_parts.append(f"[CAM:{direction}]")

        if self.last_successful_method:
            method_short = {
                "WoW Proven PostMessage": "WoW",
                "Warcraft Style PostMessage": "WC3",
                "Evasion Technique": "EVS",
                "SendInput Admin Bypass": "ADM",
                "Hybrid Fallback": "HYB"
            }.get(self.last_successful_method, "UNK")
            status_parts.append(f"[CLICK:{method_short}]")

        # Button sequence status
        button_status = self.get_button_sequence_status()
        status_parts.append(f"[BUTTONS:{button_status}]")

        return " ".join(status_parts) if status_parts else "🟢 READY"

    # === CONFIGURATION METHODS ===
    def configure_grace_period(self, duration: float = 6.0):
        """Configure grace period duration"""
        self.grace_period_duration = duration
        self.log(f"⏱️ Grace period: {duration}s")

    def configure_combat_clicks(self, min_cooldown: float = 1.5, max_cooldown: float = 3.0):
        """Configure combat click cooldowns"""
        self.combat_click_cooldown = (min_cooldown, max_cooldown)
        self.log(f"🔫 Combat clicks: {min_cooldown}-{max_cooldown}s cooldown")

    def configure_loot_clicks(self, min_cooldown: float = 0.5, max_cooldown: float = 1.0,
                             offset_min: int = 10, offset_max: int = 25):
        """Configure loot click settings"""
        self.loot_click_cooldown = (min_cooldown, max_cooldown)
        self.loot_offset_range = (offset_min, offset_max)
        self.log(f"📦 Loot clicks: {min_cooldown}-{max_cooldown}s cooldown, {offset_min}-{offset_max}px offset")

    def configure_emergency_backstep(self, threshold: int = 150, duration_min: float = 0.2,
                                   duration_max: float = 0.6, cooldown_min: float = 5, cooldown_max: float = 10):
        """Configure emergency backstep system"""
        self.emergency_distance_threshold = threshold
        self.emergency_backstep_duration = random.uniform(duration_min, duration_max)
        self.emergency_backstep_cooldown = random.uniform(cooldown_min, cooldown_max)
        self.log(f"🚨 Emergency backstep: <{threshold}px, {duration_min}-{duration_max}s duration, {cooldown_min}-{cooldown_max}s cooldown")

    def configure_button_sequence(self, enabled: bool = True, interval_minutes: int = 30, variance_minutes: int = 5):
        """Configure button sequence system"""
        self.button_sequence_enabled = enabled
        self.button_sequence_interval_base = interval_minutes * 60
        self.button_sequence_interval_variance = variance_minutes * 60

        if enabled:
            if self.button_sequence_stats['total_cycles'] == 0:
                self._schedule_first_button_cycle()
            else:
                self._schedule_next_button_cycle()
            self.log(f"📋 Buttons '-' and '=': ENABLED (interval: {interval_minutes}±{variance_minutes}min)")
        else:
            self.log("📋 Buttons '-' and '=': DISABLED")

    def get_button_sequence_stats(self) -> Dict[str, Any]:
        """Get detailed button sequence statistics"""
        current_time = time.time()
        time_until_next = max(0, self.button_sequence_next_cycle - current_time)
        time_since_last = current_time - self.button_sequence_last_cycle if self.button_sequence_last_cycle > 0 else 0

        return {
            'enabled': self.button_sequence_enabled,
            'total_cycles': self.button_sequence_stats['total_cycles'],
            'successful_cycles': self.button_sequence_stats['successful_cycles'],
            'failed_cycles': self.button_sequence_stats['failed_cycles'],
            'total_presses': self.button_sequence_stats['total_presses'],
            'cycle_success_rate': (self.button_sequence_stats['successful_cycles'] / max(1, self.button_sequence_stats['total_cycles'])) * 100,
            'sequence_active': self.button_sequence_active,
            'sequence_step': self.button_sequence_step,
            'time_until_next_cycle': time_until_next,
            'time_since_last_cycle': time_since_last,
            'next_cycle_formatted': self.get_button_sequence_status(),
            'interval_minutes': self.button_sequence_interval_base / 60,
            'variance_minutes': self.button_sequence_interval_variance / 60
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics and status"""
        current_enemy_pos = None
        target_distance = 0

        if self.last_enemy_position:
            current_enemy_pos = self.last_enemy_position
            dx = self.last_enemy_position[0] - self.screen_center_x
            dy = self.last_enemy_position[1] - self.screen_center_y
            target_distance = math.sqrt(dx*dx + dy*dy)

        # Legacy movement state mapping for compatibility
        movement_state_legacy = "idle"
        if self.mode == "combat":
            movement_state_legacy = "combat"
        elif self.mode == "exploration":
            movement_state_legacy = "exploration"
        elif self.mode == "grace_period":
            movement_state_legacy = "looting"

        button_stats = self.get_button_sequence_stats()

        return {
            # Legacy compatibility
            'movement_state': movement_state_legacy,
            'waiting_for_mob_approach': False,
            'target_distance': target_distance,
            'current_enemy_position': current_enemy_pos,
            'last_action_time': time.time(),

            # New system fields
            'mode': self.mode,
            'grace_period_active': self.mode == "grace_period",
            'grace_period_remaining': max(0, self.grace_period_duration - (time.time() - self.grace_period_start_time)) if self.mode == "grace_period" else 0,
            'emergency_backstep_active': self.emergency_backstep_active,
            'emergency_backstep_cooldown_remaining': max(0, self.emergency_backstep_cooldown - (time.time() - self.last_emergency_backstep)),
            'last_enemy_seen': time.time() - self.last_enemy_seen_time if self.last_enemy_seen_time > 0 else 0,

            # Click statistics
            'combat_clicks_performed': self.stats['position_clicks'],
            'successful_clicks': self.stats['successful_clicks'],
            'failed_clicks': self.stats['failed_clicks'],
            'click_success_rate': (self.stats['successful_clicks'] / max(1, self.stats['position_clicks'])) * 100,
            'last_combat_click_ago': time.time() - self.last_combat_click,
            'last_loot_click_ago': time.time() - self.last_loot_click,
            'last_successful_method': self.last_successful_method,

            # Method statistics
            'method_stats': self.stats['method_stats'].copy(),

            # Button sequence statistics
            'button_sequence_enabled': button_stats['enabled'],
            'button_sequence_total_cycles': button_stats['total_cycles'],
            'button_sequence_successful_cycles': button_stats['successful_cycles'],
            'button_sequence_total_presses': button_stats['total_presses'],
            'button_sequence_cycle_success_rate': button_stats['cycle_success_rate'],
            'button_sequence_active': button_stats['sequence_active'],
            'button_sequence_time_until_next': button_stats['time_until_next_cycle'],
            'button_sequence_time_since_last': button_stats['time_since_last_cycle'],
            'button_sequence_next_cycle_formatted': button_stats['next_cycle_formatted'],

            # General statistics
            'stats': self.stats.copy()
        }