"""
Reactive Combat Controller - Complete Version with HP Recovery System
Enhanced with HP monitoring, automatic health potion usage and modular continuous movement
UPDATED: Fixed infinite recovery loop by disabling problematic recovery system
"""
import win32api
import win32con
import time
import random
import math
from typing import Dict, List, Optional, Tuple, Any
from .hp_based_approach import HPBasedApproachSystem
from .mob_looting import create_mob_looter
from .continuous_movement_system import create_continuous_movement_system



class ReactiveCombatController:
    def __init__(self, logger=None):
        self.logger = logger

        # Virtual key codes
        self.VK_W, self.VK_A, self.VK_S, self.VK_D = 0x57, 0x41, 0x53, 0x44
        self.VK_1, self.VK_2, self.VK_3, self.VK_4 = 0x31, 0x32, 0x33, 0x34
        self.VK_5, self.VK_6, self.VK_7, self.VK_8 = 0x35, 0x36, 0x37, 0x38
        self.VK_MINUS, self.VK_EQUALS = 0xBD, 0xBB
        self.VK_9 = 0x39  # Key for HP potion
        self.VK_R = 0x52  # Key for healing (R)

        # Main system state
        self.mode = "exploration"  # exploration, combat, grace_period
        self.last_enemy_position: Optional[Tuple[float, float]] = None
        self.last_enemy_seen_time = 0
        self.grace_period_duration = random.uniform(4, 5)
        self.grace_period_start_time = 0

        # NEW: Grace period key 7 system
        self.grace_key7_done = False  # Flag czy klawisz 7 już naciśnięty w tym grace period

        # Grace period delay system - czekaj 2-3 klatki przed aktywacją
        self.grace_period_delay_frames = 0
        self.grace_period_delay_needed = 3  # 3 klatki opóźnienia
        self.last_seen_enemy_frame = False

        # Screen configuration - defaults, will be updated by configure_screen_size()
        self.screen_width = 1920
        self.screen_height = 1080
        self.screen_center_x = 960
        self.screen_center_y = 540

        # Camera trapezoid system
        self.trapez_bottom_width = 100  # 10% of 1920
        self.trapez_top_width = 576     # 30% of 1920
        self.trapez_height = 520        # 50% of 1080
        self.trapez_bottom_y = self.screen_center_y
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        # Micro camera movements
        self.micro_camera_duration = random.uniform(0.002, 0.02)
        self.micro_camera_cooldown = random.uniform(0.8, 1.1)
        self.last_camera_adjustment = 0
        self.camera_adjusting = False
        self.camera_key_pressed: Optional[int] = None
        self.camera_key_start_time = 0

        # Attack system
        self.attack_keys = [self.VK_1, self.VK_2, self.VK_3,
                           self.VK_5, self.VK_6, self.VK_7]
        self.attack_weights = {
            self.VK_1: 0.25, self.VK_2: 0.25, self.VK_3: 0.2, self.VK_4: 0.1,
            self.VK_5: 0.07, self.VK_6: 0.2, self.VK_7: 0.1
        }
        self.last_attack_time = 0
        self.attack_interval = random.uniform(5.0, 10.0)

        # Emergency backstep system
        self.emergency_distance_threshold = 80
        self.emergency_backstep_duration = random.uniform(0.2, 1.0)
        self.emergency_backstep_cooldown = random.uniform(5, 10)
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

        # Dynamic Approach System
        self.approach_system = HPBasedApproachSystem(self)

        # Mob Looter System
        self.mob_looter = create_mob_looter(logger=self.logger, enabled=True, timeout=3.0)

        # === CENTRALNA KONFIGURACJA SYSTEMU LECZENIA ===
        self.healing_config = {
            'emergency': {
                'critical_threshold': 25.0,  # Aktywacja emergency w walce przy HP < 25%
                'recovery_threshold': 50.0,   # Cel emergency: HP >= 50%
                'f1_to_9_delay': random.uniform(0.07, 0.1),  # Random delay F1 → 9 (0.07-0.1s)
                'use_f1_sequence': True,        # Użyj sekwencji F1 → 9
                'wait_duration': random.uniform(3.8, 4.2),  # Czas między użyciami mikstur
                'f1_key': 0x70,                # VK_F1
                'potion_key': 0x39               # VK_9 (HP potion)
            },
            'regular': {
                'hp_threshold': 50.0,          # Aktywacja regular recovery przy HP < 30%
                'mp_threshold': 10.0,          # Aktywacja MP recovery przy MP < 10%
                'hp_target': 80.0,              # Cel HP: >= 90%
                'mp_target': 90.0,              # Cel MP: >= 90%
                'f1_to_9_delay': random.uniform(0.07, 0.1),  # Random delay F1 → 9 (0.07-0.1s)
                'use_f1_sequence': True,        # Użyj sekwencji F1 → 9
                'after_combat_key': 0x37,      # VK_7 - po walce
                'mp_potion_key': 0x38,          # VK_8 - MP potion
                'hp_potion_key': 0x39,          # VK_9 - HP potion
                'f1_key': 0x70,                # VK_F1
                'potion_duration': random.uniform(0.1, 0.2),  # Jak długo trzymać miksturę
                'after_key7_wait': random.uniform(4, 5),    # Czekanie po klawiszu 7
                'regen_check_interval': 0.5,    # Sprawdzanie regeneracji
                'exploration_check_interval': 5.0, # Sprawdzanie w exploration
                'hp_retry_timeout': 3.0,         # Retry HP po timeout
                'max_hp_attempts': 5               # Max prób HP
            }
        }

        # Continuous Movement System - MODULAR
        self.continuous_movement = create_continuous_movement_system(logger=self.logger)
        self.continuous_movement.enabled = True  # ← TUTAJ wyłącz od razu

        
        # FIXED: Placeholder for bars analyzer (will be set externally)
        self.bars_analyzer = None
        self._hp_debug_counter = 0

        # === EMERGENCY HEALING SYSTEM ===
        self.emergency_healing_active = False
        self.emergency_healing_start_time = 0
        self.emergency_healing_last_r = 0
        self.emergency_healing_interval = random.uniform(1.0, 2.0)  # 1-2s between R presses

        # === POST-COMBAT HEALING SYSTEM ===
        self.post_combat_healing_active = False
        self.post_combat_healing_start_time = 0
        self.post_combat_healing_last_r = 0
        self.post_combat_healing_interval = random.uniform(2.0, 3.0)  # 2-3s between R presses (slower than emergency)
        self.post_combat_healing_triggered = False  # Prevent re-triggering in same combat session

        # Statistics
        self.stats = {
            'combat_sessions': 0,
            'camera_adjustments': 0,
            'emergency_backsteps': 0,
            'position_clicks': 0,
            'successful_clicks': 0,
            'failed_clicks': 0,
            'emergency_healings': 0,
            'emergency_healing_time_total': 0.0,
            'post_combat_healings': 0,
            'post_combat_healing_time_total': 0.0,
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
        self.button_sequence_interval_base = 4 * 60  # 4 minutes
        self.button_sequence_interval_variance = 1 * 60  # ±1 minute (4-5 minutes range)
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

    # === FIXED: HP/MP DETECTION METHODS ===
    def set_bars_analyzer(self, bars_analyzer):
        """Przypisz PlayerBarsAnalyzer do combat controller"""
        self.bars_analyzer = bars_analyzer
        self.log("🔗 Bars analyzer connected to combat controller")

        # Opcjonalnie: integruj z systemem callbacków
        if hasattr(bars_analyzer, 'integrate_with_combat_controller'):
            bars_analyzer.integrate_with_combat_controller(self)

    def get_current_hp_from_gui(self) -> float:
        """Get current HP from GUI data (not from screenshot) - FIXED"""
        if hasattr(self, 'bars_analyzer') and self.bars_analyzer and hasattr(self.bars_analyzer, 'hp_enabled') and self.bars_analyzer.hp_enabled:
            hp_value = self.bars_analyzer.hp_stats.get('last_hp_value', 100.0)

            # Debug log co 10 sprawdzeń
            self._hp_debug_counter += 1
            if self._hp_debug_counter % 20 == 0:
                self.log(f"🩸 Current HP from analyzer: {hp_value:.1f}%")

            return hp_value

        
        # Ostatni fallback - tylko raz w logach
        if self._hp_debug_counter == 1:
            self.log("⚠️ No HP data available - using fallback 100%")
        return 100.0

    def get_current_mp_from_gui(self) -> float:
        """Get current MP from GUI data - FIXED"""
        if (hasattr(self, 'bars_analyzer') and self.bars_analyzer and
            hasattr(self.bars_analyzer, 'mana_enabled') and self.bars_analyzer.mana_enabled):
            return self.bars_analyzer.mana_stats.get('last_mana_value', 100.0)

        # Fallback - zakładaj pełne MP jeśli nie ma danych
        return 100.0

    
    # === CONTINUOUS MOVEMENT SYSTEM INTERFACE ===
    def enable_continuous_movement(self):
        """Enable continuous movement system"""
        self.continuous_movement.enable()

    def disable_continuous_movement(self):
        """Disable continuous movement system"""
        self.continuous_movement.disable()

    def configure_continuous_movement(self, turn_duration_min: float = 0.3, turn_duration_max: float = 0.8,
                                    turn_interval_min: float = 1.0, turn_interval_max: float = 4.0,
                                    left_chance: float = 0.45, right_chance: float = 0.45, straight_chance: float = 0.10,
                                    pause_chance: float = 0.015, backup_chance: float = 0.008):
        """Configure continuous movement system"""
        self.continuous_movement.configure(
            turn_duration_min=turn_duration_min,
            turn_duration_max=turn_duration_max,
            turn_interval_min=turn_interval_min,
            turn_interval_max=turn_interval_max,
            left_chance=left_chance,
            right_chance=right_chance,
            straight_chance=straight_chance,
            pause_chance=pause_chance,
            backup_chance=backup_chance
        )

    def get_continuous_movement_status(self) -> str:
        """Get current continuous movement status"""
        return self.continuous_movement.get_status()

    
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

    # === GRACE PERIOD KEY 7 SYSTEM ===
    def _press_grace_key7(self, hwnd) -> bool:
        """Naciśnij klawisz 7 w grace period"""
        try:
            vk_7 = 0x37  # VK code dla klawisza '7'

            if not hwnd:
                self.log("❌ Invalid hwnd for grace key 7")
                return False

            success_down = self.send_key_down(hwnd, vk_7)
            if success_down:
                time.sleep(0.1)  # 100ms hold
                success_up = self.send_key_up(hwnd, vk_7)
                return success_up
            return False

        except Exception as e:
            self.log(f"❌ Error pressing grace key 7: {e}")
            return False

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
        if getattr(self, 'approach_escape_active', False):
            return False  # Nie rób camera adjust podczas approach escape!
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
        """Check if emergency backstep is needed - ALWAYS IN COMBAT"""
        dx = enemy_x - self.screen_center_x
        dy = enemy_y - self.screen_center_y
        distance = math.sqrt(dx*dx + dy*dy)

        # ZAWSZE uruchamiaj backstep w walce (random szansa)
        if self.mode == "combat":
            return random.random() < 0.1  # 10% szansa na krok do tyłu w każdej klatce

        return distance < self.emergency_distance_threshold

    def start_emergency_backstep(self, hwnd: int) -> bool:
        """Start emergency backstep maneuver"""
        current_time = time.time()
        if current_time - self.last_emergency_backstep < self.emergency_backstep_cooldown:
            return False

        # Zwolnij klawisze przed dodaniem S
        if self.camera_key_pressed:
            self.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_key_pressed = None
            self.camera_adjusting = False

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

            # Inform game where mouse is
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
            time.sleep(0.001)  # Short pause

            result1 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, 0, lParam)
            time.sleep(random.uniform(0.005, 0.015))
            result2 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lParam)

            success = bool(result1 and result2)
            return success
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
                    if method_func(hwnd, x, y):
                        self.last_successful_method = method_name
                        self.stats['successful_clicks'] += 1
                        self.stats['position_clicks'] += 1
                        self.update_click_timers(is_loot)
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

    # === ATTACK SYSTEM ===
    def simple_attack(self, hwnd: int) -> bool:
        """Press key 1 every 5-10 seconds during combat"""
        current_time = time.time()
        if current_time - self.last_attack_time >= self.attack_interval:
            if self.send_key_press(hwnd, self.VK_1):
                self.last_attack_time = current_time
                self.attack_interval = random.uniform(5.0, 10.0)
                return True
        return False

    def heal_with_r(self, hwnd: int) -> bool:
        """Leczenie pod klawiszem R - główna metoda regeneracji"""
        try:
            # Naciśnij klawisz R
            success1 = self.send_key_down(hwnd, self.VK_R)
            if not success1:
                return False
            time.sleep(0.1)  # 100ms hold
            success2 = self.send_key_up(hwnd, self.VK_R)

            if success1 and success2:
                self.log("R - leczenie")
                return True
            return False
        except Exception as e:
            self.log(f"Blad leczenia R: {e}")
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

    def release_all_movement_keys(self, hwnd: int) -> bool:
        """Zwolnij wszystkie klawisze ruchu (W, A, S, D) - bezpieczna metoda cleanup"""
        released_any = False

        # Zawsze zwolnij WSZYSTKIE klawisze ruchu dla bezpieczeństwa
        for vk_code, name in [(self.VK_W, 'W'), (self.VK_A, 'A'),
                               (self.VK_S, 'S'), (self.VK_D, 'D')]:
            if self.send_key_up(hwnd, vk_code):
                released_any = True

        # Reset flag które mogą śledzić stan klawiszy
        self.emergency_backstep_active = False
        if self.camera_key_pressed:
            self.camera_key_pressed = None
            self.camera_adjusting = False

        if released_any:
            self.log("🧹 Wszystkie klawisze ruchu zwolnione (W, A, S, D)")

        return released_any

    # === MAIN UPDATE LOOP - UPDATED WITH NEW HP/MP RECOVERY SYSTEM ===
    def update(self, hwnd: int, detections: Optional[List[Dict[str, Any]]] = None):
        """Main update loop - APPROACH DOESN'T BLOCK ATTACKS AND STEERING"""
        current_time = time.time()

        # === EMERGENCY HEALING CHECK - HIGHEST PRIORITY ===
        current_hp = self.get_current_hp_from_gui()
        emergency_config = self.healing_config['emergency']

        if not self.emergency_healing_active:
            # Sprawdź czy aktywować emergency healing
            if current_hp < emergency_config['critical_threshold']:
                self.emergency_healing_active = True
                self.emergency_healing_start_time = current_time
                self.emergency_healing_last_r = 0
                self.emergency_healing_interval = random.uniform(1.0, 2.0)  # 1-2s between R presses
                self.stats['emergency_healings'] += 1

                # Zatrzymaj aktywny backstep przed rozpoczęciem healingu
                if self.emergency_backstep_active:
                    self.send_key_up(hwnd, self.VK_S)
                    self.emergency_backstep_active = False
                    self.log("🚫 Emergency backstep STOPPED for healing")

                self.log(f"🚨 EMERGENCY HEALING ACTIVATED at {current_hp:.1f}% HP (target: {emergency_config['recovery_threshold']}%)")
        else:
            # W trakcie emergency healing
            if current_hp >= emergency_config['recovery_threshold']:
                # Zakończ emergency healing
                healing_time = current_time - self.emergency_healing_start_time
                self.emergency_healing_active = False
                self.stats['emergency_healing_time_total'] += healing_time
                self.log(f"✅ Emergency healing completed in {healing_time:.1f}s (HP: {current_hp:.1f}%)")
            else:
                # W trakcie leczenia - naciśnij R co 1-2s
                if current_time - self.emergency_healing_last_r >= self.emergency_healing_interval:
                    if self.heal_with_r(hwnd):
                        self.emergency_healing_last_r = current_time
                        self.emergency_healing_interval = random.uniform(1.0, 2.0)  # Randomize next interval
                        self.log(f"🩺 Emergency healing R pressed (HP: {current_hp:.1f}%, next R in {self.emergency_healing_interval:.1f}s)")

                # BLOKUJ WSZYSTKO INNE PODCZAS EMERGENCY HEALING!
                self.log(f"🩺 Emergency healing in progress... HP: {current_hp:.1f}% (target: {emergency_config['recovery_threshold']}%)")
                return  # BLOKUJ WSZYSTKO INNE!

        # === BUILD ENEMIES LIST FIRST (needed for grace period logic) ===
        enemies = []
        if detections:
            for detection in detections:
                name = detection.get('name', '').lower()
                if any(keyword in name for keyword in ['mob', 'enemy', 'monster', 'target', 'health_bar']):
                    enemies.append(detection)

        # === GRACE PERIOD PRIORITY CHECK (higher than post-combat healing) ===
        has_enemies = bool(enemies)
        current_frame_has_enemies = has_enemies

        if self.mode == "combat":
            if current_frame_has_enemies:
                # Wróg jest widoczny - resetuj licznik opóźnienia
                self.last_seen_enemy_frame = True
                self.grace_period_delay_frames = 0
            else:
                # Nie ma wroga w tej klatce - sprawdź opóźnienie
                if self.last_seen_enemy_frame:
                    # Pierwsza klatka bez wroga - zacznij liczyć
                    self.grace_period_delay_frames = 1
                    self.log(f"⏳ Enemy missing - starting grace delay ({self.grace_period_delay_frames}/{self.grace_period_delay_needed})")
                    self.last_seen_enemy_frame = False  # Ustaw na False dla kolejnych klatek
                else:
                    # Kolejne klatki bez wroga
                    self.grace_period_delay_frames += 1
                    if self.grace_period_delay_frames < self.grace_period_delay_needed:
                        # Jeszcze nie czekano wystarczająco długo
                        self.log(f"⏳ Grace delay: {self.grace_period_delay_frames}/{self.grace_period_delay_needed}")
                    else:
                        # Minął wymagany czas - aktywuj grace period
                        self.log("👻 Enemy disappeared - starting grace period (loot)")
                        self.mode = "grace_period"
                        self.grace_period_start_time = current_time
                        self.grace_key7_done = False  # Reset flag dla nowego grace period

                        # NOWE: Zwolnij WSZYSTKIE klawisze ruchu
                        self.release_all_movement_keys(hwnd)

                        # ZATRZYMAJ RUCH PRZY PRZEJŚCIU DO GRACE PERIOD
                        # Zawsze zatrzymuj continuous movement w grace period, niezależnie od flagi
                        if self.continuous_movement.w_always_active or self.continuous_movement.backup_active:
                            self.continuous_movement.stop_continuous_movement(hwnd, self.send_key_up)

        # === POST-COMBAT HEALING CHECK - SECOND PRIORITY ===
        regular_config = self.healing_config['regular']

        # If we're in grace period, handle it immediately (highest priority)
        if self.mode == "grace_period":
            # === NEW: KLAWISZ 7 W GRACE PERIOD ===
            if not self.grace_key7_done:
                if self._press_grace_key7(hwnd):
                    self.grace_key7_done = True
                    self.log("⚔️ Grace period key '7' pressed")
                else:
                    self.log("❌ Failed to press grace period key '7'")

            elapsed = current_time - self.grace_period_start_time

            if elapsed >= self.grace_period_duration:
                self.log("🔄 Grace period ended - returning to exploration")
                self.mode = "exploration"
                self.last_enemy_position = None
                self.grace_key7_done = False  # Reset dla następnego razu

                # NOWE: Zwolnij WSZYSTKIE klawisze ruchu przed wznowieniem ruchu
                self.release_all_movement_keys(hwnd)

                # PRZYWRÓĆ CONTINUOUS MOVEMENT PO GRACE PERIOD
                if self.continuous_movement.enabled:
                    self.continuous_movement.start_continuous_movement(hwnd, self.send_key_down)
            else:
                # During grace period - loot and attack
                remaining = self.grace_period_duration - elapsed

                if int(remaining) != int(remaining + 0.1):
                    self.log(f"📦 Grace period: {remaining:.1f}s remaining")

                if self.last_enemy_position and self.can_loot_click():
                    x, y = self.last_enemy_position
                    self.perform_right_click(hwnd, x, y, is_loot=True)

                # Grace period nie blokuje innych systemów ale ma wyższy priorytet
                return

        # Post-combat healing działa tylko w exploration
        if self.mode == "exploration":
            if not self.post_combat_healing_active:
                # Sprawdź czy aktywować post-combat healing
                if current_hp < regular_config['hp_threshold']:
                    self.post_combat_healing_active = True
                    self.post_combat_healing_start_time = current_time
                    self.post_combat_healing_last_r = 0
                    self.post_combat_healing_interval = random.uniform(2.0, 3.0)  # 2-3s between R presses
                    self.stats['post_combat_healings'] += 1

                    # Zatrzymaj aktywny backstep przed rozpoczęciem healingu
                    if self.emergency_backstep_active:
                        self.send_key_up(hwnd, self.VK_S)
                        self.emergency_backstep_active = False
                        self.log("🚫 Emergency backstep STOPPED for post-combat healing")

                    # NOWE: Zwolnij WSZYSTKIE klawisze ruchu
                    self.release_all_movement_keys(hwnd)
                    self.continuous_movement.stop_continuous_movement(hwnd, self.send_key_up)
                    self.log("🚫 Continuous movement STOPPED for post-combat healing")

                    self.log(f"🏥 POST-COMBAT HEALING ACTIVATED at {current_hp:.1f}% HP (target: {regular_config['hp_target']}%)")
            else:
                # W trakcie post-combat healing
                if current_hp >= regular_config['hp_target']:
                    # Zakończ post-combat healing
                    healing_time = current_time - self.post_combat_healing_start_time
                    self.post_combat_healing_active = False
                    self.stats['post_combat_healing_time_total'] += healing_time
                    self.log(f"✅ Post-combat healing completed in {healing_time:.1f}s (HP: {current_hp:.1f}%)")
                else:
                    # W trakcie leczenia - naciśnij R co 2-3s
                    if current_time - self.post_combat_healing_last_r >= self.post_combat_healing_interval:
                        if self.heal_with_r(hwnd):
                            self.post_combat_healing_last_r = current_time
                            self.post_combat_healing_interval = random.uniform(2.0, 3.0)
                            self.log(f"💚 Post-combat healing R pressed (HP: {current_hp:.1f}%, next R in {self.post_combat_healing_interval:.1f}s)")

                    # Post-combat healing w exploration nie blokuje innych systemów
                    # (ale kolejne sekcje będą checkować czy healing jest aktywne)

        # === RECOVERY SYSTEM DISABLED TO PREVENT INFINITE LOOP ===
        # Old recovery system was causing infinite loop and has been disabled
        # Combat continues without emergency recovery system
        recovery_blocking = False

        # HP Recovery blocking status dla GUI (legacy compatibility)
        hp_recovery_blocking = False  # Recovery system disabled to prevent crashes

        # ANALYZING nie blokuje - można kontynuować

        # === UPDATE INNYCH SYSTEMÓW (tylko jeśli żaden recovery nie blokuje) ===
        self.update_button_sequence_system(hwnd)
        self.update_camera_adjustment(hwnd)
        self.update_emergency_backstep(hwnd)

        # === ZNAJDŹ NAJBLIŻSZEGO WROGA ===
        closest_enemy = None
        if enemies:
            closest_enemy = min(enemies, key=lambda e:
            abs(e.get('center_x', self.screen_center_x) - self.screen_center_x) +
            abs(e.get('center_y', self.screen_center_y) - self.screen_center_y))

        # === APPROACH SYSTEM - NOWA LOGIKA: NIE BLOKUJE ATAKÓW I SKRĘCANIA ===
        approach_active = False
        approach_state = "UNKNOWN"
        approach_blocking_movement = False  # NOWA FLAGA

        if hasattr(self, 'approach_system'):
            approach_active = self.approach_system.update(hwnd, closest_enemy, enemies)
            approach_state = getattr(self.approach_system, 'state', 'UNKNOWN')

            # Approach blokuje TYLKO continuous movement, nie ataki/skręcanie
            approach_blocking_movement = (approach_active and
                                          approach_state in ["APPROACHING", "ESCAPING"])

        # === CHECK ESCAPE - TYLKO TO BLOKUJE WSZYSTKO ===
        if getattr(self, 'approach_escape_active', False):
            self.log("🚨 Approach escape active - blocking other systems")
            return

        # === CONTINUOUS MOVEMENT (blokowane przez healing, approach MOVEMENT, nie przez approach system) ===
        if not self.emergency_backstep_active:
            should_run_continuous = (
                    not approach_blocking_movement and  # ZMIENIONE: używaj nowej flagi
                    not self.post_combat_healing_active and  # BLOKUJ PODCZAS POST-COMBAT HEALING
                    approach_state == "IDLE"
            )

            if should_run_continuous:
                self.continuous_movement.update_continuous_movement(
                    hwnd, self.mode, self.send_key_down, self.send_key_up
                )

                # Handle backup end
                if self.continuous_movement.backup_active:
                    current_time = time.time()
                    if current_time - self.continuous_movement.backup_start_time >= self.continuous_movement.backup_duration:
                        self.continuous_movement.handle_backup_end(hwnd, self.send_key_up)

        # === GŁÓWNA LOGIKA TRYBÓW - NOWA: APPROACH NIE BLOKUJE TEJ SEKCJI ===
        if enemies and closest_enemy:  # DODANE: sprawdź czy closest_enemy istnieje
            # COMBAT MODE - UŻYWA TEGO SAMEGO closest_enemy co approach
            enemy_x = closest_enemy.get('center_x', self.screen_center_x)
            enemy_y = closest_enemy.get('center_y', self.screen_center_y)

            if self.mode != "combat":
                self.log("🎯 Enemy detected - entering combat")
                self.mode = "combat"
                self.stats['combat_sessions'] += 1

                # NOWE: Zwolnij WSZYSTKIE klawisze ruchu
                self.release_all_movement_keys(hwnd)

                self.continuous_movement.stop_continuous_movement(hwnd, self.send_key_up)
                # Reset grace period flag
                self.grace_key7_done = False

                # Reset grace period delay system
                self.grace_period_delay_frames = 0
                self.last_seen_enemy_frame = True

            self.last_enemy_position = (enemy_x, enemy_y)
            self.last_enemy_seen_time = current_time

            # Emergency backstep check - WYŁĄCZONY PODCZAS LECZENIA
            # Nie uruchamiaj backstepu jeśli healing jest aktywny
            if not self.emergency_healing_active and not self.post_combat_healing_active:
                if self.check_emergency_backstep(enemy_x, enemy_y):
                    self.start_emergency_backstep(hwnd)

            # === CAMERA/SKRĘCANIE - DOSTĘPNE PODCZAS APPROACH ===
            # Tylko sprawdź czy approach nie robi escape
            if not getattr(self, 'approach_escape_active', False):
                if not self.is_enemy_in_trapezoid(enemy_x, enemy_y):
                    if not self.camera_adjusting:
                        direction = self.get_camera_adjustment_direction(enemy_x, enemy_y)
                        self.micro_camera_adjust(hwnd, direction)

            # === COMBAT CLICKS - DOSTĘPNE PODCZAS APPROACH ===
            if self.can_combat_click():
                self.perform_right_click(hwnd, enemy_x, enemy_y, is_loot=False)

            # === ATAK 1 co 5-10 sekund ===
            self.simple_attack(hwnd)

        
        # === MOB LOOTING - PRZEKAŻ closest_enemy ===
        if True:  # Recovery system disabled - always allow looting
            # Przekaż tylko najbliższego wroga do lootingu
            loot_enemies = [closest_enemy] if closest_enemy else []
            self.mob_looter.process_frame(self, hwnd, loot_enemies)

    def emergency_stop(self, hwnd: int):
        """Emergency stop all activities - UPDATED"""
        # NOWE: Zwolnij WSZYSTKIE klawisze ruchu jako pierwsze
        self.release_all_movement_keys(hwnd)

        # Potem continuous movement (dla dodatkowego bezpieczeństwa)
        self.continuous_movement.stop_continuous_movement(hwnd, self.send_key_up)

        self.mode = "exploration"
        self.last_enemy_position = None
        self.grace_key7_done = False
        self.log("🚨 EMERGENCY STOP")

    def get_status(self) -> str:
        """Get current status string for display - UPDATED"""
        status_parts = []

        # === HIGHEST PRIORITY: Emergency Healing System ===
        if self.emergency_healing_active:
            current_hp = self.get_current_hp_from_gui()
            target_hp = self.healing_config['emergency']['recovery_threshold']
            elapsed = time.time() - self.emergency_healing_start_time
            next_r_in = max(0, self.emergency_healing_interval - (time.time() - self.emergency_healing_last_r))
            status_parts.append(f"🚨 EMERGENCY HEALING")
            status_parts.append(f"🩸 HP: {current_hp:.1f}% → {target_hp}%")
            status_parts.append(f"⏱️ Time: {elapsed:.1f}s")
            status_parts.append(f"⏰ Next R: {next_r_in:.1f}s")
            return " ".join(status_parts)

        # === SECOND PRIORITY: Post-Combat Healing System ===
        if self.post_combat_healing_active:
            current_hp = self.get_current_hp_from_gui()
            target_hp = self.healing_config['regular']['hp_target']
            elapsed = time.time() - self.post_combat_healing_start_time
            next_r_in = max(0, self.post_combat_healing_interval - (time.time() - self.post_combat_healing_last_r))
            status_parts.append(f"🏥 POST-COMBAT HEALING")
            status_parts.append(f"💚 HP: {current_hp:.1f}% → {target_hp}%")
            status_parts.append(f"⏱️ Time: {elapsed:.1f}s")
            status_parts.append(f"⏰ Next R: {next_r_in:.1f}s")
            return " ".join(status_parts)

        
        if self.mode == "combat":
            status_parts.append("⚔️ COMBAT")
        elif self.mode == "grace_period":
            remaining = self.grace_period_duration - (time.time() - self.grace_period_start_time)
            grace_status = f"📦 GRACE PERIOD ({remaining:.1f}s)"
            if self.grace_key7_done:
                grace_status += " [KEY7:✅]"
            else:
                grace_status += " [KEY7:⏳]"
            status_parts.append(grace_status)
        elif self.mode == "exploration":
            exploration_status = f"🔄 EXPLORATION - {self.get_continuous_movement_status()}"
            status_parts.append(exploration_status)

        if self.emergency_backstep_active:
            status_parts.append("🚨 EMERGENCY BACKSTEP")

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
        """Get comprehensive statistics and status - UPDATED"""
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

        # Get continuous movement stats from modular system
        continuous_movement_stats = self.continuous_movement.get_stats()

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

            
            # Grace period stats
            'grace_key7_done': self.grace_key7_done,

            # Continuous movement statistics (from modular system)
            'continuous_movement_enabled': self.continuous_movement.enabled,
            'continuous_movement_active': self.continuous_movement.is_active(),
            'continuous_movement_stats': continuous_movement_stats,

            # General statistics
            'stats': self.stats.copy()
        }