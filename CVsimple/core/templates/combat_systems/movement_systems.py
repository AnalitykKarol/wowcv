"""
Movement Systems - Systemy ruchu zintegrowane z InputHandler
Przeniesienie ContinuousMovement z eliminacją duplikacji kodu
"""
import time
import random
from typing import Optional
from .input_handler import InputHandler


class ContinuousMovement:
    """
    Continuous Movement System - Płynny system ruchu z W jako bazą
    IDENTYCZNY z continuous_movement.py ale używa wspólnego InputHandler
    """
    def __init__(self, input_handler: InputHandler = None, logger=None):
        # Jeśli nie podano input_handler, stwórz własny (backwards compatibility)
        self.input_handler = input_handler if input_handler else InputHandler(logger)
        self.logger = logger

        # Virtual key codes - pobrane z InputHandler
        vk_codes = self.input_handler.get_vk_codes()
        self.VK_W, self.VK_A, self.VK_S, self.VK_D = vk_codes['W'], vk_codes['A'], vk_codes['S'], vk_codes['D']

        # === SYSTEM STATE === (identyczne z oryginałem)
        self.enabled = False
        self.w_always_active = False  # W trzymane cały czas w exploration
        self.w_key_pressed = False  # Czy W jest aktualnie wciśnięte

        # === TURN SYSTEM (A/D skręty) === (identyczne z oryginałem)
        self.current_turn_key: Optional[int] = None  # Aktualny skręt A lub D
        self.turn_active = False
        self.turn_start_time = 0
        self.turn_duration = 0
        self.turn_change_time = 0  # Kiedy zmienić następny skręt

        # Turn timing (domyślne wartości)
        self.turn_duration_min = 0.3
        self.turn_duration_max = 0.8
        self.turn_interval_min = 1.0  # Jak często zmieniać skręty
        self.turn_interval_max = 4.0

        # Turn probabilities (wagi kierunków)
        self.turn_left_chance = 0.45  # A key
        self.turn_right_chance = 0.45  # D key
        self.turn_straight_chance = 0.10  # Bez skrętu

        # === RARE EVENTS SYSTEM === (identyczne z oryginałem)
        self.rare_event_time = 0  # Kiedy sprawdzić rare eventy
        self.rare_event_interval_min = 3.0
        self.rare_event_interval_max = 8.0

        # Micro pause settings
        self.micro_pause_chance = 0.015  # 1.5% szans
        self.micro_pause_active = False
        self.micro_pause_start_time = 0
        self.micro_pause_duration = 0
        self.micro_pause_min_duration = 0.2
        self.micro_pause_max_duration = 0.5

        # Short backup settings
        self.backup_chance = 0.008  # 0.8% szans
        self.backup_active = False
        self.backup_start_time = 0
        self.backup_duration = 0
        self.backup_min_duration = 0.3
        self.backup_max_duration = 0.8

        # === STATISTICS === (identyczne z oryginałem)
        self.stats = {
            'session_start_time': time.time(),
            'w_uptime_total': 0.0,
            'w_uptime_percent': 0.0,
            'total_turns': 0,
            'left_turns': 0,
            'right_turns': 0,
            'straight_periods': 0,
            'micro_pauses': 0,
            'backup_events': 0
        }

    def log(self, message: str):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)

    # === MAIN CONTROL === (identyczne z oryginałem)
    def enable(self):
        """Enable continuous movement system"""
        self.enabled = True
        self.log("🚶 Continuous Movement: ENABLED")

    def disable(self):
        """Disable continuous movement system"""
        self.enabled = False
        self.log("🚶 Continuous Movement: DISABLED")

    def start_continuous_movement(self, hwnd: int):
        """Start continuous movement system"""
        if not self.enabled or self.w_always_active:
            return

        current_time = time.time()

        # Start W key - UŻYWA InputHandler
        if self.send_key_down(hwnd, self.VK_W):
            self.w_always_active = True
            self.w_key_pressed = True
            self.stats['session_start_time'] = current_time

            # Schedule first turn change
            self.turn_change_time = current_time + random.uniform(self.turn_interval_min, self.turn_interval_max)

            # Schedule first rare event check
            self.rare_event_time = current_time + random.uniform(self.rare_event_interval_min,
                                                                 self.rare_event_interval_max)

            self.log("🚶 Continuous movement STARTED - W always active")
        else:
            self.log("❌ Failed to start continuous movement")

    def stop_continuous_movement(self, hwnd: int):
        """Stop continuous movement system"""
        if not self.w_always_active:
            return

        # Stop all keys - UŻYWA InputHandler
        if self.w_key_pressed:
            self.send_key_up(hwnd, self.VK_W)
            self.w_key_pressed = False

        if self.current_turn_key:
            self.send_key_up(hwnd, self.current_turn_key)
            self.current_turn_key = None
            self.turn_active = False

        if self.backup_active:
            self.send_key_up(hwnd, self.VK_S)
            self.backup_active = False

        self.w_always_active = False
        self.micro_pause_active = False

        self.log("🛑 Continuous movement STOPPED")

    def update(self, hwnd: int, mode: str):
        """Main update function - call every frame during exploration"""
        if not self.enabled:
            return

        # Only work in exploration mode
        if mode != "exploration":
            if self.w_always_active:
                self.stop_continuous_movement(hwnd)
            return

        # Start system if not active
        if not self.w_always_active:
            self.start_continuous_movement(hwnd)
            return

        current_time = time.time()

        # 1. Ensure W is pressed (if not in micro pause)
        if not self.micro_pause_active and not self.w_key_pressed:
            if self.send_key_down(hwnd, self.VK_W):
                self.w_key_pressed = True

        # 2. Update ongoing turn
        self._update_current_turn(hwnd, current_time)

        # 3. Check if time to change turn direction
        if current_time >= self.turn_change_time:
            self._change_turn_direction(hwnd, current_time)

        # 4. Update rare events
        self._update_rare_events(hwnd, current_time)

        # 5. Check for rare event triggers
        if current_time >= self.rare_event_time:
            self._check_rare_events(hwnd, current_time)

    # === TURN MANAGEMENT === (identyczne z oryginałem)
    def _update_current_turn(self, hwnd: int, current_time: float):
        """Update ongoing turn"""
        if not self.turn_active:
            return

        # Check if turn should end
        if current_time - self.turn_start_time >= self.turn_duration:
            if self.current_turn_key:
                self.send_key_up(hwnd, self.current_turn_key)
                self.current_turn_key = None
            self.turn_active = False

    def _change_turn_direction(self, hwnd: int, current_time: float):
        """Change turn direction"""
        # Stop current turn if active
        if self.current_turn_key:
            self.send_key_up(hwnd, self.current_turn_key)
            self.current_turn_key = None
            self.turn_active = False

        # Don't start new turn during rare events
        if self.micro_pause_active or self.backup_active:
            self._schedule_next_turn_change(current_time)
            return

        # Choose new direction
        rand = random.random()
        if rand < self.turn_left_chance:
            new_turn_key = self.VK_A
            direction = "LEFT"
            self.stats['left_turns'] += 1
        elif rand < self.turn_left_chance + self.turn_right_chance:
            new_turn_key = self.VK_D
            direction = "RIGHT"
            self.stats['right_turns'] += 1
        else:
            new_turn_key = None
            direction = "STRAIGHT"
            self.stats['straight_periods'] += 1

        # Apply new turn
        if new_turn_key:
            if self.send_key_down(hwnd, new_turn_key):
                self.current_turn_key = new_turn_key
                self.turn_active = True
                self.turn_start_time = current_time
                self.turn_duration = random.uniform(self.turn_duration_min, self.turn_duration_max)
                self.stats['total_turns'] += 1

                self.log(f"🔄 Turn: {direction} for {self.turn_duration:.2f}s")
            else:
                self.log(f"❌ Failed to start turn: {direction}")
        else:
            self.log(f"➡️ Straight ahead")

        self._schedule_next_turn_change(current_time)

    def _schedule_next_turn_change(self, current_time: float):
        """Schedule next turn change"""
        interval = random.uniform(self.turn_interval_min, self.turn_interval_max)
        self.turn_change_time = current_time + interval

    # === RARE EVENTS === (identyczne z oryginałem)
    def _update_rare_events(self, hwnd: int, current_time: float):
        """Update ongoing rare events"""
        # Update micro pause
        if self.micro_pause_active:
            if current_time - self.micro_pause_start_time >= self.micro_pause_duration:
                # Resume W key
                if self.send_key_down(hwnd, self.VK_W):
                    self.w_key_pressed = True
                self.micro_pause_active = False
                self.log("▶️ Micro pause ended - resuming movement")

        # Update backup
        if self.backup_active:
            if current_time - self.backup_start_time >= self.backup_duration:
                self.send_key_up(hwnd, self.VK_S)
                # Resume W key
                if self.send_key_down(hwnd, self.VK_W):
                    self.w_key_pressed = True
                self.backup_active = False
                self.log("▶️ Backup ended - resuming forward")

    def _check_rare_events(self, hwnd: int, current_time: float):
        """Check and trigger rare events"""
        rand = random.random()

        if rand < self.micro_pause_chance:
            self._trigger_micro_pause(hwnd, current_time)
        elif rand < self.micro_pause_chance + self.backup_chance:
            self._trigger_backup(hwnd, current_time)

        # Schedule next rare event check
        interval = random.uniform(self.rare_event_interval_min, self.rare_event_interval_max)
        self.rare_event_time = current_time + interval

    def _trigger_micro_pause(self, hwnd: int, current_time: float):
        """Trigger micro pause"""
        if self.micro_pause_active or self.backup_active:
            return

        # Stop W key
        if self.w_key_pressed:
            self.send_key_up(hwnd, self.VK_W)
            self.w_key_pressed = False

        self.micro_pause_active = True
        self.micro_pause_start_time = current_time
        self.micro_pause_duration = random.uniform(self.micro_pause_min_duration, self.micro_pause_max_duration)
        self.stats['micro_pauses'] += 1

        self.log(f"⏸️ Micro pause for {self.micro_pause_duration:.2f}s")

    def _trigger_backup(self, hwnd: int, current_time: float):
        """Trigger short backup"""
        if self.backup_active or self.micro_pause_active:
            return

        # Stop W key and start S
        if self.w_key_pressed:
            self.send_key_up(hwnd, self.VK_W)
            self.w_key_pressed = False

        if self.send_key_down(hwnd, self.VK_S):
            self.backup_active = True
            self.backup_start_time = current_time
            self.backup_duration = random.uniform(self.backup_min_duration, self.backup_max_duration)
            self.stats['backup_events'] += 1

            self.log(f"⬅️ Backup for {self.backup_duration:.2f}s")

    # === STATUS AND STATS === (identyczne z oryginałem)
    def get_status(self) -> str:
        """Get current movement status"""
        if not self.enabled:
            return "🔴 DISABLED"

        if not self.w_always_active:
            return "🔴 STOPPED"

        if self.micro_pause_active:
            remaining = self.micro_pause_duration - (time.time() - self.micro_pause_start_time)
            return f"⏸️ PAUSE ({remaining:.1f}s)"
        elif self.backup_active:
            remaining = self.backup_duration - (time.time() - self.backup_start_time)
            return f"⬅️ BACKUP ({remaining:.1f}s)"
        else:
            parts = ["🚶 W+"]

            if self.turn_active and self.current_turn_key:
                turn_name = "A" if self.current_turn_key == self.VK_A else "D"
                remaining = self.turn_duration - (time.time() - self.turn_start_time)
                parts.append(f"{turn_name}({remaining:.1f}s)")
            else:
                parts.append("→")

            return "".join(parts)

    def get_stats(self) -> dict:
        """Get continuous movement statistics"""
        self._update_uptime_stats()
        return self.stats.copy()

    def _update_uptime_stats(self):
        """Update W uptime statistics"""
        current_time = time.time()
        session_duration = current_time - self.stats['session_start_time']

        if session_duration > 0:
            # Estimate W uptime (total time minus pauses and backups)
            pause_time = self.stats['micro_pauses'] * (
                        (self.micro_pause_min_duration + self.micro_pause_max_duration) / 2)
            backup_time = self.stats['backup_events'] * ((self.backup_min_duration + self.backup_max_duration) / 2)

            w_uptime = session_duration - pause_time - backup_time
            self.stats['w_uptime_total'] = w_uptime
            self.stats['w_uptime_percent'] = (w_uptime / session_duration) * 100

    # === CONFIGURATION === (identyczne z oryginałem)
    def configure(self, turn_duration_min: float = 0.3, turn_duration_max: float = 0.8,
                  turn_interval_min: float = 1.0, turn_interval_max: float = 4.0,
                  left_chance: float = 0.45, right_chance: float = 0.45, straight_chance: float = 0.10,
                  pause_chance: float = 0.015, backup_chance: float = 0.008):
        """Configure continuous movement system"""
        self.turn_duration_min = turn_duration_min
        self.turn_duration_max = turn_duration_max
        self.turn_interval_min = turn_interval_min
        self.turn_interval_max = turn_interval_max

        # Normalize probabilities
        total = left_chance + right_chance + straight_chance
        self.turn_left_chance = left_chance / total
        self.turn_right_chance = right_chance / total
        self.turn_straight_chance = straight_chance / total

        self.micro_pause_chance = pause_chance
        self.backup_chance = backup_chance

        self.log(f"🔧 Continuous movement configured:")
        self.log(f"   Turn duration: {turn_duration_min}-{turn_duration_max}s")
        self.log(f"   Turn interval: {turn_interval_min}-{turn_interval_max}s")
        self.log(
            f"   Probabilities: L{left_chance * 100:.0f}% R{right_chance * 100:.0f}% S{straight_chance * 100:.0f}%")
        self.log(f"   Rare events: pause {pause_chance * 100:.1f}%, backup {backup_chance * 100:.1f}%")

    def emergency_stop(self, hwnd: int):
        """Emergency stop all movement"""
        if self.w_key_pressed:
            self.send_key_up(hwnd, self.VK_W)
            self.w_key_pressed = False

        if self.current_turn_key:
            self.send_key_up(hwnd, self.current_turn_key)
            self.current_turn_key = None
            self.turn_active = False

        if self.backup_active:
            self.send_key_up(hwnd, self.VK_S)
            self.backup_active = False

        self.w_always_active = False
        self.micro_pause_active = False

        self.log("🚨 EMERGENCY STOP: Continuous movement")

    # === KEY FUNCTIONS - DELEGOWANE DO InputHandler ===
    def send_key_down(self, hwnd: int, vk_code: int) -> bool:
        """Send key down message - delegated to InputHandler"""
        return self.input_handler.send_key_down(hwnd, vk_code)

    def send_key_up(self, hwnd: int, vk_code: int) -> bool:
        """Send key up message - delegated to InputHandler"""
        return self.input_handler.send_key_up(hwnd, vk_code)