"""
Continuous Movement System - Modular Component
Handles automatic W+A/D movement with micro pauses and backup events
"""
import time
import random
from typing import Optional, Dict, Any


class ContinuousMovementSystem:
    def __init__(self, logger=None):
        self.logger = logger

        # Virtual key codes
        self.VK_W, self.VK_A, self.VK_S, self.VK_D = 0x57, 0x41, 0x53, 0x44

        # System state
        self.enabled = True
        self.w_always_active = False  # W held continuously in exploration
        self.w_key_pressed = False  # Whether W is currently pressed

        # Turn system (A/D turns)
        self.current_turn_key: Optional[int] = None  # Current turn A or D
        self.turn_active = False
        self.turn_start_time = 0
        self.turn_duration = 0
        self.turn_change_time = 0  # When to change next turn

        # Turn timing
        self.turn_duration_min = 0.3
        self.turn_duration_max = 0.8
        self.turn_interval_min = 1.0  # How often to change turns
        self.turn_interval_max = 4.0

        # Turn probabilities (direction weights)
        self.turn_left_chance = 0.45  # A key
        self.turn_right_chance = 0.45  # D key
        self.turn_straight_chance = 0.10  # No turn

        # Rare events system
        self.rare_event_time = 0
        self.rare_event_interval_min = 3.0
        self.rare_event_interval_max = 8.0

        # Micro pause
        self.micro_pause_chance = 0.015  # 1.5% chance
        self.micro_pause_active = False
        self.micro_pause_start_time = 0
        self.micro_pause_duration = 0
        self.micro_pause_min_duration = 0.2
        self.micro_pause_max_duration = 0.5

        # Short backup
        self.backup_chance = 0.008  # 0.8% chance
        self.backup_active = False
        self.backup_start_time = 0
        self.backup_duration = 0
        self.backup_min_duration = 0.3
        self.backup_max_duration = 0.8

        # Statistics
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

    def start_continuous_movement(self, hwnd: int, send_key_down_func) -> bool:
        """Start continuous movement system"""
        if not self.enabled or self.w_always_active:
            return False

        current_time = time.time()

        # Start W key
        if send_key_down_func(hwnd, self.VK_W):
            self.w_always_active = True
            self.w_key_pressed = True
            self.stats['session_start_time'] = current_time

            # Schedule first turn change
            self.turn_change_time = current_time + random.uniform(self.turn_interval_min, self.turn_interval_max)

            # Schedule first rare event check
            self.rare_event_time = current_time + random.uniform(self.rare_event_interval_min,
                                                                 self.rare_event_interval_max)

            self.log("🚶 Continuous movement STARTED - W always active")
            return True
        else:
            self.log("❌ Failed to start continuous movement")
            return False

    def stop_continuous_movement(self, hwnd: int, send_key_up_func) -> bool:
        """Stop continuous movement system"""
        if not self.w_always_active:
            return False

        # Stop all keys
        if self.w_key_pressed:
            send_key_up_func(hwnd, self.VK_W)
            self.w_key_pressed = False

        if self.current_turn_key:
            send_key_up_func(hwnd, self.current_turn_key)
            self.current_turn_key = None
            self.turn_active = False

        if self.backup_active:
            send_key_up_func(hwnd, self.VK_S)
            self.backup_active = False

        self.w_always_active = False
        self.micro_pause_active = False

        self.log("🛑 Continuous movement STOPPED")
        return True

    def update_continuous_movement(self, hwnd: int, mode: str, send_key_down_func, send_key_up_func, last_detection_time=None):
        """Update continuous movement system with detection validation"""
        if not self.enabled:
            return

        # Only work in exploration mode
        if mode != "exploration":
            if self.w_always_active:
                self.stop_continuous_movement(hwnd, send_key_up_func)
            return

        # CRITICAL: Check detection data freshness
        current_time = time.time()
        if last_detection_time is not None:
            time_since_detection = current_time - last_detection_time
            if time_since_detection > 1.0:  # No detections for 1 second
                self.log(f"⚠️ No detections for {time_since_detection:.1f}s - stopping exploration movement")
                self.stop_continuous_movement(hwnd, send_key_up_func)
                return

        # Start system if not active
        if not self.w_always_active:
            self.start_continuous_movement(hwnd, send_key_down_func)
            return

        current_time = time.time()

        # 1. Ensure W is pressed (if not in micro pause)
        if not self.micro_pause_active and not self.w_key_pressed:
            if send_key_down_func(hwnd, self.VK_W):
                self.w_key_pressed = True

        # 2. Update ongoing turn
        self._update_current_turn(hwnd, current_time, send_key_up_func)

        # 3. Check if time to change turn direction
        if current_time >= self.turn_change_time:
            self._change_turn_direction(hwnd, current_time, send_key_down_func, send_key_up_func)

        # 4. Update rare events
        self._update_rare_events(hwnd, current_time, send_key_down_func)

        # 5. Check for rare event triggers
        if current_time >= self.rare_event_time:
            self._check_rare_events(hwnd, current_time, send_key_down_func, send_key_up_func)

    def _update_current_turn(self, hwnd: int, current_time: float, send_key_up_func):
        """Update ongoing turn"""
        if not self.turn_active:
            return

        # Check if turn should end
        if current_time - self.turn_start_time >= self.turn_duration:
            if self.current_turn_key:
                send_key_up_func(hwnd, self.current_turn_key)
                self.current_turn_key = None
            self.turn_active = False

    def _change_turn_direction(self, hwnd: int, current_time: float, send_key_down_func, send_key_up_func):
        """Change turn direction"""
        # Stop current turn if active
        if self.current_turn_key:
            send_key_up_func(hwnd, self.current_turn_key)
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
            if send_key_down_func(hwnd, new_turn_key):
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

    def _update_rare_events(self, hwnd: int, current_time: float, send_key_down_func):
        """Update ongoing rare events"""
        # Update micro pause
        if self.micro_pause_active:
            if current_time - self.micro_pause_start_time >= self.micro_pause_duration:
                # Resume W key
                if send_key_down_func(hwnd, self.VK_W):
                    self.w_key_pressed = True
                self.micro_pause_active = False
                self.log("▶️ Micro pause ended - resuming movement")

        # Update backup
        if self.backup_active:
            if current_time - self.backup_start_time >= self.backup_duration:
                # Note: send_key_up for S will be handled by the calling function
                # Resume W key
                if send_key_down_func(hwnd, self.VK_W):
                    self.w_key_pressed = True
                self.backup_active = False
                self.log("▶️ Backup ended - resuming forward")

    def _check_rare_events(self, hwnd: int, current_time: float, send_key_down_func, send_key_up_func):
        """Check and trigger rare events"""
        rand = random.random()

        if rand < self.micro_pause_chance:
            self._trigger_micro_pause(hwnd, current_time, send_key_up_func)
        elif rand < self.micro_pause_chance + self.backup_chance:
            self._trigger_backup(hwnd, current_time, send_key_down_func, send_key_up_func)

        # Schedule next rare event check
        interval = random.uniform(self.rare_event_interval_min, self.rare_event_interval_max)
        self.rare_event_time = current_time + interval

    def _trigger_micro_pause(self, hwnd: int, current_time: float, send_key_up_func):
        """Trigger micro pause"""
        if self.micro_pause_active or self.backup_active:
            return

        # Stop W key
        if self.w_key_pressed:
            send_key_up_func(hwnd, self.VK_W)
            self.w_key_pressed = False

        self.micro_pause_active = True
        self.micro_pause_start_time = current_time
        self.micro_pause_duration = random.uniform(self.micro_pause_min_duration, self.micro_pause_max_duration)
        self.stats['micro_pauses'] += 1

        self.log(f"⏸️ Micro pause for {self.micro_pause_duration:.2f}s")

    def _trigger_backup(self, hwnd: int, current_time: float, send_key_down_func, send_key_up_func):
        """Trigger short backup"""
        if self.backup_active or self.micro_pause_active:
            return

        # Stop W key and start S
        if self.w_key_pressed:
            send_key_up_func(hwnd, self.VK_W)
            self.w_key_pressed = False

        if send_key_down_func(hwnd, self.VK_S):
            self.backup_active = True
            self.backup_start_time = current_time
            self.backup_duration = random.uniform(self.backup_min_duration, self.backup_max_duration)
            self.stats['backup_events'] += 1

            self.log(f"⬅️ Backup for {self.backup_duration:.2f}s")

    def handle_backup_end(self, hwnd: int, send_key_up_func):
        """Handle the end of backup event (called externally to stop S key)"""
        if self.backup_active:
            send_key_up_func(hwnd, self.VK_S)

    def get_status(self) -> str:
        """Get current continuous movement status"""
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

    def update_stats(self):
        """Update continuous movement statistics"""
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

    def enable(self):
        """Enable continuous movement system"""
        self.enabled = True
        self.log("🚶 Continuous Movement: ENABLED")

    def disable(self):
        """Disable continuous movement system"""
        self.enabled = False
        self.log("🚶 Continuous Movement: DISABLED")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        self.update_stats()
        return self.stats.copy()

    def is_active(self) -> bool:
        """Check if continuous movement is currently active"""
        return self.enabled and self.w_always_active


def create_continuous_movement_system(logger=None) -> ContinuousMovementSystem:
    """Factory function to create a continuous movement system"""
    return ContinuousMovementSystem(logger=logger)