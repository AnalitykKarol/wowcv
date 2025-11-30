"""
Główne okno GUI aplikacji - Z ULEPSZONĄ DIAGNOSTYKĄ
Dodano szczegółowe logi i testy przechwytywania obrazu
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from PIL import Image, ImageTk
import cv2
import numpy as np

from core.window_capture import WindowCapture
from core.yolo_detector import OptimizedYOLODetector
from core.combat_controller import ReactiveCombatController

class MainWindow:
    def __init__(self, root, logger):
        self.root = root
        self.logger = logger

        # Komponenty z lepszą obsługą błędów
        self.window_capture = WindowCapture(logger)
        try:
            self.yolo_detector = OptimizedYOLODetector(logger)
            self.log_message("✅ Użyto OptimizedYOLODetector")
        except Exception as e:
            from core.yolo_detector import YOLODetector as FallbackYOLO
            self.yolo_detector = FallbackYOLO(logger)
            self.log_message(f"⚠️ Fallback do zwykłego YOLODetector: {str(e)}")

        self.combat_controller = ReactiveCombatController(logger)

        # Stan aplikacji
        self.selected_window = None
        self.yolo_active = False
        self.combat_mode = False
        self.detection_thread = None
        self.preview_active = False

        # GUI komponenty
        self.preview_label = None
        self.log_text = None

        # NOWE: Diagnostyka
        self.last_frame_time = 0
        self.frame_count = 0
        self.detection_count = 0

        self.setup_window()
        self.setup_ui()
        self.refresh_windows()
        self.check_initial_yolo_status()

        # Timer dla diagnostyki
        self.diagnostic_timer = None
        self.start_diagnostic_timer()

    def start_diagnostic_timer(self):
        """Uruchamia timer dla diagnostyki"""
        if hasattr(self, 'diagnostic_text'):
            self.update_diagnostic_info()
        self.diagnostic_timer = self.root.after(1000, self.start_diagnostic_timer)  # Co sekundę

    def update_diagnostic_info(self):
        """Aktualizuje informacje diagnostyczne"""
        try:
            if not hasattr(self, 'diagnostic_text'):
                return

            diagnostic_text = "=== DIAGNOSTYKA SYSTEMU ===\n\n"

            # Window Capture Stats
            if self.window_capture:
                capture_stats = self.window_capture.get_capture_stats()
                diagnostic_text += "📷 WINDOW CAPTURE:\n"
                diagnostic_text += f"  Próby przechwytywania: {capture_stats['total_attempts']}\n"
                diagnostic_text += f"  Udane: {capture_stats['successful_captures']}\n"
                diagnostic_text += f"  Nieudane: {capture_stats['failed_captures']}\n"
                diagnostic_text += f"  Skuteczność: {capture_stats['success_rate_percent']:.1f}%\n"
                if capture_stats['last_error']:
                    diagnostic_text += f"  Ostatni błąd: {capture_stats['last_error']}\n"
                diagnostic_text += "\n"

            # YOLO Detector Stats
            if self.yolo_detector:
                try:
                    yolo_diag = self.yolo_detector.get_diagnostic_info()
                    diagnostic_text += "🤖 YOLO DETECTOR:\n"
                    diagnostic_text += f"  Model załadowany: {yolo_diag['model_loaded']}\n"
                    diagnostic_text += f"  Klasy: {', '.join(yolo_diag['model_classes'])}\n"
                    diagnostic_text += f"  Wątek inference: {yolo_diag['inference_thread_running']}\n"
                    diagnostic_text += f"  Kolejka inference: {yolo_diag['inference_queue_size']}\n"
                    diagnostic_text += f"  Kolejka wyników: {yolo_diag['results_queue_size']}\n"
                    diagnostic_text += f"  Cache wykryć: {yolo_diag['cached_detections_count']}\n"

                    # Image validation stats
                    val_stats = yolo_diag['image_validation_stats']
                    diagnostic_text += f"  Obrazy otrzymane: {val_stats['total_images_received']}\n"
                    diagnostic_text += f"  Obrazy prawidłowe: {val_stats['valid_images']}\n"
                    diagnostic_text += f"  Obrazy nieprawidłowe: {val_stats['invalid_images']}\n"
                    if val_stats['total_images_received'] > 0:
                        valid_percent = val_stats['valid_images'] / val_stats['total_images_received'] * 100
                        diagnostic_text += f"  Skuteczność walidacji: {valid_percent:.1f}%\n"
                    if val_stats['last_error']:
                        diagnostic_text += f"  Ostatni błąd walidacji: {val_stats['last_error']}\n"
                    diagnostic_text += "\n"

                    # Performance stats
                    perf_stats = yolo_diag.get('performance_stats', {})
                    if perf_stats:
                        diagnostic_text += "⚡ WYDAJNOŚĆ YOLO:\n"
                        diagnostic_text += f"  Średni czas inference: {perf_stats.get('avg_inference_time_ms', 0):.1f}ms\n"
                        diagnostic_text += f"  Szacowane FPS: {perf_stats.get('estimated_fps', 0):.1f}\n"
                        diagnostic_text += f"  Próbek: {perf_stats.get('samples_count', 0)}\n"
                        diagnostic_text += "\n"

                except Exception as e:
                    diagnostic_text += f"🤖 YOLO DETECTOR: Błąd diagnostyki - {str(e)}\n\n"

            # Combat Controller Stats
            if self.combat_controller and self.combat_mode:
                try:
                    combat_stats = self.combat_controller.get_stats()
                    diagnostic_text += "⚔️ COMBAT CONTROLLER:\n"
                    diagnostic_text += f"  Stan ruchu: {combat_stats.get('movement_state', 'unknown')}\n"
                    diagnostic_text += f"  Czeka na moba: {combat_stats.get('waiting_for_mob_approach', False)}\n"
                    diagnostic_text += f"  Dystans do celu: {combat_stats.get('target_distance', 0):.0f}px\n"
                    if combat_stats.get('current_enemy_position'):
                        pos = combat_stats['current_enemy_position']
                        diagnostic_text += f"  Pozycja wroga: ({pos[0]:.0f}, {pos[1]:.0f})\n"
                    diagnostic_text += "\n"
                except Exception as e:
                    diagnostic_text += f"⚔️ COMBAT CONTROLLER: Błąd diagnostyki - {str(e)}\n\n"

            # Aplikacja Stats
            diagnostic_text += "📱 APLIKACJA:\n"
            diagnostic_text += f"  Wybrane okno: {self.selected_window['title'] if self.selected_window else 'Brak'}\n"
            diagnostic_text += f"  YOLO aktywny: {self.yolo_active}\n"
            diagnostic_text += f"  Tryb walki: {self.combat_mode}\n"
            diagnostic_text += f"  Podgląd aktywny: {self.preview_active}\n"
            diagnostic_text += f"  Ramki przetworzonych: {self.frame_count}\n"
            diagnostic_text += f"  Wykryć wykonanych: {self.detection_count}\n"

            if self.last_frame_time > 0:
                time_since_last = time.time() - self.last_frame_time
                diagnostic_text += f"  Ostatnia ramka: {time_since_last:.1f}s temu\n"

            self.diagnostic_text.delete(1.0, tk.END)
            self.diagnostic_text.insert(1.0, diagnostic_text)

        except Exception as e:
            self.log_message(f"Błąd aktualizacji diagnostyki: {str(e)}", "ERROR")

    def check_initial_yolo_status(self):
        """Sprawdza status YOLO detektora przy starcie"""
        if self.yolo_detector.model_loaded:
            model_info = self.yolo_detector.get_model_info()
            if model_info.get('loaded'):
                classes_count = model_info.get('classes_count', 0)
                class_names = ', '.join(model_info.get('class_names', []))
                self.log_message(f"✅ YOLOv8 Model gotowy: {classes_count} klas ({class_names})")
                self.yolo_status_label.config(text="🟢 YOLOv8: Model załadowany", foreground='green')
            else:
                self.log_message("❌ Problem z modelem YOLOv8")
                self.yolo_status_label.config(text="🔴 YOLOv8: Błąd", foreground='red')
        else:
            self.log_message("⚠️ YOLOv8: Brak modelu")
            self.yolo_status_label.config(text="🟡 YOLOv8: Brak modelu", foreground='orange')

    def setup_window(self):
        """Konfiguracja głównego okna"""
        self.root.title("Enhanced YOLO Game Controller v6.0")
        self.root.geometry("1600x1000")  # Większe okno dla diagnostyki
        self.root.minsize(1200, 800)
        self.root.resizable(True, True)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def setup_ui(self):
        """Tworzenie interfejsu użytkownika"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

        self.setup_control_tab()
        self.setup_preview_tab()
        self.setup_settings_tab()
        self.setup_diagnostic_tab()  # NOWA ZAKŁADKA

    def setup_diagnostic_tab(self):
        """Zakładka diagnostyki systemu"""
        diagnostic_frame = ttk.Frame(self.notebook)
        self.notebook.add(diagnostic_frame, text="🔧 Diagnostyka")

        diagnostic_frame.grid_rowconfigure(1, weight=1)
        diagnostic_frame.grid_columnconfigure(0, weight=1)

        # Nagłówek
        header_frame = ttk.Frame(diagnostic_frame)
        header_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        title_label = ttk.Label(header_frame, text="🔧 Diagnostyka systemu",
                               font=('Arial', 14, 'bold'))
        title_label.pack(side='left')

        # Przyciski testowe
        test_frame = ttk.Frame(header_frame)
        test_frame.pack(side='right')

        ttk.Button(test_frame, text="🧪 Test przechwytywania",
                  command=self.test_window_capture).pack(side='left', padx=(0, 5))
        ttk.Button(test_frame, text="🤖 Test YOLO",
                  command=self.test_yolo_detection).pack(side='left', padx=(0, 5))
        ttk.Button(test_frame, text="📊 Pokaż statystyki",
                  command=self.show_detailed_stats).pack(side='left')

        # Główny obszar diagnostyki
        diagnostic_container = ttk.Frame(diagnostic_frame)
        diagnostic_container.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        diagnostic_container.grid_rowconfigure(0, weight=1)
        diagnostic_container.grid_columnconfigure(0, weight=1)

        self.diagnostic_text = tk.Text(diagnostic_container, font=('Consolas', 9), wrap='word')
        diagnostic_scrollbar = ttk.Scrollbar(diagnostic_container, orient='vertical',
                                           command=self.diagnostic_text.yview)
        self.diagnostic_text.configure(yscrollcommand=diagnostic_scrollbar.set)

        self.diagnostic_text.grid(row=0, column=0, sticky='nsew')
        diagnostic_scrollbar.grid(row=0, column=1, sticky='ns')

        # Początkowy tekst
        initial_text = """=== DIAGNOSTYKA SYSTEMU ===

Ten panel pokazuje szczegółowe informacje o stanie wszystkich komponentów systemu.

🔧 Komponenty monitorowane:
- Window Capture: Przechwytywanie okien
- YOLO Detector: Wykrywanie obiektów  
- Combat Controller: System walki
- Image Validation: Walidacja obrazów

📊 Automatyczna aktualizacja co sekundę

Użyj przycisków powyżej aby przeprowadzić testy:
🧪 Test przechwytywania - sprawdza czy okno jest prawidłowo przechwytywane
🤖 Test YOLO - sprawdza czy YOLO otrzymuje prawidłowe obrazy
📊 Statystyki - szczegółowe informacje o wydajności
"""

        self.diagnostic_text.insert(1.0, initial_text)

    def test_window_capture(self):
        """Test przechwytywania okna z diagnostyką"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        self.log_message("🧪 Rozpoczynam test przechwytywania okna...")

        try:
            # Test podstawowy
            success = self.window_capture.test_capture(self.selected_window['hwnd'])

            if success:
                self.log_message("✅ Test przechwytywania: SUKCES")

                # Test dodatkowy - sprawdź czy obraz nadaje się dla YOLO
                frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
                if frame is not None:
                    validated_frame = self.yolo_detector.validate_and_prepare_image(frame, "Test Capture")
                    if validated_frame is not None:
                        self.log_message("✅ Obraz nadaje się dla YOLO")
                        messagebox.showinfo("Test przechwytywania",
                                          "✅ SUKCES!\n\nOkno jest prawidłowo przechwytywane\ni obraz nadaje się dla YOLO.")
                    else:
                        self.log_message("❌ Obraz nie nadaje się dla YOLO")
                        messagebox.showwarning("Test przechwytywania",
                                             "⚠️ CZĘŚCIOWY SUKCES\n\nOkno jest przechwytywane,\nale obraz ma problemy z formatem.")
                else:
                    self.log_message("❌ Nie udało się ponownie przechwycić obrazu")
                    messagebox.showerror("Test przechwytywania",
                                        "❌ BŁĄD\n\nProblem z ponownym przechwyceniem.")
            else:
                stats = self.window_capture.get_capture_stats()
                error_msg = f"❌ BŁĄD przechwytywania\n\nStatystyki:\n"
                error_msg += f"Próby: {stats['total_attempts']}\n"
                error_msg += f"Sukces: {stats['successful_captures']}\n"
                error_msg += f"Błędy: {stats['failed_captures']}\n"
                if stats['last_error']:
                    error_msg += f"Ostatni błąd: {stats['last_error']}"

                self.log_message("❌ Test przechwytywania: BŁĄD")
                messagebox.showerror("Test przechwytywania", error_msg)

        except Exception as e:
            error_msg = f"❌ Wyjątek podczas testu: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("Test przechwytywania", error_msg)

    def test_yolo_detection(self):
        """Test wykrywania YOLO z diagnostyką"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        if not self.yolo_detector.model_loaded:
            messagebox.showerror("Błąd", "Model YOLO nie jest załadowany")
            return

        self.log_message("🤖 Rozpoczynam test wykrywania YOLO...")

        try:
            # Przechwytywanie obrazu
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
            if frame is None:
                messagebox.showerror("Test YOLO", "❌ Nie udało się przechwycić obrazu")
                return

            # Test YOLO
            detections = self.yolo_detector.test_detection(frame)

            # Pokaż wyniki
            result_msg = f"🤖 Test YOLO zakończony\n\n"
            result_msg += f"Wykrycia: {len(detections)}\n\n"

            for i, det in enumerate(detections):
                result_msg += f"{i+1}. {det['name']}: {det['confidence']:.2f}\n"
                result_msg += f"   Pozycja: ({det['center_x']}, {det['center_y']})\n"
                result_msg += f"   Rozmiar: {det['width']}x{det['height']}\n\n"

            # Dodaj statystyki walidacji obrazów
            val_stats = self.yolo_detector.image_validation_stats
            result_msg += f"Statystyki walidacji obrazów:\n"
            result_msg += f"Otrzymane: {val_stats['total_images_received']}\n"
            result_msg += f"Prawidłowe: {val_stats['valid_images']}\n"
            result_msg += f"Błędne: {val_stats['invalid_images']}\n"

            if val_stats['total_images_received'] > 0:
                success_rate = val_stats['valid_images'] / val_stats['total_images_received'] * 100
                result_msg += f"Skuteczność: {success_rate:.1f}%\n"

            self.log_message(f"✅ Test YOLO: {len(detections)} wykryć")
            messagebox.showinfo("Test YOLO", result_msg)

        except Exception as e:
            error_msg = f"❌ Błąd testu YOLO: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("Test YOLO", error_msg)

    def show_detailed_stats(self):
        """Pokazuje szczegółowe statystyki"""
        try:
            stats_text = "=== SZCZEGÓŁOWE STATYSTYKI ===\n\n"

            # Window Capture
            capture_stats = self.window_capture.get_capture_stats()
            stats_text += "📷 WINDOW CAPTURE:\n"
            for key, value in capture_stats.items():
                stats_text += f"  {key}: {value}\n"
            stats_text += "\n"

            # YOLO Detector
            if self.yolo_detector.model_loaded:
                model_info = self.yolo_detector.get_model_info()
                stats_text += "🤖 YOLO DETECTOR:\n"
                stats_text += f"  Model: {model_info.get('model_type', 'Unknown')}\n"
                stats_text += f"  Klasy: {model_info.get('classes_count', 0)}\n"

                perf_stats = model_info.get('performance', {})
                if perf_stats:
                    stats_text += f"  Średni czas inference: {perf_stats.get('avg_inference_time_ms', 0):.2f}ms\n"
                    stats_text += f"  FPS: {perf_stats.get('estimated_fps', 0):.1f}\n"
                    stats_text += f"  Próbek: {perf_stats.get('samples_count', 0)}\n"

                # Image validation
                diag_info = model_info.get('diagnostics', {})
                val_stats = diag_info.get('image_validation_stats', {})
                if val_stats:
                    stats_text += f"  Obrazy otrzymane: {val_stats.get('total_images_received', 0)}\n"
                    stats_text += f"  Obrazy prawidłowe: {val_stats.get('valid_images', 0)}\n"
                    stats_text += f"  Konwersje: {val_stats.get('conversion_successes', 0)}/{val_stats.get('conversion_attempts', 0)}\n"

                stats_text += "\n"

            # Combat Controller
            if self.combat_mode:
                combat_stats = self.combat_controller.get_stats()
                stats_text += "⚔️ COMBAT CONTROLLER:\n"
                for key, value in combat_stats.items():
                    if not key.endswith('_time') or value > 0:
                        stats_text += f"  {key}: {value}\n"
                stats_text += "\n"

            # System info
            stats_text += "📱 SYSTEM:\n"
            stats_text += f"  Ramki przetworzonych: {self.frame_count}\n"
            stats_text += f"  Wykryć wykonanych: {self.detection_count}\n"
            stats_text += f"  Aktywny czas: {time.time() - getattr(self, 'start_time', time.time()):.1f}s\n"

            messagebox.showinfo("Szczegółowe statystyki", stats_text)

        except Exception as e:
            self.log_message(f"Błąd wyświetlania statystyk: {str(e)}", "ERROR")

    def setup_control_tab(self):
        """Zakładka kontroli głównej"""
        control_frame = ttk.Frame(self.notebook)
        self.notebook.add(control_frame, text="🎮 Kontrola")

        # === SEKCJA WYBORU OKNA ===
        window_frame = ttk.LabelFrame(control_frame, text="🪟 Wybór okna do przechwytywania", padding=15)
        window_frame.pack(fill='x', pady=(0, 10))

        list_container = ttk.Frame(window_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.window_listbox = tk.Listbox(list_container, height=8, font=('Consolas', 9))
        list_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.window_listbox.yview)
        self.window_listbox.configure(yscrollcommand=list_scrollbar.set)

        self.window_listbox.pack(side='left', fill='both', expand=True)
        list_scrollbar.pack(side='right', fill='y')

        window_btn_frame = ttk.Frame(window_frame)
        window_btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(window_btn_frame, text="🔄 Odśwież", command=self.refresh_windows).pack(side='left', padx=(0, 5))
        ttk.Button(window_btn_frame, text="✅ Wybierz okno", command=self.select_window).pack(side='left', padx=(0, 5))
        ttk.Button(window_btn_frame, text="👁️ Podgląd", command=self.toggle_preview).pack(side='left', padx=(0, 5))
        ttk.Button(window_btn_frame, text="🧪 Test okna", command=self.test_window_capture).pack(side='left')

        self.selected_window_label = ttk.Label(window_frame, text="❌ Brak wybranego okna",
                                             foreground='red', font=('Arial', 10, 'bold'))
        self.selected_window_label.pack(anchor='w', pady=(10, 0))

        # === SEKCJA YOLOv8 ===
        yolo_frame = ttk.LabelFrame(control_frame, text="🤖 YOLOv8 Detection", padding=15)
        yolo_frame.pack(fill='x', pady=(0, 10))

        yolo_status_frame = ttk.Frame(yolo_frame)
        yolo_status_frame.pack(fill='x')

        self.yolo_status_label = ttk.Label(yolo_status_frame, text="🔴 YOLOv8: Wyłączone",
                                        foreground='red', font=('Arial', 10, 'bold'))
        self.yolo_status_label.pack(side='left')

        yolo_btn_frame = ttk.Frame(yolo_frame)
        yolo_btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(yolo_btn_frame, text="📊 Info o modelu",
                  command=self.show_model_info).pack(side='left', padx=(0, 5))
        ttk.Button(yolo_btn_frame, text="🧪 Test YOLO",
                  command=self.test_yolo_detection).pack(side='left', padx=(0, 5))

        self.yolo_toggle_btn = ttk.Button(yolo_btn_frame, text="▶️ Włącz YOLOv8", command=self.toggle_yolo)
        self.yolo_toggle_btn.pack(side='left')

        self.yolo_progress = ttk.Progressbar(yolo_frame, mode='indeterminate')
        self.yolo_progress.pack(fill='x', pady=(10, 0))

        model_info = ttk.Label(yolo_frame, text="🎯 Enhanced YOLO with Image Validation & Diagnostics",
                              font=('Arial', 9), foreground='blue')
        model_info.pack(anchor='w', pady=(5, 0))

        # === SEKCJA TRYBU WALKI ===
        combat_frame = ttk.LabelFrame(control_frame, text="⚔️ Tryb walki", padding=15)
        combat_frame.pack(fill='x', pady=(0, 10))

        combat_status_frame = ttk.Frame(combat_frame)
        combat_status_frame.pack(fill='x')

        self.combat_status_label = ttk.Label(combat_status_frame, text="🔴 Walka: Wyłączona",
                                           foreground='red', font=('Arial', 10, 'bold'))
        self.combat_status_label.pack(side='left')

        self.combat_toggle_btn = ttk.Button(combat_frame, text="⚔️ Włącz walkę",
                                          command=self.toggle_combat_mode)
        self.combat_toggle_btn.pack(anchor='w', pady=(10, 0))

        combat_info = ttk.Label(combat_frame, text="ℹ️ Walka wymaga włączonego YOLOv8 Detection",
                              font=('Arial', 9), foreground='gray')
        combat_info.pack(anchor='w', pady=(2, 0))

        # === SEKCJA LOGÓW ===
        log_frame = ttk.LabelFrame(control_frame, text="📋 Logi systemowe", padding=15)
        log_frame.pack(fill='both', expand=True)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill='both', expand=True)

        self.log_text = tk.Text(log_container, height=10, wrap='word', font=('Consolas', 9))
        log_text_scrollbar = ttk.Scrollbar(log_container, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_text_scrollbar.set)

        self.log_text.pack(side='left', fill='both', expand=True)
        log_text_scrollbar.pack(side='right', fill='y')

        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(log_btn_frame, text="🧹 Wyczyść logi", command=self.clear_logs).pack(side='left')

    def setup_preview_tab(self):
        """Zakładka podglądu"""
        preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(preview_frame, text="👁️ Podgląd")

        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        preview_controls = ttk.Frame(preview_frame)
        preview_controls.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        ttk.Button(preview_controls, text="▶️ Start", command=self.start_preview).pack(side='left', padx=(0, 5))
        ttk.Button(preview_controls, text="⏹️ Stop", command=self.stop_preview).pack(side='left', padx=(0, 5))
        ttk.Button(preview_controls, text="📸 Screenshot", command=self.take_screenshot).pack(side='left', padx=(0, 5))

        detection_info = ttk.Label(preview_controls,
                                 text="🎯 Podgląd z wykrywaniami YOLO",
                                 font=('Arial', 9), foreground='blue')
        detection_info.pack(side='left', padx=(10, 0))

        self.preview_status_label = ttk.Label(preview_controls, text="⏹️ Podgląd zatrzymany")
        self.preview_status_label.pack(side='right')

        preview_container = ttk.Frame(preview_frame)
        preview_container.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        preview_container.grid_rowconfigure(0, weight=1)
        preview_container.grid_columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(preview_container, bg='black')

        h_scrollbar = ttk.Scrollbar(preview_container, orient='horizontal', command=self.preview_canvas.xview)
        v_scrollbar = ttk.Scrollbar(preview_container, orient='vertical', command=self.preview_canvas.yview)

        self.preview_canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

        self.preview_canvas.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        self.no_preview_label = ttk.Label(self.preview_canvas, text="🖼️ Brak podglądu\nWybierz okno i naciśnij Start",
                                        font=('Arial', 12), anchor='center')
        self.preview_canvas.create_window(400, 300, window=self.no_preview_label, tags="no_preview")

        self.preview_canvas.bind('<Configure>', self.on_canvas_configure)

        self.current_image = None
        self.canvas_image_id = None
        self.latest_detections = []

    def setup_settings_tab(self):
        """Zakładka ustawień"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="⚙️ Ustawienia")

        # Ustawienia wykrywania
        detection_frame = ttk.LabelFrame(settings_frame, text="🤖 Ustawienia YOLOv8", padding=15)
        detection_frame.pack(fill='x', pady=(10, 10), padx=10)

        ttk.Label(detection_frame, text="Próg pewności (confidence threshold):").pack(anchor='w')
        self.confidence_scale = ttk.Scale(detection_frame, from_=0.1, to=1.0, orient='horizontal')
        self.confidence_scale.set(0.25)
        self.confidence_scale.pack(fill='x', pady=(5, 10))

        confidence_info = ttk.Label(detection_frame, text="0.25 = zbalansowany, 0.1 = więcej wykryć, 0.5 = wysoka precyzja",
                                   font=('Arial', 9), foreground='gray')
        confidence_info.pack(anchor='w')

        ttk.Label(detection_frame, text="Częstotliwość wykrywania (FPS):").pack(anchor='w', pady=(10, 0))
        self.fps_scale = ttk.Scale(detection_frame, from_=1, to=30, orient='horizontal')
        self.fps_scale.set(30)
        self.fps_scale.pack(fill='x', pady=(5, 10))

        # Optymalizacje YOLO
        optimization_frame = ttk.LabelFrame(settings_frame, text="⚡ Optymalizacja YOLO", padding=15)
        optimization_frame.pack(fill='x', pady=(10, 10), padx=10)

        ttk.Label(optimization_frame, text="Tryb optymalizacji:").pack(anchor='w')

        self.optimization_var = tk.StringVar(value="balanced")
        opt_frame = ttk.Frame(optimization_frame)
        opt_frame.pack(fill='x', pady=(5, 10))

        ttk.Radiobutton(opt_frame, text="🚀 Speed", variable=self.optimization_var,
                       value="speed", command=self.apply_optimization).pack(side='left', padx=(0, 10))
        ttk.Radiobutton(opt_frame, text="⚖️ Balanced", variable=self.optimization_var,
                       value="balanced", command=self.apply_optimization).pack(side='left', padx=(0, 10))
        ttk.Radiobutton(opt_frame, text="💎 Quality", variable=self.optimization_var,
                       value="quality", command=self.apply_optimization).pack(side='left')

    def apply_optimization(self):
        """Aplikuje wybrany tryb optymalizacji"""
        try:
            level = self.optimization_var.get()
            self.yolo_detector.set_optimization_level(level)
            self.log_message(f"⚡ Zastosowano optymalizację: {level}")
        except Exception as e:
            self.log_message(f"Błąd aplikowania optymalizacji: {str(e)}", "ERROR")

    def show_model_info(self):
        """Pokazuje informacje o modelu"""
        model_info = self.yolo_detector.get_model_info()

        if model_info.get('loaded'):
            info_text = f"""Model YOLOv8 Enhanced:

