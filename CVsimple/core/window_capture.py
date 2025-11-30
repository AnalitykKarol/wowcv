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

    def log(self, message, level="info"):
        """Helper do logowania z poziomami"""
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
            print(f"[{level.upper()}] {message}")

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

            self.log(f"📐 Przechwytywanie okna: {width}x{height}", "debug")

            if width <= 0 or height <= 0:
                error_msg = f"Nieprawidłowe wymiary okna: {width}x{height}"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            # Sprawdź czy wymiary nie są zbyt duże
            if width > 4096 or height > 4096:
                self.log(f"⚠️ Bardzo duże okno: {width}x{height} - może być powolne", "warning")

            # Pobierz device context okna
            hwndDC = win32gui.GetWindowDC(hwnd)
            if not hwndDC:
                error_msg = "Nie udało się pobrać DC okna"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            # Utwórz DC z handle
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            if not mfcDC:
                error_msg = "Nie udało się utworzyć DC z handle"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            # Utwórz kompatybilny DC
            saveDC = mfcDC.CreateCompatibleDC()
            if not saveDC:
                error_msg = "Nie udało się utworzyć kompatybilnego DC"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            # Utwórz bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # Użyj PrintWindow
            user32 = ctypes.windll.user32
            PW_RENDERFULLCONTENT = 0x00000002

            self.log("🔍 Wykonywanie PrintWindow...", "debug")
            result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)

            if not result:
                error_msg = "PrintWindow zwrócił błąd - okno może być chronione lub zminimalizowane"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            self.log("✅ PrintWindow wykonany pomyślnie", "debug")

            # Pobierz dane bitmap
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            self.log(f"📊 Bitmap info: width={bmpinfo['bmWidth']}, height={bmpinfo['bmHeight']}", "debug")
            self.log(f"📊 Bitmap data length: {len(bmpstr)}", "debug")

            # Metoda 1: PIL Image.frombuffer (BGRX -> RGB)
            try:
                img = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1
                )

                # Konwertuj do numpy array (już RGB z PIL)
                img_array = np.array(img)
                self.log(f"📷 PIL konwersja: {img_array.shape}, typ: {img_array.dtype}", "debug")

                # Waliduj i napraw obraz
                img_array = self.validate_and_fix_image_array(img_array, "PIL capture")
                if img_array is not None:
                    self.log(f"✅ Obraz przechwycony przez PIL (RGB)", "debug")
                    self.capture_stats['successful_captures'] += 1
                    self.last_successful_capture = time.time()
                    return img_array

            except Exception as pil_error:
                self.log(f"⚠️ PIL konwersja nie powiodła się: {str(pil_error)}", "warning")

            # Metoda 2: Bezpośrednia konwersja numpy/cv2 (BGRX -> RGB)
            try:
                self.log("🔄 Próba bezpośredniej konwersji numpy...", "debug")

                # Konwertuj dane bitmap do numpy array
                img_bgr = np.frombuffer(bmpstr, dtype=np.uint8)

                # Sprawdź czy rozmiar się zgadza
                expected_size = width * height * 4  # BGRX = 4 bajty na piksel
                if len(img_bgr) != expected_size:
                    self.log(f"⚠️ Nieprawidłowy rozmiar danych: {len(img_bgr)} vs oczekiwane {expected_size}", "warning")
                    # Spróbuj dopasować rozmiar
                    if len(img_bgr) > expected_size:
                        img_bgr = img_bgr[:expected_size]
                    else:
                        self.log(f"❌ Za mało danych bitmap", "error")
                        raise Exception("Za mało danych bitmap")

                # Reshape do obrazu BGRX
                img_bgr = img_bgr.reshape((height, width, 4))

                # POPRAWKA: Konwertuj BGR do RGB (bez kanału alpha)
                img_array = cv2.cvtColor(img_bgr[:,:,:3], cv2.COLOR_BGR2RGB)

                self.log(f"📷 Numpy konwersja: {img_array.shape}, typ: {img_array.dtype}", "debug")

                # Waliduj i napraw obraz
                img_array = self.validate_and_fix_image_array(img_array, "Numpy capture")
                if img_array is not None:
                    self.log(f"✅ Obraz przechwycony przez numpy (BGR->RGB)", "debug")
                    self.capture_stats['successful_captures'] += 1
                    self.last_successful_capture = time.time()
                    return img_array

            except Exception as numpy_error:
                self.log(f"❌ Numpy konwersja nie powiodła się: {str(numpy_error)}", "error")

            # Jeśli obie metody zawiodły
            error_msg = "Nie udało się skonwertować danych bitmap do obrazu"
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

        finally:
            # Cleanup w odwrotnej kolejności tworzenia
            if saveBitMap:
                try:
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                except:
                    pass

            if saveDC:
                try:
                    saveDC.DeleteDC()
                except:
                    pass

            if mfcDC:
                try:
                    mfcDC.DeleteDC()
                except:
                    pass

            if hwndDC:
                try:
                    win32gui.ReleaseDC(hwnd, hwndDC)
                except:
                    pass

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