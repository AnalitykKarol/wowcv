"""
HP Recovery System - Automatic Health Potion Management
Handles critical HP detection, potion usage timing, and recovery monitoring
"""
import time
from typing import Optional, Dict, Any
import random


class HPRecoverySystem:
    def __init__(self, logger=None):
        self.logger = logger

        # System state
        self.active = False
        self.waiting_for_recovery = False
        self.start_time = 0
        self.last_potion_time = 0

        # Configuration
        self.wait_duration = random.uniform(0.8, 1.2) # seconds between potions
        self.recovery_key = 0x39  # VK_9 - health potion key
        self.f1_key = 0x70  # VK_F1 - F1 key
        self.f_key = 0x46  # VK_F - Spirit Wolves key (for future use)
        self.critical_hp_threshold = 20.0  # Below this = critical
        self.recovery_complete_threshold = 50.0  # Above this = recovery complete

        # NEW: F1 → 9 sequence timing
        self.f1_to_9_delay = random.uniform(0.07, 0.1)  # Random delay between F1 and 9 (0.07-0.1s)
        self.f1_duration = random.uniform(0.1, 0.2)   # How long to hold F1
        self.use_f1_sequence = True  # Enable F1 → 9 sequence

        # Player status tracking
        self.player_hp = 100.0
        self.player_mana = 100.0
        self.last_hp_event = None
        self.last_mana_event = None

        # Statistics
        self.stats = {
            'recovery_sessions': 0,
            'potions_used': 0,
            'f1_presses': 0,
            'f_presses': 0,  # Added missing F key statistics
            'total_recovery_time': 0.0,
            'average_recovery_time': 0.0,
            'fastest_recovery': float('inf'),
            'slowest_recovery': 0.0,
            'hp_events_processed': 0,
            'critical_events': 0,
            'warning_events': 0,
            'auto_recoveries': 0
        }

    def log(self, message: str):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)

    def configure(self, potion_key: int = None, f1_key: int = None, f_key: int = None, wait_duration: float = 1.0,
                  critical_threshold: float = 30.0, recovery_threshold: float = 80.0,
                  f1_to_9_delay: float = 0.4, use_f1_sequence: bool = True):
        """Configure HP recovery system parameters"""
        if potion_key is not None:
            self.recovery_key = potion_key
            self.log(f"💊 HP Recovery key set to: {potion_key} (VK code)")

        if f1_key is not None:
            self.f1_key = f1_key
            self.log(f"🔧 F1 key set to: {f1_key} (VK code)")

        if f_key is not None:
            self.f_key = f_key
            self.log(f"🔧 F key set to: {f_key} (VK code)")

        self.wait_duration = wait_duration
        self.critical_hp_threshold = critical_threshold
        self.recovery_complete_threshold = recovery_threshold
        self.f1_to_9_delay = f1_to_9_delay
        self.use_f1_sequence = use_f1_sequence

        self.log(f"⏱️ HP Recovery configured:")
        self.log(f"   Wait duration: {wait_duration}s between potions")
        self.log(f"   Critical threshold: {critical_threshold}%")
        self.log(f"   Recovery threshold: {recovery_threshold}%")
        self.log(f"   F1→9 sequence: {'ENABLED' if use_f1_sequence else 'DISABLED'}")
        self.log(f"   F1→9 delay: {f1_to_9_delay}s")
        self.log(f"   F1 key: {self.f1_key} (VK code)")
        self.log(f"   F key: {self.f_key} (VK code)")

    def handle_hp_event(self, event_type: str, hp_percentage: float):
        """Handle HP events from PlayerBarsAnalyzer"""
        self.player_hp = hp_percentage
        self.last_hp_event = event_type
        self.stats['hp_events_processed'] += 1

        if event_type == "hp_critical":
            self.stats['critical_events'] += 1
            self.trigger_recovery(hp_percentage, "Critical HP detected")
        elif event_type == "hp_warning":
            self.stats['warning_events'] += 1
            # Only trigger if HP is really low (below critical threshold)
            if hp_percentage <= self.critical_hp_threshold:
                self.trigger_recovery(hp_percentage, "Warning HP below critical threshold")
            else:
                self.log(f"⚠️ HP Warning: {hp_percentage:.1f}% (not critical enough)")
        elif event_type == "hp_critical_recovered":
            self.complete_recovery(hp_percentage, "Critical HP recovered")
        elif event_type == "hp_warning_recovered":
            if self.active and hp_percentage >= self.recovery_complete_threshold:
                self.complete_recovery(hp_percentage, "Warning HP recovered above threshold")
            else:
                self.log(f"✅ HP Warning cleared: {hp_percentage:.1f}%")

    def handle_mana_event(self, event_type: str, mana_percentage: float):
        """Handle Mana events from PlayerBarsAnalyzer (for future use)"""
        self.player_mana = mana_percentage
        self.last_mana_event = event_type

        if event_type == "mana_critical":
            self.log(f"🔵 CRITICAL MANA: {mana_percentage:.1f}%")
        elif event_type == "mana_recovered":
            self.log(f"✅ Mana recovered: {mana_percentage:.1f}%")

    def trigger_recovery(self, hp_percentage: float, reason: str = "Manual trigger"):
        """Start HP recovery mode with F1 → 9 sequence"""
        if self.active:
            self.log(f"🔄 HP Recovery already active, current HP: {hp_percentage:.1f}%")
            return False

        self.active = True
        self.waiting_for_recovery = True
        self.start_time = time.time()
        self.last_potion_time = 0  # Reset to use potion immediately

        # Update statistics
        self.stats['recovery_sessions'] += 1

        self.log(f"🚨 HP RECOVERY STARTED: {hp_percentage:.1f}% - {reason}")

        # NEW: Press F1 first if sequence is enabled
        if self.use_f1_sequence:
            self._press_f1_key()

        # Always press F key (Spirit Wolves)
        self._press_f_key()

        return True

    def _press_f1_key(self):
        """Press F1 key immediately when entering recovery mode"""
        # Press F1 immediately and start delay timer
        self._f1_needs_press = False  # Don't need to press later
        self._f1_pressed_time = time.time()
        self.stats['f1_presses'] += 1
        self.log("🔑 F1 key pressed immediately - HP potion will follow after delay")
        return True

    def _press_f_key(self):
        """Press F key when entering recovery mode"""
        # This will be called by the controller in the update method
        # We set a flag to indicate F should be pressed
        self._f_needs_press = True
        self.stats['f_presses'] += 1
        self.log("🔧 F key queued for press")

    def complete_recovery(self, hp_percentage: float, reason: str = "Manual completion"):
        """Complete HP recovery and return to normal operation"""
        if not self.active:
            self.log(f"✅ HP Recovery completion called but not active: {hp_percentage:.1f}%")
            return False

        # Calculate recovery time and update statistics
        recovery_time = time.time() - self.start_time
        self.stats['total_recovery_time'] += recovery_time

        if self.stats['recovery_sessions'] > 0:
            self.stats['average_recovery_time'] = (
                    self.stats['total_recovery_time'] / self.stats['recovery_sessions']
            )

        # Track fastest and slowest recoveries
        if recovery_time < self.stats['fastest_recovery']:
            self.stats['fastest_recovery'] = recovery_time
        if recovery_time > self.stats['slowest_recovery']:
            self.stats['slowest_recovery'] = recovery_time

        # Reset state
        self.active = False
        self.waiting_for_recovery = False
        self.stats['auto_recoveries'] += 1

        self.log(f"✅ HP RECOVERED: {hp_percentage:.1f}% - {reason} - recovery took {recovery_time:.1f}s")
        return True

    def manual_check_recovery(self, current_hp: float) -> bool:
        """Manual check if recovery should be completed"""
        if not self.active:
            return False

        if current_hp >= self.recovery_complete_threshold:
            self.complete_recovery(current_hp, f"Manual check - HP above {self.recovery_complete_threshold}%")
            return True

        return False

    def update(self, hwnd: int, controller) -> bool:
        """Main update loop - returns True if recovery is active and blocking other actions"""
        if not self.active:
            return False

        current_time = time.time()

        # Stop all movements when recovery starts
        if current_time - self.start_time < 0.1:  # First 100ms
            self._stop_all_movement(hwnd, controller)
            self.log("🛑 All movements stopped for HP recovery")

        # NEW: Handle F1 → 9 sequence
        if self.use_f1_sequence and hasattr(self, '_f1_pressed_time'):
            # Check if F1 delay has passed, then use HP potion
            if current_time - self._f1_pressed_time >= self.f1_to_9_delay:
                if self._use_health_potion(hwnd, controller):
                    self.last_potion_time = current_time
                    self.stats['potions_used'] += 1
                    delattr(self, '_f1_pressed_time')  # Remove the flag

                    recovery_elapsed = current_time - self.start_time
                    self.log(f"🔑 F1 → 9 sequence completed - "
                             f"potion used (#{self.stats['potions_used']}) - "
                             f"recovery time: {recovery_elapsed:.1f}s")
                else:
                    self.log("❌ FAILED to use health potion after F1 - trying again in 0.5s")

        # Legacy F1/F key support (if sequence disabled)
        if hasattr(self, '_f1_needs_press') and self._f1_needs_press:
            if self._press_f1_via_controller(hwnd, controller):
                self._f1_needs_press = False
                self.log("🔧 F1 key pressed successfully")
            else:
                self.log("❌ FAILED to press F1 key")

        if hasattr(self, '_f_needs_press') and self._f_needs_press:
            if self._press_f_via_controller(hwnd, controller):
                self._f_needs_press = False
                self.log("🔧 F key pressed successfully")
            else:
                self.log("❌ FAILED to press F key")

        # Manual check for recovery completion
        if hasattr(controller, 'get_current_hp_from_gui'):
            current_hp = controller.get_current_hp_from_gui()
            if self.manual_check_recovery(current_hp):
                return False  # Recovery completed

        # Check if it's time to use another health potion (legacy support)
        if not self.use_f1_sequence and current_time - self.last_potion_time >= self.wait_duration:
            if self._use_health_potion(hwnd, controller):
                self.last_potion_time = current_time
                self.stats['potions_used'] += 1

                recovery_elapsed = current_time - self.start_time
                self.log(f"💊 Health potion used (#{self.stats['potions_used']}) - "
                         f"recovery time: {recovery_elapsed:.1f}s - waiting {self.wait_duration:.1f}s...")
            else:
                self.log("❌ FAILED to use health potion - trying again in 0.5s")
                # Reduce wait time on failure to retry sooner
                self.last_potion_time = current_time - self.wait_duration + 0.5

        return True  # Recovery is active - block other actions

    def _stop_all_movement(self, hwnd: int, controller):
        """Stop all movement systems during recovery"""
        # Stop old movement system
        if hasattr(controller, 'stop_movement'):
            controller.stop_movement(hwnd)

        # Stop continuous movement system
        if hasattr(controller, 'stop_continuous_movement'):
            controller.stop_continuous_movement(hwnd)

        # Stop any ongoing emergency backstep
        if hasattr(controller, 'emergency_backstep_active') and controller.emergency_backstep_active:
            controller.send_key_up(hwnd, controller.VK_S)
            controller.emergency_backstep_active = False

    def _use_health_potion(self, hwnd: int, controller) -> bool:
        """Use health potion via controller's key system"""
        if hasattr(controller, 'send_key_press'):
            return controller.send_key_press(hwnd, self.recovery_key)
        else:
            self.log("❌ Controller doesn't have send_key_press method")
            return False

    def _press_f1_via_controller(self, hwnd: int, controller) -> bool:
        """Press F1 key via controller's key system"""
        if hasattr(controller, 'send_key_press'):
            return controller.send_key_press(hwnd, self.f1_key)
        else:
            self.log("❌ Controller doesn't have send_key_press method for F1")
            return False

    def _press_f_via_controller(self, hwnd: int, controller) -> bool:
        """Press F key via controller's key system"""
        if hasattr(controller, 'send_key_press'):
            return controller.send_key_press(hwnd, self.f_key)
        else:
            self.log("❌ Controller doesn't have send_key_press method for F")
            return False

    def force_stop(self):
        """Force stop HP recovery (emergency stop)"""
        if self.active:
            self.active = False
            self.waiting_for_recovery = False
            # Clear F1 flag if set
            if hasattr(self, '_f1_needs_press'):
                self._f1_needs_press = False
            # Clear F flag if set
            if hasattr(self, '_f_needs_press'):
                self._f_needs_press = False
            self.log("🚨 HP Recovery FORCE STOPPED")
            return True
        return False

    def is_active(self) -> bool:
        """Check if HP recovery is currently active"""
        return self.active

    def get_status(self) -> str:
        """Get current HP recovery status for display"""
        if not self.active:
            return ""

        current_time = time.time()
        recovery_elapsed = current_time - self.start_time
        next_potion_in = self.wait_duration - (current_time - self.last_potion_time)

        if next_potion_in <= 0:
            return f"💊 HP RECOVERY ({recovery_elapsed:.1f}s) - POTION READY"
        else:
            return f"💊 HP RECOVERY ({recovery_elapsed:.1f}s) - next potion in {next_potion_in:.1f}s"

    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed status information"""
        current_time = time.time()

        if self.active:
            recovery_elapsed = current_time - self.start_time
            next_potion_in = max(0, self.wait_duration - (current_time - self.last_potion_time))
        else:
            recovery_elapsed = 0
            next_potion_in = 0

        return {
            'active': self.active,
            'waiting_for_recovery': self.waiting_for_recovery,
            'recovery_elapsed': recovery_elapsed,
            'next_potion_in': next_potion_in,
            'player_hp': self.player_hp,
            'player_mana': self.player_mana,
            'last_hp_event': self.last_hp_event,
            'last_mana_event': self.last_mana_event,
            'recovery_key': self.recovery_key,
            'f1_key': self.f1_key,
            'f_key': self.f_key,
            'wait_duration': self.wait_duration,
            'critical_threshold': self.critical_hp_threshold,
            'recovery_threshold': self.recovery_complete_threshold
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        stats = self.stats.copy()

        # Add calculated fields
        if stats['recovery_sessions'] > 0:
            stats['potions_per_session'] = stats['potions_used'] / stats['recovery_sessions']
            stats['f1_per_session'] = stats['f1_presses'] / stats['recovery_sessions']
            stats['f_per_session'] = stats['f_presses'] / stats['recovery_sessions']
        else:
            stats['potions_per_session'] = 0.0
            stats['f1_per_session'] = 0.0
            stats['f_per_session'] = 0.0

        if stats['fastest_recovery'] == float('inf'):
            stats['fastest_recovery'] = 0.0

        return stats

    def reset_stats(self):
        """Reset all statistics"""
        self.stats = {
            'recovery_sessions': 0,
            'potions_used': 0,
            'f1_presses': 0,
            'f_presses': 0,
            'total_recovery_time': 0.0,
            'average_recovery_time': 0.0,
            'fastest_recovery': float('inf'),
            'slowest_recovery': 0.0,
            'hp_events_processed': 0,
            'critical_events': 0,
            'warning_events': 0,
            'auto_recoveries': 0
        }
        self.log("📊 HP Recovery statistics reset")


def create_hp_recovery_system(logger=None, enabled: bool = True,
                              potion_key: int = 0x34, f1_key: int = 0x70, f_key: int = 0x46, wait_duration: float = 1.0,
                              critical_threshold: float = 30.0, recovery_threshold: float = 80.0):
    """Factory function to create and configure HP Recovery System"""
    system = HPRecoverySystem(logger=logger)

    if enabled:
        system.configure(
            potion_key=potion_key,
            f1_key=f1_key,
            f_key=f_key,
            wait_duration=wait_duration,
            critical_threshold=critical_threshold,
            recovery_threshold=recovery_threshold
        )
        system.log("💊 HP Recovery System: ENABLED")
    else:
        system.log("💊 HP Recovery System: DISABLED")

    return system