📊 MODEL:
Typ: {model_info.get('model_type', 'YOLOv8')}
Status: ✅ Załadowany
Liczba klas: {model_info.get('classes_count', 0)}
Klasy: {', '.join(model_info.get('class_names', []))}

⚡ OPTYMALIZACJE:
- Threading: {'✅' if model_info.get('optimizations', {}).get('threading') else '❌'}
- Frame Skipping: {'✅' if model_info.get('optimizations', {}).get('frame_skipping') else '❌'}
- Caching: {'✅' if model_info.get('optimizations', {}).get('caching') else '❌'}

🔧 DIAGNOSTYKA:
- Image Validation: ✅ Aktywna
- Error Handling: ✅ Enhanced
- Performance Monitoring: ✅ Real-time"""

            diag_info = model_info.get('diagnostics', {})
            if diag_info:
                val_stats = diag_info.get('image_validation_stats', {})
                if val_stats.get('total_images_received', 0) > 0:
                    success_rate = val_stats.get('valid_images', 0) / val_stats['total_images_received'] * 100
                    info_text += f"""

📈 STATYSTYKI WALIDACJI OBRAZÓW:
- Otrzymane: {val_stats.get('total_images_received', 0)}
- Prawidłowe: {val_stats.get('valid_images', 0)}
- Skuteczność: {success_rate:.1f}%"""

            perf_stats = model_info.get('performance', {})
            if perf_stats:
                info_text += f"""

