"""
Color Trigger System - Moduł do reagowania na konkretne kolory w określonych pozycjach
Integruje się z ReactiveCombatController i używa konfiguracji z Color Picker Tool
"""
import cv2
import numpy as np
import time
import win32api
import win32con
from typing import List, Dict, Any, Optional

# ===== KONFIGURACJA - WKLEJ TU KOD Z COLOR PICKER TOOL =====
TRIGGER_POINTS = [

    {

        "x": 1052,

        "y": 848,

        "color": (np.int64(124), np.int64(125), np.int64(160)),

        "key": 0x39,  # Klawisz '9' - zmień jeśli potrzebujesz

        "tolerance": 30,

        "name": "trigger_1",

        "enabled": True

    },

]

# Ustawienia systemu
REGION_SIZE = 5  # Rozmiar regionu do sprawdzania (5x5 pikseli)
DEFAULT_TOLERANCE = 30  # Domyślna tolerancja kolorów
TRIGGER_COOLDOWN = 1.0  # Cooldown między triggerami tego samego typu (sekundy)


# ==============================================================


class ColorTriggerSystem:
    """
    System triggerowania akcji na podstawie wykrycia kolorów w określonych pozycjach
    """

    def __init__(self, combat_controller=None, logger=None):
        self.combat_controller = combat_controller
        self.logger = logger

        # Konfiguracja
        self.triggers = []
        self.enabled = True
        self.region_size = REGION_SIZE
        self.default_tolerance = DEFAULT_TOLERANCE

        # Stan systemu
        self.last_trigger_times = {}  # Cooldown tracking
        self.trigger_stats = {}

        # Statystyki
        self.stats = {
            'total_checks': 0,
            'successful_triggers': 0,
            'failed_triggers': 0,
            'total_trigger_count': 0,
            'uptime_start': time.time()
        }

        # Załaduj domyślną konfigurację
        self.load_config(TRIGGER_POINTS)

        self.log("🎯 ColorTriggerSystem initialized")

    def log(self, message: str, level: str = "info"):
        """Helper do logowania"""
        if self.logger:
            if level == "debug":
                self.logger.debug(message)
            elif level == "warning":
                self.logger.warning(message)
            elif level == "error":
                self.logger.error(message)
            else:
                self.logger.info(message)
        else:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] COLOR_TRIGGER: {message}")

    def load_config(self, trigger_points: List[Dict[str, Any]]):
        """Ładuje konfigurację trigger pointów"""
        self.triggers.clear()
        self.last_trigger_times.clear()
        self.trigger_stats.clear()

        for point_config in trigger_points:
            trigger = self._create_trigger_from_config(point_config)
            if trigger:
                self.triggers.append(trigger)
                trigger_id = trigger['id']
                self.last_trigger_times[trigger_id] = 0
                self.trigger_stats[trigger_id] = {
                    'checks': 0,
                    'matches': 0,
                    'triggers': 0,
                    'last_match_time': 0,
                    'last_trigger_time': 0
                }

        enabled_count = len([t for t in self.triggers if t['enabled']])
        self.log(f"🎯 Loaded {len(self.triggers)} triggers ({enabled_count} enabled)")

        # Debug info
        for trigger in self.triggers:
            if trigger['enabled']:
                pos = f"({trigger['x']}, {trigger['y']})"
                color = trigger['color']
                key_name = self._vk_to_key_name(trigger['key'])
                self.log(f"  • {trigger['name']}: {pos} → {color} → {key_name}")

    def _create_trigger_from_config(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Tworzy trigger z konfiguracji"""
        try:
            # Walidacja wymaganych pól
            required_fields = ['x', 'y', 'color', 'key']
            for field in required_fields:
                if field not in config:
                    self.log(f"❌ Missing required field '{field}' in trigger config", "error")
                    return None

            trigger = {
                'id': f"{config['x']}_{config['y']}_{hash(str(config['color']))}",
                'x': int(config['x']),
                'y': int(config['y']),
                'color': tuple(config['color']),  # RGB tuple
                'key': int(config['key']),
                'tolerance': config.get('tolerance', self.default_tolerance),
                'name': config.get('name', f"trigger_{config['x']}_{config['y']}"),
                'enabled': config.get('enabled', True),
                'cooldown': config.get('cooldown', TRIGGER_COOLDOWN),
                'region_size': config.get('region_size', self.region_size)
            }

            # Konwertuj RGB na HSV dla lepszej tolerancji
            rgb_array = np.array([[trigger['color']]], dtype=np.uint8)
            hsv_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2HSV)
            trigger['hsv_color'] = tuple(hsv_array[0, 0])

            return trigger

        except Exception as e:
            self.log(f"❌ Error creating trigger from config: {str(e)}", "error")
            return None

    def enable_system(self, enabled: bool = True):
        """Włącza/wyłącza cały system"""
        self.enabled = enabled
        status = "ENABLED" if enabled else "DISABLED"
        self.log(f"🎯 ColorTriggerSystem: {status}")

    def enable_trigger(self, trigger_name: str, enabled: bool = True):
        """Włącza/wyłącza konkretny trigger"""
        for trigger in self.triggers:
            if trigger['name'] == trigger_name:
                trigger['enabled'] = enabled
                status = "ENABLED" if enabled else "DISABLED"
                self.log(f"🎯 Trigger '{trigger_name}': {status}")
                return True

        self.log(f"❌ Trigger '{trigger_name}' not found", "warning")
        return False

    def check_triggers(self, image: np.ndarray, hwnd: int) -> Dict[str, Any]:
        """
        Główna funkcja sprawdzająca wszystkie trigger points
        Wywołuj ją z combat_controller.update()
        """
        if not self.enabled or not self.triggers:
            return {'checked': 0, 'triggered': 0}

        if image is None or image.size == 0:
            return {'checked': 0, 'triggered': 0}

        current_time = time.time()
        self.stats['total_checks'] += 1

        checked_count = 0
        triggered_count = 0

        for trigger in self.triggers:
            if not trigger['enabled']:
                continue

            checked_count += 1
            trigger_id = trigger['id']

            # Aktualizuj statystyki trigger
            self.trigger_stats[trigger_id]['checks'] += 1

            # Sprawdź cooldown
            if current_time - self.last_trigger_times[trigger_id] < trigger['cooldown']:
                continue

            # Sprawdź kolor w pozycji
            if self._check_color_at_position(image, trigger):
                self.trigger_stats[trigger_id]['matches'] += 1
                self.trigger_stats[trigger_id]['last_match_time'] = current_time

                # Wykonaj trigger
                if self._execute_trigger(hwnd, trigger):
                    triggered_count += 1
                    self.last_trigger_times[trigger_id] = current_time
                    self.trigger_stats[trigger_id]['triggers'] += 1
                    self.trigger_stats[trigger_id]['last_trigger_time'] = current_time
                    self.stats['successful_triggers'] += 1
                    self.stats['total_trigger_count'] += 1

                    self.log(f"🎯 TRIGGERED: {trigger['name']} at ({trigger['x']}, {trigger['y']})")
                else:
                    self.stats['failed_triggers'] += 1

        return {
            'checked': checked_count,
            'triggered': triggered_count,
            'total_triggers': len([t for t in self.triggers if t['enabled']])
        }

    def _check_color_at_position(self, image: np.ndarray, trigger: Dict[str, Any]) -> bool:
        """Sprawdza czy kolor w pozycji zgadza się z targetem"""
        try:
            img_height, img_width = image.shape[:2]
            x, y = trigger['x'], trigger['y']
            region_size = trigger['region_size']
            half_size = region_size // 2

            # Sprawdź czy pozycja jest w granicach obrazu
            if x < 0 or y < 0 or x >= img_width or y >= img_height:
                return False

            # Oblicz granice regionu
            x1 = max(0, x - half_size)
            y1 = max(0, y - half_size)
            x2 = min(img_width, x + half_size + 1)
            y2 = min(img_height, y + half_size + 1)

            # Wytnij region
            region = image[y1:y2, x1:x2]

            if region.size == 0:
                return False

            # Oblicz średni kolor regionu
            avg_color_rgb = np.mean(region, axis=(0, 1)).astype(int)

            # Sprawdź różnicę kolorów
            target_rgb = np.array(trigger['color'])
            color_diff = np.abs(avg_color_rgb - target_rgb)

            # Sprawdź czy mieści się w tolerancji (można użyć RGB lub HSV)
            if self._is_color_match_rgb(avg_color_rgb, target_rgb, trigger['tolerance']):
                return True

            # Alternatywnie sprawdź w HSV (lepsze dla niektórych kolorów)
            return self._is_color_match_hsv(region, trigger)

        except Exception as e:
            self.log(f"❌ Error checking color at position: {str(e)}", "error")
            return False

    def _is_color_match_rgb(self, actual_rgb: np.ndarray, target_rgb: np.ndarray, tolerance: int) -> bool:
        """Sprawdza dopasowanie koloru w przestrzeni RGB"""
        # Euclidean distance w RGB
        distance = np.sqrt(np.sum((actual_rgb - target_rgb) ** 2))
        max_distance = tolerance * 1.73  # sqrt(3) dla 3D space

        return distance <= max_distance

    def _is_color_match_hsv(self, region: np.ndarray, trigger: Dict[str, Any]) -> bool:
        """Sprawdza dopasowanie koloru w przestrzeni HSV (lepsze dla tolerancji)"""
        try:
            # Konwertuj region do HSV
            hsv_region = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
            avg_hsv = np.mean(hsv_region, axis=(0, 1)).astype(int)

            target_hsv = np.array(trigger['hsv_color'])
            tolerance = trigger['tolerance']

            # HSV tolerance (Hue wraparound, Saturation, Value)
            h_diff = min(abs(avg_hsv[0] - target_hsv[0]),
                         180 - abs(avg_hsv[0] - target_hsv[0]))  # Hue wraparound
            s_diff = abs(avg_hsv[1] - target_hsv[1])
            v_diff = abs(avg_hsv[2] - target_hsv[2])

            # Sprawdź czy wszystkie komponenty mieszczą się w tolerancji
            h_tolerance = tolerance * 180 / 255  # Scale tolerance for hue
            sv_tolerance = tolerance

            return (h_diff <= h_tolerance and
                    s_diff <= sv_tolerance and
                    v_diff <= sv_tolerance)

        except Exception as e:
            self.log(f"❌ HSV color matching error: {str(e)}", "error")
            return False

    def _execute_trigger(self, hwnd: int, trigger: Dict[str, Any]) -> bool:
        """Wykonuje akcję triggera (naciśnięcie klawisza)"""
        try:
            key_code = trigger['key']

            # Naciśnij klawisz (down + up)
            if not self._send_key_press(hwnd, key_code):
                return False

            key_name = self._vk_to_key_name(key_code)
            self.log(f"⌨️ Key pressed: {key_name} (trigger: {trigger['name']})")

            return True

        except Exception as e:
            self.log(f"❌ Error executing trigger: {str(e)}", "error")
            return False

    def _send_key_press(self, hwnd: int, vk_code: int) -> bool:
        """Wysyła naciśnięcie klawisza (podobnie jak w CombatController)"""
        try:
            # Key down
            success1 = win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            if not success1:
                return False

            # Krótka pauza
            time.sleep(0.05)

            # Key up
            success2 = win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)

            return bool(success1 and success2)

        except Exception as e:
            self.log(f"❌ Key press error: {str(e)}", "error")
            return False

    def _vk_to_key_name(self, vk_code: int) -> str:
        """Konwertuje VK code na nazwę klawisza"""
        key_names = {
            0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4', 0x35: '5',
            0x36: '6', 0x37: '7', 0x38: '8', 0x39: '9', 0x30: '0',
            0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
            0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
            0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O',
            0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
            0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
            0x5A: 'Z', 0x20: 'SPACE', 0x0D: 'ENTER', 0x1B: 'ESC',
            0x70: 'F1', 0x71: 'F2', 0x72: 'F3', 0x73: 'F4'
        }
        return key_names.get(vk_code, f'VK_{vk_code:02X}')

    # === DIAGNOSTYKA I STATYSTYKI ===

    def get_status(self) -> str:
        """Zwraca krótkий status systemu"""
        if not self.enabled:
            return "🎯 COLOR TRIGGERS: DISABLED"

        enabled_triggers = len([t for t in self.triggers if t['enabled']])
        if enabled_triggers == 0:
            return "🎯 COLOR TRIGGERS: NO ACTIVE TRIGGERS"

        recent_triggers = 0
        current_time = time.time()

        for trigger_id, stats in self.trigger_stats.items():
            if current_time - stats['last_trigger_time'] < 10:  # Ostatnie 10 sekund
                recent_triggers += 1

        if recent_triggers > 0:
            return f"🎯 COLOR TRIGGERS: {recent_triggers} RECENT ({enabled_triggers} active)"
        else:
            return f"🎯 COLOR TRIGGERS: MONITORING ({enabled_triggers} active)"

    def get_stats(self) -> Dict[str, Any]:
        """Zwraca szczegółowe statystyki"""
        uptime = time.time() - self.stats['uptime_start']

        return {
            'enabled': self.enabled,
            'total_triggers': len(self.triggers),
            'enabled_triggers': len([t for t in self.triggers if t['enabled']]),
            'total_checks': self.stats['total_checks'],
            'successful_triggers': self.stats['successful_triggers'],
            'failed_triggers': self.stats['failed_triggers'],
            'total_trigger_count': self.stats['total_trigger_count'],
            'uptime_seconds': uptime,
            'checks_per_second': self.stats['total_checks'] / max(1, uptime),
            'triggers_per_minute': (self.stats['total_trigger_count'] * 60) / max(1, uptime),
            'trigger_details': self.trigger_stats.copy()
        }

    def get_detailed_status(self) -> Dict[str, Any]:
        """Zwraca szczegółowy status dla GUI/diagnostyki"""
        current_time = time.time()
        trigger_statuses = []

        for trigger in self.triggers:
            trigger_id = trigger['id']
            stats = self.trigger_stats.get(trigger_id, {})

            last_trigger = stats.get('last_trigger_time', 0)
            last_match = stats.get('last_match_time', 0)

            status = {
                'name': trigger['name'],
                'position': f"({trigger['x']}, {trigger['y']})",
                'color': trigger['color'],
                'enabled': trigger['enabled'],
                'checks': stats.get('checks', 0),
                'matches': stats.get('matches', 0),
                'triggers': stats.get('triggers', 0),
                'last_trigger_ago': current_time - last_trigger if last_trigger > 0 else -1,
                'last_match_ago': current_time - last_match if last_match > 0 else -1,
                'cooldown_remaining': max(0, trigger['cooldown'] - (
                            current_time - last_trigger)) if last_trigger > 0 else 0
            }

            trigger_statuses.append(status)

        return {
            'system_enabled': self.enabled,
            'triggers': trigger_statuses,
            'global_stats': self.get_stats()
        }

    def test_trigger_at_position(self, image: np.ndarray, x: int, y: int, target_color: tuple, tolerance: int = 30) -> \
    Dict[str, Any]:
        """Test function dla debugowania - sprawdza kolor w konkretnej pozycji"""
        try:
            if image is None or image.size == 0:
                return {'success': False, 'reason': 'Invalid image'}

            img_height, img_width = image.shape[:2]

            if x < 0 or y < 0 or x >= img_width or y >= img_height:
                return {'success': False, 'reason': 'Position out of bounds'}

            # Utwórz tymczasowy trigger do testowania
            test_trigger = {
                'x': x, 'y': y,
                'color': target_color,
                'tolerance': tolerance,
                'region_size': self.region_size
            }

            # Dodaj HSV
            rgb_array = np.array([[target_color]], dtype=np.uint8)
            hsv_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2HSV)
            test_trigger['hsv_color'] = tuple(hsv_array[0, 0])

            # Sprawdź kolor
            match = self._check_color_at_position(image, test_trigger)

            # Pobierz aktualny kolor w pozycji dla porównania
            half_size = self.region_size // 2
            x1, y1 = max(0, x - half_size), max(0, y - half_size)
            x2, y2 = min(img_width, x + half_size + 1), min(img_height, y + half_size + 1)

            region = image[y1:y2, x1:x2]
            actual_color = tuple(np.mean(region, axis=(0, 1)).astype(int))

            return {
                'success': True,
                'match': match,
                'actual_color': actual_color,
                'target_color': target_color,
                'tolerance': tolerance,
                'position': (x, y),
                'region_bounds': (x1, y1, x2, y2)
            }

        except Exception as e:
            return {'success': False, 'reason': f'Exception: {str(e)}'}


# === INTEGRACJA Z COMBAT CONTROLLER ===

def integrate_color_triggers_with_combat_controller(combat_controller, logger=None):
    """
    Funkcja do łatwej integracji ColorTriggerSystem z istniejącym CombatController
    Wywołaj ją w main_window.py po inicjalizacji combat_controller
    """

    # Stwórz system triggerów
    color_trigger_system = ColorTriggerSystem(combat_controller, logger)

    # Dodaj do combat controller
    combat_controller.color_trigger_system = color_trigger_system

    # Dodaj metodę pomocniczą do combat controller
    def update_color_triggers(self, image, hwnd):
        """Sprawdza color triggers - dodaj wywołanie w combat_controller.update()"""
        if hasattr(self, 'color_trigger_system') and self.color_trigger_system.enabled:
            return self.color_trigger_system.check_triggers(image, hwnd)
        return {'checked': 0, 'triggered': 0}

    # Monkey patch metody
    combat_controller.update_color_triggers = update_color_triggers.__get__(combat_controller)

    # Dodaj status do get_status()
    original_get_status = combat_controller.get_status

    def enhanced_get_status(self):
        status = original_get_status()
        if hasattr(self, 'color_trigger_system'):
            trigger_status = self.color_trigger_system.get_status()
            status += f" | {trigger_status}"
        return status

    combat_controller.get_status = enhanced_get_status.__get__(combat_controller)

    logger.info("🎯 ColorTriggerSystem integrated with CombatController") if logger else print(
        "🎯 ColorTriggerSystem integrated")

    return color_trigger_system


# === PRZYKŁAD UŻYCIA ===

if __name__ == "__main__":
    # Test bez combat controller
    trigger_system = ColorTriggerSystem()

    print("🎯 ColorTriggerSystem Test")
    print(f"Loaded triggers: {len(trigger_system.triggers)}")

    # Test z przykładowym obrazem
    test_image = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)

    # Dodaj testowy czerwony obszar
    test_image[195:205, 145:155] = [255, 0, 0]  # Czerwony prostokąt w okolicy (150, 200)

    # Test sprawdzania
    result = trigger_system.check_triggers(test_image, 0)  # hwnd=0 dla testu
    print(f"Check result: {result}")

    # Pokaż statystyki
    stats = trigger_system.get_stats()
    print(f"Stats: {stats}")

    # Test konkretnej pozycji
    test_result = trigger_system.test_trigger_at_position(test_image, 150, 200, (255, 0, 0), 30)
    print(f"Position test: {test_result}")