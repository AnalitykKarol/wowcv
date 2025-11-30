"""
Reactive Combat Controller - Uproszczony i naprawiony system walki
Z bezpieczną metodą klikania oparta na WoW research
Kompatybilny z main_window.py - wszystkie wymagane metody zachowane
+ Dodana funkcja okresowego naciskania przycisku I co ~30 minut
"""
import win32api
import win32con
import win32gui
import time
import random
import math
import ctypes
from ctypes import wintypes

class ReactiveCombatController:
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
        self.VK_I = 0x49  # Dodany klawisz I
        self.VK_RBUTTON = 0x02

        # ========================================
        # SYSTEM PRZYCISKU I - NOWY
        # ========================================
        self.i_button_enabled = True  # Można włączyć/wyłączyć
        self.i_button_interval_base = 30 * 60  # 30 minut w sekundach
        self.i_button_interval_variance = 5 * 60  # ±5 minut losowości
        self.i_button_last_press = 0
        self.i_button_next_press = 0
        self.i_button_hold_duration = (0.1, 0.3)  # Czas trzymania przycisku (min, max)

        # Statystyki przycisku I
        self.i_button_stats = {
            'total_presses': 0,
            'successful_presses': 0,
            'failed_presses': 0,
            'last_press_time': 0,
            'next_press_in': 0
        }

        # Ustawienie pierwszego naciśnięcia
        self._schedule_next_i_press()

        # ========================================
        # GŁÓWNY STAN SYSTEMU - JEDEN JASNY FLOW
        # ========================================
        self.mode = "exploration"  # exploration, combat, grace_period
        self.last_enemy_position = None
        self.last_enemy_seen_time = 0

        # Grace period - JEDEN SYSTEM
        self.grace_period_duration = 6.0  # całkowity czas grace period
        self.grace_period_start_time = 0

        # ========================================
        # SYSTEM EKSPLORACJI
        # ========================================
        self.movement_state = "ready_for_next_move"
        self.current_movement_key = None
        self.movement_start_time = 0
        self.movement_duration = 0
        self.movement_pause_start_time = 0
        self.movement_pause_duration = random.uniform(0.01, 0.3)

        # Długości ruchów
        self.micro_movement_duration = random.uniform(0.1, 0.2)
        self.short_movement_duration = random.uniform(0.25, 0.4)
        self.medium_movement_duration = random.uniform(0.6, 4)

        # W+A/D system
        self.w_plus_turn_chance = 0.3
        self.turn_key_with_w = None
        self.turn_key_pressed = False
        self.turn_duration_with_w = 0
        self.turn_start_time_with_w = 0

        # ========================================
        # SYSTEM KAMERY - będzie skonfigurowany przez configure_screen_size()
        # ========================================
        self.screen_width = 1920  # domyślne
        self.screen_height = 1080  # domyślne
        self.screen_center_x = 960  # domyślne
        self.screen_center_y = 540  # domyślne

        # Trapez parameters - będą skonfigurowane przez configure_screen_size()
        self.trapez_bottom_width = 192  # domyślne 10% z 1920
        self.trapez_top_width = 576  # domyślne 30% z 1920
        self.trapez_height = 324  # domyślne 30% z 1080
        self.trapez_bottom_y = self.screen_center_y
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        # Mikro-ruchy kamery
        self.micro_camera_duration = random.uniform(0.005, 0.01)
        self.micro_camera_cooldown = random.uniform(0.8, 1.1)
        self.last_camera_adjustment = 0
        self.camera_adjusting = False
        self.camera_key_pressed = None
        self.camera_key_start_time = 0

        # ========================================
        # SYSTEM ATAKU
        # ========================================
        self.attack_keys = [self.VK_1, self.VK_2, self.VK_3, self.VK_4,
                           self.VK_5, self.VK_6, self.VK_7, self.VK_8]

        # Wagi dla klawiszy
        self.attack_weights = {
            self.VK_1: 0.25,   # 25%
            self.VK_2: 0.25,  # 25%
            self.VK_3: 0.2,   # 20%
            self.VK_4: 0.1,  # 10%
            self.VK_5: 0.05,  # 5%
            self.VK_6: 0.025, # 2.5%
            self.VK_7: 0.1, # 10%
            self.VK_8: 0.025   # 2.5%
        }

        self.last_attack_time = 0
        self.attack_interval = random.uniform(0.8, 1.5)

        # ========================================
        # EMERGENCY BACKSTEP
        # ========================================
        self.emergency_distance_threshold = 150
        self.emergency_backstep_duration = random.uniform(0.2, 0.6)
        self.emergency_backstep_cooldown = random.uniform(8, 10)
        self.last_emergency_backstep = 0
        self.emergency_backstep_active = False
        self.emergency_backstep_start_time = 0

        # ========================================
        # SYSTEM KLIKANIA - BEZPIECZNY WoW
        # ========================================
        self.last_combat_click = 0
        self.last_loot_click = 0
        self.combat_click_cooldown = (1.5, 3.0)  # min, max
        self.loot_click_cooldown = (0.5, 1)    # min, max
        self.loot_offset_range = (10, 60)        # min, max pikseli w dół

        # WoW-specific click tracking dla human-like behavior
        self.click_patterns = []
        self.detection_evasion = True
        self.last_successful_method = None

        # Statystyki
        self.stats = {
            'combat_sessions': 0,
            'camera_adjustments': 0,
            'emergency_backsteps': 0,
            'position_clicks': 0,
            'successful_clicks': 0,
            'failed_clicks': 0,
            'method_stats': {
                'wow_proven': 0,
                'warcraft_style': 0
            }
        }

    def log(self, message):
        """Helper do logowania"""
        if self.logger:
            self.logger.info(message)
        else:
            print(message)

    # ========================================
    # SYSTEM PRZYCISKU I - NOWE FUNKCJE
    # ========================================

    def _schedule_next_i_press(self):
        """Zaplanuj następne naciśnięcie przycisku I"""
        current_time = time.time()

        # Losowy interval: 30 minut ± 5 minut
        random_variance = random.uniform(-self.i_button_interval_variance,
                                       self.i_button_interval_variance)
        interval = self.i_button_interval_base + random_variance

        self.i_button_next_press = current_time + interval

        # Aktualizuj statystyki
        self.i_button_stats['next_press_in'] = interval

        self.log(f"📅 Następne naciśnięcie 'I' zaplanowane za {interval/60:.1f} minut")

    def _should_press_i_button(self):
        """Sprawdź czy pora nacisnąć przycisk I"""
        if not self.i_button_enabled:
            return False

        current_time = time.time()
        return current_time >= self.i_button_next_press

    def _press_i_button(self, hwnd):
        """Naciśnij przycisk I z human-like timing"""
        try:
            current_time = time.time()

            # Losowy czas trzymania przycisku
            hold_duration = random.uniform(*self.i_button_hold_duration)

            # Naciśnij
            success1 = self.send_key_down(hwnd, self.VK_I)
            if not success1:
                self.i_button_stats['failed_presses'] += 1
                return False

            # Trzymaj przez losowy czas
            time.sleep(hold_duration)

            # Puść
            success2 = self.send_key_up(hwnd, self.VK_I)

            if success1 and success2:
                self.i_button_stats['successful_presses'] += 1
                self.i_button_stats['last_press_time'] = current_time
                self.i_button_last_press = current_time
                self.log(f"📋 Naciśnięto przycisk 'I' (trzymano {hold_duration:.2f}s)")

                # Zaplanuj następne naciśnięcie
                self._schedule_next_i_press()
                return True
            else:
                self.i_button_stats['failed_presses'] += 1
                return False

        except Exception as e:
            self.log(f"❌ Błąd naciśnięcia przycisku 'I': {e}")
            self.i_button_stats['failed_presses'] += 1
            return False
        finally:
            self.i_button_stats['total_presses'] += 1

    def update_i_button_system(self, hwnd):
        """Aktualizuj system przycisku I (wywoływane w głównej pętli)"""
        if self._should_press_i_button():
            self._press_i_button(hwnd)

    def get_i_button_status(self):
        """Zwróć status systemu przycisku I"""
        if not self.i_button_enabled:
            return "⏸️ WYŁĄCZONY"

        current_time = time.time()
        time_until_next = self.i_button_next_press - current_time

        if time_until_next <= 0:
            return "⏰ GOTOWY DO NACIŚNIĘCIA"
        elif time_until_next < 60:
            return f"⏱️ NASTĘPNY ZA {time_until_next:.0f}s"
        elif time_until_next < 3600:
            return f"⏱️ NASTĘPNY ZA {time_until_next/60:.1f}min"
        else:
            return f"⏱️ NASTĘPNY ZA {time_until_next/3600:.1f}h"

    def configure_i_button(self, enabled=True, interval_minutes=30, variance_minutes=5,
                          hold_duration_min=0.1, hold_duration_max=0.3):
        """Konfiguruj system przycisku I"""
        self.i_button_enabled = enabled
        self.i_button_interval_base = interval_minutes * 60
        self.i_button_interval_variance = variance_minutes * 60
        self.i_button_hold_duration = (hold_duration_min, hold_duration_max)

        if enabled:
            self._schedule_next_i_press()
            self.log(f"📋 Przycisk 'I': WŁĄCZONY (co {interval_minutes}±{variance_minutes}min)")
        else:
            self.log(f"📋 Przycisk 'I': WYŁĄCZONY")

    def get_i_button_stats(self):
        """Zwróć szczegółowe statystyki przycisku I"""
        current_time = time.time()
        time_until_next = max(0, self.i_button_next_press - current_time)
        time_since_last = current_time - self.i_button_last_press if self.i_button_last_press > 0 else 0

        return {
            'enabled': self.i_button_enabled,
            'total_presses': self.i_button_stats['total_presses'],
            'successful_presses': self.i_button_stats['successful_presses'],
            'failed_presses': self.i_button_stats['failed_presses'],
            'success_rate': (self.i_button_stats['successful_presses'] / max(1, self.i_button_stats['total_presses'])) * 100,
            'time_until_next_press': time_until_next,
            'time_since_last_press': time_since_last,
            'next_press_formatted': self.get_i_button_status(),
            'interval_minutes': self.i_button_interval_base / 60,
            'variance_minutes': self.i_button_interval_variance / 60
        }

    # ========================================
    # HUMAN-LIKE BEHAVIOR & EVASION
    # ========================================

    def configure_screen_size(self, window_width, window_height):
        """Konfiguruje rozmiary ekranu i trapeza na podstawie rozmiaru okna"""
        # Ustaw środek ekranu
        self.screen_width = window_width
        self.screen_height = window_height
        self.screen_center_x = window_width // 2
        self.screen_center_y = window_height // 2

        # Konfiguruj trapez z nowymi proporcjami
        self.trapez_bottom_width = int(window_width * 0.1)  # 10% na dole (środek ekranu)
        self.trapez_top_width = int(window_width * 0.3)  # 30% u góry
        self.trapez_height = int(window_height * 0.3)  # wysokość 30% ekranu w górę od środka

        # Pozycje trapeza
        self.trapez_bottom_y = self.screen_center_y
        self.trapez_top_y = self.trapez_bottom_y - self.trapez_height

        # Dostosuj inne wartości proporcjonalnie (opcjonalne)
        base_width = 1920  # bazowa rozdzielczość
        scale_factor = window_width / base_width

        self.emergency_distance_threshold = int(70 * scale_factor)
        self.loot_offset_range = (int(10 * scale_factor), int(60 * scale_factor))

        self.log(f"🖥️ Skonfigurowano ekran: {window_width}x{window_height}")
        self.log(
            f"📐 Trapez: dół {self.trapez_bottom_width}px, góra {self.trapez_top_width}px, wysokość {self.trapez_height}px")

    def add_human_like_delay(self):
        """Dodaje human-like delay między klikami"""
        current_time = time.time()

        # Minimum delay między klikami (human reaction time)
        min_delay = 0.1
        if current_time - self.last_combat_click < min_delay:
            sleep_time = min_delay - (current_time - self.last_combat_click)
            time.sleep(sleep_time)

        # Random micro-delays dla realistyczności
        time.sleep(random.uniform(0.001, 0.01))

    def add_click_pattern(self, x, y, success):
        """Śledzi wzorce kliknięć dla analizy human-like behavior"""
        current_time = time.time()
        self.click_patterns.append({
            'x': x,
            'y': y,
            'time': current_time,
            'success': success
        })

        # Zachowaj tylko ostatnie 50 kliknięć
        if len(self.click_patterns) > 50:
            self.click_patterns.pop(0)

    # ========================================
    # METODY KLIKANIA - OPARTE NA WoW RESEARCH
    # ========================================

    def method_1_wow_proven_postmessage(self, hwnd, x, y):
        """
        Metoda 1: Proven WoW PostMessage format
        Oparta na working Stack Overflow solution
        """
        try:
            # Format zgodny z working WoW example: ((y << 16) | (x & 0xFFFF))
            lParam = ((int(y) << 16) | (int(x) & 0xFFFF))

            # Sekwencja jak w working code
            result1 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, 0, lParam)
            time.sleep(random.uniform(0.005, 0.015))  # Human-like hold time
            result2 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lParam)

            success = bool(result1 and result2)
            if success:
                self.stats['method_stats']['wow_proven'] += 1
            return success

        except Exception as e:
            self.log(f"❌ WoW Proven method failed: {e}")
            return False

    def method_2_warcraft_style_postmessage(self, hwnd, x, y):
        """
        Metoda 2: Warcraft 3 working solution adapted for WoW
        PostMessage z MK_RBUTTON jako wParam
        """
        try:
            # Format z working Warcraft code
            lParam = ((int(y) << 16) | int(x))
            wParam_down = win32con.MK_RBUTTON  # Kluczowe dla working solution
            wParam_up = 0

            # Sekwencja z working example
            result1 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, wParam_down, lParam)
            time.sleep(random.uniform(0.01, 0.03))
            result2 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, wParam_up, lParam)

            success = bool(result1 and result2)
            if success:
                self.stats['method_stats']['warcraft_style'] += 1
            return success

        except Exception as e:
            self.log(f"❌ Warcraft style method failed: {e}")
            return False

    def method_3_evasion_technique(self, hwnd, x, y):
        """
        Metoda 3: Anti-detection technique
        Oparta na research o Windows 10 security bypass
        """
        try:
            if not self.detection_evasion:
                return False

            # Sprawdź focus (anticheat może to monitorować)
            foreground = win32gui.GetForegroundWindow()
            if foreground != hwnd:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(random.uniform(0.01, 0.05))  # Krótki delay

            # Human-like delay
            self.add_human_like_delay()

            # Format lParam z bitwise operations (mniej podejrzane)
            lParam = (int(y) << 16) + (int(x) & 0xFFFF)

            # Sekwencja z dodatkowymi events dla realistyczności
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
            time.sleep(0.001)
            win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, 0x0002, lParam)
            time.sleep(random.uniform(0.015, 0.035))  # Realistic hold time
            win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lParam)

            self.stats['method_stats']['evasion_technique'] += 1
            return True

        except Exception as e:
            self.log(f"❌ Evasion technique failed: {e}")
            return False

    def method_4_sendinput_admin_bypass(self, hwnd, x, y):
        """
        Metoda 4: SendInput z admin privileges
        Może ominąć niektóre zabezpieczenia WoW
        """
        try:
            # Sprawdź admin rights (wymagane dla tego bypass)
            if not ctypes.windll.shell32.IsUserAnAdmin():
                return False

            # Konwertuj na screen coordinates
            screen_x, screen_y = win32gui.ClientToScreen(hwnd, (int(x), int(y)))

            # SendInput structures
            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [("dx", ctypes.c_long),
                           ("dy", ctypes.c_long),
                           ("mouseData", wintypes.DWORD),
                           ("dwFlags", wintypes.DWORD),
                           ("time", wintypes.DWORD),
                           ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

            class INPUT(ctypes.Structure):
                class _INPUT(ctypes.Union):
                    _fields_ = [("mi", MOUSEINPUT)]
                _anonymous_ = ("_input",)
                _fields_ = [("type", wintypes.DWORD),
                           ("_input", _INPUT)]

            # Constants
            INPUT_MOUSE = 0
            MOUSEEVENTF_RIGHTDOWN = 0x0008
            MOUSEEVENTF_RIGHTUP = 0x0010
            MOUSEEVENTF_ABSOLUTE = 0x8000

            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)

            # Convert to absolute coordinates (0-65535)
            abs_x = int((screen_x * 65536) / screen_width)
            abs_y = int((screen_y * 65536) / screen_height)

            # Create input sequence
            inputs = []

            # Right button down
            down_input = INPUT()
            down_input.type = INPUT_MOUSE
            down_input.mi.dx = abs_x
            down_input.mi.dy = abs_y
            down_input.mi.dwFlags = MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_ABSOLUTE
            inputs.append(down_input)

            # Right button up
            up_input = INPUT()
            up_input.type = INPUT_MOUSE
            up_input.mi.dx = abs_x
            up_input.mi.dy = abs_y
            up_input.mi.dwFlags = MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_ABSOLUTE
            inputs.append(up_input)

            # Send inputs atomically
            inputs_array = (INPUT * len(inputs))(*inputs)
            result = user32.SendInput(len(inputs), inputs_array, ctypes.sizeof(INPUT))

            success = (result == len(inputs))
            if success:
                self.stats['method_stats']['sendinput_admin'] += 1
            return success

        except Exception as e:
            self.log(f"❌ SendInput admin method failed: {e}")
            return False

    def method_5_hybrid_fallback(self, hwnd, x, y):
        """
        Metoda 5: Hybrid fallback - próbuje różne formaty lParam
        """
        try:
            # Multiple lParam formats to try
            formats = [
                win32api.MAKELONG(int(x), int(y)),     # Standard MAKELONG
                (int(x) + (int(y) << 16)),             # Alternative shift
                ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)  # Mask both coordinates
            ]

            for i, lParam in enumerate(formats):
                try:
                    result1 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lParam)
                    time.sleep(random.uniform(0.005, 0.015))
                    result2 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lParam)

                    if result1 and result2:
                        self.stats['method_stats']['hybrid_fallback'] += 1
                        return True

                except Exception:
                    continue

            return False

        except Exception as e:
            self.log(f"❌ Hybrid fallback failed: {e}")
            return False

    # ========================================
    # GŁÓWNA FUNKCJA KLIKANIA - UPROSZCZONA (2 METODY)
    # ========================================

    def perform_right_click(self, hwnd, x, y, is_loot=False):
        """
        Uproszczona funkcja klikania - tylko 2 najlepsze metody
        """
        try:
            # Offset dla loot
            if is_loot:
                offset_y = random.randint(*self.loot_offset_range)
                y += offset_y
                click_type = "📦 Loot"
            else:
                click_type = "🔫 Combat"

            # Tylko 2 pierwsze metody
            methods = [
                ("WoW Proven PostMessage", self.method_1_wow_proven_postmessage),
                ("Warcraft Style PostMessage", self.method_2_warcraft_style_postmessage)
            ]

            # Jeśli mamy ostatnio udaną metodę, spróbuj ją najpierw
            if self.last_successful_method:
                for method_name, method_func in methods:
                    if method_name == self.last_successful_method:
                        if method_func(hwnd, x, y):
                            self.add_click_pattern(x, y, True)
                            self.stats['successful_clicks'] += 1
                            self.stats['position_clicks'] += 1
                            self.update_click_timers(is_loot)
                            self.log(f"✅ {click_type} {method_name} (cached) na ({x:.0f}, {y:.0f})")
                            return True
                        break

            # Próbuj obie metody w kolejności
            for method_name, method_func in methods:
                try:
                    if method_func(hwnd, x, y):
                        self.last_successful_method = method_name
                        self.add_click_pattern(x, y, True)
                        self.stats['successful_clicks'] += 1
                        self.stats['position_clicks'] += 1
                        self.update_click_timers(is_loot)
                        self.log(f"✅ {click_type} {method_name} na ({x:.0f}, {y:.0f})")
                        return True
                except Exception as e:
                    self.log(f"⚠️ {method_name} exception: {e}")
                    continue

            # Obie metody zawiodły
            self.add_click_pattern(x, y, False)
            self.stats['failed_clicks'] += 1
            self.log(f"❌ {click_type} OBE METODY ZAWIODŁY na ({x:.0f}, {y:.0f})")
            return False

        except Exception as e:
            self.log(f"❌ Błąd perform_right_click: {str(e)}")
            return False

    def update_click_timers(self, is_loot):
        """Helper do aktualizacji timerów kliknięć"""
        current_time = time.time()
        if is_loot:
            self.last_loot_click = current_time
        else:
            self.last_combat_click = current_time

    # ========================================
    # SYSTEM EKSPLORACJI
    # ========================================

    def stop_movement(self, hwnd):
        """Zatrzymuje ruch"""
        if self.current_movement_key:
            self.send_key_up(hwnd, self.current_movement_key)
            self.current_movement_key = None

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

            # Jeśli to W, losowo dodaj A lub D
            if movement_key == self.VK_W and random.random() < self.w_plus_turn_chance:
                turn_key = random.choice([self.VK_A, self.VK_D])
                turn_duration = random.uniform(0.3, 0.8)

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
            self.movement_state = "waiting_for_next"
            self.movement_pause_start_time = time.time()

    def update_movement_state(self, hwnd):
        """Aktualizuje stan ruchu"""
        current_time = time.time()

        if self.movement_state == "moving":
            # Sprawdź czy skończyć dodatkowy skręt
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
            if current_time - self.movement_pause_start_time >= self.movement_pause_duration:
                self.movement_state = "ready_for_next_move"

    def simple_exploration(self, hwnd):
        """System eksploracji"""
        if self.movement_state not in ["ready_for_next_move"]:
            return

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
    # SYSTEM KAMERY
    # ========================================

    def is_enemy_in_trapezoid(self, enemy_x, enemy_y):
        """Sprawdza czy przeciwnik jest w trapezie kamery - rozszerzającym się w górę"""
        # Szybka eliminacja - sprawdź Y
        if enemy_y > self.trapez_bottom_y or enemy_y < self.trapez_top_y:
            return False

        # Oblicz szerokość trapeza na wysokości przeciwnika
        # y_ratio = 0.0 na dole (środek), 1.0 u góry
        y_ratio = (self.trapez_bottom_y - enemy_y) / self.trapez_height

        # Interpolacja szerokości: od bottom_width do top_width
        width_at_y = self.trapez_bottom_width + (self.trapez_top_width - self.trapez_bottom_width) * y_ratio

        # Sprawdź X
        left_bound = self.screen_center_x - width_at_y / 2
        right_bound = self.screen_center_x + width_at_y / 2

        return left_bound <= enemy_x <= right_bound

    def get_camera_adjustment_direction(self, enemy_x, enemy_y):
        """Określa kierunek korekty kamery"""
        if enemy_x < self.screen_center_x:
            return "left"
        else:
            return "right"

    def micro_camera_adjust(self, hwnd, direction):
        """Wykonuje mikro-ruch kamery"""
        current_time = time.time()

        if current_time - self.last_camera_adjustment < self.micro_camera_cooldown:
            return False

        key = self.VK_A if direction == "left" else self.VK_D

        self.send_key_down(hwnd, key)
        self.camera_adjusting = True
        self.camera_key_pressed = key
        self.camera_key_start_time = current_time
        self.last_camera_adjustment = current_time
        self.stats['camera_adjustments'] += 1

        if self.stats['camera_adjustments'] % 3 == 0:
            self.log(f"📹 Mikro-ruch kamery: {direction}")
        return True

    def update_camera_adjustment(self, hwnd):
        """Aktualizuje stan mikro-ruchu kamery"""
        if not self.camera_adjusting:
            return

        current_time = time.time()
        if current_time - self.camera_key_start_time >= self.micro_camera_duration:
            self.send_key_up(hwnd, self.camera_key_pressed)
            self.camera_adjusting = False
            self.camera_key_pressed = None

    # ========================================
    # SYSTEM ATAKU
    # ========================================

    def simple_attack(self, hwnd):
        """Uproszczony atak z wagami"""
        current_time = time.time()

        if current_time - self.last_attack_time < self.attack_interval:
            return False

        # Wybór klawisza według wag
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
            self.log(f"⚔️ Atak: {key_name}")
            return True

        return False

    # ========================================
    # EMERGENCY BACKSTEP
    # ========================================

    def check_emergency_backstep(self, enemy_x, enemy_y):
        """Sprawdza czy potrzebny emergency backstep"""
        dx = enemy_x - self.screen_center_x
        dy = enemy_y - self.screen_center_y
        distance = math.sqrt(dx*dx + dy*dy)

        return distance < self.emergency_distance_threshold

    def start_emergency_backstep(self, hwnd):
        """Rozpoczyna emergency backstep"""
        current_time = time.time()

        # Sprawdź cooldown
        if current_time - self.last_emergency_backstep < self.emergency_backstep_cooldown:
            return False

        self.stop_movement(hwnd)

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
            self.send_key_up(hwnd, self.VK_S)
            self.emergency_backstep_active = False
            self.log("✅ Emergency backstep zakończony")

    # ========================================
    # SYSTEM KLIKANIA - HELPERS
    # ========================================

    def can_combat_click(self):
        """Sprawdza czy można zrobić combat click"""
        current_time = time.time()
        cooldown = random.uniform(*self.combat_click_cooldown)
        return current_time - self.last_combat_click >= cooldown

    def can_loot_click(self):
        """Sprawdza czy można zrobić loot click"""
        current_time = time.time()
        cooldown = random.uniform(*self.loot_click_cooldown)
        return current_time - self.last_loot_click >= cooldown

    # ========================================
    # PODSTAWOWE FUNKCJE KLAWISZY
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
    # GŁÓWNA PĘTLA UPDATE - UPROSZCZONA
    # ========================================

    def update(self, hwnd, detections=None):
        """Główna funkcja aktualizacji - UPROSZCZONA LOGIKA"""
        current_time = time.time()

        # ========================================
        # AKTUALIZUJ SYSTEM PRZYCISKU I - NOWY
        # ========================================
        self.update_i_button_system(hwnd)

        # Aktualizuj stany mikro-operacji
        self.update_camera_adjustment(hwnd)
        self.update_emergency_backstep(hwnd)
        self.update_movement_state(hwnd)

        # Znajdź przeciwników
        enemies = []
        if detections:
            for detection in detections:
                name = detection.get('name', '').lower()
                if any(keyword in name for keyword in ['mob', 'enemy', 'monster', 'target', 'health_bar']):
                    enemies.append(detection)

        # ========================================
        # GŁÓWNA LOGIKA STANÓW - JEDEN JASNY FLOW
        # ========================================

        if enemies:
            # ===== MAMY PRZECIWNIKÓW =====
            closest_enemy = min(enemies, key=lambda e:
                abs(e.get('center_x', self.screen_center_x) - self.screen_center_x) +
                abs(e.get('center_y', self.screen_center_y) - self.screen_center_y))

            enemy_x = closest_enemy['center_x']
            enemy_y = closest_enemy['center_y']

            # Przejdź do trybu walki
            if self.mode != "combat":
                self.log("🎯 Wykryto przeciwnika - przechodzę do walki")
                self.mode = "combat"
                self.stats['combat_sessions'] += 1
                self.stop_movement(hwnd)

            # Zapamiętaj pozycję
            self.last_enemy_position = (enemy_x, enemy_y)
            self.last_enemy_seen_time = current_time

            # Emergency backstep check
            if self.check_emergency_backstep(enemy_x, enemy_y):
                if not self.emergency_backstep_active:
                    self.start_emergency_backstep(hwnd)
                    return

            # Sprawdź pozycjonowanie kamery
            if not self.emergency_backstep_active:
                if not self.is_enemy_in_trapezoid(enemy_x, enemy_y):
                    if not self.camera_adjusting:
                        direction = self.get_camera_adjustment_direction(enemy_x, enemy_y)
                        self.micro_camera_adjust(hwnd, direction)

                # Combat click w przeciwnika
                if self.can_combat_click():
                    self.perform_right_click(hwnd, enemy_x, enemy_y, is_loot=False)

                # Atakuj
                self.simple_attack(hwnd)

        else:
            # ===== BRAK PRZECIWNIKÓW =====

            if self.mode == "combat":
                # Właśnie straciliśmy przeciwnika - rozpocznij grace period
                self.log("👻 Przeciwnik zniknął - rozpoczynam grace period (loot)")
                self.mode = "grace_period"
                self.grace_period_start_time = current_time
                self.stop_movement(hwnd)

            elif self.mode == "grace_period":
                # Sprawdź czy grace period się skończył
                elapsed = current_time - self.grace_period_start_time

                if elapsed >= self.grace_period_duration:
                    # Koniec grace period - wracaj do eksploracji
                    self.log("🔄 Grace period zakończony - wracam do eksploracji")
                    self.mode = "exploration"
                    self.last_enemy_position = None
                else:
                    # W trakcie grace period - loot i atak w miejscu
                    remaining = self.grace_period_duration - elapsed

                    # Loguj co sekundę
                    if int(remaining) != int(remaining + 0.1):
                        self.log(f"📦 Grace period: {remaining:.1f}s pozostało")

                    # Loot clicking w ostatnią pozycję
                    if self.last_enemy_position and self.can_loot_click():
                        x, y = self.last_enemy_position
                        self.perform_right_click(hwnd, x, y, is_loot=True)

                    # Atak w miejscu podczas grace period
                    self.simple_attack(hwnd)

                    # BLOKUJ EKSPLORACJĘ podczas grace period
                    return

            # ===== EKSPLORACJA =====
            if self.mode == "exploration" and not self.emergency_backstep_active:
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

        self.mode = "exploration"
        self.last_enemy_position = None

        self.log("🚨 AWARYJNE ZATRZYMANIE")

    def get_status(self):
        """Zwraca aktualny status controllera"""
        status_parts = []

        if self.mode == "combat":
            status_parts.append("⚔️ WALKA")
        elif self.mode == "grace_period":
            remaining = self.grace_period_duration - (time.time() - self.grace_period_start_time)
            status_parts.append(f"📦 GRACE PERIOD ({remaining:.1f}s)")
        elif self.mode == "exploration":
            status_parts.append("🔄 EKSPLORACJA")

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
            status_parts.append(f"[Pauza: {remaining_pause:.2f}s]")

        if self.camera_adjusting:
            direction = "←" if self.camera_key_pressed == self.VK_A else "→"
            status_parts.append(f"[CAM:{direction}]")

        # Dodaj info o metodzie klikania (tylko 2 metody)
        if self.last_successful_method:
            method_short = {
                "WoW Proven PostMessage": "WoW",
                "Warcraft Style PostMessage": "WC3"
            }.get(self.last_successful_method, "UNK")
            status_parts.append(f"[CLICK:{method_short}]")

        # Dodaj status przycisku I
        i_status = self.get_i_button_status()
        status_parts.append(f"[I:{i_status}]")

        return " ".join(status_parts) if status_parts else "🟢 GOTOWY"

    # ========================================
    # KONFIGURACJA I STATYSTYKI
    # ========================================

    def configure_grace_period(self, duration=6.0):
        """Konfiguruj długość grace period"""
        self.grace_period_duration = duration
        self.log(f"⏱️ Grace period: {duration}s")

    def configure_combat_clicks(self, min_cooldown=1.5, max_cooldown=3.0):
        """Konfiguruj timing combat clicks"""
        self.combat_click_cooldown = (min_cooldown, max_cooldown)
        self.log(f"🔫 Combat clicks: {min_cooldown}-{max_cooldown}s cooldown")

    def configure_loot_clicks(self, min_cooldown=0.5, max_cooldown=1.0, offset_min=10, offset_max=25):
        """Konfiguruj timing i offset loot clicks"""
        self.loot_click_cooldown = (min_cooldown, max_cooldown)
        self.loot_offset_range = (offset_min, offset_max)
        self.log(f"📦 Loot clicks: {min_cooldown}-{max_cooldown}s cooldown, {offset_min}-{offset_max}px offset")

    def configure_emergency_backstep(self, threshold=70, duration_min=0.2, duration_max=0.6, cooldown=2.0):
        """Konfiguruj emergency backstep"""
        self.emergency_distance_threshold = threshold
        self.emergency_backstep_duration = random.uniform(duration_min, duration_max)
        self.emergency_backstep_cooldown = cooldown
        self.log(f"🚨 Emergency backstep: <{threshold}px, {duration_min}-{duration_max}s duration, {cooldown}s cooldown")

    def configure_detection_evasion(self, enabled=True):
        """Włącz/wyłącz techniki unikania detekcji"""
        self.detection_evasion = enabled
        self.log(f"🔒 Detection evasion: {'ENABLED' if enabled else 'DISABLED'}")

    def get_click_stats(self):
        """Zwraca szczegółowe statystyki kliknięć"""
        if len(self.click_patterns) < 2:
            return {}

        # Analiza timing patterns
        intervals = []
        successful_clicks = 0

        for i in range(1, len(self.click_patterns)):
            interval = self.click_patterns[i]['time'] - self.click_patterns[i-1]['time']
            intervals.append(interval)
            if self.click_patterns[i]['success']:
                successful_clicks += 1

        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        success_rate = (successful_clicks / len(self.click_patterns)) * 100 if self.click_patterns else 0

        return {
            'total_clicks': len(self.click_patterns),
            'successful_clicks': successful_clicks,
            'success_rate': success_rate,
            'avg_interval': avg_interval,
            'last_click_ago': time.time() - self.click_patterns[-1]['time'] if self.click_patterns else 0,
            'last_successful_method': self.last_successful_method,
            'method_stats': self.stats['method_stats'].copy()
        }

    def get_stats(self):
        """Zwraca statystyki dla main_window (kompatybilność)"""
        current_enemy_pos = None
        target_distance = 0

        if self.last_enemy_position:
            current_enemy_pos = self.last_enemy_position
            # Oblicz dystans do centrum ekranu
            dx = self.last_enemy_position[0] - self.screen_center_x
            dy = self.last_enemy_position[1] - self.screen_center_y
            target_distance = math.sqrt(dx*dx + dy*dy)

        # Legacy movement state mapping
        movement_state_legacy = "idle"
        if self.mode == "combat":
            movement_state_legacy = "combat"
        elif self.mode == "exploration":
            movement_state_legacy = "exploration"
        elif self.mode == "grace_period":
            movement_state_legacy = "looting"

        # Pobierz click stats
        click_stats = self.get_click_stats()

        # Pobierz I button stats
        i_button_stats = self.get_i_button_stats()

        return {
            # Legacy compatibility fields (używane przez main_window)
            'movement_state': movement_state_legacy,
            'waiting_for_mob_approach': False,  # Nie używamy tego w nowym systemie
            'target_distance': target_distance,
            'current_enemy_position': current_enemy_pos,
            'last_action_time': time.time(),

            # Nowe pola systemowe
            'mode': self.mode,
            'grace_period_active': self.mode == "grace_period",
            'grace_period_remaining': max(0, self.grace_period_duration - (time.time() - self.grace_period_start_time)) if self.mode == "grace_period" else 0,
            'emergency_backstep_active': self.emergency_backstep_active,
            'emergency_backstep_cooldown_remaining': max(0, self.emergency_backstep_cooldown - (time.time() - self.last_emergency_backstep)),
            'last_enemy_seen': time.time() - self.last_enemy_seen_time if self.last_enemy_seen_time > 0 else 0,

            # Statystyki kliknięć - rozszerzone
            'combat_clicks_performed': self.stats['position_clicks'],
            'successful_clicks': self.stats['successful_clicks'],
            'failed_clicks': self.stats['failed_clicks'],
            'click_success_rate': (self.stats['successful_clicks'] / max(1, self.stats['position_clicks'])) * 100,
            'last_combat_click_ago': time.time() - self.last_combat_click,
            'last_loot_click_ago': time.time() - self.last_loot_click,
            'last_successful_method': self.last_successful_method,

            # Statystyki metod klikania
            'method_stats': self.stats['method_stats'].copy(),
            'click_patterns_tracked': len(self.click_patterns),

            # Statystyki przycisku I - NOWE
            'i_button_enabled': i_button_stats['enabled'],
            'i_button_total_presses': i_button_stats['total_presses'],
            'i_button_successful_presses': i_button_stats['successful_presses'],
            'i_button_success_rate': i_button_stats['success_rate'],
            'i_button_time_until_next': i_button_stats['time_until_next_press'],
            'i_button_time_since_last': i_button_stats['time_since_last_press'],
            'i_button_next_press_formatted': i_button_stats['next_press_formatted'],

            # Statystyki ogólne
            'stats': self.stats.copy(),
            'detection_evasion_enabled': self.detection_evasion
        }

    # ========================================
    # DEBUG I DIAGNOSTYKA
    # ========================================

    def print_diagnostics(self):
        """Wydrukuje diagnostykę systemu klikania"""
        self.log("=" * 50)
        self.log("🔍 DIAGNOSTYKA SYSTEMU KLIKANIA")
        self.log("=" * 50)

        click_stats = self.get_click_stats()

        if click_stats:
            self.log(f"📊 Statystyki kliknięć:")
            self.log(f"  ✅ Udane: {click_stats['successful_clicks']}")
            self.log(f"  ❌ Nieudane: {len(self.click_patterns) - click_stats['successful_clicks']}")
            self.log(f"  📈 Skuteczność: {click_stats['success_rate']:.1f}%")
            self.log(f"  ⏱️ Średni odstęp: {click_stats['avg_interval']:.3f}s")

            self.log(f"📋 Statystyki metod:")
            for method, count in self.stats['method_stats'].items():
                if count > 0:
                    self.log(f"  {method}: {count} użyć")

            if self.last_successful_method:
                self.log(f"🎯 Ostatnia udana metoda: {self.last_successful_method}")
        else:
            self.log("📭 Brak danych o kliknięciach")

        # Diagnostyka przycisku I
        i_stats = self.get_i_button_stats()
        self.log(f"📋 Statystyki przycisku I:")
        self.log(f"  🔘 Status: {'WŁĄCZONY' if i_stats['enabled'] else 'WYŁĄCZONY'}")
        self.log(f"  📊 Naciśnięcia: {i_stats['successful_presses']}/{i_stats['total_presses']}")
        self.log(f"  📈 Skuteczność: {i_stats['success_rate']:.1f}%")
        self.log(f"  ⏱️ Następne za: {i_stats['next_press_formatted']}")

        self.log(f"🔒 Detection evasion: {'ENABLED' if self.detection_evasion else 'DISABLED'}")
        self.log(f"👑 Admin rights: {'YES' if ctypes.windll.shell32.IsUserAnAdmin() else 'NO'}")
        self.log("=" * 50)

    def reset_click_stats(self):
        """Resetuje statystyki kliknięć"""
        self.click_patterns = []
        self.last_successful_method = None
        self.stats['successful_clicks'] = 0
        self.stats['failed_clicks'] = 0
        self.stats['position_clicks'] = 0
        # Tylko 2 metody
        self.stats['method_stats'] = {
            'wow_proven': 0,
            'warcraft_style': 0
        }
        self.log("🔄 Statystyki kliknięć zresetowane")

    def reset_i_button_stats(self):
        """Resetuje statystyki przycisku I"""
        self.i_button_stats = {
            'total_presses': 0,
            'successful_presses': 0,
            'failed_presses': 0,
            'last_press_time': 0,
            'next_press_in': 0
        }
        self.i_button_last_press = 0
        self._schedule_next_i_press()
        self.log("🔄 Statystyki przycisku I zresetowane")

    def force_i_button_press(self, hwnd):
        """Wymusza natychmiastowe naciśnięcie przycisku I (do testów)"""
        self.log("🔧 Wymuszam naciśnięcie przycisku I...")
        success = self._press_i_button(hwnd)
        if success:
            self.log("✅ Przymusowe naciśnięcie I zakończone powodzeniem")
        else:
            self.log("❌ Przymusowe naciśnięcie I nie powiodło się")