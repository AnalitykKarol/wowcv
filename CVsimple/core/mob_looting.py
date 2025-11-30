"""
mob_looting.py - Moduł do natychmiastowego lootowania znikających mobów
Można zaimportować i użyć w dowolnym combat controllerze
"""
import time
import random
from typing import Dict, List, Tuple, Any, Optional


class ImmediateMobLooter:
    """System natychmiastowego lootowania znikających mobów"""

    def __init__(self, logger=None):
        self.logger = logger

        # Tracking mobów
        self.recent_mob_positions: Dict[str, Tuple[float, float, float]] = {}  # {mob_hash: (x, y, last_seen_time)}
        self.mob_loot_timeout = 3.0  # Jak długo pamiętać pozycję moba
        self.immediate_loot_enabled = True

        # Konfiguracja lootowania
        self.loot_offset_x_range = (-20, 20)  # Randomizacja X
        self.loot_offset_y_range = (15, 40)  # Offset Y (poniżej moba)
        self.max_loots_per_frame = 1  # Ile mobów lootować na klatkę
        self.detection_sensitivity = 30  # Rozmiar siatki do grupowania pozycji

        # Statystyki
        self.stats = {
            'total_mobs_tracked': 0,
            'mobs_disappeared': 0,
            'loot_attempts': 0,
            'successful_loots': 0,
            'current_tracked_count': 0
        }

    def log(self, message: str):
        """Log wiadomości jeśli logger dostępny"""
        if self.logger:
            self.logger.info(f"[MobLooter] {message}")

    def simple_mob_hash(self, center_x: float, center_y: float) -> str:
        """Stwórz prosty hash dla moba na podstawie pozycji"""
        # Zaokrąglij pozycję do siatki żeby uwzględnić małe ruchy
        grid_x = int(center_x // self.detection_sensitivity) * self.detection_sensitivity
        grid_y = int(center_y // self.detection_sensitivity) * self.detection_sensitivity
        return f"{grid_x}_{grid_y}"

    def update_and_get_disappeared(self, current_enemies: List[Dict]) -> List[Tuple[float, float]]:
        """
        Aktualizuj pozycje mobów i zwróć listę pozycji znikłych mobów

        Args:
            current_enemies: Lista obecnych mobów z detections

        Returns:
            Lista tupli (x, y) pozycji mobów które właśnie zniknęły
        """
        if not self.immediate_loot_enabled:
            return []

        current_time = time.time()
        current_mob_hashes = set()

        # Aktualizuj pozycje obecnych mobów
        for enemy in current_enemies:
            center_x = enemy.get('center_x', 0)
            center_y = enemy.get('center_y', 0)

            # Pomiń jeśli brak współrzędnych
            if center_x == 0 and center_y == 0:
                continue

            mob_hash = self.simple_mob_hash(center_x, center_y)

            # Jeśli to nowy mob
            if mob_hash not in self.recent_mob_positions:
                self.stats['total_mobs_tracked'] += 1
                self.log(f"🎯 New mob tracked at ({center_x:.0f}, {center_y:.0f})")

            self.recent_mob_positions[mob_hash] = (center_x, center_y, current_time)
            current_mob_hashes.add(mob_hash)

        # Znajdź zniknięte mowy (ostatnio widziane ale nie w obecnej klatce)
        disappeared_mobs = []
        for mob_hash, (x, y, last_seen) in list(self.recent_mob_positions.items()):
            time_since_seen = current_time - last_seen

            # Mob zniknął niedawno
            if mob_hash not in current_mob_hashes and time_since_seen < 0.5:
                disappeared_mobs.append((x, y))
                self.stats['mobs_disappeared'] += 1
                self.log(f"💀 Mob disappeared at ({x:.0f}, {y:.0f}) - ready for loot")

        # Wyczyść stare pozycje
        expired_hashes = []
        for mob_hash, (_, _, last_seen) in self.recent_mob_positions.items():
            if current_time - last_seen > self.mob_loot_timeout:
                expired_hashes.append(mob_hash)

        for mob_hash in expired_hashes:
            del self.recent_mob_positions[mob_hash]

        # Aktualizuj statystyki
        self.stats['current_tracked_count'] = len(self.recent_mob_positions)

        return disappeared_mobs

    def calculate_loot_position(self, mob_x: float, mob_y: float,
                                screen_width: int = 1920, screen_height: int = 1080) -> Tuple[float, float]:
        """
        Oblicz pozycję do lootowania na podstawie pozycji moba

        Args:
            mob_x, mob_y: Ostatnia pozycja moba
            screen_width, screen_height: Rozmiary ekranu dla granic

        Returns:
            Tupla (loot_x, loot_y) - pozycja do kliknięcia
        """
        # Dodaj randomizację i przesuń nieco poniżej moba
        loot_x = mob_x + random.uniform(*self.loot_offset_x_range)
        loot_y = mob_y + random.uniform(*self.loot_offset_y_range)

        # Upewnij się że pozycja jest w granicach ekranu
        margin = 50
        loot_x = max(margin, min(screen_width - margin, loot_x))
        loot_y = max(margin, min(screen_height - margin, loot_y))

        return loot_x, loot_y

    def attempt_loot_at_positions(self, combat_controller, hwnd: int,
                                  disappeared_positions: List[Tuple[float, float]]) -> int:
        """
        Spróbuj zlootować mowy na podanych pozycjach

        Args:
            combat_controller: Instancja CombatController z metodą perform_right_click
            hwnd: Handle okna gry
            disappeared_positions: Lista pozycji do zlootowania

        Returns:
            Liczba udanych prób lootowania
        """
        if not disappeared_positions or not self.immediate_loot_enabled:
            return 0

        # Sprawdź czy możemy lootować (cooldown)
        if not hasattr(combat_controller, 'can_loot_click') or not combat_controller.can_loot_click():
            return 0

        successful_loots = 0

        # Lootuj maksymalnie określoną liczbę mobów na klatkę
        for i, (mob_x, mob_y) in enumerate(disappeared_positions[:self.max_loots_per_frame]):

            # Oblicz pozycję lootowania
            loot_x, loot_y = self.calculate_loot_position(
                mob_x, mob_y,
                getattr(combat_controller, 'screen_width', 1920),
                getattr(combat_controller, 'screen_height', 1080)
            )

            # Spróbuj zlootować
            self.stats['loot_attempts'] += 1

            if hasattr(combat_controller, 'perform_right_click'):
                try:
                    if combat_controller.perform_right_click(hwnd, loot_x, loot_y, is_loot=True):
                        successful_loots += 1
                        self.stats['successful_loots'] += 1
                        self.log(f"💰 IMMEDIATE LOOT #{i + 1}: ({loot_x:.0f}, {loot_y:.0f}) ✅")
                    else:
                        self.log(f"💰 IMMEDIATE LOOT #{i + 1}: ({loot_x:.0f}, {loot_y:.0f}) ❌")
                except Exception as e:
                    self.log(f"❌ Loot error at ({loot_x:.0f}, {loot_y:.0f}): {e}")
            else:
                self.log("❌ CombatController doesn't have perform_right_click method")
                break

        return successful_loots

    def process_frame(self, combat_controller, hwnd: int, current_enemies: List[Dict]) -> int:
        """
        Główna metoda - przetwórz klatkę i spróbuj zlootować zniknięte mowy

        Args:
            combat_controller: Instancja CombatController
            hwnd: Handle okna gry
            current_enemies: Lista obecnych mobów

        Returns:
            Liczba udanych lootów w tej klatce
        """
        # Znajdź zniknięte mowy
        disappeared_positions = self.update_and_get_disappeared(current_enemies)

        if not disappeared_positions:
            return 0

        # Spróbuj je zlootować
        return self.attempt_loot_at_positions(combat_controller, hwnd, disappeared_positions)

    def configure(self, enabled: bool = True, timeout: float = 3.0,
                  max_loots_per_frame: int = 1, detection_sensitivity: int = 30):
        """
        Konfiguruj system lootowania

        Args:
            enabled: Czy system ma być włączony
            timeout: Jak długo pamiętać pozycje mobów (sekundy)
            max_loots_per_frame: Maksymalna liczba lootów na klatkę
            detection_sensitivity: Rozmiar siatki do grupowania pozycji mobów
        """
        self.immediate_loot_enabled = enabled
        self.mob_loot_timeout = timeout
        self.max_loots_per_frame = max_loots_per_frame
        self.detection_sensitivity = detection_sensitivity

        if enabled:
            self.log(f"💰 Immediate looting: ENABLED")
            self.log(f"   Timeout: {timeout}s")
            self.log(f"   Max loots/frame: {max_loots_per_frame}")
            self.log(f"   Detection sensitivity: {detection_sensitivity}px")
        else:
            self.log("💰 Immediate looting: DISABLED")
            self.recent_mob_positions.clear()

    def get_status(self) -> str:
        """Zwróć status systemu jako string"""
        if not self.immediate_loot_enabled:
            return "🔴 DISABLED"

        tracked = self.stats['current_tracked_count']
        if tracked == 0:
            return "👻 NO MOBS"

        return f"🎯 {tracked} tracked"

    def get_stats(self) -> Dict[str, Any]:
        """Zwróć szczegółowe statystyki"""
        stats = self.stats.copy()

        # Oblicz wskaźniki sukcesu
        if stats['loot_attempts'] > 0:
            stats['loot_success_rate'] = (stats['successful_loots'] / stats['loot_attempts']) * 100
        else:
            stats['loot_success_rate'] = 0.0

        # Dodaj informacje o konfiguracji
        stats['config'] = {
            'enabled': self.immediate_loot_enabled,
            'timeout': self.mob_loot_timeout,
            'max_loots_per_frame': self.max_loots_per_frame,
            'detection_sensitivity': self.detection_sensitivity,
            'loot_offset_x_range': self.loot_offset_x_range,
            'loot_offset_y_range': self.loot_offset_y_range
        }

        return stats

    def reset_stats(self):
        """Zresetuj statystyki"""
        self.stats = {
            'total_mobs_tracked': 0,
            'mobs_disappeared': 0,
            'loot_attempts': 0,
            'successful_loots': 0,
            'current_tracked_count': len(self.recent_mob_positions)
        }
        self.log("📊 Statistics reset")


# === FUNKCJA POMOCNICZA DO ŁATWEGO IMPORTU ===
def create_mob_looter(logger=None, **config_kwargs):
    """
    Funkcja pomocnicza do stworzenia i skonfigurowania MobLootera

    Args:
        logger: Logger do logowania
        **config_kwargs: Argumenty dla metody configure()

    Returns:
        Skonfigurowana instancja ImmediateMobLooter
    """
    looter = ImmediateMobLooter(logger)

    if config_kwargs:
        looter.configure(**config_kwargs)

    return looter