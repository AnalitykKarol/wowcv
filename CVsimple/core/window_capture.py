"""
Poprawiony moduł przechwytywania okien z lepszą obsługą obrazów i diagnostyki
Zintegrowany z dxcam dla wysokiej wydajności
"""
import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import ctypes
from ctypes import wintypes
from PIL import Image
import threading
import time

# Try to import dxcam for high-performance capture
try:
    from .dx_window_capture import DXWindowCapture
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

            # self.log("🔍 Wykonywanie PrintWindow...", "debug")
            result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)

            if not result:
                error_msg = "PrintWindow zwrócił błąd - okno może być chronione lub zminimalizowane"
                self.log(f"❌ {error_msg}", "error")
                self.capture_stats['failed_captures'] += 1
                self.capture_stats['last_error'] = error_msg
                return None

            # self.log("✅ PrintWindow wykonany pomyślnie", "debug")

            # Pobierz dane bitmap
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            # Wyłączono intensywne logi DEBUG dla wydajności
            # self.log(f"📊 Bitmap info: width={bmpinfo['bmWidth']}, height={bmpinfo['bmHeight']}", "debug")
            # self.log(f"📊 Bitmap data length: {len(bmpstr)}", "debug")

            # Optymalizacja: Bezpośrednia konwersja numpy (BGRX -> RGB) - BEZ PIL
            try:
                # self.log("🔄 Próba bezpośredniej konwersji numpy...", "debug")

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

                # Wyłączono intensywne logi DEBUG dla wydajności
                # self.log(f"📷 Numpy konwersja: {img_array.shape}, typ: {img_array.dtype}", "debug")

                # Waliduj i napraw obraz
                img_array = self.validate_and_fix_image_array(img_array, "Numpy capture")
                if img_array is not None:
                    # self.log(f"✅ Obraz przechwycony przez numpy (BGR->RGB)", "debug")
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


