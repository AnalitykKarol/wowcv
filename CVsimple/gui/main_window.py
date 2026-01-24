"""
Główne okno GUI aplikacji - Z HP/MANA ANALYSIS
Dodano integrację z PlayerBarsAnalyzer i osobną pętlę analizy pasków
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from PIL import Image, ImageTk
import cv2
import numpy as np
import psutil

from core.window_capture import WindowCapture
from core.yolo_detector import OptimizedYOLODetector
from core.combat_controller import ReactiveCombatController
from core.hp_bar_analyzer import PlayerBarsAnalyzer  # NOWY IMPORT
from utils.preset_manager import PresetManager  # NOWY IMPORT
from gui.preset_dialog import PresetDialog  # NOWY IMPORT

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

        # NOWY: Preset Manager
        self.preset_manager = PresetManager(logger=logger)

        # NOWY: Player Bars Analyzer
        self.bars_analyzer = PlayerBarsAnalyzer(logger)
        self.bars_analysis_active = False
        self.bars_thread = None

        # Stan aplikacji
        self.selected_window = None
        self.yolo_active = False
        self.combat_mode = False
        self.detection_thread = None
        self.preview_active = False

        # GUI komponenty
        self.preview_label = None
        self.log_text = None

        # NOWE: HP/Mana GUI komponenty
        self.hp_status_label = None
        self.mana_status_label = None
        self.hp_toggle_btn = None
        self.mana_toggle_btn = None
        self.hp_value_label = None
        self.mana_value_label = None
        self.bars_last_update_label = None

        # Key 9 exploration buff toggle
        self.key9_toggle_btn = None
        self.key9_status_label = None

        # NOWE: Pozycje pasków (domyślne wartości)
        self.hp_x_var = tk.StringVar(value="120")
        self.hp_y_var = tk.StringVar(value="62")
        self.hp_w_var = tk.StringVar(value="135")
        self.hp_h_var = tk.StringVar(value="5")

        self.mana_x_var = tk.StringVar(value="120")
        self.mana_y_var = tk.StringVar(value="76")
        self.mana_w_var = tk.StringVar(value="135")
        self.mana_h_var = tk.StringVar(value="5")

        # NOWE: Aktualne wartości pasków
        self.current_hp = 0.0
        self.current_mana = 0.0
        self.bars_last_update = 0

        # NOWE: Interaktywny edytor współrzędnych
        self.edit_mode = False
        self.editing_region = None  # 'hp', 'mana', None
        self.drag_start = None
        self.original_coords = {}
        self.region_rectangles = {}  # IDs dla edytowalnych regionów

        # DIAGNOSTYKA
        self.last_frame_time = 0
        self.frame_count = 0
        self.detection_count = 0

        self.setup_window()
        self.setup_ui()
        self.refresh_windows()
        self.check_initial_yolo_status()
        self.setup_bars_callbacks()  # NOWE

        # Timer dla diagnostyki
        self.diagnostic_timer = None
        self.start_diagnostic_timer()

    def setup_bars_callbacks(self):

        self.combat_controller.bars_analyzer = self.bars_analyzer
        """Konfiguruje callback dla PlayerBarsAnalyzer"""
        def hp_callback(event_type: str, hp_percentage: float):
            """Callback dla zdarzeń HP"""
            self.current_hp = hp_percentage
            self.bars_last_update = time.time()

            # DODAJ TO: Przekaż do combat controller
            if hasattr(self, 'combat_controller') and self.combat_mode:
                self.combat_controller.handle_hp_event(event_type, hp_percentage)

            # Integracja z nowym systemem presetów
            if hasattr(self, 'bars_analyzer') and self.bars_analyzer:
                self.bars_analyzer.integrate_with_combat_controller(self.combat_controller)

            # Aktualizuj GUI w main thread
            self.root.after(0, self.update_bars_display)

            # Log krytycznych stanów
            if event_type == "hp_critical":
                self.log_message(f"🚨 KRYTYCZNE HP: {hp_percentage:.1f}%", "WARNING")
            elif event_type == "hp_warning":
                self.log_message(f"⚠️ NISKIE HP: {hp_percentage:.1f}%", "WARNING")

        def mana_callback(event_type: str, mana_percentage: float):
            """Callback dla zdarzeń Mana"""
            self.current_mana = mana_percentage
            self.bars_last_update = time.time()

            # Aktualizuj GUI w main thread
            self.root.after(0, self.update_bars_display)

            # Log krytycznych stanów
            if event_type == "mana_critical":
                self.log_message(f"🚨 KRYTYCZNA MANA: {mana_percentage:.1f}%", "WARNING")

        # Dodaj callbacks
        self.bars_analyzer.add_hp_change_callback(hp_callback)
        self.bars_analyzer.add_mana_change_callback(mana_callback)

        # Integruj z combat controller
        self.bars_analyzer.integrate_with_combat_controller(self.combat_controller)

    def update_bars_display(self):
        """Aktualizuje wyświetlanie wartości pasków w GUI"""
        if hasattr(self, 'hp_value_label') and self.hp_value_label:
            # Aktualizuj HP
            hp_text = f"HP: {self.current_hp:.1f}%"
            hp_color = 'red' if self.current_hp < 25 else 'orange' if self.current_hp < 50 else 'green'
            self.hp_value_label.config(text=hp_text, foreground=hp_color)

            # Aktualizuj Mana
            mana_text = f"Mana: {self.current_mana:.1f}%"
            mana_color = 'red' if self.current_mana < 15 else 'blue'
            self.mana_value_label.config(text=mana_text, foreground=mana_color)

            # Aktualizuj timestamp
            if self.bars_last_update > 0:
                time_ago = time.time() - self.bars_last_update
                if time_ago < 60:
                    update_text = f"Zaktualizowano: {time_ago:.1f}s temu"
                else:
                    update_text = f"Zaktualizowano: {time.strftime('%H:%M:%S', time.localtime(self.bars_last_update))}"
                self.bars_last_update_label.config(text=update_text)

    def start_diagnostic_timer(self):
        """Uruchamia timer dla diagnostyki"""
        if hasattr(self, 'diagnostic_text'):
            self.update_diagnostic_info()
        self.diagnostic_timer = self.root.after(1000, self.start_diagnostic_timer)

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

                    perf_stats = yolo_diag.get('performance_stats', {})
                    if perf_stats:
                        diagnostic_text += "⚡ WYDAJNOŚĆ YOLO:\n"
                        diagnostic_text += f"  Średni czas inference: {perf_stats.get('avg_inference_time_ms', 0):.1f}ms\n"
                        diagnostic_text += f"  Szacowane FPS: {perf_stats.get('estimated_fps', 0):.1f}\n"
                        diagnostic_text += f"  Próbek: {perf_stats.get('samples_count', 0)}\n"
                        diagnostic_text += "\n"

                except Exception as e:
                    diagnostic_text += f"🤖 YOLO DETECTOR: Błąd diagnostyki - {str(e)}\n\n"

            # GPU Utilization Stats
            gpu_stats = self.get_gpu_utilization()
            if gpu_stats:
                diagnostic_text += "🚀 GPU UTILIZATION:\n"
                diagnostic_text += f"  Pamięć GPU użycie: {gpu_stats['gpu_memory_used']:.2f}GB / {gpu_stats['gpu_memory_total']:.2f}GB\n"
                diagnostic_text += f"  Pamięć GPU %: {gpu_stats['gpu_memory_percent']:.1f}%\n"
                diagnostic_text += f"  CPU % (placeholder): {gpu_stats['gpu_utilization']:.1f}%\n"
                diagnostic_text += "\n"

            # NOWE: Player Bars Analyzer Stats
            if self.bars_analyzer:
                try:
                    bars_stats = self.bars_analyzer.get_combined_stats()
                    diagnostic_text += "📊 PLAYER BARS ANALYZER:\n"
                    diagnostic_text += f"  HP włączone: {bars_stats['hp_enabled']}\n"
                    diagnostic_text += f"  Mana włączona: {bars_stats['mana_enabled']}\n"
                    diagnostic_text += f"  HP pozycja: {bars_stats['hp_position']}\n"
                    diagnostic_text += f"  Mana pozycja: {bars_stats['mana_position']}\n"

                    hp_stats = bars_stats['hp_stats']
                    mana_stats = bars_stats['mana_stats']

                    diagnostic_text += f"  HP analiz: {hp_stats['total_analyses']}\n"
                    diagnostic_text += f"  HP sukces: {hp_stats['successful_detections']}\n"
                    diagnostic_text += f"  HP ostrzeżenia: {hp_stats['critical_warnings']}\n"
                    diagnostic_text += f"  HP czas avg: {hp_stats['avg_analysis_time_ms']:.1f}ms\n"

                    diagnostic_text += f"  Mana analiz: {mana_stats['total_analyses']}\n"
                    diagnostic_text += f"  Mana sukces: {mana_stats['successful_detections']}\n"
                    diagnostic_text += f"  Mana ostrzeżenia: {mana_stats['critical_warnings']}\n"
                    diagnostic_text += f"  Mana czas avg: {mana_stats['avg_analysis_time_ms']:.1f}ms\n"
                    diagnostic_text += "\n"

                except Exception as e:
                    diagnostic_text += f"📊 PLAYER BARS: Błąd diagnostyki - {str(e)}\n\n"

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

            # Key 8 and Key 9 Systems Status
            if self.combat_controller:
                try:
                    key8_status = self.combat_controller.get_multi_enemy_key8_status()
                    key9_status = self.combat_controller.get_exploration_key9_status()

                    diagnostic_text += "🔑 KEY SYSTEMS:\n"
                    diagnostic_text += f"  Key 8 (Multi-enemy): {'✅' if key8_status['enabled'] else '❌'}\n"
                    if key8_status['accumulated'] > 0:
                        diagnostic_text += f"    Accumulated: {key8_status['accumulated']:.1f}/{key8_status['threshold']}s\n"
                    if key8_status['cooldown_remaining'] > 0:
                        diagnostic_text += f"    Cooldown: {key8_status['cooldown_remaining']:.1f}s\n"

                    diagnostic_text += f"  Key 9 (Exploration): {'✅' if key9_status['enabled'] else '❌'}\n"
                    if key9_status['accumulated'] > 0:
                        diagnostic_text += f"    Accumulated: {key9_status['accumulated']:.1f}/{key9_status['threshold']}s\n"
                    if key9_status.get('pressed_this_session', False):
                        diagnostic_text += f"    Status: Already pressed (wait for mode change)\n"
                    diagnostic_text += "\n"
                except Exception as e:
                    diagnostic_text += f"🔑 KEY SYSTEMS: Błąd diagnostyki - {str(e)}\n\n"

            # Aplikacja Stats
            diagnostic_text += "📱 APLIKACJA:\n"
            diagnostic_text += f"  Wybrane okno: {self.selected_window['title'] if self.selected_window else 'Brak'}\n"
            diagnostic_text += f"  YOLO aktywny: {self.yolo_active}\n"
            diagnostic_text += f"  Analiza pasków: {self.bars_analysis_active}\n"
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

    def get_gpu_utilization(self):
        """Get current GPU utilization"""
        try:
            import torch
            if torch.cuda.is_available():
                return {
                    'gpu_memory_used': torch.cuda.memory_allocated() / 1024**3,  # GB
                    'gpu_memory_total': torch.cuda.get_device_properties(0).total_memory / 1024**3,
                    'gpu_memory_percent': (torch.cuda.memory_allocated() / torch.cuda.get_device_properties(0).total_memory) * 100,
                    'gpu_utilization': psutil.cpu_percent(interval=0.1)  # Placeholder - for real GPU % use nvidia-ml-py3
                }
            return None
        except:
            return None

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
        self.root.title("Enhanced YOLO Game Controller v6.1 - with HP/Mana Analysis")
        self.root.geometry("1600x1000")
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
        self.setup_diagnostic_tab()

    def setup_control_tab(self):
        """Zakładka kontroli głównej"""
        control_frame = ttk.Frame(self.notebook)
        self.notebook.add(control_frame, text="🎮 Kontrola")

        # === SEKCJA WYBORU OKNA ===
        window_frame = ttk.LabelFrame(control_frame, text="🪟 Wybór okna do przechwytywania", padding=15)
        window_frame.pack(fill='x', pady=(0, 10))

        list_container = ttk.Frame(window_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.window_listbox = tk.Listbox(list_container, height=6, font=('Consolas', 9))
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

        # === NOWA SEKCJA: ANALIZA PASKÓW GRACZA ===
        bars_frame = ttk.LabelFrame(control_frame, text="📊 Analiza pasków gracza", padding=15)
        bars_frame.pack(fill='x', pady=(0, 10))

        # Status pasków
        bars_status_frame = ttk.Frame(bars_frame)
        bars_status_frame.pack(fill='x')

        self.hp_value_label = ttk.Label(bars_status_frame, text="HP: ---%",
                                       font=('Arial', 12, 'bold'), foreground='gray')
        self.hp_value_label.pack(side='left', padx=(0, 20))

        self.mana_value_label = ttk.Label(bars_status_frame, text="Mana: ---%",
                                         font=('Arial', 12, 'bold'), foreground='gray')
        self.mana_value_label.pack(side='left', padx=(0, 20))

        # Przyciski HP/Mana
        bars_btn_frame = ttk.Frame(bars_frame)
        bars_btn_frame.pack(fill='x', pady=(10, 0))

        self.hp_toggle_btn = ttk.Button(bars_btn_frame, text="🟢 Włącz HP", command=self.toggle_hp_analysis)
        self.hp_toggle_btn.pack(side='left', padx=(0, 5))

        self.mana_toggle_btn = ttk.Button(bars_btn_frame, text="🔵 Włącz Mana", command=self.toggle_mana_analysis)
        self.mana_toggle_btn.pack(side='left', padx=(0, 5))


        ttk.Button(bars_btn_frame, text="🧪 Test HP", command=self.test_hp_analysis).pack(side='left', padx=(0, 5))
        ttk.Button(bars_btn_frame, text="🧪 Test Mana", command=self.test_mana_analysis).pack(side='left', padx=(0, 5))
        ttk.Button(bars_btn_frame, text="🎯 Włącz Color Triggers", command=self.toggle_color_triggers).pack(side='left', padx=(0, 5))

        self.bars_toggle_btn = ttk.Button(bars_btn_frame, text="▶️ Start Analiza", command=self.toggle_bars_analysis)
        self.bars_toggle_btn.pack(side='left', padx=(10, 0))

        # Status aktualizacji
        self.bars_last_update_label = ttk.Label(bars_frame, text="Brak danych",
                                               font=('Arial', 9), foreground='gray')
        self.bars_last_update_label.pack(anchor='w', pady=(5, 0))

        bars_info = ttk.Label(bars_frame, text="ℹ️ Skonfiguruj pozycje pasków w zakładce Ustawienia",
                             font=('Arial', 9), foreground='blue')
        bars_info.pack(anchor='w', pady=(2, 0))

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

        # === KEY 9 EXPLORATION BUFF SECTION ===
        key9_frame = ttk.LabelFrame(combat_frame, text="🔑 Key 9 - Exploration Buff")
        key9_frame.pack(fill='x', pady=(10, 0))

        key9_info = ttk.Label(key9_frame,
            text="Naciśnij klawisz 9 po 10 sekund w exploration mode",
            font=('Arial', 9), foreground='gray')
        key9_info.pack(anchor='w', pady=(5, 0))

        key9_btn_frame = ttk.Frame(key9_frame)
        key9_btn_frame.pack(fill='x', pady=(5, 0))

        self.key9_toggle_btn = ttk.Button(key9_btn_frame,
            text="🔴 Key 9: Wyłączony",
            command=self.toggle_key9_exploration)
        self.key9_toggle_btn.pack(side='left', padx=(0, 5))

        self.key9_status_label = ttk.Label(key9_frame,
            text="Status: Wyłączony",
            font=('Arial', 9), foreground='red')
        self.key9_status_label.pack(anchor='w', pady=(5, 0))

        # === SEKCJA LOGÓW ===
        log_frame = ttk.LabelFrame(control_frame, text="📋 Logi systemowe", padding=15)
        log_frame.pack(fill='both', expand=True)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill='both', expand=True)

        self.log_text = tk.Text(log_container, height=8, wrap='word', font=('Consolas', 9))
        log_text_scrollbar = ttk.Scrollbar(log_container, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_text_scrollbar.set)

        self.log_text.pack(side='left', fill='both', expand=True)
        log_text_scrollbar.pack(side='right', fill='y')

        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(log_btn_frame, text="🧹 Wyczyść logi", command=self.clear_logs).pack(side='left')

    # === NOWE METODY DLA ANALIZY PASKÓW ===

    def toggle_hp_analysis(self):
        """Włącza/wyłącza analizę HP"""
        current_state = self.bars_analyzer.hp_enabled
        new_state = not current_state

        if new_state:
            # Aplikuj ustawienia pozycji
            self.apply_bars_positions()

        self.bars_analyzer.enable_hp_analysis(new_state)

        if new_state:
            self.hp_toggle_btn.config(text="🔴 Wyłącz HP")
            self.log_message("🟢 Analiza HP włączona")
        else:
            self.hp_toggle_btn.config(text="🟢 Włącz HP")
            self.log_message("🔴 Analiza HP wyłączona")

    def toggle_mana_analysis(self):
        """Włącza/wyłącza analizę Mana"""
        current_state = self.bars_analyzer.mana_enabled
        new_state = not current_state

        if new_state:
            # Aplikuj ustawienia pozycji
            self.apply_bars_positions()

        self.bars_analyzer.enable_mana_analysis(new_state)

        if new_state:
            self.mana_toggle_btn.config(text="🔴 Wyłącz Mana")
            self.log_message("🔵 Analiza Mana włączona")
        else:
            self.mana_toggle_btn.config(text="🔵 Włącz Mana")
            self.log_message("🔴 Analiza Mana wyłączona")

    def toggle_bars_analysis(self):
        """Włącza/wyłącza główną pętlę analizy pasków"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        if not self.bars_analysis_active:
            self.start_bars_analysis()
        else:
            self.stop_bars_analysis()

    def start_bars_analysis(self):
        """Uruchamia pętlę analizy pasków"""
        self.bars_analysis_active = True
        self.bars_toggle_btn.config(text="⏹️ Stop Analiza")

        # Uruchom wątek analizy pasków
        self.bars_thread = threading.Thread(target=self.bars_analysis_loop, daemon=True)
        self.bars_thread.start()

        self.log_message("📊 Analiza pasków uruchomiona")

    def stop_bars_analysis(self):
        """Zatrzymuje pętlę analizy pasków"""
        self.bars_analysis_active = False
        self.bars_toggle_btn.config(text="▶️ Start Analiza")
        self.log_message("⏹️ Analiza pasków zatrzymana")

    def apply_bars_positions(self):
        """Aplikuje pozycje pasków z ustawień"""
        try:
            # HP pozycja
            hp_x = int(float(self.hp_x_var.get()))
            hp_y = int(float(self.hp_y_var.get()))
            hp_w = int(float(self.hp_w_var.get()))
            hp_h = int(float(self.hp_h_var.get()))
            self.bars_analyzer.set_hp_position_px(hp_x, hp_y, hp_w, hp_h)

            # Mana pozycja
            mana_x = int(float(self.mana_x_var.get()))
            mana_y = int(float(self.mana_y_var.get()))
            mana_w = int(float(self.mana_w_var.get()))
            mana_h = int(float(self.mana_h_var.get()))
            self.bars_analyzer.set_mana_position_px(mana_x, mana_y, mana_w, mana_h)

            self.log_message(f"📊 Pozycje pasków zaktualizowane: HP({hp_x},{hp_y},{hp_w},{hp_h}) Mana({mana_x},{mana_y},{mana_w},{mana_h})")

        except ValueError as e:
            self.log_message(f"❌ Błąd pozycji pasków: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nieprawidłowe pozycje pasków:\n{str(e)}")

    def test_hp_analysis(self):
        """Test analizy HP"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            self.apply_bars_positions()
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

            if frame is not None:
                result = self.bars_analyzer.analyze_hp(frame)

                if result['success']:
                    hp_percent = result['hp_percentage']
                    analysis_time = result['analysis_time_ms']
                    green_data = result['green_data']

                    test_msg = f"🟢 Test HP - SUKCES!\n\n"
                    test_msg += f"HP: {hp_percent:.1f}%\n"
                    test_msg += f"Czas analizy: {analysis_time:.1f}ms\n"
                    test_msg += f"Zielone piksele: {green_data['colored_pixels']}/{green_data['total_pixels']}\n"
                    test_msg += f"Pokrycie kolorem: {green_data['percentage']:.1f}%\n"
                    test_msg += f"Krytyczne: {'TAK' if result['critical'] else 'NIE'}"

                    self.log_message(f"🧪 Test HP: {hp_percent:.1f}% ({analysis_time:.1f}ms)")
                    messagebox.showinfo("Test HP", test_msg)
                else:
                    error_msg = f"❌ Test HP - BŁĄD\n\nPowód: {result['reason']}"
                    self.log_message(f"❌ Test HP nieudany: {result['reason']}")
                    messagebox.showerror("Test HP", error_msg)
            else:
                messagebox.showerror("Test HP", "❌ Nie udało się przechwycić obrazu")

        except Exception as e:
            self.log_message(f"❌ Błąd testu HP: {str(e)}", "ERROR")
            messagebox.showerror("Test HP", f"❌ Błąd testu:\n{str(e)}")

    def test_mana_analysis(self):
        """Test analizy Mana"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            self.apply_bars_positions()
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

            if frame is not None:
                result = self.bars_analyzer.analyze_mana(frame)

                if result['success']:
                    mana_percent = result['mana_percentage']
                    analysis_time = result['analysis_time_ms']
                    blue_data = result['blue_data']

                    test_msg = f"🔵 Test Mana - SUKCES!\n\n"
                    test_msg += f"Mana: {mana_percent:.1f}%\n"
                    test_msg += f"Czas analizy: {analysis_time:.1f}ms\n"
                    test_msg += f"Niebieskie piksele: {blue_data['colored_pixels']}/{blue_data['total_pixels']}\n"
                    test_msg += f"Pokrycie kolorem: {blue_data['percentage']:.1f}%\n"
                    test_msg += f"Krytyczne: {'TAK' if result['critical'] else 'NIE'}"

                    self.log_message(f"🧪 Test Mana: {mana_percent:.1f}% ({analysis_time:.1f}ms)")
                    messagebox.showinfo("Test Mana", test_msg)
                else:
                    error_msg = f"❌ Test Mana - BŁĄD\n\nPowód: {result['reason']}"
                    self.log_message(f"❌ Test Mana nieudany: {result['reason']}")
                    messagebox.showerror("Test Mana", error_msg)
            else:
                messagebox.showerror("Test Mana", "❌ Nie udało się przechwycić obrazu")

        except Exception as e:
            self.log_message(f"❌ Błąd testu Mana: {str(e)}", "ERROR")
            messagebox.showerror("Test Mana", f"❌ Błąd testu:\n{str(e)}")

    def bars_analysis_loop(self):
        """Główna pętla analizy pasków - działa asynchronicznie"""
        self.log_message("📊 Rozpoczęto pętlę analizy pasków")

        bars_fps = 10  # 10 FPS dla analizy pasków
        analysis_count = 0

        while self.bars_analysis_active:
            try:
                if not self.selected_window:
                    break

                any_analysis_enabled = (
                        self.bars_analyzer.hp_enabled or
                        self.bars_analyzer.mana_enabled or
                        getattr(self.bars_analyzer, 'color_triggers_enabled', False)
                )

                if not any_analysis_enabled:
                    time.sleep(0.5)
                    continue

                # Przechwytywanie obrazu
                frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

                if frame is not None:
                    analysis_count += 1
                    # Przed analyze_both():
                    self.bars_analyzer._current_hwnd = self.selected_window['hwnd']
                    # Analiza HP i Mana
                    both_results = self.bars_analyzer.analyze_both(frame)

                    # Aktualizuj current values (callback już to robi, ale dla pewności)
                    if both_results['hp_result'].get('success'):
                        self.current_hp = both_results['hp_percentage']

                    if both_results['mana_result'].get('success'):
                        self.current_mana = both_results['mana_percentage']

                    self.bars_last_update = time.time()
                    self.root.after(0, self.update_bars_display)

  
                # Kontrola FPS
                time.sleep(max(0.02, 1/bars_fps))

            except Exception as e:
                self.log_message(f"❌ Błąd pętli analizy pasków: {str(e)}", "ERROR")
                time.sleep(1)  # Czekaj dłużej przy błędzie

        self.log_message("🏁 Pętla analizy pasków zakończona")

    def toggle_color_triggers(self):
        current_state = self.bars_analyzer.color_triggers_enabled
        self.bars_analyzer.enable_color_triggers(not current_state)
        status = "ENABLED" if not current_state else "DISABLED"
        self.log_message(f"🎯 Color Triggers: {status}")
    # === RESZTA METOD (bez zmian) ===

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
        ttk.Button(test_frame, text="📊 Test pasków",
                  command=self.test_bars_combined).pack(side='left', padx=(0, 5))
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
- Player Bars Analyzer: Analiza HP/Mana
- Combat Controller: System walki
- Image Validation: Walidacja obrazów