📈 WYDAJNOŚĆ:
- FPS: {perf_stats.get('estimated_fps', 0):.1f}
- Avg time: {perf_stats.get('avg_inference_time_ms', 0):.1f}ms
- Próbek: {perf_stats.get('samples_count', 0)}"""
        else:
            info_text = f"""Model YOLOv8 - Problem:

Status: ❌ Nie załadowany
Błąd: {model_info.get('error', 'Nieznany błąd')}"""

        messagebox.showinfo("📊 Model YOLOv8 Enhanced", info_text)

    def log_message(self, message, level="INFO"):
        """Dodaje wiadomość do logów"""
        if hasattr(self, 'log_text') and self.log_text is not None:
            timestamp = time.strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {level}: {message}\n"

            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)

            lines = self.log_text.get(1.0, tk.END).split('\n')
            if len(lines) > 1000:
                self.log_text.delete(1.0, f"{len(lines) - 1000}.0")
        else:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")

        if self.logger:
            self.logger.info(message)

    def clear_logs(self):
        """Czyści logi"""
        if self.log_text:
            self.log_text.delete(1.0, tk.END)

    def refresh_windows(self):
        """Odświeża listę okien"""
        self.log_message("Odświeżanie listy okien...")

        try:
            windows = self.window_capture.get_window_list()

            self.window_listbox.delete(0, tk.END)
            self.windows_data = {}

            for window in windows:
                display_text = f"{window['title']} | {window['width']}x{window['height']} | ID:{window['hwnd']}"
                self.window_listbox.insert(tk.END, display_text)
                self.windows_data[display_text] = window

            self.log_message(f"Znaleziono {len(windows)} okien")

        except Exception as e:
            self.log_message(f"Błąd odświeżania okien: {str(e)}", "ERROR")

    def select_window(self):
        """Wybiera okno do przechwytywania"""
        selection = self.window_listbox.curselection()
        if not selection:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno z listy")
            return

        selected_text = self.window_listbox.get(selection[0])
        window_data = self.windows_data[selected_text]

        if not self.window_capture.is_window_valid(window_data['hwnd']):
            messagebox.showerror("Błąd", "Wybrane okno już nie istnieje")
            self.refresh_windows()
            return

        self.selected_window = window_data
        self.selected_window_label.config(
            text=f"✅ Wybrane: {window_data['title']}",
            foreground='green'
        )

        self.log_message(f"Wybrano okno: {window_data['title']} (ID: {window_data['hwnd']})")

    def toggle_yolo(self):
        """Włącza/wyłącza YOLOv8 Detection"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        if not self.yolo_detector.model_loaded:
            messagebox.showerror("Błąd", "Model YOLOv8 nie jest załadowany!")
            return

        if not self.yolo_active:
            self.start_yolo_detection()
        else:
            self.stop_yolo_detection()

    def start_yolo_detection(self):
        """Uruchamia wykrywanie YOLOv8"""
        self.yolo_active = True
        # Skonfiguruj rozmiary ekranu w combat controller
        if self.selected_window:
            self.combat_controller.configure_screen_size(
                self.selected_window['width'],
                self.selected_window['height']
            )
        self.yolo_status_label.config(text="🟢 YOLOv8: Aktywny", foreground='green')
        self.yolo_toggle_btn.config(text="⏹️ Wyłącz YOLOv8")
        self.yolo_progress.start()

        self.detection_thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.detection_thread.start()

        self.log_message("🤖 YOLOv8 Detection uruchomiony")

    def stop_yolo_detection(self):
        """Zatrzymuje wykrywanie YOLOv8"""
        self.yolo_active = False
        self.yolo_status_label.config(text="🟢 YOLOv8: Model załadowany", foreground='green')
        self.yolo_toggle_btn.config(text="▶️ Włącz YOLOv8")
        self.yolo_progress.stop()

        self.log_message("⏹️ YOLOv8 Detection zatrzymany")

    def toggle_combat_mode(self):
        """Przełącza tryb walki"""
        if not self.yolo_active and not self.combat_mode:
            messagebox.showwarning("Błąd", "Najpierw włącz YOLOv8 Detection!")
            return

        self.combat_mode = not self.combat_mode

        if self.combat_mode:
            if not self.yolo_active:
                self.toggle_yolo()

            self.combat_status_label.config(text="🟢 Walka: Włączona", foreground='green')
            self.combat_toggle_btn.config(text="⏹️ Wyłącz walkę")
            self.log_message("⚔️ Tryb walki włączony")
        else:
            self.combat_status_label.config(text="🔴 Walka: Wyłączona", foreground='red')
            self.combat_toggle_btn.config(text="⚔️ Włącz walkę")

            if self.selected_window:
                self.combat_controller.emergency_stop(self.selected_window['hwnd'])

            self.log_message("⏹️ Tryb walki wyłączony")

    def draw_detections_on_image(self, image, detections):
        """
        POPRAWIONA: Rysuje wykrycia YOLO na obrazie z lepszą obsługą błędów
        """
        if not detections or len(detections) == 0:
            self.log_message("🖼️ Brak wykryć do narysowania", "DEBUG")
            return image

        self.log_message(f"🖼️ Rysuję {len(detections)} wykryć na obrazie", "DEBUG")

        try:
            # POPRAWKA 1: Nie używaj yolo_detector.visualize_detections - zrób to lokalnie
            result_image = image.copy()

            # Sprawdź czy obraz jest prawidłowy
            if result_image is None or result_image.size == 0:
                self.log_message("❌ Błąd: obraz do rysowania jest pusty", "ERROR")
                return image

            self.log_message(f"🖼️ Obraz do rysowania: {result_image.shape}, typ: {result_image.dtype}", "DEBUG")

            # Kolory dla różnych typów wykryć
            colors = {
                'health_bar': (0, 255, 0),  # Zielony
                'healthbar': (0, 255, 0),  # Zielony
                'health': (0, 255, 0),  # Zielony
                'bar': (0, 255, 0),  # Zielony
                'mob': (255, 255, 0),  # Żółty
                'enemy': (255, 0, 0),  # Czerwony
                'monster': (255, 0, 0),  # Czerwony
                'target': (255, 0, 255),  # Magenta
                'unknown': (255, 255, 255)  # Biały
            }

            successful_draws = 0

            for i, detection in enumerate(detections):
                try:
                    # Pobierz współrzędne
                    x1 = detection.get('x1', 0)
                    y1 = detection.get('y1', 0)
                    x2 = detection.get('x2', 0)
                    y2 = detection.get('y2', 0)
                    name = detection.get('name', 'unknown')
                    confidence = detection.get('confidence', 0.0)

                    self.log_message(f"🖼️ Wykrycie #{i + 1}: {name} ({confidence:.2f}) - Box: [{x1}, {y1}, {x2}, {y2}]",
                                     "DEBUG")

                    # Walidacja współrzędnych
                    if x2 <= x1 or y2 <= y1:
                        self.log_message(
                            f"⚠️ Pomijam wykrycie #{i + 1} - nieprawidłowe współrzędne: ({x1}, {y1}, {x2}, {y2})",
                            "WARNING")
                        continue

                    if x1 < 0 or y1 < 0 or x2 >= result_image.shape[1] or y2 >= result_image.shape[0]:
                        self.log_message(f"⚠️ Wykrycie #{i + 1} poza obrazem - przycinam", "WARNING")
                        # Przytnij do granic obrazu
                        x1 = max(0, x1)
                        y1 = max(0, y1)
                        x2 = min(result_image.shape[1] - 1, x2)
                        y2 = min(result_image.shape[0] - 1, y2)

                    # Wybierz kolor
                    color = colors.get(name.lower(), colors['unknown'])

                    # Narysuj prostokąt
                    cv2.rectangle(result_image, (int(x1), int(y1)), (int(x2), int(y2)), color, 3)

                    # Przygotuj tekst
                    text = f"{name}: {confidence:.2f}"

                    # Sprawdź gdzie umieścić tekst (nad lub pod prostokątem)
                    text_y = int(y1) - 10 if y1 > 30 else int(y2) + 25

                    # Narysuj tło dla tekstu
                    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    cv2.rectangle(result_image,
                                  (int(x1), text_y - text_height - 5),
                                  (int(x1) + text_width + 5, text_y + 5),
                                  (0, 0, 0), -1)  # Czarne tło

                    # Narysuj tekst
                    cv2.putText(result_image, text, (int(x1), text_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                    successful_draws += 1
                    self.log_message(f"✅ Narysowano wykrycie #{i + 1}: {name}", "DEBUG")

                except Exception as draw_error:
                    self.log_message(f"❌ Błąd rysowania wykrycia #{i + 1}: {str(draw_error)}", "ERROR")
                    continue

            self.log_message(f"🖼️ Narysowano {successful_draws}/{len(detections)} wykryć", "INFO")

            if successful_draws == 0:
                self.log_message("⚠️ Nie udało się narysować żadnego wykrycia!", "WARNING")
                return image  # Zwróć oryginalny obraz

            return result_image

        except Exception as e:
            self.log_message(f"❌ Krytyczny błąd rysowania wykryć: {str(e)}", "ERROR")
            import traceback
            self.log_message(f"❌ Stack trace: {traceback.format_exc()}", "ERROR")
            return image  # Zwróć oryginalny obraz w przypadku błędu

    def toggle_preview(self):
        """Przełącza podgląd"""
        if self.preview_active:
            self.stop_preview()
        else:
            self.start_preview()

    def start_preview(self):
        """Uruchamia podgląd"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        self.preview_active = True
        self.preview_status_label.config(text="▶️ Podgląd aktywny")
        self.notebook.select(1)

        preview_thread = threading.Thread(target=self.preview_loop, daemon=True)
        preview_thread.start()

        self.log_message("👁️ Podgląd uruchomiony")

    def stop_preview(self):
        """Zatrzymuje podgląd"""
        self.preview_active = False
        self.preview_status_label.config(text="⏹️ Podgląd zatrzymany")
        self.log_message("⏹️ Podgląd zatrzymany")

    def preview_loop(self):
        """Pętla podglądu z lepszą obsługą błędów"""
        while self.preview_active:
            try:
                if not self.selected_window:
                    break

                frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

                if frame is not None:
                    self.current_image = frame
                    self.frame_count += 1
                    self.last_frame_time = time.time()
                    self.root.after(0, self.scale_and_display_image, frame)
                else:
                    self.log_message("⚠️ Podgląd: Nie udało się przechwycić ramki", "WARNING")

                time.sleep(1/30)

            except Exception as e:
                self.log_message(f"Błąd podglądu: {str(e)}", "ERROR")
                time.sleep(1)

    def on_canvas_configure(self, event):
        """Obsługuje zmianę rozmiaru canvas"""
        if self.current_image is not None:
            self.scale_and_display_image(self.current_image)

    def scale_and_display_image(self, img_array):
        """
        POPRAWIONA: Wyświetla obraz z wykryciami YOLO
        """
        try:
            self.preview_canvas.delete("preview_image")
            self.preview_canvas.delete("no_preview")

            if img_array is None or img_array.size == 0:
                self.log_message("⚠️ Preview: Pusty obraz", "WARNING")
                return

            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            if canvas_width <= 1 or canvas_height <= 1:
                return

            display_image = img_array.copy()

            self.log_message(f"🖼️ Oryginalny obraz: {display_image.shape}, typ: {display_image.dtype}", "DEBUG")

            # POPRAWKA: Lepsze sprawdzenie wykryć i rysowanie
            detections_to_draw = None
            if hasattr(self, 'yolo_active') and self.yolo_active:
                if hasattr(self, 'latest_detections') and self.latest_detections:
                    detections_to_draw = self.latest_detections
                    self.log_message(f"🖼️ Mam {len(detections_to_draw)} wykryć do narysowania", "DEBUG")
                else:
                    self.log_message("🖼️ Brak wykryć do narysowania (latest_detections puste)", "DEBUG")
            else:
                self.log_message("🖼️ YOLO nieaktywny - nie rysuję wykryć", "DEBUG")

            # Rysuj wykrycia jeśli są
            if detections_to_draw and len(detections_to_draw) > 0:
                try:
                    self.log_message(f"🖼️ Rozpoczynam rysowanie {len(detections_to_draw)} wykryć", "DEBUG")
                    display_image = self.draw_detections_on_image(display_image, detections_to_draw)
                    self.log_message(f"🖼️ Zakończono rysowanie wykryć", "DEBUG")
                except Exception as draw_error:
                    self.log_message(f"❌ Błąd rysowania wykryć: {str(draw_error)}", "ERROR")
                    import traceback
                    self.log_message(f"❌ Stack trace: {traceback.format_exc()}", "ERROR")

            # Przeskaluj obraz do canvas
            img_height, img_width = display_image.shape[:2]
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            scale = min(scale_x, scale_y, 1.0)

            new_width = max(1, int(img_width * scale))
            new_height = max(1, int(img_height * scale))

            self.log_message(
                f"🖼️ Przeskalowuję z {img_width}x{img_height} do {new_width}x{new_height} (scale: {scale:.3f})",
                "DEBUG")

            # Upewnij się że obraz jest uint8
            if display_image.dtype != np.uint8:
                if display_image.max() <= 1.0:
                    display_image = (display_image * 255).astype(np.uint8)
                else:
                    display_image = display_image.astype(np.uint8)

            # Konwertuj do PIL i wyświetl
            try:
                img_pil = Image.fromarray(display_image, 'RGB')
                img_resized = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img_resized)

                x = canvas_width // 2
                y = canvas_height // 2

                self.canvas_image_id = self.preview_canvas.create_image(
                    x, y, anchor='center', image=img_tk, tags="preview_image"
                )

                # WAŻNE: Zachowaj referencję do obrazu
                self.preview_canvas.image = img_tk
                self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

                self.log_message(f"✅ Obraz wyświetlony w preview", "DEBUG")

            except Exception as pil_error:
                self.log_message(f"❌ Błąd konwersji PIL: {str(pil_error)}", "ERROR")

        except Exception as e:
            self.log_message(f"❌ Błąd wyświetlania obrazu: {str(e)}", "ERROR")
            import traceback
            self.log_message(f"❌ Stack trace: {traceback.format_exc()}", "ERROR")

    def take_screenshot(self):
        """Zapisuje screenshot"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
            if frame is not None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_enhanced_{timestamp}.png"

                # Waliduj obraz przed zapisem
                validated_frame = self.yolo_detector.validate_and_prepare_image(frame, "Screenshot")
                if validated_frame is not None:
                    img = Image.fromarray(validated_frame)
                    img.save(filename)
                    self.log_message(f"📸 Screenshot zapisany: {filename}")
                    messagebox.showinfo("Sukces", f"Screenshot zapisany jako {filename}")
                else:
                    self.log_message("❌ Błąd walidacji obrazu do screenshot", "ERROR")
                    messagebox.showerror("Błąd", "Nie można zwalidować obrazu do zapisu")
            else:
                raise Exception("Nie udało się przechwycić obrazu")

        except Exception as e:
            self.log_message(f"Błąd zapisywania screenshot: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można zapisać screenshot:\n{str(e)}")

    def detection_loop(self):
        """Pętla wykrywania YOLO z lepszą obsługą błędów - POPRAWIONA Z DEBUG"""
        detection_count = 0
        fps = int(self.fps_scale.get())
        confidence_threshold = float(self.confidence_scale.get())

        self.log_message(f"🤖 Rozpoczęto Enhanced YOLO Detection (conf: {confidence_threshold:.2f}, FPS: {fps})")

        while self.yolo_active:
            try:
                if not self.selected_window:
                    break

                # Przechwytywanie obrazu
                frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

                if frame is not None and frame.size > 0:
                    try:
                        self.frame_count += 1
                        self.last_frame_time = time.time()

                        # Uruchom wykrywanie YOLO
                        detections = self.yolo_detector.detect(frame, confidence_threshold)

                        # ============= DODAJ SZCZEGÓŁOWY DEBUG =============


                        # ============= SPRAWDŹ WARUNKI =============
                        condition1 = detections is not None
                        condition2 = len(detections) > 0 if detections is not None else False


                        # ============= POPRAWIONA LOGIKA =============
                        # Zabezpieczenie: jeśli detections to None, zamień na pustą listę
                        if detections is None:
                            detections = []


                        # Teraz sprawdź długość
                        if len(detections) > 0:
                            detection_count += 1
                            self.detection_count += len(detections)

                            if detection_count % 30 == 0:
                                self.log_message(f"🤖 Enhanced YOLO: {len(detections)} wykryć (#{detection_count})")

                            # ========= PRZEKAŻ WYKRYCIA DO COMBAT CONTROLLER =========
                            for i, det in enumerate(detections):
                                name = det.get('name', 'unknown')
                                conf = det.get('confidence', 0)
                                pos = (det.get('center_x', 0), det.get('center_y', 0))
                                self.log_message(f"   #{i + 1}: {name} (conf: {conf:.3f}) at {pos}", "DEBUG")

                            # Tryb walki - PRZEKAŻ WYKRYCIA
                            if self.combat_mode:
                                try:
                                    self.combat_controller.update(self.selected_window['hwnd'], detections)

                                    if detection_count % 100 == 0:
                                        status = self.combat_controller.get_status()
                                        self.log_message(f"⚔️ Combat: {status}")

                                except Exception as combat_error:
                                    self.log_message(f"Błąd trybu walki: {str(combat_error)}", "ERROR")

                            # Zapisz wykrycia dla podglądu
                            self.latest_detections = detections.copy() if detections else []
                            self.log_message(f"🖼️ Zapisałem {len(self.latest_detections)} wykryć dla podglądu", "DEBUG")

                        else:
                            # BRAK WYKRYĆ
                            self.log_message(f"🔍 DETECTION DEBUG: BRAK WYKRYĆ - len(detections) = {len(detections)}",
                                             "DEBUG")
                            self.latest_detections = []

                            # Combat mode bez wykryć - PRZEKAŻ PUSTĄ LISTĘ
                            if self.combat_mode:
                                try:
                                    self.combat_controller.update(self.selected_window['hwnd'], [])
                                except Exception as combat_error:
                                    self.log_message(f"Błąd eksploracji: {str(combat_error)}", "ERROR")

                    except Exception as detection_error:
                        self.log_message(f"Błąd Enhanced YOLO: {str(detection_error)}", "ERROR")
                        import traceback
                        self.log_message(f"Stack trace: {traceback.format_exc()}", "ERROR")
                        self.latest_detections = []

                else:
                    self.log_message("⚠️ Detection: Nie udało się przechwycić ramki", "WARNING")

                    # NAWET BEZ RAMKI WYŚLIJ PUSTĄ LISTĘ
                    if self.combat_mode:
                        try:
                            self.combat_controller.update(self.selected_window['hwnd'], [])
                        except Exception as combat_error:
                            self.log_message(f"Błąd combat controller (brak ramki): {str(combat_error)}", "ERROR")

                time.sleep(max(0.02, 1 / fps))

            except Exception as e:
                self.log_message(f"Błąd głównej pętli Enhanced YOLO: {str(e)}", "ERROR")
                import traceback
                self.log_message(f"Stack trace: {traceback.format_exc()}", "ERROR")
                time.sleep(1)

        self.log_message("🏁 Pętla Enhanced YOLO zakończona")
    def __del__(self):
        """Cleanup przy zamykaniu"""
        try:
            if hasattr(self, 'diagnostic_timer') and self.diagnostic_timer:
                self.root.after_cancel(self.diagnostic_timer)
        except:
            pass