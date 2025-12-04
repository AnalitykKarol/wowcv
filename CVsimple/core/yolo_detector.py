"""
Uproszczony moduł wykrywania YOLO - bez threadingu, tylko podstawowe funkcje
FIXED dla PyTorch 2.6+ weights_only issue
"""
import cv2
import numpy as np
from pathlib import Path
import time
import torch
import warnings
import threading
from packaging import version
from ultralytics import YOLO


class OptimizedYOLODetector:
    def __init__(self, logger=None):
        self.logger = logger
        self.model = None
        self.model_loaded = False
        self.class_names = []

        # Statystyki walidacji obrazów
        self.image_validation_stats = {
            'total_images_received': 0,
            'valid_images': 0,
            'invalid_images': 0,
            'last_error': None
        }

        # Performance monitoring
        self.inference_times = []
        self.max_time_samples = 20

        # Prosta metoda logowania
        self.log = print

        # NOWE: Aplikuj fix PyTorch 2.6+ na początku
        self._apply_pytorch26_fix()

        # Automatycznie załaduj model
        self.auto_load_model()

    def _apply_pytorch26_fix(self):
        """
        Fix dla PyTorch 2.6+ weights_only issue
        Aplikuje patch dla torch.load aby modele YOLO ładowały się z weights_only=False
        """
        torch_version = torch.__version__
        print(f"🔍 PyTorch version: {torch_version}")

        if version.parse(torch_version) >= version.parse("2.6.0"):
            print("🔧 Aplikuję fix dla PyTorch 2.6+ weights_only issue...")

            # Zapisz oryginalną funkcję torch.load
            if not hasattr(torch, '_original_load'):
                torch._original_load = torch.load

                def patched_torch_load(f, *args, **kwargs):
                    """
                    Patched torch.load który automatycznie ustawia weights_only=False
                    dla plików .pt (modeli YOLO)
                    """
                    # Sprawdź czy to plik .pt
                    is_pt_file = False
                    if isinstance(f, str) and f.endswith('.pt'):
                        is_pt_file = True
                    elif hasattr(f, 'name') and f.name.endswith('.pt'):
                        is_pt_file = True

                    # Jeśli to plik .pt i nie ma weights_only, ustaw na False
                    if is_pt_file and 'weights_only' not in kwargs:
                        kwargs['weights_only'] = False
                        print(f"📥 Ładuję model {f} z weights_only=False")

                    # Wycisz ostrzeżenia o weights_only
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore",
                                              message=".*weights_only=False.*",
                                              category=FutureWarning)
                        return torch._original_load(f, *args, **kwargs)

                # Zastąp torch.load naszą wersją
                torch.load = patched_torch_load
                print("✅ PyTorch 2.6+ fix zaaplikowany - modele .pt będą ładowane z weights_only=False")
        else:
            print("ℹ️ PyTorch < 2.6 - fix nie jest potrzebny")

  
    def auto_load_model(self):
        """Automatycznie ładuje model przy starcie"""
        model_paths = [
            r"E:\Work\fun\yolo-V8\runs\detect\train16\weights\best.pt"
        ]

        for model_path in model_paths:
            if Path(model_path).exists():
                self.log(f"🚀 Znaleziono model: {model_path}")
                if self.load_model(model_path):
                    self.log("✅ Model automatycznie załadowany!")
                    return True

        self.log("⚠️ Nie znaleziono modelu. Użyj 'Załaduj model' aby wybrać plik best.pt", "warning")
        return False

    def load_model(self, model_path=None):
        """Ładuje model YOLO z obsługą PyTorch 2.6+"""
        try:
            if model_path is None:
                model_path = r"E:\Work\fun\yolo-V8\runs\detect\train16\weights\best.pt"

            model_path = Path(model_path)
            if not model_path.exists():
                raise Exception(f"Plik modelu nie istnieje: {model_path}")

            self.log(f"🚀 Ładowanie modelu: {model_path}")

            # DODATKOWY FIX: Wycisz ostrzeżenia FutureWarning podczas ładowania YOLO
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
                warnings.filterwarnings("ignore", message=".*weights_only.*")

                # Załaduj model - teraz z fix'em dla PyTorch 2.6+
                self.model = YOLO(str(model_path))

            # GPU jeśli dostępne
            try:
                if torch.cuda.is_available():
                    self.model.to('cuda')
                    self.log("🔥 Model przeniesiony na GPU")
                else:
                    self.log("💻 Używam CPU")
            except:
                self.log("💻 Używam CPU")

            # Pobierz nazwy klas
            if hasattr(self.model, 'names'):
                self.class_names = list(self.model.names.values())
                self.log(f"📋 Klasy modelu: {self.class_names}")
            else:
                self.class_names = ['health_bar']
                self.log("⚠️ Używam domyślnej klasy 'health_bar'", "warning")

            # Testowe uruchomienie
            self.log("🔥 Rozgrzewanie modelu...")
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                _ = self.model(dummy_frame, verbose=False)

            self.model_loaded = True
            self.log("✅ Model YOLO załadowany pomyślnie!")
            return True

        except Exception as e:
            self.log(f"❌ Błąd ładowania modelu: {str(e)}", "error")
            self.model_loaded = False

            # Sprawdź czy to błąd weights_only
            if "weights_only" in str(e) or "WeightsUnpickler" in str(e):
                self.log("🔧 Wykryto błąd PyTorch 2.6+ weights_only - próbuję alternatywną metodę...", "warning")
                return self._load_model_fallback(model_path)

            return False

    def _load_model_fallback(self, model_path):
        """
        Fallback method dla ładowania modelu gdy główny fix nie zadziałał
        """
        try:
            self.log("🔄 Próbuję załadować model z bezpośrednim weights_only=False...")

            # Bezpośrednie nadpisanie torch.load dla tego konkretnego ładowania
            original_load = torch.load

            def force_weights_only_false(*args, **kwargs):
                kwargs['weights_only'] = False
                return original_load(*args, **kwargs)

            # Tymczasowo zastąp torch.load
            torch.load = force_weights_only_false

            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore")
                    self.model = YOLO(str(model_path))

                self.model_loaded = True
                self.log("✅ Model załadowany metodą fallback!")
                return True

            finally:
                # Przywróć oryginalny torch.load
                torch.load = original_load

        except Exception as fallback_error:
            self.log(f"❌ Błąd metody fallback: {str(fallback_error)}", "error")
            return False

    def validate_and_prepare_image(self, frame, context=""):
        """Waliduje i przygotowuje obraz dla YOLO"""
        self.image_validation_stats['total_images_received'] += 1

        if frame is None:
            error_msg = f"{context}: Otrzymano pustą ramkę (None)"
            self.log(f"❌ {error_msg}", "error")
            self.image_validation_stats['invalid_images'] += 1
            self.image_validation_stats['last_error'] = error_msg
            return None

        if not isinstance(frame, np.ndarray):
            error_msg = f"{context}: Ramka nie jest numpy array: {type(frame)}"
            self.log(f"❌ {error_msg}", "error")
            self.image_validation_stats['invalid_images'] += 1
            self.image_validation_stats['last_error'] = error_msg
            return None

        if frame.size == 0:
            error_msg = f"{context}: Ramka ma rozmiar 0"
            self.log(f"❌ {error_msg}", "error")
            self.image_validation_stats['invalid_images'] += 1
            self.image_validation_stats['last_error'] = error_msg
            return None

        try:
            # Konwersja do RGB (Window capture zwraca BGR)
            if len(frame.shape) == 2:
                # Grayscale -> RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            elif len(frame.shape) == 3:
                if frame.shape[2] == 4:
                    # RGBA -> RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
                elif frame.shape[2] == 3:
                    # BGR -> RGB (Window capture zawsze daje BGR!)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Upewnij się że jest uint8
            if frame.dtype != np.uint8:
                if frame.dtype in [np.float32, np.float64]:
                    if frame.max() <= 1.0:
                        frame = (frame * 255).astype(np.uint8)
                    else:
                        frame = frame.astype(np.uint8)
                else:
                    frame = frame.astype(np.uint8)

            self.image_validation_stats['valid_images'] += 1
            return frame

        except Exception as e:
            error_msg = f"{context}: Błąd konwersji obrazu: {str(e)}"
            self.log(f"❌ {error_msg}", "error")
            self.image_validation_stats['invalid_images'] += 1
            self.image_validation_stats['last_error'] = error_msg
            return None

    def stop_inference_thread(self):
        """Stopuje inference - metoda wymagana przez main.py"""
        try:
            self.log("🔄 Zatrzymuję wątek YOLO inference...")
            # OptimizedYOLODetector nie używa threadingu, więc tylko logujemy
            self.model = None
            self.model_loaded = False
            self.log("✅ YOLO inference zatrzymany")
        except Exception as e:
            self.log(f"❌ Błąd zatrzymywania inference: {str(e)}", "error")

    def detect(self, image, confidence_threshold=0.15):
        """
        GŁÓWNA METODA WYKRYWANIA - UPROSZCZONA I DZIAŁAJĄCA
        """
        if not self.model_loaded:
            self.log("❌ Model YOLO nie jest załadowany!", "error")
            return []

        try:
            # 1. Walidacja obrazu
            validated_image = self.validate_and_prepare_image(image, "Main Detect")
            if validated_image is None:
                self.log("❌ Walidacja obrazu nie powiodła się", "error")
                return []

            # 2. Uruchom YOLO
            start_time = time.time()

            # Wycisz ostrzeżenia podczas inference
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                results = self.model(validated_image, conf=confidence_threshold, verbose=False)

            inference_time = (time.time() - start_time) * 1000
            self.inference_times.append(inference_time)
            if len(self.inference_times) > self.max_time_samples:
                self.inference_times.pop(0)

            # 3. Przetwórz wyniki
            detections = []

            if results and len(results) > 0:
                result = results[0]  # Pierwszy wynik

                if hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes

                    
                    for i, box in enumerate(boxes):
                        try:
                            # Pobierz dane z box
                            xyxy = box.xyxy[0].cpu().numpy()  # [x1, y1, x2, y2]
                            conf = float(box.conf[0].cpu().numpy())
                            cls = int(box.cls[0].cpu().numpy())

                            # Sprawdź próg pewności (dodatkowa kontrola)
                            if conf >= confidence_threshold:
                                # Pobierz nazwę klasy
                                if hasattr(result, 'names') and cls in result.names:
                                    class_name = result.names[cls]
                                elif cls < len(self.class_names):
                                    class_name = self.class_names[cls]
                                else:
                                    class_name = 'health_bar'  # Domyślna klasa

                                # Stwórz detekcję w formacie zgodnym z Combat Controller
                                detection = {
                                    'name': class_name,
                                    'confidence': conf,
                                    'x1': int(xyxy[0]),
                                    'y1': int(xyxy[1]),
                                    'x2': int(xyxy[2]),
                                    'y2': int(xyxy[3]),
                                    'center_x': int((xyxy[0] + xyxy[2]) / 2),
                                    'center_y': int((xyxy[1] + xyxy[3]) / 2),
                                    'width': int(xyxy[2] - xyxy[0]),
                                    'height': int(xyxy[3] - xyxy[1]),
                                    'class_id': cls,
                                    'area': int((xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1]))
                                }

                                detections.append(detection)
                                self.log(f"✅ Dodano detekcję: {class_name} ({conf:.3f}) at ({detection['center_x']}, {detection['center_y']})")
                            else:
                                self.log(f"⚠️ Odrzucono detekcję #{i+1}: conf {conf:.3f} < {confidence_threshold}")

                        except Exception as box_error:
                            self.log(f"❌ Błąd przetwarzania box #{i+1}: {str(box_error)}", "error")
                            continue
                
            return detections

        except Exception as e:
            self.log(f"❌ Błąd wykrywania: {str(e)}", "error")
            import traceback
            self.log(f"❌ Stack trace: {traceback.format_exc()}", "error")
            return []

    def detect_health_bars(self, frame, confidence_threshold=0.15):
        """Kompatybilność z HP detector API"""
        return self.detect(frame, confidence_threshold)

    def visualize_detections(self, img, detections, save_path=None):
        """Rysuje wykrycia na obrazie"""
        if not detections:
            return img

        validated_img = self.validate_and_prepare_image(img, "Visualization")
        if validated_img is None:
            return img

        try:
            result_image = validated_img.copy()

            colors = {
                'health_bar': (0, 255, 0),      # Zielony
                'healthbar': (0, 255, 0),       # Zielony
                'health': (0, 255, 0),          # Zielony
                'bar': (0, 255, 0),             # Zielony
                'mob': (255, 255, 0),           # Żółty
                'enemy': (255, 0, 0),           # Czerwony
                'monster': (255, 0, 0),         # Czerwony
                'target': (255, 0, 255),        # Magenta
                'unknown': (255, 255, 255)      # Biały
            }

            for detection in detections:
                try:
                    x1, y1 = detection['x1'], detection['y1']
                    x2, y2 = detection['x2'], detection['y2']
                    name = detection.get('name', 'unknown')
                    confidence = detection['confidence']

                    # Walidacja współrzędnych
                    if x2 <= x1 or y2 <= y1 or x1 < 0 or y1 < 0:
                        continue

                    color = colors.get(name.lower(), colors['unknown'])

                    # Rysuj prostokąt
                    cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 3)

                    # Rysuj tekst
                    text = f"{name}: {confidence:.2f}"
                    text_y = y1 - 10 if y1 > 30 else y2 + 25

                    # Tło dla tekstu
                    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    cv2.rectangle(result_image,
                                (x1, text_y - text_height - 5),
                                (x1 + text_width + 5, text_y + 5),
                                (0, 0, 0), -1)

                    # Tekst
                    cv2.putText(result_image, text, (x1, text_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                except Exception as draw_error:
                    self.log(f"❌ Błąd rysowania detekcji: {str(draw_error)}", "error")
                    continue

            return result_image

        except Exception as e:
            self.log(f"❌ Błąd wizualizacji: {str(e)}", "error")
            return img

    def get_model_info(self):
        """Zwraca informacje o modelu"""
        if not self.model_loaded:
            return {'loaded': False, 'error': 'Model nie jest załadowany'}

        try:
            avg_time = sum(self.inference_times) / len(self.inference_times) if self.inference_times else 0
            estimated_fps = 1000 / avg_time if avg_time > 0 else 0

            return {
                'loaded': True,
                'model_type': 'YOLOv8 (PyTorch 2.6+ Compatible)',
                'classes_count': len(self.class_names),
                'class_names': self.class_names,
                'performance': {
                    'avg_inference_time_ms': avg_time,
                    'estimated_fps': estimated_fps,
                    'samples_count': len(self.inference_times)
                },
                'diagnostics': {
                    'image_validation_stats': self.image_validation_stats,
                    'pytorch_version': torch.__version__,
                    'pytorch_26_fix_applied': version.parse(torch.__version__) >= version.parse("2.6.0")
                }
            }
        except Exception as e:
            return {'loaded': True, 'error': str(e)}

    def get_diagnostic_info(self):
        """Zwraca informacje diagnostyczne"""
        avg_time = sum(self.inference_times) / len(self.inference_times) if self.inference_times else 0
        estimated_fps = 1000 / avg_time if avg_time > 0 else 0

        return {
            'model_loaded': self.model_loaded,
            'model_classes': self.class_names,
            'inference_thread_running': False,  # Brak threadingu
            'inference_queue_size': 0,          # Brak kolejek
            'results_queue_size': 0,            # Brak kolejek
            'cached_detections_count': 0,       # Brak cache
            'image_validation_stats': self.image_validation_stats,
            'performance_stats': {
                'avg_inference_time_ms': avg_time,
                'estimated_fps': estimated_fps,
                'samples_count': len(self.inference_times)
            },
            'pytorch_info': {
                'version': torch.__version__,
                'pytorch_26_fix_applied': version.parse(torch.__version__) >= version.parse("2.6.0")
            }
        }

    def test_detection(self, frame):
        """Test wykrywania z diagnostyką"""
        self.log("=== TEST WYKRYWANIA SIMPLIFIED YOLO ===")

        validated_frame = self.validate_and_prepare_image(frame, "Test Detection")
        if validated_frame is None:
            self.log("❌ Test: Błąd walidacji obrazu")
            return []

        start_time = time.time()
        detections = self.detect(validated_frame, confidence_threshold=0.1)
        total_time = (time.time() - start_time) * 1000

        self.log(f"✅ Test zakończony: {total_time:.1f}ms, {len(detections)} wykryć")

        for i, det in enumerate(detections):
            self.log(f"  {i+1}. {det['name']} - confidence: {det['confidence']:.3f}, pozycja: ({det['center_x']}, {det['center_y']})")

        return detections

    def set_optimization_level(self, level="balanced"):
        """Placeholder dla kompatybilności"""
        self.log(f"⚙️ Ustawiono poziom optymalizacji: {level}")

    def get_capture_stats(self):
        """Placeholder dla kompatybilności z diagnostyką"""
        return {
            'total_attempts': self.image_validation_stats['total_images_received'],
            'successful_captures': self.image_validation_stats['valid_images'],
            'failed_captures': self.image_validation_stats['invalid_images'],
            'success_rate_percent': (self.image_validation_stats['valid_images'] / max(1, self.image_validation_stats['total_images_received'])) * 100,
            'last_error': self.image_validation_stats['last_error']
        }


class MultiThreadedYOLODetector(OptimizedYOLODetector):
    """
    Multi-threaded YOLO detector with dedicated inference thread and queue management
    Designed for async processing pipeline to achieve 30+ FPS performance
    """

    def __init__(self, logger=None, inference_queue_size=3, results_queue_size=8):
        super().__init__(logger)

        # Queue configuration
        self.inference_queue_size = inference_queue_size
        self.results_queue_size = results_queue_size

        # Threading components
        self.inference_thread = None
        self.inference_queue = None
        self.results_queue = None
        self.model_lock = None
        self.is_running = False

        # Performance tracking
        self.inference_times = []
        self.inference_count = 0
        self.frames_queued = 0
        self.frames_dropped = 0
        self.results_processed = 0

        # Initialize thread-safe components
        self._init_threading()

    def _init_threading(self):
        """Initialize threading components"""
        import threading
        import queue

        self.model_lock = threading.Lock()
        self.inference_queue = queue.Queue(maxsize=self.inference_queue_size)
        self.results_queue = queue.Queue(maxsize=self.results_queue_size)

        self.log(f"🔄 MultiThreadedYOLODetector initialized: inference_queue={self.inference_queue_size}, results_queue={self.results_queue_size}")

    def start_inference(self):
        """Start dedicated inference thread"""
        if self.inference_thread and self.inference_thread.is_alive():
            self.log("⚠️ Inference thread already running")
            return

        if not self.model_loaded:
            self.log("❌ Model not loaded, cannot start inference")
            return False

        self.is_running = True
        self.inference_count = 0
        self.frames_queued = 0
        self.frames_dropped = 0
        self.results_processed = 0

        self.inference_thread = threading.Thread(
            target=self._inference_worker,
            name="YOLOInferenceThread",
            daemon=True
        )
        self.inference_thread.start()
        self.log("🚀 YOLO inference thread started")
        return True

    def stop_inference(self):
        """Stop inference thread gracefully"""
        if not self.is_running:
            return

        self.is_running = False

        if self.inference_thread and self.inference_thread.is_alive():
            self.inference_thread.join(timeout=3.0)
            if self.inference_thread.is_alive():
                self.log("⚠️ Inference thread did not stop gracefully")
            else:
                self.log("✅ Inference thread stopped gracefully")

        # Clear queues
        self._clear_queues()

        self.log(f"📊 Inference stopped - Queued: {self.frames_queued}, Dropped: {self.frames_dropped}, Processed: {self.results_processed}")

    def _clear_queues(self):
        """Clear all queues"""
        inference_cleared = 0
        results_cleared = 0

        while not self.inference_queue.empty():
            try:
                self.inference_queue.get_nowait()
                inference_cleared += 1
            except:
                break

        while not self.results_queue.empty():
            try:
                self.results_queue.get_nowait()
                results_cleared += 1
            except:
                break

        self.log(f"🗑️ Cleared queues: inference={inference_cleared}, results={results_cleared}")

    def _inference_worker(self):
        """Dedicated inference thread"""
        import time

        self.log("🔄 Inference worker started")

        while self.is_running:
            try:
                # Get frame from queue (blocking with timeout)
                frame_data = self.inference_queue.get(timeout=0.016)  # 16ms = 60 FPS

                if frame_data is None:  # Poison pill
                    continue

                inference_start = time.perf_counter()

                # Perform inference with model lock
                with self.model_lock:
                    if not self.model_loaded or self.model is None:
                        self.log("❌ Model not available for inference")
                        continue

                    try:
                        # Validate and prepare frame
                        validated_frame = self.validate_and_prepare_image(
                            frame_data['frame'],
                            f"Inference-{frame_data.get('frame_id', 'unknown')}"
                        )

                        if validated_frame is None:
                            self.log(f"⚠️ Frame validation failed for frame {frame_data.get('frame_id', 'unknown')}")
                            continue

                        # Perform YOLO inference
                        results = self.model(
                            validated_frame,
                            conf=frame_data.get('confidence', 0.5),
                            verbose=False,
                            device='cuda' if torch.cuda.is_available() else 'cpu'
                        )

                        # Process results
                        detections = self._process_yolo_results(
                            results,
                            validated_frame,
                            frame_data.get('frame_id', 0)
                        )

                    except Exception as inference_error:
                        self.log(f"❌ Inference error: {str(inference_error)}")
                        detections = []

                # Calculate inference time
                inference_time = (time.perf_counter() - inference_start) * 1000

                # Update performance stats
                self._update_inference_stats(inference_time)

                # Queue results
                result_data = {
                    'detections': detections,
                    'frame_id': frame_data.get('frame_id', 0),
                    'timestamp': frame_data.get('timestamp', time.time()),
                    'inference_time_ms': inference_time,
                    'confidence': frame_data.get('confidence', 0.5),
                    'input_shape': validated_frame.shape if 'validated_frame' in locals() else None
                }

                try:
                    self.results_queue.put_nowait(result_data)
                    self.results_processed += 1
                except:
                    # Results queue full - drop oldest
                    try:
                        self.results_queue.get_nowait()
                        self.results_queue.put_nowait(result_data)
                    except:
                        self.log("⚠️ Results queue overflow, dropping result")

            except Exception as worker_error:
                self.log(f"❌ Worker error: {str(worker_error)}")
                time.sleep(0.01)

        self.log("🛑 Inference worker stopped")

    def _process_yolo_results(self, results, frame, frame_id):
        """Process YOLO results into detection format"""
        try:
            detections = []

            if results and hasattr(results, 'boxes') and results.boxes is not None:
                boxes = results.boxes

                for box in boxes:
                    # Extract coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())

                    # Get class name
                    class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"

                    # Calculate center point
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)

                    # Create detection object
                    detection = {
                        'name': class_name,
                        'confidence': float(confidence),
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'center_x': center_x,
                        'center_y': center_y,
                        'width': int(x2 - x1),
                        'height': int(y2 - y1),
                        'class_id': class_id,
                        'frame_id': frame_id
                    }

                    detections.append(detection)

            return detections

        except Exception as e:
            self.log(f"❌ Error processing YOLO results: {str(e)}")
            return []

    def _update_inference_stats(self, inference_time):
        """Update inference performance statistics"""
        self.inference_times.append(inference_time)

        # Keep only recent samples
        if len(self.inference_times) > 100:
            self.inference_times = self.inference_times[-100:]

        self.inference_count += 1

    def queue_frame(self, frame, confidence=0.5, frame_id=None, timestamp=None):
        """Queue frame for inference"""
        if not self.is_running:
            self.log("⚠️ Inference not running, cannot queue frame")
            return False

        if frame_id is None:
            frame_id = self.frames_queued

        if timestamp is None:
            timestamp = time.time()

        frame_data = {
            'frame': frame,
            'confidence': confidence,
            'frame_id': frame_id,
            'timestamp': timestamp
        }

        try:
            self.inference_queue.put_nowait(frame_data)
            self.frames_queued += 1
            return True
        except:
            self.frames_dropped += 1
            return False

    def get_latest_results(self, block=False, timeout=None):
        """Get latest inference results"""
        import queue

        try:
            if block:
                result_data = self.results_queue.get(timeout=timeout or 0.016)  # 16ms = 60 FPS
            else:
                result_data = self.results_queue.get_nowait()
            return result_data
        except queue.Empty:
            return None

    def get_queue_sizes(self):
        """Get current queue sizes"""
        return {
            'inference_queue': self.inference_queue.qsize(),
            'results_queue': self.results_queue.qsize(),
            'inference_queue_capacity': self.inference_queue_size,
            'results_queue_capacity': self.results_queue_size
        }

    def get_inference_stats(self):
        """Get detailed inference statistics"""
        base_stats = super().get_capture_stats()

        if self.inference_times:
            avg_time = sum(self.inference_times) / len(self.inference_times)
            max_time = max(self.inference_times)
            min_time = min(self.inference_times)
            estimated_fps = 1000.0 / avg_time if avg_time > 0 else 0
        else:
            avg_time = max_time = min_time = estimated_fps = 0

        thread_stats = {
            'is_running': self.is_running,
            'inference_count': self.inference_count,
            'frames_queued': self.frames_queued,
            'frames_dropped': self.frames_dropped,
            'results_processed': self.results_processed,
            'drop_rate_percent': (self.frames_dropped / max(1, self.frames_queued + self.frames_dropped)) * 100,
            'avg_inference_time_ms': avg_time,
            'max_inference_time_ms': max_time,
            'min_inference_time_ms': min_time,
            'estimated_fps': estimated_fps,
            'queue_sizes': self.get_queue_sizes()
        }

        # Merge with base stats
        base_stats.update(thread_stats)
        return base_stats

    def set_queue_sizes(self, inference_size=None, results_size=None):
        """Dynamically adjust queue sizes (requires restart)"""
        if inference_size and 1 <= inference_size <= 20:
            self.inference_queue_size = inference_size
            self.log(f"🔄 Inference queue size set to: {inference_size}")

        if results_size and 1 <= results_size <= 50:
            self.results_queue_size = results_size
            self.log(f"🔄 Results queue size set to: {results_size}")

    def get_model_info(self):
        """Get model information with threading status"""
        info = super().get_model_info()

        threading_info = {
            'threading_enabled': True,
            'is_running': self.is_running,
            'inference_thread_alive': self.inference_thread.is_alive() if self.inference_thread else False,
            'queue_sizes': self.get_queue_sizes(),
            'frames_queued': self.frames_queued,
            'frames_processed': self.results_processed
        }

        info.update(threading_info)
        return info

    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self.stop_inference()
        except:
            pass


# Aliasy dla kompatybilności
YOLODetector = OptimizedYOLODetector
HPBarDetector = OptimizedYOLODetector
FastHPDetector = OptimizedYOLODetector