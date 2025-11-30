# dynamic_approach.py
"""
Dynamic Target Approach System - FINAL FIXED VERSION
Poprawki:
1. Approach = TYLKO W (forward), bez A/D
2. Ciągłe sprawdzanie zasięgu WSZYSTKICH mobów podczas ruchu
3. WYMUSZONY escape timing 0.7-1.5s + force cleanup
4. Wolniejsze, delikatniejsze ruchy
5. Lepszy timing i assessment
6. STUCK DETECTION + Emergency Escape (W + A/D, 0.7-1.5s)
7. Backup safety timeout dla escape
"""

import time
import math
import random


class QuickResponseAnalyzer:
    """Analyzes target response to approach attempts using rapid YOLO feedback"""

    def __init__(self, screen_center_x, screen_center_y, engagement_threshold):
        self.screen_center_x = screen_center_x
        self.screen_center_y = screen_center_y
        self.engagement_range_threshold = engagement_threshold
        self.recent_detections = []
        self.consecutive_improvements = 0
        self.consecutive_worsening = 0
        self.baseline_distance = None

        # STUCK DETECTION
        self.no_progress_counter = 0
        self.stuck_threshold = 5  # 5 kroków bez postępu = stuck

    def calculate_distance(self, enemy_x, enemy_y):
        """Calculate distance from screen center to enemy"""
        dx = enemy_x - self.screen_center_x
        dy = enemy_y - self.screen_center_y
        return math.sqrt(dx * dx + dy * dy)

    def add_detection(self, enemy_detection):
        """Process new YOLO detection and make quick decision"""
        enemy_x = enemy_detection.get('center_x')
        enemy_y = enemy_detection.get('center_y')
        distance = self.calculate_distance(enemy_x, enemy_y)

        detection_data = {
            'distance': distance,
            'position': (enemy_x, enemy_y),
            'timestamp': time.time()
        }

        self.recent_detections.append(detection_data)

        # Keep only last 5 detections for rapid analysis
        if len(self.recent_detections) > 5:
            self.recent_detections.pop(0)

        return self.quick_decision()

    def quick_decision(self):
        """Make rapid decision based on latest detections"""
        if len(self.recent_detections) < 2:
            return "CONTINUE"

        current = self.recent_detections[-1]
        previous = self.recent_detections[-2]

        distance_change = previous['distance'] - current['distance']

        # SUCCESS: reached engagement range
        if current['distance'] <= self.engagement_range_threshold:
            return "SUCCESS"

        # STUCK DETECTION: brak postępu
        if abs(distance_change) < 3:  # Mniej niż 3px zmiany = brak postępu
            self.no_progress_counter += 1
            if self.no_progress_counter >= self.stuck_threshold:
                return "ABORT_STUCK"
        else:
            self.no_progress_counter = 0  # Reset przy jakiejkolwiek zmianie

        # POSITIVE: getting closer (bardziej czuły)
        if distance_change > 2:  # 2px improvement per step (było 5px)
            self.consecutive_improvements += 1
            self.consecutive_worsening = 0
            return "CONTINUE_GOOD"

        # NEGATIVE: getting further (szybsza reakcja)
        if distance_change < -5:  # distance worsening (było -8px)
            self.consecutive_improvements = 0
            self.consecutive_worsening += 1

            if self.consecutive_worsening >= 3:  # 3 bad steps in a row
                return "ABORT_WORSENING"

        # NEUTRAL: no significant change
        return "CONTINUE_NEUTRAL"

    def reset(self):
        """Reset analyzer for new approach attempt"""
        self.recent_detections.clear()
        self.consecutive_improvements = 0
        self.consecutive_worsening = 0
        self.baseline_distance = None
        self.no_progress_counter = 0  # Reset stuck counter


