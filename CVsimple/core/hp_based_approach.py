# hybrid_approach.py
"""
Hybrid Approach System - NAJLEPSZE Z OBU ŚWIATÓW
Łączy:
- Szybki feedback pozycyjny (z dynamic)
- HP tracking jako dodatkowy wskaźnik (z hp_based)
- Proste stany i szybkie reakcje
- Naturalne pulsowanie W z inteligentną oceną
"""

import time
import math
import random


class HPBasedApproachSystem:
    """
    Hybrydowy system approach łączący:
    - Pozycyjny feedback (YOLO) jako główny wskaźnik
    - HP tracking jako dodatkowy wskaźnik walki
    - Szybkie reakcje i proste stany
    """

    def __init__(self, combat_controller):
        self.controller = combat_controller

        # === KONFIGURACJA ===
        self.engagement_distance = 80  # Docelowa odległość
        self.start_delay = 1.0  # KRÓTKIE opóźnienie - 3s zamiast 10s

        # Pulsujący ruch W (naturalne timing)
        self.w_press_min = 0.15
        self.w_press_max = 0.35
        self.w_pause_min = 0.3
        self.w_pause_max = 0.6

        # Ocena postępu
        self.assessment_interval = 0.5  # Ocena co 0.5s
        self.stuck_threshold = 4  # 4 oceny bez postępu = stuck
        self.max_approach_time = 30.0  # KRÓTKI timeout - 15s zamiast 30s

        # HP tracking (dodatkowy wskaźnik)
        self.hp_check_interval = 1.0  # Sprawdzanie HP co 1s
        self.hp_drop_threshold = 3.0  # 3% spadek = prawdopodobna walka

        # Escape timing
        self.escape_time_min = 1
        self.escape_time_max = 1.2

        # === STAN SYSTEMU ===
        self.state = "IDLE"  # IDLE, APPROACHING, ESCAPING
        self.target_id = None
        self.enemy_tracking = {}  # target_id -> first_seen_time

        # Approach state
        self.approach_start_time = 0
        self.last_distance = 0
        self.distance_history = []  # (distance, timestamp)
        self.stuck_counter = 0
        self.last_assessment_time = 0

        # HP tracking
        self.baseline_hp = 0
        self.last_hp_check_time = 0
        self.hp_combat_detected = False

        # Pulsing W movement
        self.w_pressed = False
        self.w_action_time = 0
        self.w_duration = 0

        # Escape state
        self.escape_start_time = 0
        self.escape_duration = 0
        self.escape_key = None

    def update(self, hwnd, closest_enemy, enemies):
        """Główna metoda update"""

        # === PRIORITY: HP RECOVERY ===
        if hasattr(self.controller, 'hp_recovery') and self.controller.hp_recovery.is_active():
            if self.state != "IDLE":
                self._log("🚨 HP Recovery active - aborting approach")
                self._reset_state(hwnd)
            return False

        # === PRIORITY: ACTIVE COMBAT ===
        if self._is_in_active_combat():
            if self.state != "IDLE":
                self._log("⚔️ Active combat detected - focusing on fight")
                self._reset_state(hwnd)
            return False

        # === JEŚLI NIE MA WROGA - przejdź do IDLE i NIC NIE RÓB ===
        if not closest_enemy:
            if self.state != "IDLE":
                self._reset_state(hwnd)
            return False  # ← PASYWNY - nie zwracaj True!

        current_distance = self._calculate_distance(closest_enemy)
        current_time = time.time()

        # === JEŚLI W ZASIĘGU - przejdź do IDLE i NIC NIE RÓB ===
        if current_distance <= self.engagement_distance:
            if self.state != "IDLE":
                self._log(f"✅ In range! Distance: {current_distance:.0f}px")
                self._reset_state(hwnd)
            return False  # ← PASYWNY - nie zwracaj True!

        # === MASZYNA STANÓW ===
        if self.state == "IDLE":
            # W IDLE - bądź CAŁKOWICIE PASYWNY, tylko trackuj
            return self._handle_idle_passive(hwnd, closest_enemy, current_distance, current_time)
        elif self.state == "APPROACHING":
            return self._handle_approaching(hwnd, closest_enemy, current_distance, current_time)
        elif self.state == "ESCAPING":
            return self._handle_escaping(hwnd, current_time)

        return False

    def _handle_idle_passive(self, hwnd, enemy, distance, current_time):
        """Obsługa PASYWNEGO stanu bezczynności - tylko tracking, zero ingerencji"""

        # Sprawdź czy warto się zbliżać
        if distance > self.engagement_distance * 1.3:  # 104px+
            enemy_id = self._get_enemy_id(enemy)

            # Tracking nowych celów
            if enemy_id not in self.enemy_tracking:
                self.enemy_tracking[enemy_id] = current_time
                self._log(f"🎯 New target tracked - waiting {self.start_delay}s")
                return False  # ← PASYWNY

            # Sprawdź czy minął czas oczekiwania
            time_waited = current_time - self.enemy_tracking[enemy_id]
            if time_waited >= self.start_delay:
                if self._should_approach(enemy, distance):
                    self._start_approach(hwnd, enemy, distance, current_time)
                    return True  # ← TYLKO TERAZ AKTYWNY!
                else:
                    # Cel nie nadaje się - usuń z trackingu
                    del self.enemy_tracking[enemy_id]
                    self._log("❌ Target not suitable for approach")

        return False  # ← PASYWNY - pozwól innym systemom działać

    def _handle_approaching(self, hwnd, enemy, distance, current_time):
        """Obsługa aktywnego approach"""

        # === TIMEOUT CHECK ===
        if current_time - self.approach_start_time > self.max_approach_time:
            self._log(f"⏰ Approach timeout ({self.max_approach_time}s) - escaping")
            self._start_escape(hwnd, "TIMEOUT")
            return True

        # === POZYCYJNY FEEDBACK (główny wskaźnik) ===
        if current_time - self.last_assessment_time >= self.assessment_interval:
            assessment = self._assess_progress(distance, current_time)

            if assessment == "SUCCESS":
                self._log("✅ Approach successful")
                self._reset_state(hwnd)
                return False
            elif assessment == "STUCK":
                self._log("🚧 Stuck detected - escaping")
                self._start_escape(hwnd, "STUCK")
                return True
            elif assessment == "WORSENING":
                self._log("📉 Progress worsening - escaping")
                self._start_escape(hwnd, "WORSENING")
                return True

            self.last_assessment_time = current_time

        # === HP TRACKING (dodatkowy wskaźnik) ===
        if current_time - self.last_hp_check_time >= self.hp_check_interval:
            self._check_hp_status()
            self.last_hp_check_time = current_time

        # === PULSUJĄCY RUCH W ===
        self._update_pulsing_movement(hwnd, current_time)

        return True

    def _handle_escaping(self, hwnd, current_time):
        """Obsługa escape"""
        elapsed = current_time - self.escape_start_time

        if elapsed >= self.escape_duration:
            self._log("🔄 Escape completed - resetting")
            self._reset_state(hwnd)
            return False

        # Kontynuuj escape
        return True

    def _should_approach(self, enemy, distance):
        """Sprawdź czy warto podchodzić do celu"""
        # Proste kryteria - daleko i stabilny
        return distance > self.engagement_distance * 1.5

    def _start_approach(self, hwnd, enemy, distance, current_time):
        """Rozpocznij approach - TERAZ approach przejmuje kontrolę"""
        self.controller.approach_escape_active = False  # Reset na początku
        self.state = "APPROACHING"
        self.target_id = self._get_enemy_id(enemy)
        self.approach_start_time = current_time

        # Reset progress tracking
        self.last_distance = distance
        self.distance_history = [(distance, current_time)]
        self.stuck_counter = 0
        self.last_assessment_time = current_time

        # HP baseline
        self.baseline_hp = self._get_current_hp()
        self.hp_combat_detected = False
        self.last_hp_check_time = current_time

        # TERAZ zatrzymaj inne systemy i przejmij kontrolę
        if hasattr(self.controller, 'continuous_movement'):
            self.controller.continuous_movement.stop_continuous_movement(hwnd, self.controller.send_key_up)
            self._log("🛑 Stopped continuous movement for approach")

        # Zatrzymaj inne ruchy
        self._stop_all_movement(hwnd)

        # Setup pulsing W - TYLKO w APPROACHING!
        self.w_pressed = False
        self.w_action_time = current_time

        self._log(f"🎯 Approach started - distance: {distance:.0f}px, HP: {self.baseline_hp:.1f}%")

    def _assess_progress(self, current_distance, current_time):
        """Ocena postępu approach (główny wskaźnik)"""

        # Dodaj do historii
        self.distance_history.append((current_distance, current_time))

        # Zachowaj ostatnie 10 pomiarów
        if len(self.distance_history) > 10:
            self.distance_history.pop(0)

        if len(self.distance_history) < 3:
            return "CONTINUE"  # Za mało danych

        # Sprawdź czy osiągnięto zasięg
        if current_distance <= self.engagement_distance:
            return "SUCCESS"

        # Analiza trendu
        recent_distances = [d[0] for d in self.distance_history[-3:]]  # Ostatnie 3 pomiary
        distance_change = recent_distances[0] - recent_distances[-1]  # Zmiana od 3 pomiarów temu

        # Pozytywny postęp
        if distance_change > 5:  # Zbliżył się o 5px+
            self.stuck_counter = 0
            self._log(f"👍 Good progress: -{distance_change:.0f}px, distance: {current_distance:.0f}px")
            return "GOOD_PROGRESS"

        # Brak postępu
        if abs(distance_change) < 3:  # Mniej niż 3px zmiany
            self.stuck_counter += 1
            if self.stuck_counter >= self.stuck_threshold:
                return "STUCK"

        # Pogorszenie
        if distance_change < -8:  # Oddalił się o 8px+
            return "WORSENING"

        return "CONTINUE"

    def _check_hp_status(self):
        """Sprawdź HP jako dodatkowy wskaźnik"""
        current_hp = self._get_current_hp()

        if current_hp <= 0:
            return

        hp_change = self.baseline_hp - current_hp

        # Wykryj walkę przez spadek HP
        if hp_change >= self.hp_drop_threshold:
            if not self.hp_combat_detected:
                self._log(f"⚔️ Combat detected via HP drop: {hp_change:.1f}%")
                self.hp_combat_detected = True
            self.baseline_hp = current_hp  # Aktualizuj baseline

        # Wykryj uleczenie
        elif current_hp > self.baseline_hp + 10:
            self._log(f"🩺 Healing detected: +{current_hp - self.baseline_hp:.1f}%")
            self.baseline_hp = current_hp
            self.hp_combat_detected = True  # Uleczenie = walka

    def _update_pulsing_movement(self, hwnd, current_time):
        """Aktualizuj pulsujący ruch W"""

        # TYLKO działaj gdy jesteś w stanie APPROACHING!
        if self.state != "APPROACHING":
            # Jeśli W jest naciśnięty a nie powinien być, zwolnij go
            if self.w_pressed:
                self.controller.send_key_up(hwnd, self.controller.VK_W)
                self.w_pressed = False
                self._log("🛑 Pulsing W stopped - not in APPROACHING state")
            return

        if current_time < self.w_action_time:
            return  # Czekaj

        if not self.w_pressed:
            # Rozpocznij press W
            if self.controller.send_key_down(hwnd, self.controller.VK_W):
                self.w_pressed = True
                self.w_duration = random.uniform(self.w_press_min, self.w_press_max)
                self.w_action_time = current_time + self.w_duration
        else:
            # Zakończ press W, rozpocznij pause
            self.controller.send_key_up(hwnd, self.controller.VK_W)
            self.w_pressed = False
            pause_duration = random.uniform(self.w_pause_min, self.w_pause_max)
            self.w_action_time = current_time + pause_duration

    def _start_escape(self, hwnd, reason):
        """Rozpocznij escape"""
        # USTAW FLAGĘ BLOKUJĄCĄ INNE SYSTEMY!
        self.controller.approach_escape_active = True
        self.state = "ESCAPING"
        self.escape_start_time = time.time()
        self.escape_duration = random.uniform(self.escape_time_min, self.escape_time_max)

        # Zatrzymaj approach
        self._stop_all_movement(hwnd)

        # Losowy escape movement
        escape_moves = [
            (self.controller.VK_S, "BACK"),
            (self.controller.VK_A, "LEFT"),
            (self.controller.VK_D, "RIGHT")
        ]

        key, direction = random.choice(escape_moves)
        if self.controller.send_key_down(hwnd, key):
            self.escape_key = key
            self._log(f"🏃 Escaping {direction} for {self.escape_duration:.1f}s - reason: {reason}")

    def _is_in_active_combat(self):
        """Sprawdź czy trwa aktywna walka"""
        try:
            # Sprawdź mode controller
            if hasattr(self.controller, 'mode') and self.controller.mode == "combat":
                # Dodatkowo sprawdź czy HP się zmienia (ostatnie 5s)
                current_hp = self._get_current_hp()
                if hasattr(self, '_last_combat_hp') and hasattr(self, '_last_combat_time'):
                    time_diff = time.time() - self._last_combat_time
                    if time_diff < 5.0:
                        hp_diff = abs(self._last_combat_hp - current_hp)
                        if hp_diff > 1.0:  # HP się zmieniło = aktywna walka
                            return True

                self._last_combat_hp = current_hp
                self._last_combat_time = time.time()

            # Sprawdź dedykowaną metodę
            if hasattr(self.controller, 'is_in_combat'):
                return self.controller.is_in_combat()

            return False
        except:
            return False

    def _calculate_distance(self, enemy):
        """Oblicz odległość od centrum"""
        dx = enemy.get('center_x', 0) - self.controller.screen_center_x
        dy = enemy.get('center_y', 0) - self.controller.screen_center_y
        return math.sqrt(dx * dx + dy * dy)

    def _get_enemy_id(self, enemy):
        """Pobierz ID wroga"""
        return f"{enemy.get('center_x', 0):.0f}_{enemy.get('center_y', 0):.0f}"

    def _get_current_hp(self):
        """Pobierz aktualne HP"""
        try:
            return self.controller.get_current_hp_from_gui()
        except:
            return 0.0

    def _stop_all_movement(self, hwnd):
        """Zatrzymaj wszystkie ruchy"""
        keys = [self.controller.VK_W, self.controller.VK_A, self.controller.VK_S, self.controller.VK_D]
        for key in keys:
            self.controller.send_key_up(hwnd, key)

        self.w_pressed = False
        self.escape_key = None

    def _reset_state(self, hwnd):
        """Reset do stanu początkowego - MINIMALNA ingerencja"""
        self.controller.approach_escape_active = False

        # TYLKO zatrzymaj klawisze które approach system używał
        if self.state in ["APPROACHING", "ESCAPING"]:
            self._stop_all_movement(hwnd)
            self._log("🛑 Stopped approach movement")

        self.state = "IDLE"
        self.target_id = None

        # WYMUŚ EXPLORATION MODE tylko gdy potrzeba
        current_mode = getattr(self.controller, 'mode', 'unknown')
        if current_mode != "exploration":
            self.controller.mode = "exploration"
            self._log(f"🔄 Mode set to exploration")

        # NIE RUSZAJ CONTINUOUS MOVEMENT - pozwól mu działać spokojnie!

        # Wyczyść stare śledzenia (>60s)
        current_time = time.time()
        old_targets = [tid for tid, t in self.enemy_tracking.items()
                       if current_time - t > 60.0]
        for tid in old_targets:
            del self.enemy_tracking[tid]

    def _log(self, message):
        """Logowanie"""
        if hasattr(self.controller, 'log'):
            self.controller.log(f"[Hybrid-Approach] {message}")
        else:
            print(f"[Hybrid-Approach] {message}")

    def get_status(self):
        """Status dla UI"""
        if self.state == "IDLE":
            tracked = len(self.enemy_tracking)
            if tracked > 0:
                return f"👀 Tracking {tracked} targets"
            return None

        elif self.state == "APPROACHING":
            current_time = time.time()
            elapsed = current_time - self.approach_start_time
            distance = self.distance_history[-1][0] if self.distance_history else 0
            hp_status = "⚔️" if self.hp_combat_detected else "🔍"
            w_status = "▶️" if self.w_pressed else "⏸️"

            return (f"🎯 Approach: {elapsed:.1f}s, {distance:.0f}px, "
                    f"stuck:{self.stuck_counter}/{self.stuck_threshold}, {hp_status}, W:{w_status}")

        elif self.state == "ESCAPING":
            elapsed = time.time() - self.escape_start_time
            remaining = self.escape_duration - elapsed
            return f"🏃 Escaping: {remaining:.1f}s left"

    def force_abort(self, hwnd):
        """Wymuszony abort"""
        if self.state != "IDLE":
            self._log("🚨 Force abort")
            self._reset_state(hwnd)

    def get_stats(self):
        """Statystyki"""
        return {
            'state': self.state,
            'start_delay': self.start_delay,
            'max_approach_time': self.max_approach_time,
            'tracked_enemies': len(self.enemy_tracking),
            'stuck_threshold': self.stuck_threshold,
            'hp_combat_detected': self.hp_combat_detected,
            'assessment_interval': self.assessment_interval
        }


# === INTEGRACJA ===
"""
W combat_controller.py:

1. IMPORT:
from .hybrid_approach import HybridApproachSystem

2. INIT:
self.approach_system = HybridApproachSystem(self)

3. UPDATE (bez zmian):
if hasattr(self, 'approach_system'):
    if self.approach_system.update(hwnd, closest_enemy, enemies):
        return  # Skip normal combat

ZALETY HYBRYDOWEGO SYSTEMU:
✅ Szybkie reakcje (3s delay, 15s timeout)
✅ Pozycyjny feedback jako główny wskaźnik
✅ HP tracking jako dodatkowy wskaźnik walki
✅ Proste stany (IDLE → APPROACHING → ESCAPING)
✅ Naturalne pulsowanie W z oceną postępu
✅ Stuck detection po 4 ocenach bez postępu
✅ Priorytet dla aktywnej walki
✅ Automatyczne zatrzymywanie exploration
✅ Szybkie escape (0.8-1.2s)
✅ Tracking wielu celów z timeoutami
"""