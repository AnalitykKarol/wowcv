"""
Simplified Combat Controller - CLEAN VERSION
- Eksploracja z starym systemem + W+A/D jednocześnie
- System trapeza dla pozycjonowania kamery
- Uproszczony atak z wagami priorytetów
- Emergency backstep gdy mob za blisko
- Klikanie w ostatnią pozycję przeciwnika
- Grace period 5s po stracie przeciwnika
"""
import win32api
import win32con
import time
import random
import math

class SimplifiedCombatController:
    def __init__(self, logger=None):
        self.logger = logger

        # Kody klawiszy
        self.VK_W = 0x57
        self.VK_A = 0x41
        self.VK_S = 0x53
        self.VK_D = 0x44
        self.VK_1 = 0x31
        self.VK_2 = 0x32
        self.VK_3 = 0x33
        self.VK_4 = 0x34
        self.VK_5 = 0x35
        self.VK_6 = 0x36
        self.VK_7 = 0x37
        self.VK_8 = 0x38
        self.VK_RBUTTON = 0x02

        # ========================================
        # 1. STARY SYSTEM EKSPLORACJI (PRZYWRÓCONY) + W+A/D
        # ========================================
        self.movement_state = "ready_for_next_move"
        self.current_movement_key = None
        self.movement_start_time = 0
        self.movement_duration = 0
        self.movement_pause_start_time = 0
        self.movement_pause_duration = random.uniform(0.01, 0.3)

        # Długości ruchów jak w starym systemie
        self.micro_movement_duration = random.uniform(0.1, 0.2)
        self.short_movement_duration = random.uniform(0.25, 0.4)
        self.medium_movement_duration = random.uniform(0.6, 4)

        # NOWE: W+A/D system
        self.w_plus_turn_chance = 0.3  # 30% szans na dodanie A/D do W
        self.turn_key_with_w = None
        self.turn_key_pressed = False
        self.turn_duration_with_w = 0
        self.turn_start_time_with_w = 0

        # ========================================
        # 2. SYSTEM TRAPEZA KAMERY
        # ========================================
        self.screen_center_x = 960  # 1920/2
        self.screen_center_y = 540  # 1080/2

        # Trapez parameters (skalowane z ekranem)
        self.trapez_top_width = 400      # Szerokość góry (32% z 800px przykładu)
        self.trapez_height = 300         # Wysokość (67% z 450px przykładu)
        self.trapez_bottom_y = self.screen_center_y  # Ucięty na poziomie postaci
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        # Mikro-ruchy kamery - MNIEJ AGRESYWNE
        self.micro_camera_duration = random.uniform(0.005, 0.01)     # Krótsze naciśnięcia
        self.micro_camera_cooldown = random.uniform(0.3, 0.5)      # Dłuższe pauzy
        self.last_camera_adjustment = 0
        self.camera_adjusting = False
        self.camera_key_pressed = None
        self.camera_key_start_time = 0

        # ========================================
        # 3. UPROSZCZONY SYSTEM ATAKU Z WAGAMI
        # ========================================
        self.attack_keys = [self.VK_1, self.VK_2, self.VK_3, self.VK_4,
                           self.VK_5, self.VK_6, self.VK_7, self.VK_8]

        # Wagi dla klawiszy (możesz dostosować)
        self.attack_weights = {
            self.VK_1: 0.3,   # 30% - najczęściej
            self.VK_2: 0.25,  # 25%
            self.VK_3: 0.2,   # 20%
            self.VK_4: 0.15,  # 15%
            self.VK_5: 0.05,  # 5%
            self.VK_6: 0.025, # 2.5%
            self.VK_7: 0.015, # 1.5%
            self.VK_8: 0.01   # 1% - najrzadziej
        }

        self.last_attack_time = 0
        self.attack_interval = random.uniform(0.8, 1.5)  # Prosty cooldown

        # ========================================
        # 4. EMERGENCY BACKSTEP - MNIEJ AGRESYWNY
        # ========================================
        self.emergency_distance_threshold = 70   # Mniejszy próg
        self.emergency_backstep_duration = random.uniform(0.2, 0.6)    # Krótszy czas
        self.emergency_backstep_cooldown = 6.0   # Dłuższy cooldown
        self.last_emergency_backstep = 0
        self.emergency_backstep_active = False
        self.emergency_backstep_start_time = 0

        # ========================================
        # 5. OSTATNIA POZYCJA PRZECIWNIKA + GRACE PERIOD
        # ========================================
        self.last_enemy_position = None
        self.last_enemy_seen_time = 0
        self.enemy_memory_duration = 3.0  # Pamiętaj pozycję przez 3 sekundy
        self.last_click_on_position = 0
        self.click_position_cooldown = random.uniform(0.5, 1)

        # GRACE PERIOD - kontynuuj walkę przez 5s po stracie przeciwnika
        self.enemy_lost_grace_period = 5.0
        self.in_grace_period = False
        self.grace_period_start_time = 0

        # ========================================
        # 6. STAN OGÓLNY
        # ========================================
        self.has_enemy = False
        self.current_enemy_position = None
        self.mode = "exploration"  # exploration, combat, emergency_backstep

        # Statystyki
        self.stats = {
            'combat_sessions': 0,
            'camera_adjustments': 0,
            'emergency_backsteps': 0,
            'position_clicks': 0
        }

    def log(self, message):
        """Helper do logowania"""
        if self.logger:
            self.logger.info(message)
        else:
            print(message)

    # ========================================
    # 1. STARY SYSTEM EKSPLORACJI (PRZYWRÓCONY)
    # ========================================

    def stop_movement(self, hwnd):
        """Zatrzymuje ruch (puszcza wszystkie klawisze ruchu)"""
        if self.current_movement_key:
            self.send_key_up(hwnd, self.current_movement_key)
            self.current_movement_key = None

        # Zatrzymaj też dodatkowy klawisz skrętu
        if self.turn_key_pressed and self.turn_key_with_w:
            self.send_key_up(hwnd, self.turn_key_with_w)
            self.turn_key_with_w = None
            self.turn_key_pressed = False

    def start_movement(self, hwnd, movement_key, duration, reason):
        """Rozpoczyna ruch z możliwością dodania A/D do W"""
        self.stop_movement(hwnd)

        if movement_key:
            self.send_key_down(hwnd, movement_key)
            self.current_movement_key = movement_key
            self.movement_start_time = time.time()
            self.movement_duration = duration
            self.movement_state = "moving"

            # NOWE: Jeśli to W, losowo dodaj A lub D
            if movement_key == self.VK_W and random.random() < self.w_plus_turn_chance:
                turn_key = random.choice([self.VK_A, self.VK_D])
                turn_duration = random.uniform(0.3, 0.8)  # Krótszy niż główny ruch

                self.send_key_down(hwnd, turn_key)
                self.turn_key_with_w = turn_key
                self.turn_key_pressed = True
                self.turn_duration_with_w = turn_duration
                self.turn_start_time_with_w = time.time()

                turn_name = "A" if turn_key == self.VK_A else "D"
                self.log(f"🔄 Ruch: W+{turn_name} na {duration:.2f}s → {reason}")
            else:
                key_name = {self.VK_W: "W", self.VK_A: "A", self.VK_S: "S", self.VK_D: "D"}[movement_key]
                self.log(f"🔄 Ruch: {key_name} na {duration:.2f}s → {reason}")
        else:
            # Brak ruchu - od razu przejdź do waiting
            self.movement_state = "waiting_for_next"
            self.movement_pause_start_time = time.time()

    def update_movement_state(self, hwnd):
        """Aktualizuje stan ruchu"""
        current_time = time.time()

        if self.movement_state == "moving":
            # Sprawdź czy skończyć dodatkowy skręt (A/D z W)
            if (self.turn_key_pressed and
                current_time - self.turn_start_time_with_w >= self.turn_duration_with_w):
                self.send_key_up(hwnd, self.turn_key_with_w)
                self.turn_key_pressed = False
                self.turn_key_with_w = None

            # Sprawdź czy skończył się główny ruch
            if current_time - self.movement_start_time >= self.movement_duration:
                self.stop_movement(hwnd)
                self.movement_state = "waiting_for_next"
                self.movement_pause_start_time = current_time
                self.movement_pause_duration = random.uniform(0.1, 0.3)

        elif self.movement_state == "waiting_for_next":
            # Sprawdź czy skończył się czas czekania
            if current_time - self.movement_pause_start_time >= self.movement_pause_duration:
                self.movement_state = "ready_for_next_move"

    def simple_exploration(self, hwnd):
        """Stary system eksploracji - sprawdzony i działający"""
        current_time = time.time()

        # Sprawdź czy można się ruszyć
        if self.movement_state not in ["ready_for_next_move"]:
            return

        # Prosty system eksploracji jak w starym kodzie
        rand = random.random()
        if rand < 0.8:  # 80% do przodu
            movement_key = self.VK_W
            duration = self.medium_movement_duration
            reason = "Eksploracja PRZÓD"
        elif rand < 0.9:  # 10% lewo
            movement_key = self.VK_A
            duration = self.micro_movement_duration
            reason = "Eksploracja LEWO"
        elif rand < 0.95:  # 5% prawo
            movement_key = self.VK_D
            duration = self.micro_movement_duration
            reason = "Eksploracja PRAWO"
        else:  # 5% wstecz
            movement_key = self.VK_S
            duration = self.micro_movement_duration
            reason = "Eksploracja WSTECZ"

        self.start_movement(hwnd, movement_key, duration, reason)

    # ========================================
    # 2. SYSTEM TRAPEZA KAMERY
    # ========================================

    def is_enemy_in_trapezoid(self, enemy_x, enemy_y):
        """Sprawdza czy przeciwnik jest w trapezie kamery"""
        # Sprawdź czy Y jest w zakresie (od środka ekranu w górę)
        if enemy_y > self.trapez_bottom_y or enemy_y < self.trapez_top_y:
            return False

        # Oblicz szerokość trapeza na wysokości przeciwnika
        y_ratio = (self.trapez_bottom_y - enemy_y) / self.trapez_height
        width_at_y = self.trapez_top_width * y_ratio

        # Sprawdź czy X jest w zakresie
        left_bound = self.screen_center_x - width_at_y / 2
        right_bound = self.screen_center_x + width_at_y / 2

        return left_bound <= enemy_x <= right_bound

    def get_camera_adjustment_direction(self, enemy_x, enemy_y):
        """Określa kierunek korekty kamery"""
        if enemy_x < self.screen_center_x:
            return "left"  # Przeciwnik po lewej - skręć kamerę w lewo (A)
        else:
            return "right"  # Przeciwnik po prawej - skręć kamerę w prawo (D)

    def micro_camera_adjust(self, hwnd, direction):
        """Wykonuje mikro-ruch kamery"""
        current_time = time.time()

        # Sprawdź cooldown
        if current_time - self.last_camera_adjustment < self.micro_camera_cooldown:
            return False

        # Określ klawisz
        key = self.VK_A if direction == "left" else self.VK_D

        # Rozpocznij mikro-ruch
        self.send_key_down(hwnd, key)
        self.camera_adjusting = True
        self.camera_key_pressed = key
        self.camera_key_start_time = current_time
        self.last_camera_adjustment = current_time
        self.stats['camera_adjustments'] += 1

        # Rzadsze logowanie dla wydajności
        if self.stats['camera_adjustments'] % 3 == 0:
            self.log(f"📹 Mikro-ruch kamery: {direction}")
        return True

    def update_camera_adjustment(self, hwnd):
        """Aktualizuje stan mikro-ruchu kamery"""
        if not self.camera_adjusting:
            return

        current_time = time.time()
        if current_time - self.camera_key_start_time >= self.micro_camera_duration:
            # Zakończ mikro-ruch
            self.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_adjusting = False
            self.camera_key_pressed = None

    # ========================================
    # 3. UPROSZCZONY SYSTEM ATAKU
    # ========================================

    def simple_attack(self, hwnd):
        """Uproszczony atak z wagami - losowy klawisz według priorytetów"""
        current_time = time.time()

        if current_time - self.last_attack_time < self.attack_interval:
            return False

        # Wybór klawisza według wag
        rand = random.random()
        cumulative_weight = 0
        attack_key = self.VK_1  # fallback

        for key, weight in self.attack_weights.items():
            cumulative_weight += weight
            if rand <= cumulative_weight:
                attack_key = key
                break

        if self.send_key_press(hwnd, attack_key):
            self.last_attack_time = current_time
            self.attack_interval = random.uniform(0.8, 1.5)  # Nowy random interval

            key_name = str(attack_key - 0x30)  # Convert to number string
            self.log(f"⚔️ Atak: {key_name}")
            return True

        return False

    # ========================================
    # 4. EMERGENCY BACKSTEP
    # ========================================

    def check_emergency_backstep(self, enemy_x, enemy_y):
        """Sprawdza czy potrzebny emergency backstep"""
        # Oblicz odległość od środka ekranu
        dx = enemy_x - self.screen_center_x
        dy = enemy_y - self.screen_center_y
        distance = math.sqrt(dx*dx + dy*dy)

        return distance < self.emergency_distance_threshold

    def start_emergency_backstep(self, hwnd):
        """Rozpoczyna emergency backstep"""
        current_time = time.time()

        if current_time - self.last_emergency_backstep < self.emergency_backstep_cooldown:
            return False

        # Zatrzymaj inne ruchy
        self.stop_movement(hwnd)

        # Rozpocznij backstep
        self.send_key_down(hwnd, self.VK_S)
        self.emergency_backstep_active = True
        self.emergency_backstep_start_time = current_time
        self.last_emergency_backstep = current_time
        self.stats['emergency_backsteps'] += 1

        self.log(f"🚨 EMERGENCY BACKSTEP! Mob za blisko")
        return True

    def update_emergency_backstep(self, hwnd):
        """Aktualizuje emergency backstep"""
        if not self.emergency_backstep_active:
            return

        current_time = time.time()
        if current_time - self.emergency_backstep_start_time >= self.emergency_backstep_duration:
            # Zakończ backstep
            self.send_key_up(hwnd, self.VK_S)
            self.emergency_backstep_active = False
            self.log("✅ Emergency backstep zakończony")

    # ========================================
    # 5. KLIKANIE W OSTATNIĄ POZYCJĘ
    # ========================================

    def remember_enemy_position(self, enemy_x, enemy_y):
        """Zapamiętuje pozycję przeciwnika"""
        self.last_enemy_position = (enemy_x, enemy_y)
        self.last_enemy_seen_time = time.time()

    def click_last_enemy_position(self, hwnd):
        """Klika w ostatnią zapamiętaną pozycję przeciwnika"""
        current_time = time.time()

        # Sprawdź czy mamy zapamiętaną pozycję
        if not self.last_enemy_position:
            return False

        # Sprawdź czy pozycja nie jest za stara
        if current_time - self.last_enemy_seen_time > self.enemy_memory_duration:
            self.last_enemy_position = None
            return False

        # Sprawdź cooldown
        if current_time - self.last_click_on_position < self.click_position_cooldown:
            return False

        enemy_x, enemy_y = self.last_enemy_position

        try:
            # Kliknij prawym przyciskiem
            lParam = win32api.MAKELONG(int(enemy_x), int(enemy_y))
            win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lParam)
            time.sleep(0.05)
            win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lParam)

            self.last_click_on_position = current_time
            self.stats['position_clicks'] += 1

            self.log(f"🎯 Kliknięcie w ostatnią pozycję: ({enemy_x:.0f}, {enemy_y:.0f})")
            return True

        except Exception as e:
            self.log(f"❌ Błąd kliknięcia: {str(e)}")
            return False

    # ========================================
    # 6. PODSTAWOWE FUNKCJE KLAWISZY
    # ========================================

    def send_key_down(self, hwnd, vk_code):
        """Naciska klawisz"""
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            return True
        except Exception as e:
            self.log(f"Błąd naciśnięcia klawisza {vk_code}: {str(e)}")
            return False

    def send_key_up(self, hwnd, vk_code):
        """Puszcza klawisz"""
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
            return True
        except Exception as e:
            self.log(f"Błąd puszczenia klawisza {vk_code}: {str(e)}")
            return False

    def send_key_press(self, hwnd, vk_code):
        """Naciśnij i puść klawisz"""
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(0.05)
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
            return True
        except Exception as e:
            self.log(f"Błąd naciśnięcia klawisza {vk_code}: {str(e)}")
            return False

    # ========================================
    # 7. GŁÓWNA PĘTLA UPDATE
    # ========================================

    def update(self, hwnd, detections=None):
        """Główna funkcja aktualizacji - NOWA UPROSZCZONA LOGIKA"""
        current_time = time.time()

        # Aktualizuj stany mikro-operacji
        self.update_camera_adjustment(hwnd)
        self.update_emergency_backstep(hwnd)

        # KROK 1: Znajdź przeciwników
        enemies = []
        if detections:
            for detection in detections:
                name = detection.get('name', '').lower()
                if any(keyword in name for keyword in ['mob', 'enemy', 'monster', 'target', 'health_bar']):
                    enemies.append(detection)

        # KROK 2: Aktualizuj stany ruchów
        self.update_movement_state(hwnd)
        # KROK 3: Określ czy mamy aktywnego przeciwnika
        if enemies:
            # Wybierz najbliższego przeciwnika
            closest_enemy = min(enemies, key=lambda e:
                abs(e.get('center_x', self.screen_center_x) - self.screen_center_x) +
                abs(e.get('center_y', self.screen_center_y) - self.screen_center_y))

            enemy_x = closest_enemy['center_x']
            enemy_y = closest_enemy['center_y']

            # Zapamiętaj pozycję
            self.remember_enemy_position(enemy_x, enemy_y)

            if not self.has_enemy:
                self.log("🎯 Wykryto przeciwnika - przechodzę do walki")
                self.has_enemy = True
                self.mode = "combat"
                self.stats['combat_sessions'] += 1
                self.stop_movement(hwnd)

                # Reset grace period
                self.in_grace_period = False

            self.current_enemy_position = (enemy_x, enemy_y)

            # Emergency backstep check
            if self.check_emergency_backstep(enemy_x, enemy_y):
                if not self.emergency_backstep_active:
                    self.start_emergency_backstep(hwnd)
                    return

            # Sprawdź pozycjonowanie kamery (jeśli nie w emergency backstep)
            if not self.emergency_backstep_active:
                if not self.is_enemy_in_trapezoid(enemy_x, enemy_y):
                    if not self.camera_adjusting:
                        direction = self.get_camera_adjustment_direction(enemy_x, enemy_y)
                        self.micro_camera_adjust(hwnd, direction)

                # Atakuj
                self.simple_attack(hwnd)

        else:
            # BRAK PRZECIWNIKÓW
            current_time = time.time()

            if self.has_enemy:
                # Przeciwnik zniknął - rozpocznij GRACE PERIOD (5 sekund)
                if not self.in_grace_period:
                    self.in_grace_period = True
                    self.grace_period_start_time = current_time
                    self.log("⏳ Przeciwnik zniknął - grace period 5s (kontynuuję walkę)")

                # Sprawdź czy grace period się skończył
                grace_time_elapsed = current_time - self.grace_period_start_time
                if grace_time_elapsed >= self.enemy_lost_grace_period:
                    # Grace period minął - przejdź do eksploracji
                    self.log("👻 Grace period minął - wracam do eksploracji")
                    self.has_enemy = False
                    self.mode = "exploration"
                    self.current_enemy_position = None
                    self.in_grace_period = False
                else:
                    # Nadal w grace period - kontynuuj walkę
                    remaining_grace = self.enemy_lost_grace_period - grace_time_elapsed
                    if int(remaining_grace) != int(remaining_grace + 0.1):  # Log co sekundę
                        self.log(f"⏳ Grace period: {remaining_grace:.1f}s pozostało")

                    # Próbuj kliknąć w ostatnią pozycję
                    self.click_last_enemy_position(hwnd)

                    # Kontynuuj ataki w miejscu
                    self.simple_attack(hwnd)

                    # Nie rozpoczynaj eksploracji podczas grace period!
                    return

            else:
                # Nie ma przeciwnika i nie jesteśmy w grace period
                self.in_grace_period = False

            # Eksploracja (tylko jeśli nie w emergency backstep i nie w grace period)
            if not self.emergency_backstep_active and not self.in_grace_period:
                if self.mode == "exploration":
                    self.simple_exploration(hwnd)

    def emergency_stop(self, hwnd):
        """Awaryjne zatrzymanie wszystkich akcji"""
        self.stop_movement(hwnd)

        if self.camera_key_pressed:
            self.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_adjusting = False
            self.camera_key_pressed = None

        if self.emergency_backstep_active:
            self.send_key_up(hwnd, self.VK_S)
            self.emergency_backstep_active = False

        self.has_enemy = False
        self.current_enemy_position = None
        self.last_enemy_position = None
        self.mode = "exploration"

        # Reset grace period
        self.in_grace_period = False

        self.log("🚨 AWARYJNE ZATRZYMANIE")

    def get_status(self):
        """Zwraca aktualny status controllera"""
        status_parts = []

        if self.mode == "combat":
            status_parts.append("⚔️ WALKA")
        elif self.mode == "exploration":
            status_parts.append("🔄 EKSPLORACJA")

        if self.emergency_backstep_active:
            status_parts.append("🚨 EMERGENCY BACKSTEP")

        if self.in_grace_period:
            remaining = self.enemy_lost_grace_period - (time.time() - self.grace_period_start_time)
            status_parts.append(f"⏳ GRACE {remaining:.1f}s")

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
            status_parts.append(f"[Pauza: {remaining_pause:.2f}s]")

        if self.camera_adjusting:
            direction = "←" if self.camera_key_pressed == self.VK_A else "→"
            status_parts.append(f"[CAM:{direction}]")

        if self.last_enemy_position:
            time_since = time.time() - self.last_enemy_seen_time
            status_parts.append(f"[LastPos:{time_since:.1f}s]")

        return " ".join(status_parts) if status_parts else "🟢 GOTOWY"

    def get_stats(self):
        """Zwraca statystyki controllera"""
        return {
            'mode': self.mode,
            'has_enemy': self.has_enemy,
            'current_enemy_position': self.current_enemy_position,
            'movement_state': self.movement_state,
            'current_movement_key': self.current_movement_key,
            'turn_key_pressed': self.turn_key_pressed,
            'turn_key_with_w': self.turn_key_with_w,
            'camera_adjusting': self.camera_adjusting,
            'emergency_backstep_active': self.emergency_backstep_active,
            'in_grace_period': self.in_grace_period,
            'grace_period_remaining': max(0, self.enemy_lost_grace_period - (time.time() - self.grace_period_start_time)) if self.in_grace_period else 0,
            'last_enemy_position': self.last_enemy_position,
            'stats': self.stats,

            # Trapez konfiguracja
            'trapez_top_width': self.trapez_top_width,
            'trapez_height': self.trapez_height,
            'trapez_bottom_y': self.trapez_bottom_y,
            'trapez_top_y': self.trapez_top_y,

            # Wagi ataków
            'attack_weights': self.attack_weights,
        }

# Aliasy dla kompatybilności
CombatController = SimplifiedCombatController
ReactiveCombatController = SimplifiedCombatController
MotionCompensatedCombatController = SimplifiedCombatController
WoWAwareCombatController = SimplifiedCombatController