class DynamicApproachSystem:
    """
    Complete Dynamic Target Approach System - FINAL FIXED VERSION
    - Approach = TYLKO W (forward)
    - Ciągłe sprawdzanie zasięgu WSZYSTKICH mobów
    - WYMUSZONY escape timing + force cleanup
    - STUCK DETECTION + Emergency Escape
    """

    def __init__(self, combat_controller):
        """Initialize with reference to combat controller"""
        self.controller = combat_controller

        # Configuration - WOLNIEJSZE TIMING
        self.target_stability_threshold = 30  # pixels
        self.target_stationary_time_limit = 15.0  # seconds
        self.approach_micro_step_duration = random.uniform(0.1, 0.3) # 100ms
        self.approach_quick_assessment = random.uniform(0.3, 0.5)  # 500ms
        self.approach_max_steps = 20  # więcej kroków, ale krótszych

        # ESCAPE TIMING - 0.7-1.5s
        self.min_escape_time = 0.7
        self.max_escape_time = 1.5
        self.max_safety_timeout = 2.0  # Backup safety - wymuszony stop po 2s

        # State tracking
        self.target_position_history = []
        self.active = False
        self.phase = "MONITORING"  # MONITORING, QUICK_STEPPING, QUICK_ASSESSING, ROTATING, EMERGENCY_ESCAPE
        self.current_step = 0

        # Target tracking
        self.locked_target_position = None
        self.target_tolerance = 40

        # Timing
        self.micro_step_start_time = 0
        self.quick_assessment_start = 0
        self.rotation_start_time = 0
        self.rotation_duration = 0
        self.rotation_key = None

        # EMERGENCY ESCAPE
        self.emergency_escape_start = 0
        self.emergency_escape_duration = 0
        self.emergency_escape_direction = None

        # Initialize analyzer
        engagement_threshold = getattr(combat_controller, 'emergency_distance_threshold', 80) + 20
        self.analyzer = QuickResponseAnalyzer(
            combat_controller.screen_center_x,
            combat_controller.screen_center_y,
            engagement_threshold
        )

    def update(self, hwnd, closest_enemy, enemies):
        """
        Main update method

        Args:
            hwnd: Window handle
            closest_enemy: Current closest enemy detection
            enemies: List of all enemy detections

        Returns:
            bool: True if approach system is handling combat (skip normal combat logic)
        """
        if not closest_enemy:
            if self.active:
                self._log("🚨 Target lost - aborting approach")
                self._force_cleanup_and_restart(hwnd)
            return False

        # Skip if other systems have priority
        if (getattr(self.controller, 'hp_recovery_active', False) or
                getattr(self.controller, 'emergency_backstep_active', False)):
            if self.active:
                self._log("⏸️ Approach paused - other system priority")
                self._force_cleanup_and_restart(hwnd)
            return False

        # During active approach, check if we're still tracking the same target
        if self.active:
            if not self._is_same_target(closest_enemy):
                self._log("🔄 Target switched - aborting current approach")
                self._force_cleanup_and_restart(hwnd)
                return False
            return self._handle_active_approach(hwnd, closest_enemy, enemies)

        # Track target position for new approach consideration
        self._track_target_position(closest_enemy)

        # Check if should start new approach
        if self._should_start_approach():
            self._initiate_approach(hwnd, closest_enemy)
            return True

        return False  # Normal combat can proceed

    def _is_same_target(self, current_enemy):
        """Check if current enemy is the same target we locked onto"""
        if not self.locked_target_position or not current_enemy:
            return False

        current_x = current_enemy.get('center_x', 0)
        current_y = current_enemy.get('center_y', 0)
        locked_x, locked_y = self.locked_target_position

        distance = math.sqrt((current_x - locked_x) ** 2 + (current_y - locked_y) ** 2)
        return distance <= self.target_tolerance

    def _track_target_position(self, enemy):
        """Track target position over time"""
        current_time = time.time()
        enemy_x = enemy.get('center_x')
        enemy_y = enemy.get('center_y')

        self.target_position_history.append((enemy_x, enemy_y, current_time))

        # Keep only last 25 seconds
        cutoff_time = current_time - 25.0
        self.target_position_history = [pos for pos in self.target_position_history
                                        if pos[2] > cutoff_time]

    def _is_target_stationary(self):
        """Check if target has been stationary"""
        if len(self.target_position_history) < 10:
            return False

        current_time = time.time()
        recent_positions = [pos for pos in self.target_position_history
                            if current_time - pos[2] <= self.target_stationary_time_limit]

        if len(recent_positions) < 5:
            return False

        # Calculate position variance
        avg_x = sum(pos[0] for pos in recent_positions) / len(recent_positions)
        avg_y = sum(pos[1] for pos in recent_positions) / len(recent_positions)

        max_deviation = max(
            math.sqrt((pos[0] - avg_x) ** 2 + (pos[1] - avg_y) ** 2)
            for pos in recent_positions
        )

        return max_deviation < self.target_stability_threshold

    def _should_start_approach(self):
        """Check if should initiate approach"""
        return (
                getattr(self.controller, 'mode', '') == "combat" and
                not self.active and
                self._is_target_stationary()
        )

    def _initiate_approach(self, hwnd, enemy):
        """Start approach sequence with target locking"""
        self.active = True
        self.phase = "QUICK_STEPPING"
        self.current_step = 0

        # Lock onto this specific target
        target_x = enemy.get('center_x')
        target_y = enemy.get('center_y')
        self.locked_target_position = (target_x, target_y)

        # Stop continuous movement if exists
        if hasattr(self.controller, 'stop_continuous_movement'):
            self.controller.stop_continuous_movement(hwnd)

        # Reset analyzer
        self.analyzer.reset()

        # Start first step
        self._execute_approach_step(hwnd)

        self._log(f"🎯 DYNAMIC APPROACH initiated - locked onto target at ({target_x:.0f}, {target_y:.0f})")

    def _execute_approach_step(self, hwnd):
        """Execute single micro-step - TYLKO W (forward)"""
        # TYLKO forward movement - BEZ A/D!
        if not self.controller.send_key_down(hwnd, self.controller.VK_W):
            return False

        self.micro_step_start_time = time.time()
        self.phase = "QUICK_STEPPING"
        return True

    def _stop_approach_step(self, hwnd):
        """Stop current movement"""
        self.controller.send_key_up(hwnd, self.controller.VK_W)

        self.phase = "QUICK_ASSESSING"
        self.quick_assessment_start = time.time()

    def _handle_active_approach(self, hwnd, enemy, enemies):
        """Handle active approach state machine"""
        current_time = time.time()

        # ✅ SPRAWDZANIE ZASIĘGU WSZYSTKICH MOBÓW - priorytet #1
        for mob in enemies:
            if not mob:
                continue
            distance = self.analyzer.calculate_distance(
                mob.get('center_x', 0), mob.get('center_y', 0)
            )
            if distance <= self.analyzer.engagement_range_threshold:
                self._conclude_success(hwnd, f"mob at distance {distance:.0f}px")
                return False  # Natychmiastowy powrót do walki

        # ✅ BACKUP SAFETY TIMEOUT - wymuszony stop escape
        if self.phase in ["ROTATING", "EMERGENCY_ESCAPE"]:
            escape_start = self.rotation_start_time if self.phase == "ROTATING" else self.emergency_escape_start
            if current_time - escape_start > self.max_safety_timeout:
                self._log(f"🚨 SAFETY TIMEOUT - force stopping {self.phase} after {self.max_safety_timeout}s")
                self._force_cleanup_and_restart(hwnd)
                return False

        if self.phase == "QUICK_STEPPING":
            # Check if step completed
            if current_time - self.micro_step_start_time >= self.approach_micro_step_duration:
                self._stop_approach_step(hwnd)

        elif self.phase == "QUICK_ASSESSING":
            # Assessment period
            if current_time - self.quick_assessment_start >= self.approach_quick_assessment:
                decision = self.analyzer.add_detection(enemy)

                if decision == "SUCCESS":
                    self._conclude_success(hwnd, "analyzer success")
                    return False  # Resume normal combat
                elif decision == "ABORT_STUCK":
                    self._initiate_emergency_escape(hwnd, "STUCK_DETECTED")
                    return True
                elif decision.startswith("ABORT"):
                    self._initiate_rotation_escape(hwnd, decision)
                    return True
                else:
                    # Continue approach
                    self.current_step += 1
                    if self.current_step >= self.approach_max_steps:
                        self._initiate_rotation_escape(hwnd, "ABORT_MAX_STEPS")
                        return True

                    # Next step
                    self._execute_approach_step(hwnd)

                    # Log progress every 3 steps
                    if self.current_step % 3 == 0:
                        if self.analyzer.recent_detections:
                            distance = self.analyzer.recent_detections[-1]['distance']
                            self._log(
                                f"👣 Approach progress: Step {self.current_step}/{self.approach_max_steps}, distance: {distance:.0f}px, status: {decision}")

        elif self.phase == "EMERGENCY_ESCAPE":
            # Handle emergency escape - WYMUSZONY TIMING
            elapsed = current_time - self.emergency_escape_start
            self._log_escape_progress("EMERGENCY_ESCAPE", elapsed, self.emergency_escape_duration)

            if elapsed >= self.emergency_escape_duration:
                self._complete_emergency_escape(hwnd)
                return False

        elif self.phase == "ROTATING":
            # Handle rotation escape - WYMUSZONY TIMING
            elapsed = current_time - self.rotation_start_time
            self._log_escape_progress("ROTATING", elapsed, self.rotation_duration)

            if elapsed >= self.rotation_duration:
                self._complete_rotation_escape(hwnd)
                return False

        return True  # Continue handling approach

    def _log_escape_progress(self, phase_name, elapsed, duration):
        """Log escape progress every 0.5s for debugging"""
        if hasattr(self, '_last_escape_log_time'):
            if elapsed - getattr(self, '_last_escape_log_time', 0) >= 0.5:
                self._log(f"⏱️ {phase_name}: {elapsed:.1f}s / {duration:.1f}s")
                self._last_escape_log_time = elapsed
        else:
            self._last_escape_log_time = elapsed

    def _conclude_success(self, hwnd, reason=""):
        """Successfully reached engagement range"""
        self.active = False
        self.phase = "MONITORING"
        self.locked_target_position = None

        # Clean up movement
        self._cleanup_all_keys(hwnd)

        self._log(f"✅ APPROACH SUCCESS - engagement range reached ({reason}) in {self.current_step} steps")

    def _initiate_emergency_escape(self, hwnd, reason):
        """Start emergency escape - W + A/D ukosem (0.7-1.5s)"""
        self.phase = "EMERGENCY_ESCAPE"
        self.emergency_escape_start = time.time()

        # Stop approach movement
        self.controller.send_key_up(hwnd, self.controller.VK_W)

        # Start emergency escape - W + losowy kierunek (A lub D)
        self.emergency_escape_direction = random.choice([self.controller.VK_A, self.controller.VK_D])
        self.emergency_escape_duration = random.uniform(self.min_escape_time, self.max_escape_time)  # 0.7-1.5s

        # Wciskamy W + A/D jednocześnie (ruch ukosem)
        self.controller.send_key_down(hwnd, self.controller.VK_W)
        self.controller.send_key_down(hwnd, self.emergency_escape_direction)

        direction = "LEFT" if self.emergency_escape_direction == self.controller.VK_A else "RIGHT"
        self._log(f"🚨 {reason} - emergency escape W+{direction} for {self.emergency_escape_duration:.1f}s")

    def _complete_emergency_escape(self, hwnd):
        """Complete emergency escape and RESTART CYCLE"""
        # Stop emergency escape movement
        self._cleanup_all_keys(hwnd)

        # ✅ RESTART CYKLU
        self._restart_cycle()
        self._log("🏃 Emergency escape complete - RESTARTING approach cycle")

    def _initiate_rotation_escape(self, hwnd, reason):
        """Start rotation escape (0.7-1.5s)"""
        self.phase = "ROTATING"
        self.rotation_start_time = time.time()

        # Stop approach movement
        self.controller.send_key_up(hwnd, self.controller.VK_W)

        # Start rotation (0.7-1.5s)
        rotation_key = random.choice([self.controller.VK_A, self.controller.VK_D])
        self.controller.send_key_down(hwnd, rotation_key)
        self.rotation_key = rotation_key
        self.rotation_duration = random.uniform(self.min_escape_time, self.max_escape_time)  # 0.7-1.5s

        direction = "LEFT" if rotation_key == self.controller.VK_A else "RIGHT"
        self._log(f"🔄 APPROACH FAILED - {reason} - rotating {direction} for {self.rotation_duration:.1f}s")

    def _complete_rotation_escape(self, hwnd):
        """Complete rotation and RESTART CYCLE"""
        # Stop rotation
        self._cleanup_all_keys(hwnd)

        # ✅ RESTART CYKLU
        self._restart_cycle()
        self._log("🔄 Rotation complete - RESTARTING approach cycle")

    def _force_cleanup_and_restart(self, hwnd):
        """WYMUSZONY cleanup wszystkich klawiszy + restart"""
        self._cleanup_all_keys(hwnd)
        self._restart_cycle()
        self._log("🛑 FORCE CLEANUP - all keys released, approach cycle restarted")

    def _cleanup_all_keys(self, hwnd):
        """Wymuś puszczenie WSZYSTKICH klawiszy"""
        self.controller.send_key_up(hwnd, self.controller.VK_W)
        self.controller.send_key_up(hwnd, self.controller.VK_A)
        self.controller.send_key_up(hwnd, self.controller.VK_D)

        # Reset key tracking
        self.rotation_key = None
        self.emergency_escape_direction = None

    def _restart_cycle(self):
        """Restart całego cyklu approach"""
        self.active = False
        self.phase = "MONITORING"
        self.locked_target_position = None
        self.target_position_history.clear()

        # Reset timing
        self.micro_step_start_time = 0
        self.quick_assessment_start = 0
        self.rotation_start_time = 0
        self.emergency_escape_start = 0

    def _log(self, message):
        """Log message using controller's log method"""
        if hasattr(self.controller, 'log'):
            self.controller.log(message)
        else:
            print(f"[DynamicApproach] {message}")

    def get_status(self):
        """Get current status for debugging"""
        if not self.active:
            return None

        target_info = ""
        if self.locked_target_position:
            tx, ty = self.locked_target_position
            target_info = f" Target:({tx:.0f},{ty:.0f})"

        timing_info = ""
        current_time = time.time()
        if self.phase == "ROTATING" and self.rotation_start_time > 0:
            elapsed = current_time - self.rotation_start_time
            timing_info = f" Time:{elapsed:.1f}s/{self.rotation_duration:.1f}s"
        elif self.phase == "EMERGENCY_ESCAPE" and self.emergency_escape_start > 0:
            elapsed = current_time - self.emergency_escape_start
            timing_info = f" Time:{elapsed:.1f}s/{self.emergency_escape_duration:.1f}s"

        if self.analyzer.recent_detections:
            distance = self.analyzer.recent_detections[-1]['distance']
            stuck_info = f" Stuck:{self.analyzer.no_progress_counter}/{self.analyzer.stuck_threshold}"
            return f"🎯 Dynamic Approach: Step {self.current_step}/{self.approach_max_steps}, Phase: {self.phase}, Distance: {distance:.0f}px{target_info}{stuck_info}{timing_info}"
        else:
            return f"🎯 Dynamic Approach: Step {self.current_step}/{self.approach_max_steps}, Phase: {self.phase}{target_info}{timing_info}"

    def force_abort(self, hwnd):
        """Force abort approach"""
        if self.active:
            self._log("🚨 FORCE ABORT - approach system manually stopped")
            self._force_cleanup_and_restart(hwnd)


# INTEGRATION NOTES:
"""
# 1. Zamień stary plik dynamic_approach.py tym nowym

# 2. Integracja w combat_controller.py:
from dynamic_approach import DynamicApproachSystem

# 3. W __init__():
self.approach_system = DynamicApproachSystem(self)

# 4. W update() przed normalnym combat:
if self.approach_system.update(hwnd, closest_enemy, enemies):
    return  # Skip normal combat this frame

# FINALNE ZMIANY:
# ✅ Approach = TYLKO W (forward), bez A/D
# ✅ Ciągłe sprawdzanie zasięgu WSZYSTKICH mobów
# ✅ WYMUSZONY escape timing 0.7-1.5s + force cleanup
# ✅ Backup safety timeout (2s max)
# ✅ STUCK DETECTION (5 kroków bez postępu = stuck)
# ✅ EMERGENCY ESCAPE (W + A/D, 0.7-1.5s losowo)
# ✅ Lepsze logowanie z timing progress
# ✅ Cleanup wszystkich klawiszy
"""