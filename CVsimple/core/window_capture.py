"""
Poprawiony moduł przechwytywania okien z lepszą obsługą obrazów i diagnostyką
"""
import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import ctypes
from ctypes import wintypes
from PIL import Image
import time
import collections

# Szybkie metody capture
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import dxcam
    DXCAM_AVAILABLE = True
except ImportError:
    DXCAM_AVAILABLE = False

class WindowCapture:
    def __init__(self, logger=None):
        self.logger = logger
        self.last_successful_capture = None
        self.capture_stats = {
            'total_attempts': 0,
            'successful_captures': 0,
            'failed_captures': 0,
            'last_error': None
        }
        # Prosta metoda logowania
        self.log = print

        # Memory optimization: reusable buffers
        self._buffer = None  # Reusable numpy buffer
        self._buffer_size = (0, 0)  # Current buffer dimensions

        # Frame buffering for smoother processing
        self.frame_buffer_size = 1  # Zmniejszono aby uniknąć opóźnień
        self.frame_buffer = collections.deque(maxlen=self.frame_buffer_size)
        self.last_capture_time = 0

        # DXCam instance dla GPU capture
        self._dx_camera = None
        if DXCAM_AVAILABLE:
            try:
                self._dx_camera = dxcam.create()
                self.log("🎮 DXCam zainicjalizowany - GPU capture dostępny")
            except Exception as e:
                self.log(f"⚠️ Nie udało się zainicjalizować DXCam: {e}")
                self._dx_camera = None

    def _get_or_create_buffer(self, width, height, channels=3):
        """Get or create reusable buffer for image data"""
        if (self._buffer is None or
            self._buffer_size != (width, height) or
            self._buffer.shape != (height, width, channels)):
            # Create new buffer if needed
            self._buffer = np.empty((height, width, channels), dtype=np.uint8)
            self._buffer_size = (width, height)
        return self._buffer

    def cleanup_buffers(self):
        """Explicit cleanup to free memory"""
        if self._buffer is not None:
            del self._buffer
            self._buffer = None
            self._buffer_size = (0, 0)

        # Cleanup DXCam
        if self._dx_camera is not None:
            try:
                self._dx_camera.release()
                self._dx_camera = None
            except:
                pass

    def get_window_list(self):
        """Pobiera listę wszystkich widocznych okien"""
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title and len(window_title.strip()) > 0:
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]

                        # Filtruj zbyt małe okna
                        if width > 100 and height > 100:
                            windows.append({
                                'hwnd': hwnd,
                                'title': window_title,
                                'rect': rect,
                                'width': width,
                                'height': height
                            })
                    except:
                        pass
            return True

        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        windows.sort(key=lambda x: x['title'].lower())

        self.log(f"Znaleziono {len(windows)} dostępnych okien")
        return windows

    def is_window_valid(self, hwnd):
        """Sprawdza czy okno nadal istnieje i jest widoczne"""
        try:
            return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
        except:
            return False

    def validate_and_fix_image_array(self, img_array, context=""):
        """Waliduje i naprawia obraz aby był prawidłowy dla YOLO"""
        if img_array is None:
            self.log(f"❌ {context}: Obraz jest None", "error")
            return None

        if not isinstance(img_array, np.ndarray):
            self.log(f"❌ {context}: Obraz nie jest numpy array: {type(img_array)}", "error")
            return None

        if img_array.size == 0:
            self.log(f"❌ {context}: Obraz ma rozmiar 0", "error")
            return None

        # Sprawdź i napraw wymiary
        if len(img_array.shape) == 2:
            # Grayscale -> RGB
            self.log(f"🔄 {context}: Konwersja grayscale do RGB", "debug")
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif len(img_array.shape) != 3:
            self.log(f"❌ {context}: Nieprawidłowy kształt obrazu: {img_array.shape}", "error")
            return None

        # Sprawdź i napraw kanały
        if img_array.shape[2] == 4:
            # RGBA -> RGB
            self.log(f"🔄 {context}: Konwersja RGBA do RGB", "debug")
            img_array = img_array[:,:,:3]  # Usuń kanał alpha
        elif img_array.shape[2] != 3:
            self.log(f"❌ {context}: Nieprawidłowa liczba kanałów: {img_array.shape[2]}", "error")
            return None

        # Sprawdź i napraw typ danych
        if img_array.dtype != np.uint8:
            self.log(f"🔄 {context}: Konwersja typu danych z {img_array.dtype} do uint8", "debug")
            if img_array.dtype in [np.float32, np.float64]:
                if img_array.max() <= 1.0:
                    img_array = (img_array * 255).astype(np.uint8)
                else:
                    img_array = img_array.astype(np.uint8)
            else:
                img_array = img_array.astype(np.uint8)

        # Sprawdź czy obraz nie jest pusty
        if np.all(img_array == 0):
            self.log(f"⚠️ {context}: Obraz jest całkowicie czarny", "warning")
        elif np.all(img_array == 255):
            self.log(f"⚠️ {context}: Obraz jest całkowicie biały", "warning")


        return img_array

    def capture_window_screenshot(self, hwnd):
        """
        Przechwytuje screenshot okna z ulepszoną obsługą błędów i walidacją
        """
        self.capture_stats['total_attempts'] += 1

        hwndDC = None
        mfcDC = None
        saveDC = None
        saveBitMap = None

        try:
            # Sprawdź czy okno istnieje
            if not self.is_window_valid(hwnd):
                error_msg = f"Okno {hwnd} nie istnieje lub nie jest widoczne"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            # Pobierz rozmiar okna
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # Wyłączono intensywne logi DEBUG dla wydajności
            # self.log(f"📐 Przechwytywanie okna: {width}x{height}", "debug")

            if width <= 0 or height <= 0:
                error_msg = f"Nieprawidłowe wymiary okna: {width}x{height}"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            # Sprawdź czy wymiary nie są zbyt duże
            if width > 4096 or height > 4096:
                self.log(f"⚠️ Bardzo duże okno: {width}x{height} - może być powolne", "warning")

            # Najpierw spróbuj tradycyjne metody (PrintWindow/BitBlt)
            # Te metody pobierają zawartość okna, niezależnie od nakładających się okien
            try:
                # Pobierz device context okna
                hwndDC = win32gui.GetWindowDC(hwnd)
                if not hwndDC:
                    raise Exception("Nie udało się pobrać DC okna")

                # Utwórz DC z handle
                mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                if not mfcDC:
                    raise Exception("Nie udało się utworzyć DC z handle")

                # Utwórz kompatybilny DC
                saveDC = mfcDC.CreateCompatibleDC()
                if not saveDC:
                    raise Exception("Nie udało się utworzyć kompatybilnego DC")

                # Utwórz bitmap
                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
                saveDC.SelectObject(saveBitMap)

                capture_start = time.time()
                # Najpierw spróbuj PrintWindow (pobiera zawartość okna, nie ekranu)
                user32 = ctypes.windll.user32
                PW_RENDERFULLCONTENT = 0x00000002
                result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)
                capture_method = "PrintWindow"

                # Jeśli PrintWindow nie zadziała, spróbuj BitBlt
                if not result:
                    try:
                        result = saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
                        if result:
                            capture_method = "BitBlt"
                        else:
                            raise Exception("BitBlt failed")
                    except:
                        raise Exception("PrintWindow i BitBlt nie zadziałały")

                if not result:
                    raise Exception(f"Metoda {capture_method} zwróciła błąd")

                # Pobierz dane bitmap
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)

                # Konwersja BGRX -> RGB
                img_bgrx = np.frombuffer(bmpstr, dtype=np.uint8)
                expected_size = width * height * 4  # BGRX = 4 bajty na piksel

                if len(img_bgrx) != expected_size:
                    if len(img_bgrx) > expected_size:
                        img_bgrx = img_bgrx[:expected_size]
                    else:
                        raise Exception("Za mało danych bitmap")

                # Reshape do obrazu BGRX
                img_bgrx = img_bgrx.reshape((height, width, 4))

                # Konwertuj BGRX do RGB
                img_array = self._get_or_create_buffer(width, height, 3)
                cv2.cvtColor(img_bgrx[:,:,:3], cv2.COLOR_BGR2RGB, dst=img_array)

                # Waliduj i napraw obraz
                img_array = self.validate_and_fix_image_array(img_array, f"{capture_method} capture")
                if img_array is not None:
                    self.capture_stats['successful_captures'] += 1
                    self.last_successful_capture = time.time()
                    self.frame_buffer.append(img_array)
                    self.last_capture_time = time.time()

                    # Cleanup
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(hwnd, hwndDC)

                    return img_array
                else:
                    raise Exception("Walidacja obrazu nie powiodła się")

            except Exception as pw_error:
                self.log(f"⚠️ PrintWindow/BitBlt nie zadziałały: {str(pw_error)}", "debug")

            # Fallback do MSS (tylko jeśli PrintWindow nie zadziałał)
            if MSS_AVAILABLE:
                try:
                    capture_start = time.time()

                    # Create new MSS instance dla bezpieczeństwa wielowątkowego
                    with mss.mss() as sct:
                        # Define the monitor region
                        monitor = {
                            "top": rect[1],
                            "left": rect[0],
                            "width": width,
                            "height": height
                        }

                        # Grab the data
                        screenshot = sct.grab(monitor)

                        # Sprawdź rozmiar przed konwersją
                        if hasattr(screenshot, 'raw') and screenshot.raw:
                            # Użyj raw data jeśli dostępne
                            img_bytes = screenshot.raw
                        elif hasattr(screenshot, 'rgb'):
                            # Konwertuj RGB buffer
                            img_bytes = screenshot.rgb
                        else:
                            # Fallback do konwersji przez numpy
                            img_array = np.array(screenshot)
                            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)
                            img_bytes = None

                        if img_bytes:
                            # Konwertuj bytes do array
                            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                            expected_size = width * height * 4  # BGRA = 4 bytes per pixel

                            if len(img_array) != expected_size:
                                # Próba dopasowania do RGB (3 bytes per pixel)
                                expected_size_rgb = width * height * 3
                                if len(img_array) == expected_size_rgb:
                                    # To już RGB, tylko reshape
                                    img_array = img_array.reshape((height, width, 3))
                                else:
                                    raise ValueError(f"Rozmiar danych nie pasuje: {len(img_array)} vs {expected_size} (BGRA) lub {expected_size_rgb} (RGB)")
                            else:
                                # BGRA -> BGR -> RGB
                                img_array = img_array.reshape((height, width, 4))
                                img_array = img_array[:, :, :3]  # Usuń alpha
                                # Utwórz nową tablicę dla cvtColor
                                img_rgb = np.empty_like(img_array)
                                cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB, dst=img_rgb)
                                img_array = img_rgb

                    capture_time = (time.time() - capture_start) * 1000
                    # Logi usunięte dla wydajności

                    # Waliduj i napraw obraz
                    img_array = self.validate_and_fix_image_array(img_array, "MSS optimized")
                    if img_array is not None:
                        self.capture_stats['successful_captures'] += 1
                        self.last_successful_capture = time.time()

                        # Store in buffer
                        self.frame_buffer.append(img_array)
                        self.last_capture_time = time.time()
                        return img_array
                except Exception as mss_error:
                    self.log(f"⚠️ MSS nie zadziałał: {str(mss_error)}", "debug")

            # Fallback do DXCam (tylko jeśli MSS nie zadziałał)
            if DXCAM_AVAILABLE and self._dx_camera:
                try:
                    capture_start = time.time()

                    # Przechwyć cały ekran z GPU
                    frame = self._dx_camera.grab()

                    if frame is not None and frame.size > 0:
                        # Pobierz wymiary ekranu
                        screen_height, screen_width = frame.shape[:2]

                        # Sprawdź czy okno jest w granicach ekranu
                        if (rect[1] < screen_height and rect[3] <= screen_height and
                            rect[0] < screen_width and rect[2] <= screen_width):

                            # Wytnij region okna z pełnego ekranu
                            y1, y2 = max(0, rect[1]), min(screen_height, rect[3])
                            x1, x2 = max(0, rect[0]), min(screen_width, rect[2])

                            if y2 > y1 and x2 > x1:
                                img_array = frame[y1:y2, x1:x2]

                                # Konwersja BGRA do RGB jeśli trzeba
                                if img_array.shape[2] == 4:
                                    img_array = img_array[:, :, :3]  # Usuń alpha
                                    # Reverse channels BGRA->RGB
                                    img_array = img_array[:, :, [2, 1, 0]]
                                elif img_array.shape[2] == 3:
                                    # BGR do RGB
                                    img_array = img_array[:, :, [2, 1, 0]]

                                # Waliduj i napraw obraz
                                img_array = self.validate_and_fix_image_array(img_array, "DXCam capture")
                                if img_array is not None:
                                    self.capture_stats['successful_captures'] += 1
                                    self.last_successful_capture = time.time()

                                    # Store in buffer
                                    self.frame_buffer.append(img_array)
                                    self.last_capture_time = time.time()
                                    return img_array
                            else:
                                # Nieprawidłowe współrzędne
                                pass
                        else:
                            # Okno poza ekranem
                            pass
                    else:
                        # Brak frame od DXCam
                        pass
                except Exception as dx_error:
                    self.log(f"⚠️ DXCam nie zadziałał: {str(dx_error)}", "debug")

            # Wszystkie metody zawiodły
            error_msg = "Wszystkie metody przechwytywania zawiodły"
            self.log(f"❌ {error_msg}", "error")
            self.capture_stats['failed_captures'] += 1
            self.capture_stats['last_error'] = error_msg
            return None

        except Exception as e:
            error_msg = f"Błąd przechwytywania okna: {str(e)}"
            self.log(f"❌ {error_msg}", "error")
            self.capture_stats['failed_captures'] += 1
            self.capture_stats['last_error'] = error_msg
            return None

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.cleanup_buffers()

    def get_capture_stats(self):
        """Zwraca statystyki przechwytywania"""
        total = self.capture_stats['total_attempts']
        success = self.capture_stats['successful_captures']
        failed = self.capture_stats['failed_captures']

        success_rate = (success / total * 100) if total > 0 else 0

        return {
            'total_attempts': total,
            'successful_captures': success,
            'failed_captures': failed,
            'success_rate_percent': success_rate,
            'last_error': self.capture_stats['last_error'],
            'last_successful_capture': self.last_successful_capture
        }

    def test_capture(self, hwnd):
        """Testuje przechwytywanie okna z szczegółową diagnostyką"""
        self.log("=== TEST PRZECHWYTYWANIA OKNA ===")

        start_time = time.time()
        img_array = self.capture_window_screenshot(hwnd)
        capture_time = (time.time() - start_time) * 1000

        if img_array is not None:
            self.log(f"✅ Test przechwytywania: SUKCES ({capture_time:.1f}ms)")
            self.log(f"📊 Obraz: {img_array.shape}, typ: {img_array.dtype}")
            self.log(f"📊 Wartości: min={img_array.min()}, max={img_array.max()}, średnia={img_array.mean():.1f}")

            # Test czy obraz nie jest pusty
            unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
            self.log(f"📊 Unikalnych kolorów: {unique_colors}")

            if unique_colors < 10:
                self.log("⚠️ Obraz wydaje się być bardzo jednolity - sprawdź czy okno nie jest zminimalizowane", "warning")

            return True
        else:
            self.log(f"❌ Test przechwytywania: BŁĄD ({capture_time:.1f}ms)")
            stats = self.get_capture_stats()
            self.log(f"📊 Statystyki: {stats['successful_captures']}/{stats['total_attempts']} sukces ({stats['success_rate_percent']:.1f}%)")
            if stats['last_error']:
                self.log(f"📊 Ostatni błąd: {stats['last_error']}")
            return False

    def get_window_info(self, hwnd):
        """Pobiera szczegółowe informacje o oknie"""
        try:
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)

            # Dodatkowe informacje
            try:
                class_name = win32gui.GetClassName(hwnd)
            except:
                class_name = "Unknown"

            try:
                is_minimized = win32gui.IsIconic(hwnd)
                is_maximized = win32gui.IsZoomed(hwnd)
            except:
                is_minimized = False
                is_maximized = False

            return {
                'title': title,
                'class_name': class_name,
                'rect': rect,
                'width': rect[2] - rect[0],
                'height': rect[3] - rect[1],
                'visible': win32gui.IsWindowVisible(hwnd),
                'exists': win32gui.IsWindow(hwnd),
                'minimized': is_minimized,
                'maximized': is_maximized,
                'capture_stats': self.get_capture_stats()
            }
        except Exception as e:
            return {'error': str(e)}

    def get_screen_info(self):
        """Pobiera szczegółowe informacje o ekranie i monitorach"""
        try:
            resolution = self.get_screen_resolution()
            monitor_info = self.get_monitor_info()

            return {
                'resolution': resolution,
                'monitor_info': monitor_info,
                'timestamp': time.time()
            }
        except Exception as e:
            self.log(f"❌ Błąd pobierania informacji o ekranie: {str(e)}")
            return {'resolution': (1920, 1080), 'monitor_info': None, 'error': str(e)}