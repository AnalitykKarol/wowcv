# hp_mp_recovery.py
"""
Smart HP/MP Recovery System - czeka na regenerację i powtarza mikstuty
FIXED: USUNIĘTY TIMEOUT - system czeka nieskończenie aż się uleczy lub pojawią się moby
ADDED: F1 przed HP recovery
Logika:
1. ZAWSZE naciska 7 (po każdej walce)
2. Jeśli MP < 40% → naciska 8, czeka aż MP ≥ 90%
3. Jeśli HP < 90% → naciska F1, potem 9, czeka aż HP ≥ 90% (retry po 3s jeśli nie działa)
4. Sprawdza regularnie HP/MP w exploration mode (co 5s)
5. PRZERYWA TYLKO PRZEZ MOBY - nie ma timeoutu!
"""

import time
import random


class HPMPRecoverySystem:
    """Inteligentny system recovery z oczekiwaniem na regenerację - BEZ TIMEOUTU"""

    def __init__(self, combat_controller):
        self.controller = combat_controller

        # === KONFIGURACJA ===
        self.mp_threshold = 10.0  # Użyj MP potion gdy < 40%
        self.hp_threshold = 30.0  # Użyj HP potion gdy < 30%
        self.target_mp = 90.0  # Czekaj aż MP ≥ 90%
        self.target_hp = 90.0  # Czekaj aż HP ≥ 90%

        # Klawisze - VK kody
        self.after_combat_key = 0x37  # VK_7
        self.mp_potion_key = 0x38  # VK_8 (MP potion)
        self.hp_potion_key = 0x39  # VK_9 (HP potion)
        self.f1_key = 0x70  # VK_F1 - NOWY klawisz

        # Timing
        self.potion_press_duration = random.uniform(0.1, 0.2)  # Jak długo trzymać klawisz
        self.wait_after_key7 = random.uniform(4, 5)  # Czekaj 1s po klawiszu 7
        self.wait_after_f1 = random.uniform(0.07, 0.1)  # Random delay after F1 before HP potion (0.07-0.1s)
        self.regen_check_interval = 0.5  # Sprawdzaj regenerację co 0.5s
        self.hp_retry_timeout = 3.0  # Retry HP po 3s jeśli nie działa

        # REMOVED: max_recovery_time - NIE MA TIMEOUTU!

        # Regularna analiza w exploration
        self.exploration_check_interval = 5.0  # Sprawdzaj HP/MP co 5s w exploration

        # === STAN SYSTEMU ===
        self.state = "IDLE"  # IDLE, CHECKING, AFTER_COMBAT, WAITING_MP, F1_BEFORE_HP, WAITING_HP, COOLDOWN
        self.last_mode = None
        self.recovery_start_time = 0
        self.action_start_time = 0
        self.last_check_time = 0
        self.last_exploration_check = 0

        # Recovery tracking
        self.needs_mp = False
        self.needs_hp = False
        self.hp_attempts = 0
        self.max_hp_attempts = 5  # Zwiększone z 3 na 5 - więcej prób

        # Bazowe wartości
        self.baseline_hp = 0
        self.baseline_mp = 0

        # Statystyki
        self.stats = {
            'recoveries_started': 0,
            'hp_potions_used': 0,
            'mp_potions_used': 0,
            'after_combat_keys': 0,
            'f1_keys_used': 0,  # NOWA statystyka
            'last_recovery_time': 0,
            'analysis_sessions': 0,
            'hp_recoveries': 0,
            'mp_recoveries': 0,
            'emergency_stops': 0,  # Tylko przez moby
            'avg_hp_time': 0.0,
            'avg_mp_time': 0.0,
            'longest_recovery': 0.0,  # Najdłuższy czas recovery
            'successful_recoveries': 0
        }

    def update(self, hwnd, enemies=None):
        """Główna metoda update - BEZ TIMEOUTU"""
        current_time = time.time()
        current_mode = getattr(self.controller, 'mode', 'unknown')

        # === SAFETY: Przerwij recovery TYLKO jeśli wykryto wrogów ===
        if enemies and len(enemies) > 0 and self.state != "IDLE":
            recovery_time = current_time - self.recovery_start_time
            self._log(f"🚨 Enemies detected during recovery after {recovery_time:.1f}s - aborting!")
            self.force_stop(hwnd)
            return False

        # === SAFETY: Przerwij recovery jeśli mode nie jest exploration ===
        if current_mode != "exploration" and self.state != "IDLE":
            recovery_time = current_time - self.recovery_start_time
            self._log(f"🚨 Mode changed to {current_mode} during recovery after {recovery_time:.1f}s - aborting!")
            self.force_stop(hwnd)
            return False

        # === TRIGGER - rozszerzona logika aktywacji ===
        should_start_recovery = False

        # Przypadek 1: Zmiana mode na exploration
        if (self.last_mode != current_mode and
                current_mode == "exploration" and
                self.state == "IDLE" and
                (not enemies or len(enemies) == 0)):
            should_start_recovery = True
            self._log(f"🔄 Mode transition to exploration - starting recovery sequence")

        # Przypadek 2: Już w exploration, ale sprawdź czy potrzeba recovery (co 5s)
        elif (current_mode == "exploration" and
              self.state == "IDLE" and
              (not enemies or len(enemies) == 0) and
              current_time - self.last_exploration_check > self.exploration_check_interval):

            # Sprawdź czy potrzeba recovery
            try:
                current_hp = self.controller.get_current_hp_from_gui()
                current_mp = self.controller.get_current_mp_from_gui()

                self._log(f"🔍 Regular exploration check - HP: {current_hp:.1f}%, MP: {current_mp:.1f}%")

                if current_hp < self.hp_threshold or current_mp < self.mp_threshold:
                    should_start_recovery = True
                    self._log(
                        f"🔄 Regular exploration check - HP: {current_hp:.1f}%, MP: {current_mp:.1f}% - starting recovery")
                    self.stats['analysis_sessions'] += 1
                else:
                    self._log(
                        f"✅ Regular exploration check - HP: {current_hp:.1f}%, MP: {current_mp:.1f}% - no recovery needed")
            except Exception as e:
                self._log(f"❌ Error checking HP/MP in exploration: {e}")

            self.last_exploration_check = current_time

        # Uruchom recovery jeśli potrzeba
        if should_start_recovery:
            self.state = "CHECKING"
            self.recovery_start_time = current_time
            self.hp_attempts = 0

        self.last_mode = current_mode

        # === REMOVED: TIMEOUT PROTECTION - Recovery czeka nieskończenie! ===
        # NIE MA JUŻ TIMEOUTU - recovery działa aż się uleczy lub pojawią się moby

        # === MASZYNA STANÓW ===
        if self.state == "CHECKING":
            self._handle_checking()
        elif self.state == "AFTER_COMBAT":
            self._handle_after_combat(hwnd, current_time)
        elif self.state == "WAITING_MP":
            self._handle_waiting_mp(hwnd, current_time)
        elif self.state == "F1_BEFORE_HP":  # NOWY stan
            self._handle_f1_before_hp(hwnd, current_time)
        elif self.state == "WAITING_HP":
            self._handle_waiting_hp(hwnd, current_time)
        elif self.state == "COOLDOWN":
            self._handle_cooldown(current_time)

        # NIGDY nie blokuj innych systemów - pozwól wykrywaniu wrogów działać
        return False  # Zawsze False = inne systemy mogą działać

    def _handle_checking(self):
        """Sprawdź HP/MP i zaplanuj recovery"""
        try:
            self.baseline_hp = self.controller.get_current_hp_from_gui()
            self.baseline_mp = self.controller.get_current_mp_from_gui()

            self._log(f"📊 Starting recovery analysis:")
            self._log(f"   HP: {self.baseline_hp:.1f}% (threshold: {self.hp_threshold}%)")
            self._log(f"   MP: {self.baseline_mp:.1f}% (threshold: {self.mp_threshold}%)")

            # Określ co potrzebuje recovery
            self.needs_mp = self.baseline_mp < self.mp_threshold
            self.needs_hp = self.baseline_hp < self.hp_threshold

            if self.needs_mp:
                self._log(f"🔵 MP needs recovery: {self.baseline_mp:.1f}% < {self.mp_threshold}%")
            else:
                self._log(f"✅ MP OK: {self.baseline_mp:.1f}% >= {self.mp_threshold}%")

            if self.needs_hp:
                self._log(f"🩸 HP needs recovery: {self.baseline_hp:.1f}% < {self.hp_threshold}% (F1 will be used first)")
            else:
                self._log(f"✅ HP OK: {self.baseline_hp:.1f}% >= {self.hp_threshold}%")

            # Jeśli nic nie potrzeba recovery
            if not self.needs_mp and not self.needs_hp:
                self._log(f"✅ No recovery needed - only using after-combat key")

            # ZAWSZE zacznij od klawisza 7
            self.state = "AFTER_COMBAT"
            self.action_start_time = time.time()
            self.stats['recoveries_started'] += 1
            self.stats['last_recovery_time'] = time.time()

        except Exception as e:
            self._log(f"❌ Error checking HP/MP: {e}")
            self._log(f"❌ Falling back to emergency recovery completion")
            self._finish_recovery()

    def _handle_after_combat(self, hwnd, current_time):
        """Obsługa klawisza 7 (zawsze pierwszy)"""
        if self.action_start_time == current_time:
            # Naciśnij klawisz 7
            if self._press_key(hwnd, self.after_combat_key):
                self.stats['after_combat_keys'] += 1
                self._log(f"⚔️ After-combat key '7' pressed")
            else:
                self._log(f"❌ Failed to press after-combat key")

        # Czekaj po klawiszu 7
        if current_time - self.action_start_time >= self.wait_after_key7:
            # Przejdź do następnego kroku
            if self.needs_mp:
                self._start_mp_recovery(hwnd)
            elif self.needs_hp:
                self._start_f1_before_hp(hwnd)  # ZMIENIONE: najpierw F1
            else:
                self._log("✅ Only key 7 needed - recovery complete")
                self._finish_recovery()

    def _start_mp_recovery(self, hwnd):
        """Rozpocznij recovery MP"""
        if self._press_key(hwnd, self.mp_potion_key):
            self.state = "WAITING_MP"
            self.action_start_time = time.time()
            self.last_check_time = time.time()
            self.stats['mp_potions_used'] += 1
            self.stats['mp_recoveries'] += 1
            self._log(f"🔵 MP potion '8' used - waiting for regen to {self.target_mp}% (NO TIMEOUT)")
        else:
            self._log(f"❌ Failed to use MP potion")
            self._finish_recovery()

    def _start_f1_before_hp(self, hwnd):
        """NOWA METODA: Naciśnij F1 przed HP recovery"""
        if self._press_key(hwnd, self.f1_key):
            self.state = "F1_BEFORE_HP"
            self.action_start_time = time.time()
            self.stats['f1_keys_used'] += 1
            self._log(f"🔑 F1 key pressed before HP recovery - waiting {self.wait_after_f1}s")
        else:
            self._log(f"❌ Failed to press F1 key - proceeding to HP recovery anyway")
            self._start_hp_recovery(hwnd)

    def _handle_f1_before_hp(self, hwnd, current_time):
        """NOWA METODA: Obsługa stanu F1_BEFORE_HP"""
        # Czekaj po F1
        if current_time - self.action_start_time >= self.wait_after_f1:
            self._log(f"⏰ F1 delay completed - starting HP recovery")
            self._start_hp_recovery(hwnd)

    def _start_hp_recovery(self, hwnd):
        """Rozpocznij recovery HP (po F1)"""
        if self._press_key(hwnd, self.hp_potion_key):
            self.state = "WAITING_HP"
            self.action_start_time = time.time()
            self.last_check_time = time.time()
            self.hp_attempts += 1
            self.stats['hp_potions_used'] += 1
            if self.hp_attempts == 1:
                self.stats['hp_recoveries'] += 1
            self._log(
                f"🩸 HP potion '9' used (attempt {self.hp_attempts}) after F1 - waiting for regen to {self.target_hp}% (NO TIMEOUT)")
        else:
            self._log(f"❌ Failed to use HP potion")
            self._finish_recovery()

    def _handle_waiting_mp(self, hwnd, current_time):
        """Czekaj na regenerację MP - BEZ TIMEOUTU"""
        if current_time - self.last_check_time >= self.regen_check_interval:
            try:
                current_mp = self.controller.get_current_mp_from_gui()
                elapsed = current_time - self.action_start_time
                self._log(f"🔵 MP regen check: {current_mp:.1f}% (target: {self.target_mp}%) - elapsed: {elapsed:.1f}s")

                if current_mp >= self.target_mp:
                    recovery_time = current_time - self.action_start_time
                    self._log(f"✅ MP recovered to {current_mp:.1f}% in {recovery_time:.1f}s")

                    # Update timing stats
                    if self.stats['mp_recoveries'] > 0:
                        self.stats['avg_mp_time'] = ((self.stats['avg_mp_time'] * (
                                    self.stats['mp_recoveries'] - 1)) + recovery_time) / self.stats['mp_recoveries']

                    # MP OK, sprawdź czy potrzeba HP
                    if self.needs_hp:
                        self._start_f1_before_hp(hwnd)  # ZMIENIONE: F1 przed HP
                    else:
                        self._finish_recovery()
                else:
                    self.last_check_time = current_time

            except Exception as e:
                self._log(f"❌ Error checking MP: {e}")
                # NIE kończymy recovery na błędzie - próbujemy dalej
                self.last_check_time = current_time

    def _handle_waiting_hp(self, hwnd, current_time):
        """Czekaj na regenerację HP z retry - BEZ TIMEOUTU"""
        if current_time - self.last_check_time >= self.regen_check_interval:
            try:
                current_hp = self.controller.get_current_hp_from_gui()
                elapsed = current_time - self.action_start_time
                self._log(f"🩸 HP regen check: {current_hp:.1f}% (target: {self.target_hp}%) - elapsed: {elapsed:.1f}s")

                if current_hp >= self.target_hp:
                    recovery_time = current_time - self.action_start_time
                    self._log(f"✅ HP recovered to {current_hp:.1f}% in {recovery_time:.1f}s")

                    # Update timing stats
                    if self.stats['hp_recoveries'] > 0:
                        self.stats['avg_hp_time'] = ((self.stats['avg_hp_time'] * (
                                    self.stats['hp_recoveries'] - 1)) + recovery_time) / self.stats['hp_recoveries']

                    self._finish_recovery()
                    return

                # Sprawdź czy czas na retry
                time_since_potion = current_time - self.action_start_time
                if time_since_potion >= self.hp_retry_timeout:
                    if self.hp_attempts < self.max_hp_attempts:
                        self._log(
                            f"🔄 HP retry timeout ({self.hp_retry_timeout}s) - using F1+potion again (attempt {self.hp_attempts + 1})")
                        self._start_f1_before_hp(hwnd)  # ZMIENIONE: F1 przed retry
                    else:
                        # Zwiększ próby zamiast kończyć recovery
                        self._log(
                            f"⚠️ Max HP attempts ({self.max_hp_attempts}) reached - continuing to wait for natural regen")
                        self.last_check_time = current_time
                else:
                    self.last_check_time = current_time

            except Exception as e:
                self._log(f"❌ Error checking HP: {e}")
                # NIE kończymy recovery na błędzie - próbujemy dalej
                self.last_check_time = current_time

    def _handle_cooldown(self, current_time):
        """Krótki cooldown po recovery"""
        if current_time - self.recovery_start_time >= 1.0:  # 1s cooldown
            total_recovery_time = current_time - self.recovery_start_time
            self.stats['successful_recoveries'] += 1

            # Track longest recovery
            if total_recovery_time > self.stats['longest_recovery']:
                self.stats['longest_recovery'] = total_recovery_time

            self.state = "IDLE"
            self._log(f"⏰ Recovery sequence completed in {total_recovery_time:.1f}s")

    def _press_key(self, hwnd, vk_code):
        """Naciśnij klawisz"""
        try:
            success = self.controller.send_key_down(hwnd, vk_code)
            if success:
                time.sleep(self.potion_press_duration)
                self.controller.send_key_up(hwnd, vk_code)
                return True
            return False
        except Exception as e:
            self._log(f"❌ Error pressing key {vk_code}: {e}")
            return False

    def _finish_recovery(self):
        """Zakończ recovery sequence"""
        self.state = "COOLDOWN"
        self.needs_mp = False
        self.needs_hp = False
        self.hp_attempts = 0

    def is_active(self):
        """Czy system jest aktywny"""
        return self.state != "IDLE"

    def is_analyzing(self):
        """Czy system analizuje (CHECKING state)"""
        return self.state == "CHECKING"

    def force_stop(self, hwnd):
        """Wymuszony stop - TYLKO przez moby lub zmianę mode"""
        if self.state != "IDLE":
            recovery_time = time.time() - self.recovery_start_time
            self._log(f"🚨 Recovery force stopped after {recovery_time:.1f}s")
            self.state = "IDLE"
            self.needs_mp = False
            self.needs_hp = False
            self.hp_attempts = 0
            self.stats['emergency_stops'] += 1

            # Track recovery time even if interrupted
            if recovery_time > self.stats['longest_recovery']:
                self.stats['longest_recovery'] = recovery_time

            # Zwolnij klawisze
            try:
                self.controller.send_key_up(hwnd, self.after_combat_key)
                self.controller.send_key_up(hwnd, self.mp_potion_key)
                self.controller.send_key_up(hwnd, self.hp_potion_key)
                self.controller.send_key_up(hwnd, self.f1_key)  # NOWE: zwolnij F1
            except:
                pass

    def get_status(self):
        """Status dla UI"""
        if self.state == "IDLE":
            return None
        elif self.state == "CHECKING":
            return "📊 Analyzing HP/MP levels"
        elif self.state == "AFTER_COMBAT":
            return "⚔️ Using after-combat key (7)"
        elif self.state == "WAITING_MP":
            elapsed = time.time() - self.action_start_time
            return f"🔵 Waiting for MP regen → {self.target_mp}% ({elapsed:.0f}s)"
        elif self.state == "F1_BEFORE_HP":  # NOWY status
            elapsed = time.time() - self.action_start_time
            return f"🔑 F1 pressed, waiting {self.wait_after_f1}s before HP potion"
        elif self.state == "WAITING_HP":
            elapsed = time.time() - self.action_start_time
            return f"🩸 Waiting for HP regen → {self.target_hp}% (attempt {self.hp_attempts}, {elapsed:.0f}s)"
        elif self.state == "COOLDOWN":
            return "⏰ Recovery cooldown"

    def get_stats(self):
        """Statystyki - ROZSZERZONE"""
        return {
            'state': self.state,
            'is_active': self.is_active(),
            'is_analyzing': self.is_analyzing(),
            'mp_threshold': self.mp_threshold,
            'hp_threshold': self.hp_threshold,
            'target_mp': self.target_mp,
            'target_hp': self.target_hp,
            'analysis_sessions': self.stats['analysis_sessions'],
            'recoveries_started': self.stats['recoveries_started'],
            'successful_recoveries': self.stats['successful_recoveries'],
            'after_combat_keys': self.stats['after_combat_keys'],
            'mp_potions_used': self.stats['mp_potions_used'],
            'hp_potions_used': self.stats['hp_potions_used'],
            'f1_keys_used': self.stats['f1_keys_used'],  # NOWA statystyka
            'hp_recoveries': self.stats['hp_recoveries'],
            'mp_recoveries': self.stats['mp_recoveries'],
            'emergency_stops': self.stats['emergency_stops'],
            'avg_hp_time': self.stats['avg_hp_time'],
            'avg_mp_time': self.stats['avg_mp_time'],
            'longest_recovery': self.stats['longest_recovery'],
            'success_rate': (self.stats['successful_recoveries'] / max(1, self.stats['recoveries_started'])) * 100,
            'last_recovery': time.strftime('%H:%M:%S', time.localtime(self.stats['last_recovery_time'])) if self.stats[
                'last_recovery_time'] else 'Never'
        }

    def _log(self, message):
        """Logowanie"""
        if hasattr(self.controller, 'log'):
            self.controller.log(f"[Smart-Recovery] {message}")
        else:
            print(f"[Smart-Recovery] {message}")


# === SCENARIUSZE DZIAŁANIA - NOWA SEKWENCJA Z F1 ===
"""
NOWA LOGIKA HP RECOVERY:
1. Klawisz 7 (zawsze)
2. Jeśli MP < 40% → klawisz 8, czekaj na regenerację
3. Jeśli HP < 90% → klawisz F1, czekaj 0.5s, potem klawisz 9, czekaj na regenerację
4. Retry HP: F1 → czekaj 0.5s → klawisz 9 (do 5 prób)

PRZYKŁAD SEKWENCJI:
⚔️ After-combat key '7' pressed
🔑 F1 key pressed before HP recovery - waiting 0.5s
⏰ F1 delay completed - starting HP recovery  
🩸 HP potion '9' used (attempt 1) after F1 - waiting for regen to 90% (NO TIMEOUT)
🩸 HP regen check: 45.2% (target: 90%) - elapsed: 67s
...
🔄 HP retry timeout (3s) - using F1+potion again (attempt 2)
🔑 F1 key pressed before HP recovery - waiting 0.5s
🩸 HP potion '9' used (attempt 2) after F1 - waiting for regen to 90% (NO TIMEOUT)
"""