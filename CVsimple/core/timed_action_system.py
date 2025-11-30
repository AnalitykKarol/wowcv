# core/timed_action_system.py
"""
System do wykonywania cyklicznych akcji w określonych odstępach czasu.
Idealny do używania buffów, jedzenia lub innych przedmiotów co kilka minut.
"""

import time
import random
import win32api
import win32con


class TimedActionSystem:
    def __init__(self, combat_controller):
        """
        Inicjalizuje system.
        :param combat_controller: Referencja do głównego kontrolera walki.
        """
        self.controller = combat_controller
        self.logger = combat_controller.logger

        # Konfiguracja akcji
        self.actions = []  # Lista akcji do wykonania
        self.enabled = True

        # Statystyki
        self.stats = {
            'actions_triggered': 0,
            'last_action_time': 0
        }

    def add_action(self, name, key_code, interval_min_sec, interval_max_sec):
        """
        Dodaje nową cykliczną akcję.
        :param name: Nazwa akcji (dla logowania).
        :param key_code: Kod wirtualnego klawisza do naciśnięcia.
        :param interval_min_sec: Minimalny czas oczekiwania w sekundach.
        :param interval_max_sec: Maksymalny czas oczekiwania w sekundach.
        """
        action = {
            'name': name,
            'key_code': key_code,
            'interval_min': interval_min_sec,
            'interval_max': interval_max_sec,
            'next_execution_time': time.time() + random.uniform(interval_min_sec, interval_max_sec)
        }
        self.actions.append(action)
        self.log(
            f"✅ Dodano cykliczną akcję '{name}' z klawiszem {hex(key_code)} co {interval_min_sec}-{interval_max_sec}s")

    def update(self, hwnd: int): # Add hwnd parameter
        """Główna metoda aktualizacji, wywoływana w każdej pętli kontrolera."""
        if not self.enabled:
            return

        current_time = time.time()
        for action in self.actions:
            if current_time >= action['next_execution_time']:
                self.log(f"⏰ Wykonywanie cyklicznej akcji: '{action['name']}'")

                # Determine if we are in combat mode
                in_combat_mode = (self.controller.mode == "combat")

                # Press the key using the controller's send_key_press method
                # This ensures consistent key press behavior with the rest of the controller
                if self.controller.send_key_press(hwnd, action['key_code']):
                    self.log(f"   Key {hex(action['key_code'])} for '{action['name']}' pressed.")
                    self.stats['actions_triggered'] += 1
                    self.stats['last_action_time'] = current_time

                    # Schedule next execution
                    next_interval = random.uniform(action['interval_min'], action['interval_max'])

                    # If not in combat, use it immediately and reset for a full interval
                    # If in combat, schedule for a random time within the interval
                    if not in_combat_mode:
                        # Use it now, schedule next for full interval from now
                        action['next_execution_time'] = current_time + next_interval
                        self.log(f"   Not in combat. Next execution for '{action['name']}' scheduled for {next_interval:.1f}s from now.")
                    else:
                        # In combat. Schedule next for random time within interval.
                        # This implies it might be used sooner than a full interval if combat is prolonged
                        action['next_execution_time'] = current_time + next_interval
                        self.log(f"   In combat. Next execution for '{action['name']}' scheduled for {next_interval:.1f}s from now.")
                else:
                    self.log(f"   Failed to press key {hex(action['key_code'])} for '{action['name']}'.")
                    # If key press failed, try again sooner, or just keep the current next_execution_time
                    # For now, let's just log and not reschedule immediately to avoid spamming


    def get_stats(self):
        return {
            'enabled': self.enabled,
            'actions_configured': len(self.actions),
            **self.stats
        }

    def log(self, message):
        if self.logger:
            self.logger.info(f"[TimedAction] {message}")
        else:
            print(f"[TimedAction] {message}")