class ThreadSafeWindowCapture(WindowCapture):
    """
    Thread-safe window capture with dedicated capture thread running at high FPS
    Designed for multi-threaded YOLO pipeline architecture
    """

    def __init__(self, logger=None, target_fps=60, queue_size=3):
        super().__init__(logger)
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.queue_size = queue_size

        # Threading components
        self.capture_thread = None
        self.frame_queue = None
        self.stats_lock = None
        self.is_capturing = False
        self.hwnd = None

        # Performance tracking
        self.capture_times = []
        self.frame_id_counter = 0
        self.frames_dropped = 0
        self.last_capture_time = 0

        # Initialize dxcam for high-performance capture
        self.dx_capture = None
        self.use_dx_capture = DXCAM_AVAILABLE

        if self.use_dx_capture:
            try:
                self.dx_capture = DXWindowCapture(output_color="RGB")  # RGB for direct YOLO input
                self.log("🚀 dxcam initialized for high-performance capture")

                # Test dxcam immediately to ensure it works
                test_hwnd = win32gui.GetForegroundWindow()
                test_frame = self.dx_capture.capture_window_screenshot(test_hwnd)
                if test_frame is not None:
                    self.log(f"✅ dxcam test successful - frame shape: {test_frame.shape}")
                else:
                    self.log("⚠️ dxcam test failed - falling back to PrintWindow")
                    self.use_dx_capture = False
                    self.dx_capture = None

            except Exception as e:
                self.log(f"⚠️ dxcam initialization failed: {e}")
                self.use_dx_capture = False
                self.dx_capture = None
                self.log("🔄 Falling back to PrintWindow")
        else:
            self.log("⚠️ dxcam not available - using optimized PrintWindow")

        # Initialize thread-safe components
        self._init_threading()

    def _init_threading(self):
        """Initialize threading components"""
        import threading
        import queue

        self.stats_lock = threading.Lock()
        self.frame_queue = queue.Queue(maxsize=self.queue_size)

        self.log(f"🔄 ThreadSafeWindowCapture initialized: {self.target_fps} FPS, queue size: {self.queue_size}")

    def start_capture(self, hwnd):
        """Start dedicated capture thread"""
        if self.capture_thread and self.capture_thread.is_alive():
            self.log("⚠️ Capture thread already running")
            return

        if not self.is_window_valid(hwnd):
            self.log(f"❌ Invalid window handle: {hwnd}")
            return False

        self.hwnd = hwnd
        self.is_capturing = True
        self.frames_dropped = 0
        self.frame_id_counter = 0

        self.capture_thread = threading.Thread(
            target=self._capture_worker,
            name="WindowCaptureThread",
            daemon=True
        )
        self.capture_thread.start()
        self.log(f"🚀 Capture thread started for window {hwnd}")
        return True

    def stop_capture(self):
        """Stop capture thread gracefully"""
        if not self.is_capturing:
            return

        self.is_capturing = False

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
            if self.capture_thread.is_alive():
                self.log("⚠️ Capture thread did not stop gracefully")
            else:
                self.log("✅ Capture thread stopped gracefully")

        # Clear queue
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                break

        self.log(f"📊 Capture stopped - Total frames dropped: {self.frames_dropped}")

    def _capture_worker(self):
        """Dedicated capture thread running at target_fps"""
        import time
        import numpy as np

        self.log(f"🔄 Capture worker started: {self.target_fps} FPS target")

        while self.is_capturing:
            frame_start_time = time.perf_counter()

            try:
                # Validate window before capture
                if not self.is_window_valid(self.hwnd):
                    self.log("❌ Window became invalid during capture")
                    time.sleep(0.1)
                    continue

                # Capture frame using dxcam (high-performance) or fallback
                if self.use_dx_capture and self.dx_capture:
                    frame = self.dx_capture.capture_window_screenshot(self.hwnd)
                    # dxcam returns RGB, but we need to match expected format
                    # For YOLO, RGB is actually preferred
                else:
                    frame = super().capture_window_screenshot(self.hwnd)

                if frame is not None and isinstance(frame, np.ndarray) and frame.size > 0:
                    # Create frame metadata
                    timestamp = time.time()
                    frame_id = self.frame_id_counter

                    frame_data = {
                        'frame': frame,
                        'timestamp': timestamp,
                        'frame_id': frame_id,
                        'hwnd': self.hwnd,
                        'capture_time': timestamp
                    }

                    # Add to queue (drop if full)
                    try:
                        self.frame_queue.put_nowait(frame_data)
                        self.frame_id_counter += 1
                    except:
                        self.frames_dropped += 1

                        # Memory optimization: Drop oldest frame and cleanup
                        try:
                            old_frame = self.frame_queue.get_nowait()
                            # Explicit cleanup of large numpy array
                            if old_frame and 'frame' in old_frame:
                                del old_frame['frame']
                                del old_frame
                            import gc
                            gc.collect()
                            self.frame_queue.put_nowait(frame_data)
                        except:
                            pass

                    # Track capture timing
                    capture_duration = (time.perf_counter() - frame_start_time) * 1000
                    self._update_capture_stats(capture_duration)

                else:
                    # Failed capture - sleep briefly
                    time.sleep(0.001)

            except Exception as e:
                self.log(f"❌ Capture error: {str(e)}")
                time.sleep(0.01)

            # Maintain target FPS
            frame_duration = time.perf_counter() - frame_start_time
            sleep_time = max(0, self.frame_interval - frame_duration)
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.log("🛑 Capture worker stopped")

    def _update_capture_stats(self, capture_duration):
        """Update capture performance statistics"""
        with self.stats_lock:
            self.capture_times.append(capture_duration)
            # Keep only recent samples (last 100)
            if len(self.capture_times) > 100:
                self.capture_times = self.capture_times[-100:]
            self.last_capture_time = time.time()

    def get_latest_frame(self, block=False, timeout=None):
        """Get latest frame from queue"""
        import queue

        try:
            if block:
                frame_data = self.frame_queue.get(timeout=timeout or 0.016)  # 16ms = 60 FPS
            else:
                frame_data = self.frame_queue.get_nowait()
            return frame_data
        except queue.Empty:
            return None

    def get_latest_frame_non_blocking(self):
        """Get latest frame, dropping old frames to ensure freshness"""
        frame_data = None
        dropped = 0

        # Get all frames from queue, keep only the newest
        while not self.frame_queue.empty():
            try:
                frame_data = self.frame_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break

        if dropped > 1:
            self.frames_dropped += (dropped - 1)
            if self.logger:
                self.logger.debug(f"🔥 Dropped {dropped-1} old frames to get latest")

        return frame_data

    def get_queue_size(self):
        """Get current frame queue size"""
        return self.frame_queue.qsize()

    def get_capture_stats(self):
        """Get detailed capture statistics"""
        with self.stats_lock:
            stats = super().get_capture_stats()

            if self.capture_times:
                avg_time = sum(self.capture_times) / len(self.capture_times)
                max_time = max(self.capture_times)
                min_time = min(self.capture_times)
                actual_fps = 1000.0 / avg_time if avg_time > 0 else 0
            else:
                avg_time = max_time = min_time = actual_fps = 0

            # Get dxcam performance stats if available
            dx_stats = {}
            if self.use_dx_capture and self.dx_capture:
                dx_stats = self.dx_capture.get_performance_stats()

            thread_stats = {
                'target_fps': self.target_fps,
                'actual_fps': actual_fps,
                'avg_capture_time_ms': avg_time,
                'max_capture_time_ms': max_time,
                'min_capture_time_ms': min_time,
                'frames_captured': self.frame_id_counter,
                'frames_dropped': self.frames_dropped,
                'drop_rate_percent': (self.frames_dropped / max(1, self.frame_id_counter + self.frames_dropped)) * 100,
                'queue_size': self.frame_queue.qsize(),
                'queue_utilization': (self.frame_queue.qsize() / self.queue_size) * 100,
                'is_capturing': self.is_capturing,
                'last_capture_time': self.last_capture_time,
                # dxcam specific stats
                'capture_method': 'dxcam' if self.use_dx_capture else 'PrintWindow',
                'dx_available': DXCAM_AVAILABLE,
                'dx_stats': dx_stats
            }

            stats.update(thread_stats)
            return stats

    def clear_queue(self):
        """Clear all frames from queue"""
        cleared = 0
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
                cleared += 1
            except:
                break
        self.log(f"🗑️ Cleared {cleared} frames from queue")
        return cleared

    def set_target_fps(self, new_fps):
        """Change target FPS dynamically"""
        if 1 <= new_fps <= 120:
            old_fps = self.target_fps
            self.target_fps = new_fps
            self.frame_interval = 1.0 / new_fps
            self.log(f"🔄 Target FPS changed: {old_fps} → {new_fps}")
        else:
            self.log(f"⚠️ Invalid FPS: {new_fps} (must be 1-120)")

    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self.stop_capture()
        except:
            pass