📊 Automatyczna aktualizacja co sekundę

Użyj przycisków powyżej aby przeprowadzić testy:
🧪 Test przechwytywania - sprawdza czy okno jest prawidłowo przechwytywane
🤖 Test YOLO - sprawdza czy YOLO otrzymuje prawidłowe obrazy
📊 Test pasków - sprawdza analizę HP/Mana
📊 Statystyki - szczegółowe informacje o wydajności
"""

        self.diagnostic_text.insert(1.0, initial_text)

    def test_bars_combined(self):
        """Test kombinowany dla analizy pasków"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            self.apply_bars_positions()
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

            if frame is not None:
                test_results = self.bars_analyzer.test_analysis(frame)

                result_text = "📊 TEST ANALIZY PASKÓW\n\n"

                # HP Test
                hp_test = test_results['hp_test']
                result_text += f"🟢 HP TEST:\n"
                if hp_test['success']:
                    result_text += f"  Status: ✅ SUKCES\n"
                    result_text += f"  HP: {hp_test['hp_percentage']:.1f}%\n"
                    result_text += f"  Czas: {hp_test['analysis_time_ms']:.1f}ms\n"
                    result_text += f"  Krytyczne: {'TAK' if hp_test['critical'] else 'NIE'}\n"
                else:
                    result_text += f"  Status: ❌ BŁĄD\n"
                    result_text += f"  Powód: {hp_test['reason']}\n"

                result_text += "\n"

                # Mana Test
                mana_test = test_results['mana_test']
                result_text += f"🔵 MANA TEST:\n"
                if mana_test['success']:
                    result_text += f"  Status: ✅ SUKCES\n"
                    result_text += f"  Mana: {mana_test['mana_percentage']:.1f}%\n"
                    result_text += f"  Czas: {mana_test['analysis_time_ms']:.1f}ms\n"
                    result_text += f"  Krytyczne: {'TAK' if mana_test['critical'] else 'NIE'}\n"
                else:
                    result_text += f"  Status: ❌ BŁĄD\n"
                    result_text += f"  Powód: {mana_test['reason']}\n"

                result_text += "\n"

                # Combined Test
                combined = test_results['combined_test']
                result_text += f"🔄 KOMBINOWANY TEST:\n"
                result_text += f"  Oba udane: {'TAK' if combined['both_successful'] else 'NIE'}\n"
                result_text += f"  HP: {combined['hp_percentage']:.1f}%\n"
                result_text += f"  Mana: {combined['mana_percentage']:.1f}%\n"

                # Stats
                stats = test_results['stats']
                result_text += f"\n📈 STATYSTYKI:\n"
                result_text += f"  HP włączone: {stats['hp_enabled']}\n"
                result_text += f"  Mana włączona: {stats['mana_enabled']}\n"
                result_text += f"  HP analiz: {stats['hp_stats']['total_analyses']}\n"
                result_text += f"  Mana analiz: {stats['mana_stats']['total_analyses']}\n"

                self.log_message("🧪 Test kombinowany zakończony")
                messagebox.showinfo("Test Analizy Pasków", result_text)

            else:
                messagebox.showerror("Test pasków", "❌ Nie udało się przechwycić obrazu")

        except Exception as e:
            self.log_message(f"❌ Błąd testu pasków: {str(e)}", "ERROR")
            messagebox.showerror("Test pasków", f"❌ Błąd testu:\n{str(e)}")

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

            # NOWE: Player Bars Analyzer Stats
            if self.bars_analyzer:
                try:
                    bars_stats = self.bars_analyzer.get_combined_stats()
                    stats_text += "📊 PLAYER BARS ANALYZER:\n"
                    stats_text += f"  HP włączone: {bars_stats['hp_enabled']}\n"
                    stats_text += f"  Mana włączona: {bars_stats['mana_enabled']}\n"

                    hp_stats = bars_stats['hp_stats']
                    mana_stats = bars_stats['mana_stats']

                    stats_text += f"  HP - analiz: {hp_stats['total_analyses']}, sukces: {hp_stats['successful_detections']}\n"
                    stats_text += f"  HP - avg czas: {hp_stats['avg_analysis_time_ms']:.1f}ms, ostrzeżenia: {hp_stats['critical_warnings']}\n"
                    stats_text += f"  HP - ostatnia wartość: {hp_stats['last_hp_value']:.1f}%\n"

                    stats_text += f"  Mana - analiz: {mana_stats['total_analyses']}, sukces: {mana_stats['successful_detections']}\n"
                    stats_text += f"  Mana - avg czas: {mana_stats['avg_analysis_time_ms']:.1f}ms, ostrzeżenia: {mana_stats['critical_warnings']}\n"
                    stats_text += f"  Mana - ostatnia wartość: {mana_stats['last_mana_value']:.1f}%\n"
                    stats_text += "\n"

                except Exception as e:
                    stats_text += f"📊 PLAYER BARS: Błąd statystyk - {str(e)}\n\n"

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
            stats_text += f"  Analiza pasków aktywna: {self.bars_analysis_active}\n"
            stats_text += f"  HP aktualne: {self.current_hp:.1f}%\n"
            stats_text += f"  Mana aktualna: {self.current_mana:.1f}%\n"
            stats_text += f"  Aktywny czas: {time.time() - getattr(self, 'start_time', time.time()):.1f}s\n"

            messagebox.showinfo("Szczegółowe statystyki", stats_text)

        except Exception as e:
            self.log_message(f"Błąd wyświetlania statystyk: {str(e)}", "ERROR")

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

        # NOWE: Przyciski interaktywnego edytora
        ttk.Separator(preview_controls, orient='vertical').pack(side='left', padx=(10, 0), fill='y')
        self.edit_toggle_btn = ttk.Button(preview_controls, text="Edytuj współrzędne",
                                         command=self.toggle_edit_mode)
        self.edit_toggle_btn.pack(side='left', padx=(0, 5))
        ttk.Button(preview_controls, text="💾 Zapisz presety",
                  command=self.save_current_preset).pack(side='left', padx=(0, 5))

        detection_info = ttk.Label(preview_controls,
                                 text="🎯 Podgląd z wykrywaniami YOLO + HP/Mana",
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

        # === NOWA SEKCJA: USTAWIENIA PASKÓW HP/MANA ===
        bars_settings_frame = ttk.LabelFrame(settings_frame, text="📊 Ustawienia pasków gracza", padding=15)
        bars_settings_frame.pack(fill='x', pady=(10, 10), padx=10)

        # HP Position
        hp_frame = ttk.LabelFrame(bars_settings_frame, text="🟢 Pozycja paska HP", padding=10)
        hp_frame.pack(fill='x', pady=(0, 10))

        hp_pos_frame = ttk.Frame(hp_frame)
        hp_pos_frame.pack(fill='x')

        ttk.Label(hp_pos_frame, text="X:").grid(row=0, column=0, padx=(0, 5))
        ttk.Entry(hp_pos_frame, textvariable=self.hp_x_var, width=8).grid(row=0, column=1, padx=(0, 10))

        ttk.Label(hp_pos_frame, text="Y:").grid(row=0, column=2, padx=(0, 5))
        ttk.Entry(hp_pos_frame, textvariable=self.hp_y_var, width=8).grid(row=0, column=3, padx=(0, 10))

        ttk.Label(hp_pos_frame, text="Szerokość:").grid(row=0, column=4, padx=(0, 5))
        ttk.Entry(hp_pos_frame, textvariable=self.hp_w_var, width=8).grid(row=0, column=5, padx=(0, 10))

        ttk.Label(hp_pos_frame, text="Wysokość:").grid(row=0, column=6, padx=(0, 5))
        ttk.Entry(hp_pos_frame, textvariable=self.hp_h_var, width=8).grid(row=0, column=7)

        # Mana Position
        mana_frame = ttk.LabelFrame(bars_settings_frame, text="🔵 Pozycja paska Mana", padding=10)
        mana_frame.pack(fill='x', pady=(0, 10))

        mana_pos_frame = ttk.Frame(mana_frame)
        mana_pos_frame.pack(fill='x')

        ttk.Label(mana_pos_frame, text="X:").grid(row=0, column=0, padx=(0, 5))
        ttk.Entry(mana_pos_frame, textvariable=self.mana_x_var, width=8).grid(row=0, column=1, padx=(0, 10))

        ttk.Label(mana_pos_frame, text="Y:").grid(row=0, column=2, padx=(0, 5))
        ttk.Entry(mana_pos_frame, textvariable=self.mana_y_var, width=8).grid(row=0, column=3, padx=(0, 10))

        ttk.Label(mana_pos_frame, text="Szerokość:").grid(row=0, column=4, padx=(0, 5))
        ttk.Entry(mana_pos_frame, textvariable=self.mana_w_var, width=8).grid(row=0, column=5, padx=(0, 10))

        ttk.Label(mana_pos_frame, text="Wysokość:").grid(row=0, column=6, padx=(0, 5))
        ttk.Entry(mana_pos_frame, textvariable=self.mana_h_var, width=8).grid(row=0, column=7)

        # Przyciski konfiguracji pasków
        bars_config_frame = ttk.Frame(bars_settings_frame)
        bars_config_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(bars_config_frame, text="💾 Zapisz pozycje",
                  command=self.save_bars_positions).pack(side='left', padx=(0, 5))
        ttk.Button(bars_config_frame, text="🧪 Test pozycji HP",
                  command=self.test_hp_position).pack(side='left', padx=(0, 5))
        ttk.Button(bars_config_frame, text="🧪 Test pozycji Mana",
                  command=self.test_mana_position).pack(side='left', padx=(0, 5))
        ttk.Button(bars_config_frame, text="🔄 Resetuj domyślne",
                  command=self.reset_bars_positions).pack(side='left', padx=(0, 5))

        # NOWE: Przyciski zarządzania presetami
        preset_buttons_frame = ttk.Frame(bars_settings_frame)
        preset_buttons_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(preset_buttons_frame, text="⚙️ Zarządzaj presetami",
                  command=self.open_preset_manager).pack(side='left', padx=(0, 5))
        ttk.Button(preset_buttons_frame, text="📂 Wczytaj preset",
                  command=self.load_preset_from_file).pack(side='left', padx=(0, 5))
        ttk.Button(preset_buttons_frame, text="💾 Zapisz jako preset",
                  command=self.save_current_as_preset).pack(side='left', padx=(0, 5))
        ttk.Button(preset_buttons_frame, text="🔄 Zastosuj preset",
                  command=self.apply_current_preset).pack(side='left', padx=(0, 5))
        ttk.Button(preset_buttons_frame, text="✏️ Aktualizuj preset",
                  command=self.update_current_preset_runtime).pack(side='left', padx=(5, 0))

        # Ustawienia progów
        thresholds_frame = ttk.LabelFrame(bars_settings_frame, text="⚠️ Progi ostrzeżeń", padding=10)
        thresholds_frame.pack(fill='x', pady=(10, 0))

        # HP thresholds
        hp_thresh_frame = ttk.Frame(thresholds_frame)
        hp_thresh_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(hp_thresh_frame, text="🟢 HP - Próg ostrzeżenia:").pack(side='left')
        self.hp_warning_scale = ttk.Scale(hp_thresh_frame, from_=10, to=90, orient='horizontal', length=200)
        self.hp_warning_scale.set(50)
        self.hp_warning_scale.pack(side='left', padx=(10, 5))

        ttk.Label(hp_thresh_frame, text="Próg krytyczny:").pack(side='left', padx=(10, 0))
        self.hp_critical_scale = ttk.Scale(hp_thresh_frame, from_=5, to=50, orient='horizontal', length=200)
        self.hp_critical_scale.set(25)
        self.hp_critical_scale.pack(side='left', padx=(10, 0))

        # Mana thresholds
        mana_thresh_frame = ttk.Frame(thresholds_frame)
        mana_thresh_frame.pack(fill='x', pady=(5, 0))

        ttk.Label(mana_thresh_frame, text="🔵 Mana - Próg krytyczny:").pack(side='left')
        self.mana_critical_scale = ttk.Scale(mana_thresh_frame, from_=5, to=50, orient='horizontal', length=200)
        self.mana_critical_scale.set(15)
        self.mana_critical_scale.pack(side='left', padx=(10, 5))

        ttk.Button(mana_thresh_frame, text="💾 Zapisz progi",
                  command=self.save_thresholds).pack(side='left', padx=(20, 0))

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

    # === NOWE METODY DLA USTAWIEŃ PASKÓW ===

    def save_bars_positions(self):
        """Zapisuje pozycje pasków"""
        try:
            self.apply_bars_positions()
            self.log_message("💾 Pozycje pasków zapisane")
            messagebox.showinfo("Sukces", "✅ Pozycje pasków zostały zapisane!")
        except Exception as e:
            self.log_message(f"❌ Błąd zapisywania pozycji: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"❌ Nie można zapisać pozycji:\n{str(e)}")

    def test_hp_position(self):
        """Test pozycji paska HP"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            self.apply_bars_positions()
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

            if frame is not None:
                # Stwórz debug obraz z HP regionem
                debug_image = self.bars_analyzer.create_debug_image(frame)

                # Pokaż region HP
                hp_pos = self.bars_analyzer.hp_position
                region_info = f"🟢 Test pozycji HP\n\n"
                region_info += f"Region: ({hp_pos['x']}, {hp_pos['y']}) "
                region_info += f"{hp_pos['width']}x{hp_pos['height']}px\n\n"

                # Wykonaj analizę
                result = self.bars_analyzer.analyze_hp(frame)
                if result['success']:
                    region_info += f"✅ Wykryto HP: {result['hp_percentage']:.1f}%\n"
                    region_info += f"Czas analizy: {result['analysis_time_ms']:.1f}ms\n"
                    region_info += f"Zielone piksele: {result['green_data']['colored_pixels']}\n"
                    region_info += f"Pokrycie: {result['green_data']['percentage']:.1f}%"
                else:
                    region_info += f"❌ Błąd: {result['reason']}"

                self.log_message("🧪 Test pozycji HP zakończony")
                messagebox.showinfo("Test pozycji HP", region_info)
            else:
                messagebox.showerror("Test pozycji HP", "❌ Nie udało się przechwycić obrazu")

        except Exception as e:
            self.log_message(f"❌ Błąd testu pozycji HP: {str(e)}", "ERROR")
            messagebox.showerror("Test pozycji HP", f"❌ Błąd testu:\n{str(e)}")

    def test_mana_position(self):
        """Test pozycji paska Mana"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            self.apply_bars_positions()
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

            if frame is not None:
                # Stwórz debug obraz z Mana regionem
                debug_image = self.bars_analyzer.create_debug_image(frame)

                # Pokaż region Mana
                mana_pos = self.bars_analyzer.mana_position
                region_info = f"🔵 Test pozycji Mana\n\n"
                region_info += f"Region: ({mana_pos['x']}, {mana_pos['y']}) "
                region_info += f"{mana_pos['width']}x{mana_pos['height']}px\n\n"

                # Wykonaj analizę
                result = self.bars_analyzer.analyze_mana(frame)
                if result['success']:
                    region_info += f"✅ Wykryto Mana: {result['mana_percentage']:.1f}%\n"
                    region_info += f"Czas analizy: {result['analysis_time_ms']:.1f}ms\n"
                    region_info += f"Niebieskie piksele: {result['blue_data']['colored_pixels']}\n"
                    region_info += f"Pokrycie: {result['blue_data']['percentage']:.1f}%"
                else:
                    region_info += f"❌ Błąd: {result['reason']}"

                self.log_message("🧪 Test pozycji Mana zakończony")
                messagebox.showinfo("Test pozycji Mana", region_info)
            else:
                messagebox.showerror("Test pozycji Mana", "❌ Nie udało się przechwycić obrazu")

        except Exception as e:
            self.log_message(f"❌ Błąd testu pozycji Mana: {str(e)}", "ERROR")
            messagebox.showerror("Test pozycji Mana", f"❌ Błąd testu:\n{str(e)}")

    def reset_bars_positions(self):
        """Resetuje pozycje pasków do domyślnych"""
        self.hp_x_var.set("108")
        self.hp_y_var.set("88")
        self.hp_w_var.set("119")
        self.hp_h_var.set("4")

        self.mana_x_var.set("108")
        self.mana_y_var.set("99")
        self.mana_w_var.set("120")
        self.mana_h_var.set("5")

        self.log_message("🔄 Pozycje pasków zresetowane do domyślnych")
        messagebox.showinfo("Reset", "✅ Pozycje pasków zostały zresetowane do domyślnych wartości")

    def save_thresholds(self):
        """Zapisuje progi ostrzeżeń"""
        try:
            hp_warning = float(self.hp_warning_scale.get())
            hp_critical = float(self.hp_critical_scale.get())
            mana_critical = float(self.mana_critical_scale.get())

            # Ustaw progi w analyzer
            self.bars_analyzer.set_hp_thresholds(
                warning=hp_warning,
                warning_recovery=hp_warning + 30,  # Histereza +30%
                critical=hp_critical,
                critical_recovery=hp_critical + 30  # Histereza +30%
            )

            self.bars_analyzer.set_mana_thresholds(
                critical=mana_critical,
                recovery=mana_critical + 30  # Histereza +30%
            )

            self.log_message(f"💾 Progi zapisane: HP warn:{hp_warning}% crit:{hp_critical}%, Mana crit:{mana_critical}%")
            messagebox.showinfo("Sukces", "✅ Progi ostrzeżeń zostały zapisane!")

        except Exception as e:
            self.log_message(f"❌ Błąd zapisywania progów: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"❌ Nie można zapisać progów:\n{str(e)}")

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

    def toggle_key9_exploration(self):
        """Włącza/wyłącza system key 9 w exploration mode"""
        if not hasattr(self, 'combat_controller'):
            return

        current_state = self.combat_controller.exploration_key9_enabled
        new_state = not current_state

        self.combat_controller.set_exploration_key9_enabled(new_state)

        if new_state:
            self.key9_toggle_btn.config(text="🟢 Key 9: Włączony")
            self.key9_status_label.config(text="Status: Włączony", foreground='green')
            self.log_message("🟢 Key 9 Exploration system włączony")
        else:
            self.key9_toggle_btn.config(text="🔴 Key 9: Wyłączony")
            self.key9_status_label.config(text="Status: Wyłączony", foreground='red')
            self.log_message("🔴 Key 9 Exploration system wyłączony")

    def draw_detections_on_image(self, image, detections):
        """
        POPRAWIONA: Rysuje wykrycia YOLO na obrazie z lepszą obsługą błędów
        """
        if not detections or len(detections) == 0:
            # self.log_message("🖼️ Brak wykryć do narysowania", "DEBUG")
            return image

        # self.log_message(f"🖼️ Rysuję {len(detections)} wykryć na obrazie", "DEBUG")

        try:
            result_image = image.copy()

            if result_image is None or result_image.size == 0:
                self.log_message("❌ Błąd: obraz do rysowania jest pusty", "ERROR")
                return image

            # self.log_message(f"🖼️ Obraz do rysowania: {result_image.shape}, typ: {result_image.dtype}", "DEBUG")

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
                    # self.log_message(f"✅ Narysowano wykrycie #{i + 1}: {name}", "DEBUG")

                except Exception as draw_error:
                    self.log_message(f"❌ Błąd rysowania wykrycia #{i + 1}: {str(draw_error)}", "ERROR")
                    continue

            
            if successful_draws == 0:
                self.log_message("⚠️ Nie udało się narysować żadnego wykrycia!", "WARNING")
                return image  # Zwróć oryginalny obraz

            return result_image

        except Exception as e:
            self.log_message(f"❌ Krytyczny błąd rysowania wykryć: {str(e)}", "ERROR")
            import traceback
            self.log_message(f"❌ Stack trace: {traceback.format_exc()}", "ERROR")
            return image  # Zwróć oryginalny obraz w przypadku błędu

    def draw_bars_on_image(self, image):
        """
        NOWE: Rysuje regiony HP/Mana na obrazie dla podglądu
        """
        try:
            result_image = image.copy()

            # Narysuj HP region jeśli włączony
            if self.bars_analyzer.hp_enabled:
                hp_pos = self.bars_analyzer.hp_position
                if hp_pos['width'] > 0 and hp_pos['height'] > 0:
                    x, y, w, h = hp_pos['x'], hp_pos['y'], hp_pos['width'], hp_pos['height']

                    # Prostokąt HP (zielony)
                    cv2.rectangle(result_image, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Label HP
                    cv2.putText(result_image, f"HP: {self.current_hp:.1f}%",
                               (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # Narysuj Mana region jeśli włączony
            if self.bars_analyzer.mana_enabled:
                mana_pos = self.bars_analyzer.mana_position
                if mana_pos['width'] > 0 and mana_pos['height'] > 0:
                    x, y, w, h = mana_pos['x'], mana_pos['y'], mana_pos['width'], mana_pos['height']

                    # Prostokąt Mana (niebieski)
                    cv2.rectangle(result_image, (x, y), (x + w, y + h), (255, 0, 0), 2)

                    # Label Mana
                    cv2.putText(result_image, f"Mana: {self.current_mana:.1f}%",
                               (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

            return result_image

        except Exception as e:
            self.log_message(f"❌ Błąd rysowania pasków: {str(e)}", "ERROR")
            return image

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
        """OPTIMIZED: Pętla podglądu używająca shared frame (bez podwójnego capture)"""
        while self.preview_active:
            try:
                if not self.selected_window:
                    break

                # PERFORMANCE: Use shared frame instead of re-capturing
                frame = getattr(self, 'shared_frame', None)

                if frame is not None:
                    self.current_image = frame
                    self.frame_count += 1
                    self.last_frame_time = time.time()
                    self.root.after(0, self.scale_and_display_image, frame)
                else:
                    # No frame available, skip display
                    pass

                # OPTIMIZATION: Remove hardcoded 30 FPS limit
                # Sync with detection loop FPS for smoothness
                current_fps = getattr(self, 'cached_fps', 30)
                time.sleep(max(0.016, 1 / max(30, current_fps)))  # 30-60 FPS

            except Exception as e:
                self.log_message(f"Błąd podglądu: {str(e)}", "ERROR")
                time.sleep(1)

    def on_canvas_configure(self, event):
        """Obsługuje zmianę rozmiaru canvas"""
        if self.current_image is not None:
            self.scale_and_display_image(self.current_image)

    def scale_and_display_image(self, img_array):
        """
        OPTIMIZED: Wyświetla obraz z wykryciami YOLO i paskami HP/Mana
        """
        try:
            # PERFORMANCE: Only delete if image exists
            if hasattr(self, 'canvas_image_id') and self.canvas_image_id:
                self.preview_canvas.delete(self.canvas_image_id)
            self.preview_canvas.delete("no_preview")

            if img_array is None or img_array.size == 0:
                                return

            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            # ADD HP/MANA DEBUG OVERLAY
            if hasattr(self, 'hp_analyzer') and self.hp_analyzer:
                try:
                    debug_image = self.hp_analyzer.create_debug_image(img_array)
                    if debug_image is not None:
                        # Convert debug image to PhotoImage and display on canvas
                        pil_image = Image.fromarray(debug_image)
                        self.debug_photo = tk.PhotoImage(pil_image)

                        # Scale to canvas size
                        scale_x = canvas_width / debug_image.shape[1]
                        scale_y = canvas_height / debug_image.shape[0]
                        scaled_width = int(debug_image.shape[1] * scale_x)
                        scaled_height = int(debug_image.shape[0] * scale_y)

                        if scaled_width > 0 and scaled_height > 0:
                            scaled_pil = pil_image.resize((scaled_width, scaled_height), Image.LANCZOS)
                            self.debug_photo = tk.PhotoImage(scaled_pil)

                            # Clear previous debug image and display new one
                            self.preview_canvas.delete("debug_overlay")
                            self.preview_canvas.create_image(0, 0, image=self.debug_photo,
                                                     anchor="nw", tags="debug_overlay")
                            self.log_message(f"🎯 HP/Mana Debug overlay: {scaled_width}x{scaled_height}")
                        else:
                            self.log_message("⚠️ Debug overlay: Nie można wyświetlić", "WARNING")
                except Exception as e:
                    self.log_message(f"❌ Błąd debug overlay: {str(e)}", "ERROR")

            if canvas_width <= 1 or canvas_height <= 1:
                return

            display_image = img_array.copy()

            # self.log_message(f"🖼️ Oryginalny obraz: {display_image.shape}, typ: {display_image.dtype}", "DEBUG")

            # Rysuj wykrycia YOLO jeśli aktywne
            detections_to_draw = None
            if hasattr(self, 'yolo_active') and self.yolo_active:
                if hasattr(self, 'latest_detections') and self.latest_detections:
                    detections_to_draw = self.latest_detections
                    # self.log_message(f"🖼️ Mam {len(detections_to_draw)} wykryć YOLO do narysowania", "DEBUG")

            # Rysuj wykrycia jeśli są
            if detections_to_draw and len(detections_to_draw) > 0:
                try:
                    # self.log_message(f"🖼️ Rozpoczynam rysowanie {len(detections_to_draw)} wykryć YOLO", "DEBUG")
                    display_image = self.draw_detections_on_image(display_image, detections_to_draw)
                    # # # self.log_message(f"🖼️ Zakończono rysowanie wykryć YOLO", "DEBUG")
                except Exception as draw_error:
                    self.log_message(f"❌ Błąd rysowania wykryć YOLO: {str(draw_error)}", "ERROR")

            # NOWE: Rysuj regiony HP/Mana jeśli analiza pasków jest aktywna
            if self.bars_analysis_active:
                try:
                    # self.log_message(f"🖼️ Rysowanie regionów HP/Mana", "DEBUG")
                    display_image = self.draw_bars_on_image(display_image)
                    # # self.log_message(f"🖼️ Zakończono rysowanie regionów pasków", "DEBUG")
                except Exception as bars_error:
                    self.log_message(f"❌ Błąd rysowania regionów pasków: {str(bars_error)}", "ERROR")

            # Przeskaluj obraz do canvas
            img_height, img_width = display_image.shape[:2]
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            scale = min(scale_x, scale_y, 1.0)

            new_width = max(1, int(img_width * scale))
            new_height = max(1, int(img_height * scale))

            # self.log_message(
                # f"🖼️ Przeskalowuję z {img_width}x{img_height} do {new_width}x{new_height} (scale: {scale:.3f})",
                # "DEBUG")

            # Upewnij się że obraz jest uint8
            if display_image.dtype != np.uint8:
                if display_image.max() <= 1.0:
                    display_image = (display_image * 255).astype(np.uint8)
                else:
                    display_image = display_image.astype(np.uint8)

            # Konwertuj do PIL i wyświetl
            try:
                img_pil = Image.fromarray(display_image, 'RGB')
                # PERFORMANCE: Use faster NEAREST for preview, BILINEAR for quality
                if hasattr(self, 'high_quality_preview') and self.high_quality_preview:
                    img_resized = img_pil.resize((new_width, new_height), Image.Resampling.BILINEAR)
                else:
                    img_resized = img_pil.resize((new_width, new_height), Image.Resampling.NEAREST)  # Fastest
                img_tk = ImageTk.PhotoImage(img_resized)

                x = canvas_width // 2
                y = canvas_height // 2

                self.canvas_image_id = self.preview_canvas.create_image(
                    x, y, anchor='center', image=img_tk, tags="preview_image"
                )

                # WAŻNE: Zachowaj referencję do obrazu
                self.preview_canvas.image = img_tk
                self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

                # self.log_message(f"✅ Obraz wyświetlony w preview", "DEBUG")

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
                    # NOWE: Dodaj wizualizacje do screenshota
                    display_frame = validated_frame.copy()

                    # Dodaj wykrycia YOLO jeśli aktywne
                    if self.yolo_active and hasattr(self, 'latest_detections') and self.latest_detections:
                        display_frame = self.draw_detections_on_image(display_frame, self.latest_detections)

                    # Dodaj regiony HP/Mana jeśli aktywne
                    if self.bars_analysis_active:
                        display_frame = self.draw_bars_on_image(display_frame)

                    img = Image.fromarray(display_frame)
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

        self.log_message("🤖 Rozpoczęto Enhanced YOLO Detection (dynamic threshold)")

        last_confidence_log = 0

        # OPTIMIZATION: Cache values to avoid repeated GUI calls
        cached_fps = int(self.fps_scale.get())
        cached_confidence = float(self.confidence_scale.get())
        last_gui_check = 0

        while self.yolo_active:
            # OPTIMIZATION: Only check GUI values every 2 seconds
            current_time = time.time()
            if current_time - last_gui_check > 2.0:
                cached_fps = int(self.fps_scale.get())
                cached_confidence = float(self.confidence_scale.get())
                last_gui_check = current_time
            fps = cached_fps
            confidence_threshold = cached_confidence

            
            try:
                if not self.selected_window:
                    break

                # Przechwytywanie obrazu
                frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

                if frame is not None and frame.size > 0:
                    try:
                        self.frame_count += 1
                        self.last_frame_time = time.time()

                        # GPU OPTIMIZATION: Force CUDA sync every few frames to ensure GPU work
                        if hasattr(self, 'cuda_sync_counter'):
                            self.cuda_sync_counter += 1
                        else:
                            self.cuda_sync_counter = 0

                        if self.cuda_sync_counter % 10 == 0:
                            import torch
                            if torch.cuda.is_available():
                                torch.cuda.synchronize()
                                torch.cuda.empty_cache()  # Clear cache periodically

                        # Uruchom wykrywanie YOLO (z dodanym obciążeniem GPU)
                        detections = self.yolo_detector.detect(frame, confidence_threshold)

                        # Zabezpieczenie: jeśli detections to None, zamień na pustą listę
                        if detections is None:
                            detections = []

                        # Sprawdź długość
                        if len(detections) > 0:
                            detection_count += 1
                            self.detection_count += len(detections)

                        # OPTIMIZATION: Single combat controller update per frame
                        if self.combat_mode:
                            try:
                                self.combat_controller.update(self.selected_window['hwnd'], detections)
                            except Exception as combat_error:
                                self.log_message(f"Błąd trybu walki: {str(combat_error)}", "ERROR")

                        # OPTIMIZATION: Direct assignment instead of copy
                        self.latest_detections = detections if detections else []

                        # PERFORMANCE: Share frame with preview to avoid double capture
                        self.shared_frame = frame

                    except Exception as detection_error:
                        self.log_message(f"Błąd Enhanced YOLO: {str(detection_error)}", "ERROR")
                        self.latest_detections = []
                        # PERFORMANCE: Remove expensive traceback in main loop

                else:
                    # No frame available
                    self.shared_frame = None

                    # NAWET BEZ RAMKI WYŚLIJ PUSTĄ LISTĘ
                    if self.combat_mode:
                        try:
                            self.combat_controller.update(self.selected_window['hwnd'], [])
                        except Exception as combat_error:
                            self.log_message(f"Błąd combat controller (brak ramki): {str(combat_error)}", "ERROR")

                time.sleep(max(0.02, 1 / fps))

            except Exception as e:
                self.log_message(f"Błąd głównej pętli Enhanced YOLO: {str(e)}", "ERROR")
                # PERFORMANCE: Remove expensive traceback from main loop
                time.sleep(1)

        self.log_message("🏁 Pętla Enhanced YOLO zakończona")

    def __del__(self):
        """Cleanup przy zamykaniu"""
        try:
            if hasattr(self, 'diagnostic_timer') and self.diagnostic_timer:
                self.root.after_cancel(self.diagnostic_timer)

            # NOWE: Zatrzymaj analizę pasków
            if hasattr(self, 'bars_analysis_active'):
                self.bars_analysis_active = False

        except:
            pass

    # NOWE: Funkcje interaktywnegoedytora współrzędnych
    def toggle_edit_mode(self):
        """Przełącza tryb edycji współrzędnych"""
        if not hasattr(self, 'edit_toggle_btn') or self.edit_toggle_btn is None:
            self.log_message("[ERROR] Przycisk edycji nie jest dostępny", "ERROR")
            return

        self.edit_mode = not self.edit_mode

        if self.edit_mode:
            self.edit_toggle_btn.config(text="X Zakończ edycję")
            self.log_message("[INFO] Tryb edycji współrzędnych aktywny", "INFO")
            # Dodaj event handlery do canvas
            self.preview_canvas.bind("<Button-1>", self.on_canvas_click)
            self.preview_canvas.bind("<B1-Motion>", self.on_canvas_drag)
            self.preview_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
            self.preview_canvas.bind("<Motion>", self.on_canvas_hover)
            self.preview_canvas.config(cursor="crosshair")
        else:
            self.edit_toggle_btn.config(text="Edytuj współrzędne")
            self.log_message("[INFO] Tryb edycji współrzędnych wyłączony", "INFO")
            # Usuń event handlery
            self.preview_canvas.unbind("<Button-1>")
            self.preview_canvas.unbind("<B1-Motion>")
            self.preview_canvas.unbind("<ButtonRelease-1>")
            self.preview_canvas.unbind("<Motion>")
            self.preview_canvas.config(cursor="")

            # Wyczyść edytowalne regiony
            for item_id in list(self.preview_canvas.find_all()):
                try:
                    tags = self.preview_canvas.gettags(item_id)
                    if tags and any("edit_rect" in str(tag) for tag in tags):
                        self.preview_canvas.delete(item_id)
                except Exception as e:
                    # Skip items that can't be processed
                    continue
            self.region_rectangles.clear()

    def on_canvas_click(self, event):
        """Obsługuje kliknięcie na canvas - rozpoczynijanie lub rozpoczynijanie regionów"""
        if self.current_image is None or not hasattr(self.current_image, 'shape'):
            return

        # Konwertuj współrzędne canvas na współrzędne obrazu
        canvas_x = self.preview_canvas.canvasx(event.x)
        canvas_y = self.preview_canvas.canvasy(event.y)

        # Sprawdź czy kliknięto w istniejącym regionie
        clicked_region = self.get_region_at_point(canvas_x, canvas_y)

        if clicked_region:
            # Rozpoczynijanie istniejacego regionu
            self.editing_region = clicked_region
            self.drag_start = (canvas_x, canvas_y)
            self.log_message(f"✏️ Rozpoczyniam region: {clicked_region}")
        else:
            # Rozpoczynijanie nowego regionu HP lub Mana
            self.start_new_region(canvas_x, canvas_y)

    def on_canvas_drag(self, event):
        """Obsługuje przesuwanie myszy podczas edycji"""
        if not self.edit_mode or not self.drag_start or not self.editing_region:
            return

        canvas_x = self.preview_canvas.canvasx(event.x)
        canvas_y = self.preview_canvas.canvasy(event.y)

        # Przesuń region
        dx = canvas_x - self.drag_start[0]
        dy = canvas_y - self.drag_start[1]

        # Usuń starą figurę i narysuj nową
        if self.editing_region in self.region_rectangles:
            self.preview_canvas.delete(self.region_rectangles[self.editing_region])

        # Pobierz oryginalne koordynaty
        original = self.original_coords.get(self.editing_region, {})
        if original:
            new_x = original["x"] + dx
            new_y = original["y"] + dy
            new_w = original.get("w", 100)
            new_h = original.get("h", 5)

            # Narysuj nową figurę
            rect_id = self.preview_canvas.create_rectangle(
                new_x, new_y, new_x + new_w, new_y + new_h,
                outline="yellow" if self.editing_region.startswith("hp") else "cyan",
                width=2, tags=["edit_rect", self.editing_region]
            )
            self.region_rectangles[self.editing_region] = rect_id

            # Aktualizuj pola tekstowe
            self.update_coordinate_fields(self.editing_region, new_x, new_y, new_w, new_h)

    def on_canvas_release(self, event):
        """Obsługuje zwolnienie przecisku myszy"""
        if not self.edit_mode or not self.drag_start:
            return

        self.drag_start = None
        self.editing_region = None

        # Zastosuj nowe koordynaty
        if hasattr(self, 'apply_bars_positions'):
            self.apply_bars_positions()

        self.log_message("✅ Współrzędne zaktualizowane")

    def on_canvas_hover(self, event):
        """Obsługuje najechanie myszy - pokazuje współrzędne"""
        if not self.edit_mode:
            return

        canvas_x = self.preview_canvas.canvasx(event.x)
        canvas_y = self.preview_canvas.canvasy(event.y)

        region = self.get_region_at_point(canvas_x, canvas_y)
        if region:
            self.preview_canvas.config(cursor="hand2")
        else:
            self.preview_canvas.config(cursor="crosshair")

    def start_new_region(self, x, y):
        """Rozpoczynia nowy region HP lub Mana"""
        # Domyślne rozmiary
        default_w, default_h = 100, 5

        # Próbuje inteligentnie określić typ regionu
        hp_pos = self.bars_analyzer.hp_position
        mana_pos = self.bars_analyzer.mana_position

        # Sprawdź czy bliżej HP czy Mana
        dist_to_hp = abs(x - hp_pos.get("x", 0)) + abs(y - hp_pos.get("y", 0))
        dist_to_mana = abs(x - mana_pos.get("x", 0)) + abs(y - mana_pos.get("y", 0))

        if dist_to_hp < dist_to_mana:
            self.editing_region = "hp"
            self.log_message("✏️ Rozpoczyniam nowy region HP")
        else:
            self.editing_region = "mana"
            self.log_message("✏️ Rozpoczyniam nowy region Mana")

        self.drag_start = (x, y)
        self.original_coords[self.editing_region] = {"x": x, "y": y, "w": default_w, "h": default_h}

        # Narysuj nową figurę
        rect_id = self.preview_canvas.create_rectangle(
            x, y, x + default_w, y + default_h,
            outline="yellow" if self.editing_region == "hp" else "cyan",
            width=2, tags=["edit_rect", self.editing_region]
        )
        self.region_rectangles[self.editing_region] = rect_id

    def get_region_at_point(self, x, y):
        """Sprawdza czy punkt jest wewnątrz regionu HP lub Mana"""
        # Pobierz aktualne pozycje
        hp_pos = self.bars_analyzer.hp_position
        mana_pos = self.bars_analyzer.mana_position

        # Sprawdź HP
        if (hp_pos.get("x", 0) <= x <= hp_pos.get("x", 0) + hp_pos.get("w", 0) and
            hp_pos.get("y", 0) <= y <= hp_pos.get("y", 0) + hp_pos.get("h", 0)):
            return "hp"

        # Sprawdź Mana
        if (mana_pos.get("x", 0) <= x <= mana_pos.get("x", 0) + mana_pos.get("w", 0) and
            mana_pos.get("y", 0) <= y <= mana_pos.get("y", 0) + mana_pos.get("h", 0)):
            return "mana"

        return None

    def update_coordinate_fields(self, region_type, x, y, w, h):
        """Aktualizuj pola tekstowe współrzędnych"""
        if region_type == "hp":
            self.hp_x_var.set(str(x))
            self.hp_y_var.set(str(y))
            self.hp_w_var.set(str(w))
            self.hp_h_var.set(str(h))
        elif region_type == "mana":
            self.mana_x_var.set(str(x))
            self.mana_y_var.set(str(y))
            self.mana_w_var.set(str(w))
            self.mana_h_var.set(str(h))

    def save_current_preset(self):
        """Zapisuje aktualne współrzędne jako nowy preset z podaną nazwą"""
        try:
            # Poproś użytkownika o nazwę presetu
            from tkinter import simpledialog
            preset_name = simpledialog.askstring(
                "Zapisz Preset",
                "Podaj nazwę presetu:",
                parent=self.root
            )

            if not preset_name:
                return  # Użytkownik anulował

            # Pobierz aktualne współrzędne
            hp_coords = {
                "x": int(self.hp_x_var.get()),
                "y": int(self.hp_y_var.get()),
                "w": int(self.hp_w_var.get()),
                "h": int(self.hp_h_var.get())
            }
            mana_coords = {
                "x": int(self.mana_x_var.get()),
                "y": int(self.mana_y_var.get()),
                "w": int(self.mana_w_var.get()),
                "h": int(self.mana_h_var.get())
            }

            # Importuj json, time i zapisz
            import json
            import time
            from datetime import datetime
            with open("configs/bar_presets.json", "r", encoding="utf-8") as f:
                presets_data = json.load(f)

            # Dodaj nowy preset z podaną nazwą
            new_preset_name = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            new_preset = {
                "name": preset_name,
                "category": "custom",
                "resolution": "custom",  # Placeholder
                "description": f"Zapisany przez użytkownika: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "relative_coords": {
                    "hp": hp_coords,
                    "mana": mana_coords
                },
                "colors": {
                    "hp": {"h_min": 50, "h_max": 80, "s_min": 100, "v_min": 100},
                    "mana": {"h_min": 100, "h_max": 130, "s_min": 80, "v_min": 80}
                }
            }

            presets_data["presets"][new_preset_name] = new_preset

            # Zapisz z powrotem
            with open("configs/bar_presets.json", "w", encoding="utf-8") as f:
                json.dump(presets_data, f, indent=2, ensure_ascii=False)

            self.log_message(f"✅ Preset zapisany: {preset_name} ({new_preset_name})")
            messagebox.showinfo("Sukces", f"Preset zapisany jako:\n{preset_name}")

        except Exception as e:
            self.log_message(f"❌ Błąd zapisu presetu: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można zapisać presetu:\n{str(e)}")

    # NOWE: Funkcje do zarządzania presetami
    def open_preset_manager(self):
        """Otwiera okno dialogowe do zarządzania presetami"""
        try:
            dialog = PresetDialog(self, self.preset_manager, self.logger)
            result = dialog.show()

            if result:
                # Jeśli wybrano preset, zastosuj go
                self.apply_preset_by_id(result)

        except Exception as e:
            self.log_message(f"❌ Błąd otwierania menedżera presetów: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można otworzyć menedżera presetów:\n{str(e)}")

    def apply_preset_by_id(self, preset_id: str):
        """Zastosowuje preset po ID"""
        try:
            preset = self.preset_manager.get_preset_by_id(preset_id)
            if not preset:
                self.log_message(f"❌ Nie znaleziono presetu: {preset_id}", "ERROR")
                return

            # Pobierz współrzędne
            coords = self.preset_manager.get_preset_coords(preset_id, force_absolute=True)
            if not coords:
                self.log_message(f"❌ Preset {preset_id} nie ma współrzędnych", "ERROR")
                return

            # Zastosuj współrzędne HP
            if 'hp' in coords:
                hp = coords['hp']
                self.hp_x_var.set(str(hp.get('x', 112)))
                self.hp_y_var.set(str(hp.get('y', 87)))
                self.hp_w_var.set(str(hp.get('w', 119)))
                self.hp_h_var.set(str(hp.get('h', 5)))

            # Zastosuj współrzędne Mana
            if 'mana' in coords:
                mana = coords['mana']
                self.mana_x_var.set(str(mana.get('x', 112)))
                self.mana_y_var.set(str(mana.get('y', 99)))
                self.mana_w_var.set(str(mana.get('w', 120)))
                self.mana_h_var.set(str(mana.get('h', 5)))
            elif 'mp' in coords:
                mp = coords['mp']
                self.mana_x_var.set(str(mp.get('x', 112)))
                self.mana_y_var.set(str(mp.get('y', 99)))
                self.mana_w_var.set(str(mp.get('w', 120)))
                self.mana_h_var.set(str(mp.get('h', 5)))

            # Zastosuj do analizatora
            self.apply_bars_positions()

            # Ustaw jako aktualny
            self.preset_manager.set_current_preset(preset_id)

            preset_name = preset.get('name', preset_id)
            self.log_message(f"✅ Zastosowano preset: {preset_name}")

        except Exception as e:
            self.log_message(f"❌ Błąd stosowania presetu: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można zastosować presetu:\n{str(e)}")

    def update_current_preset_runtime(self):
        """Aktualizuje aktualnie wybrany preset w runtime"""
        try:
            current_id = self.preset_manager.get_current_preset_id()
            if not current_id:
                messagebox.showinfo("Info", "Nie wybrano żadnego presetu do aktualizacji")
                return

            # Pobierz aktualne wartości z GUI
            try:
                hp_coords = {
                    'x': int(self.hp_x_var.get()),
                    'y': int(self.hp_y_var.get()),
                    'w': int(self.hp_w_var.get()),
                    'h': int(self.hp_h_var.get())
                }
            except ValueError:
                messagebox.showerror("Błąd", "Nieprawidłowe współrzędne HP - wymagane liczby")
                return

            try:
                mana_coords = {
                    'x': int(self.mana_x_var.get()),
                    'y': int(self.mana_y_var.get()),
                    'w': int(self.mana_w_var.get()),
                    'h': int(self.mana_h_var.get())
                }
            except ValueError:
                messagebox.showerror("Błąd", "Nieprawidłowe współrzędne MP - wymagane liczby")
                return

            # Zaktualizuj preset w runtime z przekazaniem analyzer
            if self.preset_manager.update_preset_runtime(
                current_id,
                hp_coords=hp_coords,
                mana_coords=mana_coords,
                apply_immediately=True
            ):
                preset_name = "nieznany"
                preset = self.preset_manager.get_preset_by_id(current_id)
                if preset:
                    preset_name = preset.get('name', current_id)
                    # Natychmiastowe odświeżenie analyzer przez menedżera
                    if hasattr(self, 'bars_analyzer'):
                        # Przekaż analyzer do menedżera do odświeżenia
                        self.preset_manager._refresh_current_preset(self.bars_analyzer)
                        self.apply_bars_positions()  # Natychmiastowe zastosowanie

                self.log_message(f"🔄 Zaktualizowano preset w runtime: {preset_name}")
                messagebox.showinfo("Sukces", f"Zaktualizowano preset: {preset_name}")
            else:
                messagebox.showerror("Błąd", "Nie udało się zaktualizować presetu")

        except Exception as e:
            self.log_message(f"❌ Błąd aktualizacji presetu: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można zaktualizować presetu:\n{str(e)}")

    def load_preset_from_file(self):
        """Wczytuje preset z pliku JSON"""
        try:
            from tkinter import filedialog

            file_path = filedialog.askopenfilename(
                title="Wybierz plik presetu",
                filetypes=[("Pliki JSON", "*.json"), ("Wszystkie pliki", "*.*")]
            )

            if not file_path:
                return

            # Importuj preset przez menedżer
            new_id = self.preset_manager.import_preset(file_path)

            if new_id:
                messagebox.showinfo("Sukces", f"Zaimportowano preset jako: {new_id}")
                # Zastosuj nowy preset
                self.apply_preset_by_id(new_id)
            else:
                messagebox.showerror("Błąd", "Nie udało się zaimportować presetu")

        except Exception as e:
            self.log_message(f"❌ Błąd wczytywania presetu: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można wczytać presetu:\n{str(e)}")

    def save_current_as_preset(self):
        """Zapisuje aktualne ustawienia jako nowy preset"""
        try:
            # Pobierz aktualne współrzędne
            try:
                hp_coords = {
                    'x': int(self.hp_x_var.get()),
                    'y': int(self.hp_y_var.get()),
                    'w': int(self.hp_w_var.get()),
                    'h': int(self.hp_h_var.get())
                }
                mana_coords = {
                    'x': int(self.mana_x_var.get()),
                    'y': int(self.mana_y_var.get()),
                    'w': int(self.mana_w_var.get()),
                    'h': int(self.mana_h_var.get())
                }
            except ValueError:
                messagebox.showerror("Błąd", "Nieprawidłowe wartości współrzędnych")
                return

            # Dialog z nazwą
            from tkinter import simpledialog
            preset_name = simpledialog.askstring(
                "Zapisz Preset",
                "Podaj nazwę presetu:",
                initialvalue=f"Preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            if not preset_name:
                return

            # Dodaj preset przez menedżer
            new_id = self.preset_manager.add_custom_preset(
                name=preset_name,
                hp_coords=hp_coords,
                mana_coords=mana_coords,
                resolution="custom"
            )

            if new_id:
                self.log_message(f"✅ Zapisano preset: {preset_name}")
                messagebox.showinfo("Sukces", f"Zapisano preset jako:\n{preset_name}")

                # Zastosuj nowy preset
                self.preset_manager.set_current_preset(new_id)
            else:
                messagebox.showerror("Błąd", "Nie udało się zapisać presetu")

        except Exception as e:
            self.log_message(f"❌ Błąd zapisu presetu: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można zapisać presetu:\n{str(e)}")

    def apply_current_preset(self):
        """Zastosowuje aktualnie wybrany preset"""
        current_id = self.preset_manager.get_current_preset_id()

        if current_id:
            self.apply_preset_by_id(current_id)
        else:
            messagebox.showinfo("Informacja", "Nie wybrano żadnego presetu.\nUżyj 'Zarządzaj presetami' aby wybrać preset.")

    def test_bar_position(self, bar_type: str, x: int, y: int, w: int, h: int):
        """Testuje pozycję paska rysując prostokąt na podglądzie"""
        try:
            if not hasattr(self, 'preview_canvas') or not self.preview_canvas:
                messagebox.showinfo("Test", f"Test pozycji {bar_type.upper()}:\nX: {x}, Y: {y}\nSzer: {w}, Wys: {h}")
                return

            # Rysuj tymczasowy prostokąt
            import time

            if hasattr(self, 'test_rect_id'):
                self.preview_canvas.delete(self.test_rect_id)

            if hasattr(self, 'test_rect_label'):
                self.preview_canvas.delete(self.test_rect_label)

            # Konwertuj współrzędne na skalę canvasa
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            if canvas_width <= 1 or canvas_height <= 1:
                messagebox.showinfo("Test", f"Test pozycji {bar_type.upper()}:\nX: {x}, Y: {y}\nSzer: {w}, Wys: {h}")
                return

            # Skaluj współrzędne
            scale_x = canvas_width / (self.selected_window['width'] if self.selected_window else 1920)
            scale_y = canvas_height / (self.selected_window['height'] if self.selected_window else 1080)

            canvas_x = x * scale_x
            canvas_y = y * scale_y
            canvas_w = w * scale_x
            canvas_h = h * scale_y

            color = "#00ff00" if bar_type == "hp" else "#0080ff"

            # Narysuj prostokąt
            self.test_rect_id = self.preview_canvas.create_rectangle(
                canvas_x, canvas_y, canvas_x + canvas_w, canvas_y + canvas_h,
                outline=color, width=3, tags="test"
            )

            # Dodaj etykietę
            self.test_rect_label = self.preview_canvas.create_text(
                canvas_x + canvas_w/2, canvas_y - 10,
                text=f"TEST {bar_type.upper()}: {w}x{h}",
                fill=color, font=('Arial', 10, 'bold'), tags="test"
            )

            # Usuń po 3 sekundach
            self.root.after(3000, self._clear_test_rect)

            self.log_message(f"🧪 Test pozycji {bar_type.upper()}: ({x},{y}) {w}x{h}")

        except Exception as e:
            self.log_message(f"❌ Błąd testowania pozycji: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Błąd testowania:\n{str(e)}")

    def _clear_test_rect(self):
        """Usuwa prostokąt testowy"""
        try:
            if hasattr(self, 'preview_canvas') and self.preview_canvas:
                self.preview_canvas.delete("test")
        except:
            pass