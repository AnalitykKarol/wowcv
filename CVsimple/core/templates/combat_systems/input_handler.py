"""
InputHandler - Wspólne funkcje zarządzania kluczami dla wszystkich systemów
Eliminuje duplikację kodu między continuous_movement.py i combat_controller.py
"""
import win32api
import win32con
import time
from typing import Optional


class InputHandler:
    """
    Centralne zarządzanie wszystkimi input'ami do gry
    Wspólne funkcje dla ContinuousMovement i ReactiveCombatController
    """

    def __init__(self, logger=None):
        self.logger = logger

        # Virtual key codes - wspólne dla wszystkich systemów
        self.VK_W, self.VK_A, self.VK_S, self.VK_D = 0x57, 0x41, 0x53, 0x44
        self.VK_1, self.VK_2, self.VK_3, self.VK_4 = 0x31, 0x32, 0x33, 0x34
        self.VK_5, self.VK_6, self.VK_7, self.VK_8 = 0x35, 0x36, 0x37, 0x38
        self.VK_MINUS, self.VK_EQUALS = 0xBD, 0xBB

    def log(self, message: str):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)

    def send_key_down(self, hwnd: int, vk_code: int) -> bool:
        """
        Send key down message
        Identyczny kod z obu plików - teraz w jednym miejscu
        """
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            return True
        except Exception as e:
            self.log(f"❌ send_key_down failed: {e}")
            return False

    def send_key_up(self, hwnd: int, vk_code: int) -> bool:
        """
        Send key up message
        Identyczny kod z obu plików - teraz w jednym miejscu
        """
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
            return True
        except Exception as e:
            self.log(f"❌ send_key_up failed: {e}")
            return False

    def send_key_press(self, hwnd: int, vk_code: int) -> bool:
        """
        Send complete key press (down + up)
        Z combat_controller.py - dodane dla kompletności
        """
        try:
            if not self.send_key_down(hwnd, vk_code):
                return False
            time.sleep(0.05)
            return self.send_key_up(hwnd, vk_code)
        except Exception as e:
            self.log(f"❌ send_key_press failed: {e}")
            return False

    def send_mouse_click(self, hwnd: int, x: float, y: float, button_type: str = "right") -> bool:
        """
        Send mouse click - extracted from combat_controller method_1_wow_proven_postmessage
        Używane przez clicking system w combat_controller
        """
        try:
            lParam = ((int(y) << 16) | (int(x) & 0xFFFF))

            # Inform game where mouse is
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
            time.sleep(0.001)

            if button_type == "right":
                # Right click
                result1 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, 0, lParam)
                time.sleep(0.01)  # Small delay between down and up
                result2 = win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lParam)
            elif button_type == "left":
                # Left click
                result1 = win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, 0, lParam)
                time.sleep(0.01)
                result2 = win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
            else:
                self.log(f"❌ Unknown button type: {button_type}")
                return False

            success = bool(result1 and result2)
            return success
        except Exception as e:
            self.log(f"❌ send_mouse_click failed: {e}")
            return False

    def validate_hwnd(self, hwnd: int) -> bool:
        """
        Validate that hwnd is valid
        Pomocnicza funkcja dla bezpieczeństwa
        """
        try:
            import win32gui
            return win32gui.IsWindow(hwnd)
        except Exception:
            return False

    def get_vk_codes(self) -> dict:
        """
        Get all virtual key codes as dictionary
        Ułatwia dostęp do kodów kluczy z zewnątrz
        """
        return {
            'W': self.VK_W, 'A': self.VK_A, 'S': self.VK_S, 'D': self.VK_D,
            '1': self.VK_1, '2': self.VK_2, '3': self.VK_3, '4': self.VK_4,
            '5': self.VK_5, '6': self.VK_6, '7': self.VK_7, '8': self.VK_8,
            'MINUS': self.VK_MINUS, 'EQUALS': self.VK_EQUALS
        }


# === TESTING/DEMO CODE ===
if __name__ == "__main__":
    print("⌨️ InputHandler - Direct execution test")
    print("=" * 50)

    try:
        # Test initialization
        input_handler = InputHandler(logger=None)
        print("✅ InputHandler initialized successfully")

        # Test VK codes
        vk_codes = input_handler.get_vk_codes()
        print(f"📋 Available VK codes: {list(vk_codes.keys())}")
        print(f"📋 W key code: {vk_codes['W']}")
        print(f"📋 Attack keys: {[vk_codes[str(i)] for i in range(1, 9)]}")

        # Test validation (will fail without real hwnd, but shows method works)
        test_hwnd = 0
        is_valid = input_handler.validate_hwnd(test_hwnd)
        print(f"🪟 HWND validation test (expected False): {is_valid}")

        print("\n🎯 InputHandler is ready to use!")
        print("   This provides centralized key and mouse input for all combat systems")
        print("   Usage:")
        print("   input_handler.send_key_down(hwnd, input_handler.VK_W)")
        print("   input_handler.send_mouse_click(hwnd, x, y, 'right')")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        print("Make sure you have win32api installed: pip install pywin32")