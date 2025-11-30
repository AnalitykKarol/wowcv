"""
Główne okno GUI aplikacji - Z INTEGRACJĄ HP ANALYZER + WSZYSTKIE FUNKCJE
Dodano analizę HP gracza z emergency heal system + naprawiono brakujące metody
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
from core.hp_bar_analyzer import PlayerHPBarAnalyzer, add_hp_analysis_to_combat_controller

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

        # === NOWY: HP ANALYZER ===
        self.hp_analyzer = PlayerHPBarAnalyzer(logger)
        self.hp_analyzer_integrated = False

        # HP system configuration
        self.hp_emergency_threshold = 50.0  # Próg emergency heal
        self.hp_analysis_enabled = True
        self.last_hp_analysis_time = 0
        self.hp_analysis_interval = 0.1  # Co 100ms

        # HP statistics
        self.hp_stats = {
            'total_hp_checks': 0,
            'successful_hp_detections': 0,
            'emergency_heals_triggered': 0,
            'last_hp_value': 0,
            'last_hp_color': 'unknown',
            'hp_detection_rate': 0
        }

        # Stan aplikacji
        self.selected_window = None
        self.yolo_active = False
        self.combat_mode = False
        self.detection_thread = None
        self.preview_active = False

        # GUI komponenty
        self.preview_label = None
        self.log_text = None

        # NOWE: HP GUI komponenty
        self.hp_status_label = None
        self.hp_emergency_threshold_scale = None
        self.hp_position_frame = None

        # Diagnostyka
        self.last_frame_time = 0
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = time.time()  # Dodane dla statystyk

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
        self.diagnostic_timer = self.root.after(1000, self.start_diagnostic_timer)

    def update_diagnostic_info(self):
        """Aktualizuje informacje diagnostyczne z HP"""
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
                diagnostic_text += f"  Skuteczność: {capture_stats['success_rate_percent']:.1f}%\n"
                if capture_stats['last_error']:
                    diagnostic_text += f"  Ostatni błąd: {capture_stats['last_error']}\n"
                diagnostic_text += "\n"

            # === NOWY: HP ANALYZER STATS ===
            if self.hp_analyzer:
                try:
                    hp_diag = self.hp_analyzer.get_diagnostic_info()
                    diagnostic_text += "💚 HP ANALYZER:\n"
                    diagnostic_text += f"  Tryb pozycjonowania: {hp_diag['positioning_mode']}\n"
                    diagnostic_text += f"  Cache HP: {hp_diag['cache_status']['has_cache']}\n"
                    if hp_diag['cache_status']['has_cache']:
                        diagnostic_text += f"  Cache confidence: {hp_diag['cache_status']['cache_confidence']:.2f}\n"
                        diagnostic_text += f"  Cache age: {hp_diag['cache_status']['cache_age_seconds']:.1f}s\n"

                    perf = hp_diag['performance']
                    diagnostic_text += f"  Analizy HP: {perf['total_analyses']}\n"
                    diagnostic_text += f"  Sukces: {perf['successful_detections']}\n"
                    diagnostic_text += f"  Skuteczność: {perf['success_rate']:.1f}%\n"
                    diagnostic_text += f"  Średni czas: {perf['avg_analysis_time_ms']:.2f}ms\n"

                    current = hp_diag['current_state']
                    diagnostic_text += f"  Ostatnie HP: {current['last_hp_value']:.1f}% ({current['last_hp_color']})\n"
                    diagnostic_text += f"  Historia HP: {len(current['hp_history'])} próbek\n"
                    diagnostic_text += f"  Emergency threshold: {self.hp_emergency_threshold:.0f}%\n"
                    diagnostic_text += "\n"

                    # HP Statistics
                    diagnostic_text += "💊 HP EMERGENCY SYSTEM:\n"
                    diagnostic_text += f"  Emergency heals: {self.hp_stats['emergency_heals_triggered']}\n"
                    diagnostic_text += f"  Próg emergency: {self.hp_emergency_threshold:.0f}%\n"
                    if hasattr(self.combat_controller, 'emergency_heal_active'):
                        diagnostic_text += f"  Emergency aktywny: {self.combat_controller.emergency_heal_active}\n"
                    diagnostic_text += "\n"

                except Exception as e:
                    diagnostic_text += f"💚 HP ANALYZER: Błąd diagnostyki - {str(e)}\n\n"

            # YOLO Detector Stats
            if self.yolo_detector:
                try:
                    yolo_diag = self.yolo_detector.get_diagnostic_info()
                    diagnostic_text += "🤖 YOLO DETECTOR:\n"
                    diagnostic_text += f"  Model załadowany: {yolo_diag['model_loaded']}\n"
                    diagnostic_text += f"  Wątek inference: {yolo_diag['inference_thread_running']}\n"
                    diagnostic_text += f"  Kolejka inference: {yolo_diag['inference_queue_size']}\n"
                    diagnostic_text += "\n"
                except Exception as e:
                    diagnostic_text += f"🤖 YOLO DETECTOR: Błąd diagnostyki - {str(e)}\n\n"

            # Combat Controller Stats
            if self.combat_controller and self.combat_mode:
                try:
                    combat_stats = self.combat_controller.get_stats()
                    diagnostic_text += "⚔️ COMBAT CONTROLLER:\n"
                    diagnostic_text += f"  Mode: {combat_stats.get('mode', 'unknown')}\n"
                    if hasattr(self.combat_controller, 'player_hp'):
                        diagnostic_text += f"  Player HP: {self.combat_controller.player_hp:.1f}%\n"
                    if hasattr(self.combat_controller, 'emergency_heal_active'):
                        diagnostic_text += f"  Emergency heal: {self.combat_controller.emergency_heal_active}\n"
                    diagnostic_text += "\n"
                except Exception as e:
                    diagnostic_text += f"⚔️ COMBAT CONTROLLER: Błąd diagnostyki - {str(e)}\n\n"

            # Aplikacja Stats
            diagnostic_text += "📱 APLIKACJA:\n"
            diagnostic_text += f"  Wybrane okno: {self.selected_window['title'] if self.selected_window else 'Brak'}\n"
            diagnostic_text += f"  YOLO aktywny: {self.yolo_active}\n"
            diagnostic_text += f"  Tryb walki: {self.combat_mode}\n"
            diagnostic_text += f"  HP Analyzer: {self.hp_analysis_enabled}\n"
            diagnostic_text += f"  Ramki: {self.frame_count}\n"

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
        self.root.title("Enhanced YOLO Game Controller v7.0 + HP Analyzer")
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
        self.setup_hp_tab()  # === NOWA ZAKŁADKA HP ===
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

        self.selected_window_label = ttk.Label(window_frame, text="❌ Brak wybranego okna",
                                             foreground='red', font=('Arial', 10, 'bold'))
        self.selected_window_label.pack(anchor='w', pady=(10, 0))

        # === NOWY: HP STATUS ===
        hp_status_frame = ttk.LabelFrame(control_frame, text="💚 Status HP gracza", padding=15)
        hp_status_frame.pack(fill='x', pady=(0, 10))

        self.hp_status_label = ttk.Label(hp_status_frame, text="❌ HP Analyzer nieaktywny",
                                       foreground='red', font=('Arial', 10, 'bold'))
        self.hp_status_label.pack(anchor='w')

        hp_btn_frame = ttk.Frame(hp_status_frame)
        hp_btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(hp_btn_frame, text="🧪 Test HP", command=self.test_hp_analysis).pack(side='left', padx=(0, 5))
        ttk.Button(hp_btn_frame, text="📊 HP Stats", command=self.show_hp_stats).pack(side='left', padx=(0, 5))
        ttk.Button(hp_btn_frame, text="🔧 Kalibruj HP", command=self.calibrate_hp_position).pack(side='left')

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

        ttk.Button(yolo_btn_frame, text="📊 Info o modelu", command=self.show_model_info).pack(side='left', padx=(0, 5))
        ttk.Button(yolo_btn_frame, text="🧪 Test YOLO", command=self.test_yolo_detection).pack(side='left', padx=(0, 5))

        self.yolo_toggle_btn = ttk.Button(yolo_btn_frame, text="▶️ Włącz YOLOv8", command=self.toggle_yolo)
        self.yolo_toggle_btn.pack(side='left')

        # Progress bar
        self.yolo_progress = ttk.Progressbar(yolo_frame, mode='indeterminate')
        self.yolo_progress.pack(fill='x', pady=(10, 0))

        # === SEKCJA TRYBU WALKI ===
        combat_frame = ttk.LabelFrame(control_frame, text="⚔️ Tryb walki + Emergency Heal", padding=15)
        combat_frame.pack(fill='x', pady=(0, 10))

        combat_status_frame = ttk.Frame(combat_frame)
        combat_status_frame.pack(fill='x')

        self.combat_status_label = ttk.Label(combat_status_frame, text="🔴 Walka: Wyłączona",
                                           foreground='red', font=('Arial', 10, 'bold'))
        self.combat_status_label.pack(side='left')

        self.combat_toggle_btn = ttk.Button(combat_frame, text="⚔️ Włącz walkę",
                                          command=self.toggle_combat_mode)
        self.combat_toggle_btn.pack(anchor='w', pady=(10, 0))

        # Emergency heal threshold
        emergency_frame = ttk.Frame(combat_frame)
        emergency_frame.pack(fill='x', pady=(5, 0))

        ttk.Label(emergency_frame, text="🚨 Próg Emergency Heal (klawisz 4):").pack(anchor='w')
        self.hp_emergency_threshold_scale = ttk.Scale(emergency_frame, from_=10, to=80, orient='horizontal')
        self.hp_emergency_threshold_scale.set(50)
        self.hp_emergency_threshold_scale.pack(fill='x', pady=(5, 0))

        threshold_info = ttk.Label(emergency_frame, text="Gdy HP < threshold → naciśnij '4' na 2s",
                                 font=('Arial', 9), foreground='blue')
        threshold_info.pack(anchor='w', pady=(2, 0))

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

    # === NOWA ZAKŁADKA HP ===
    def setup_hp_tab(self):
        """Zakładka konfiguracji HP Analyzer"""
        hp_frame = ttk.Frame(self.notebook)
        self.notebook.add(hp_frame, text="💚 HP Analyzer")

        # === TRYB POZYCJONOWANIA ===
        mode_frame = ttk.LabelFrame(hp_frame, text="🎯 Tryb pozycjonowania paska HP", padding=15)
        mode_frame.pack(fill='x', pady=(0, 10))

        self.hp_mode_var = tk.StringVar(value="manual")

        mode_btn_frame = ttk.Frame(mode_frame)
        mode_btn_frame.pack(fill='x')

        ttk.Radiobutton(mode_btn_frame, text="📍 Manual", variable=self.hp_mode_var,
                       value="manual", command=self.on_hp_mode_change).pack(side='left', padx=(0, 20))
        ttk.Radiobutton(mode_btn_frame, text="🤖 Auto", variable=self.hp_mode_var,
                       value="auto", command=self.on_hp_mode_change).pack(side='left', padx=(0, 20))
        ttk.Radiobutton(mode_btn_frame, text="🔍 Search", variable=self.hp_mode_var,
                       value="search", command=self.on_hp_mode_change).pack(side='left')

        # === POZYCJA MANUALNA ===
        self.hp_position_frame = ttk.LabelFrame(hp_frame, text="📍 Pozycja manualna (% ekranu)", padding=15)
        self.hp_position_frame.pack(fill='x', pady=(0, 10))

        # X Position
        x_frame = ttk.Frame(self.hp_position_frame)
        x_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(x_frame, text="X (% od lewej):").pack(side='left', padx=(0, 10))
        self.hp_x_scale = ttk.Scale(x_frame, from_=0, to=50, orient='horizontal')
        self.hp_x_scale.set(5)
        self.hp_x_scale.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.hp_x_value_label = ttk.Label(x_frame, text="5%")
        self.hp_x_value_label.pack(side='left')
        self.hp_x_scale.configure(command=self.update_hp_position_labels)

        # Y Position
        y_frame = ttk.Frame(self.hp_position_frame)
        y_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(y_frame, text="Y (% od góry):").pack(side='left', padx=(0, 10))
        self.hp_y_scale = ttk.Scale(y_frame, from_=0, to=50, orient='horizontal')
        self.hp_y_scale.set(5)
        self.hp_y_scale.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.hp_y_value_label = ttk.Label(y_frame, text="5%")
        self.hp_y_value_label.pack(side='left')
        self.hp_y_scale.configure(command=self.update_hp_position_labels)

        # Width
        w_frame = ttk.Frame(self.hp_position_frame)
        w_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(w_frame, text="Szerokość (%):").pack(side='left', padx=(0, 10))
        self.hp_w_scale = ttk.Scale(w_frame, from_=5, to=30, orient='horizontal')
        self.hp_w_scale.set(15)
        self.hp_w_scale.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.hp_w_value_label = ttk.Label(w_frame, text="15%")
        self.hp_w_value_label.pack(side='left')
        self.hp_w_scale.configure(command=self.update_hp_position_labels)

        # Height
        h_frame = ttk.Frame(self.hp_position_frame)
        h_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(h_frame, text="Wysokość (%):").pack(side='left', padx=(0, 10))
        self.hp_h_scale = ttk.Scale(h_frame, from_=1, to=10, orient='horizontal')
        self.hp_h_scale.set(3)
        self.hp_h_scale.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.hp_h_value_label = ttk.Label(h_frame, text="3%")
        self.hp_h_value_label.pack(side='left')
        self.hp_h_scale.configure(command=self.update_hp_position_labels)

        # Apply button
        ttk.Button(self.hp_position_frame, text="✅ Zastosuj pozycję",
                  command=self.apply_hp_position).pack(pady=(10, 0))

        # === KONFIGURACJA KOLORÓW ===
        color_frame = ttk.LabelFrame(hp_frame, text="🎨 Konfiguracja koloru zielonego (HSV)", padding=15)
        color_frame.pack(fill='x', pady=(0, 10))

        # Hue
        hue_frame = ttk.Frame(color_frame)
        hue_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(hue_frame, text="Hue (odcień):").pack(side='left', padx=(0, 10))
        self.hue_min_scale = ttk.Scale(hue_frame, from_=0, to=179, orient='horizontal')
        self.hue_min_scale.set(40)
        self.hue_min_scale.pack(side='left', fill='x', expand=True, padx=(0, 5))
        ttk.Label(hue_frame, text="-").pack(side='left', padx=(0, 5))
        self.hue_max_scale = ttk.Scale(hue_frame, from_=0, to=179, orient='horizontal')
        self.hue_max_scale.set(80)
        self.hue_max_scale.pack(side='left', fill='x', expand=True)

        # Apply colors button
        ttk.Button(color_frame, text="🎨 Zastosuj kolory",
                  command=self.apply_hp_colors).pack(pady=(10, 0))

        # === PRZYCISKI TESTOWE ===
        test_frame = ttk.LabelFrame(hp_frame, text="🧪 Testy i diagnostyka", padding=15)
        test_frame.pack(fill='x', pady=(0, 10))

        test_btn_frame = ttk.Frame(test_frame)
        test_btn_frame.pack(fill='x')

        ttk.Button(test_btn_frame, text="🧪 Test HP", command=self.test_hp_analysis).pack(side='left', padx=(0, 5))
        ttk.Button(test_btn_frame, text="📊 Statystyki", command=self.show_hp_stats).pack(side='left', padx=(0, 5))
        ttk.Button(test_btn_frame, text="🔧 Auto-kalibracja", command=self.calibrate_hp_position).pack(side='left', padx=(0, 5))
        ttk.Button(test_btn_frame, text="💾 Zapisz debug", command=self.save_hp_debug_crop).pack(side='left')

        # === STATUS HP ===
        status_frame = ttk.LabelFrame(hp_frame, text="📊 Aktualny status HP", padding=15)
        status_frame.pack(fill='both', expand=True)

        self.hp_info_text = tk.Text(status_frame, height=10, wrap='word', font=('Consolas', 9))
        hp_info_scrollbar = ttk.Scrollbar(status_frame, orient='vertical', command=self.hp_info_text.yview)
        self.hp_info_text.configure(yscrollcommand=hp_info_scrollbar.set)

        self.hp_info_text.pack(side='left', fill='both', expand=True)
        hp_info_scrollbar.pack(side='right', fill='y')

        # Initial HP info
        initial_hp_text = """💚 HP ANALYZER STATUS

🔧 Konfiguracja:
- Tryb: Manual
- Pozycja: 5%, 5%, 15%x3%
- Próg emergency: 50%

📊 Statystyki:
- Analizy: 0
- Sukces: 0%
- Średni czas: 0ms

💡 Instrukcje:
1. Wybierz okno gry
2. Ustaw pozycję paska HP
3. Przetestuj wykrywanie  
4. Włącz tryb walki

🚨 Emergency Heal:
- Klawisz '4' zostanie naciśnięty na 2s gdy HP < 50%
"""
        self.hp_info_text.insert(1.0, initial_hp_text)

    def update_hp_position_labels(self, value=None):
        """Aktualizuje labele z wartościami pozycji HP"""
        self.hp_x_value_label.config(text=f"{self.hp_x_scale.get():.0f}%")
        self.hp_y_value_label.config(text=f"{self.hp_y_scale.get():.0f}%")
        self.hp_w_value_label.config(text=f"{self.hp_w_scale.get():.0f}%")
        self.hp_h_value_label.config(text=f"{self.hp_h_scale.get():.0f}%")

    def on_hp_mode_change(self):
        """Obsługuje zmianę trybu HP"""
        mode = self.hp_mode_var.get()

        # Włącz/wyłącz manual position frame
        if mode == "manual":
            # Pokaż opcje manual
            for child in self.hp_position_frame.winfo_children():
                child.configure(state='normal')
        else:
            # Ukryj/wyłącz opcje manual
            for child in self.hp_position_frame.winfo_children():
                if isinstance(child, (ttk.Scale, ttk.Button)):
                    child.configure(state='disabled')

        # Zastosuj tryb
        self.hp_analyzer.set_positioning_mode(mode)
        self.log_message(f"🎯 Tryb HP zmieniony na: {mode}")

    def apply_hp_position(self):
        """Stosuje manualną pozycję HP"""
        x_percent = float(self.hp_x_scale.get())
        y_percent = float(self.hp_y_scale.get())
        w_percent = float(self.hp_w_scale.get())
        h_percent = float(self.hp_h_scale.get())

        self.hp_analyzer.set_manual_position(x_percent, y_percent, w_percent, h_percent)
        self.log_message(f"📍 Pozycja HP: {x_percent}%, {y_percent}%, {w_percent}%x{h_percent}%")

        # Test pozycji jeśli mamy okno
        if self.selected_window:
            self.test_hp_analysis()

    def apply_hp_colors(self):
        """Stosuje konfigurację kolorów HP"""
        hue_min = int(self.hue_min_scale.get())
        hue_max = int(self.hue_max_scale.get())

        self.hp_analyzer.configure_green_hsv_advanced(
            hue_min=hue_min,
            hue_max=hue_max,
            sat_min=50,
            sat_max=255,
            val_min=50,
            val_max=255,
            add_noise_filter=True,
            filter_size=2
        )

        self.log_message(f"🎨 Kolory HP: Hue {hue_min}-{hue_max}")

    # === HP TESTING METHODS ===
    def test_hp_analysis(self):
        """Test analizy HP"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
            if frame is None:
                messagebox.showerror("Błąd", "Nie udało się przechwycić obrazu")
                return

            # Test HP
            result = self.hp_analyzer.test_hp_analysis(frame)

            msg = "🧪 TEST ANALIZY HP\n\n"

            for mode_name, mode_result in result.items():
                if mode_name == 'best_recommendation':
                    continue

                if mode_result and mode_result.get('success'):
                    hp = mode_result['hp_percentage']
                    green_data = mode_result.get('green_data', {})
                    green_coverage = green_data.get('green_percentage', 0)
                    region = mode_result.get('region', (0,0,0,0))

                    msg += f"{mode_name.upper()}:\n"
                    msg += f"  HP: {hp:.1f}%\n"
                    msg += f"  Pokrycie zielone: {green_coverage:.1f}%\n"
                    msg += f"  Region: {region[0]},{region[1]} {region[2]-region[0]}x{region[3]-region[1]}\n"
                    msg += f"  Czas: {mode_result.get('analysis_time_ms', 0):.1f}ms\n\n"
                else:
                    msg += f"{mode_name.upper()}: BŁĄD\n\n"

            recommendation = result.get('best_recommendation', {})
            msg += f"🏆 REKOMENDACJA: {recommendation.get('mode', 'brak')}\n"
            msg += f"HP: {recommendation.get('hp_percentage', 0):.1f}%\n"
            msg += f"Powód: {recommendation.get('reason', 'brak')}"

            messagebox.showinfo("Test HP", msg)

            # Aktualizuj status
            self.update_hp_info_display()

        except Exception as e:
            self.log_message(f"Błąd testu HP: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Błąd testu HP:\n{str(e)}")

    def show_hp_stats(self):
        """Pokazuje statystyki HP"""
        try:
            stats = self.hp_analyzer.get_stats()
            diagnostics = self.hp_analyzer.get_diagnostic_info()

            msg = "📊 STATYSTYKI HP ANALYZER\n\n"

            msg += "🔢 PODSTAWOWE:\n"
            msg += f"  Analizy: {stats['total_analyses']}\n"
            msg += f"  Sukces: {stats['successful_detections']}\n"
            msg += f"  Skuteczność: {(stats['successful_detections']/max(1,stats['total_analyses']))*100:.1f}%\n"
            msg += f"  Średni czas: {stats['avg_analysis_time_ms']:.2f}ms\n"
            msg += f"  Cache hits: {stats['cache_hits']}\n\n"

            msg += "💚 AKTUALNY STAN:\n"
            msg += f"  Ostatnie HP: {stats['last_hp_value']:.1f}%\n"
            msg += f"  Kolor: {stats['last_hp_color']}\n\n"

            msg += "🚨 EMERGENCY SYSTEM:\n"
            msg += f"  Próg: {self.hp_emergency_threshold:.0f}%\n"
            msg += f"  Wyzwolone: {self.hp_stats['emergency_heals_triggered']}\n\n"

            cache_status = diagnostics['cache_status']
            msg += "💾 CACHE:\n"
            msg += f"  Status: {'Aktywny' if cache_status['has_cache'] else 'Brak'}\n"
            if cache_status['has_cache']:
                msg += f"  Confidence: {cache_status['cache_confidence']:.2f}\n"
                msg += f"  Wiek: {cache_status['cache_age_seconds']:.1f}s\n"

            messagebox.showinfo("Statystyki HP", msg)

        except Exception as e:
            self.log_message(f"Błąd statystyk HP: {str(e)}", "ERROR")

    def calibrate_hp_position(self):
        """Auto-kalibracja pozycji HP"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
            if frame is None:
                messagebox.showerror("Błąd", "Nie udało się przechwycić obrazu")
                return

            # Kalibracja
            result = self.hp_analyzer.calibrate_hp_position(frame)

            if result['success']:
                hp = result['hp_percentage']
                region = result['region']

                msg = f"✅ KALIBRACJA UDANA!\n\n"
                msg += f"HP wykryte: {hp:.1f}%\n"
                msg += f"Region: {region}\n"
                msg += f"Kolor: {result['dominant_color']}\n\n"
                msg += f"Pozycja została automatycznie ustawiona."

                messagebox.showinfo("Kalibracja HP", msg)
                self.log_message(f"✅ Auto-kalibracja HP: {hp:.1f}% w regionie {region}")

                # Aktualizuj UI
                self.update_hp_info_display()

            else:
                reason = result.get('reason', 'Nieznany błąd')
                messagebox.showerror("Kalibracja HP", f"❌ Kalibracja nieudana:\n{reason}")

        except Exception as e:
            self.log_message(f"Błąd kalibracji HP: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Błąd kalibracji HP:\n{str(e)}")

    def save_hp_debug_crop(self):
        """Zapisuje debug crop HP"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
            if frame is None:
                messagebox.showerror("Błąd", "Nie udało się przechwycić obrazu")
                return

            # Analiza HP
            result = self.hp_analyzer.analyze_player_hp(frame)

            if result['success']:
                filename = self.hp_analyzer.save_debug_crop(frame, result)
                messagebox.showinfo("Debug", f"Debug crop zapisany:\n{filename}")
                self.log_message(f"💾 Debug crop HP: {filename}")
            else:
                messagebox.showerror("Debug", "Nie udało się przeanalizować HP dla debug crop")

        except Exception as e:
            self.log_message(f"Błąd debug crop: {str(e)}", "ERROR")

    def update_hp_info_display(self):
        """Aktualizuje wyświetlanie informacji HP"""
        try:
            if not hasattr(self, 'hp_info_text'):
                return

            stats = self.hp_analyzer.get_stats()
            diagnostics = self.hp_analyzer.get_diagnostic_info()

            info_text = "💚 HP ANALYZER STATUS\n\n"

            info_text += "🔧 KONFIGURACJA:\n"
            info_text += f"- Tryb: {diagnostics['positioning_mode']}\n"
            cache_status = diagnostics['cache_status']
            if cache_status['has_cache']:
                region = cache_status['cached_region']
                info_text += f"- Region: {region}\n"
            info_text += f"- Próg emergency: {self.hp_emergency_threshold:.0f}%\n\n"

            info_text += "📊 STATYSTYKI:\n"
            perf = diagnostics['performance']
            info_text += f"- Analizy: {perf['total_analyses']}\n"
            info_text += f"- Sukces: {perf['success_rate']:.1f}%\n"
            info_text += f"- Średni czas: {perf['avg_analysis_time_ms']:.2f}ms\n"
            info_text += f"- Cache hit rate: {perf['cache_hit_rate']:.1f}%\n\n"

            current = diagnostics['current_state']
            info_text += "💚 AKTUALNY STAN:\n"
            info_text += f"- HP: {current['last_hp_value']:.1f}% ({current['last_hp_color']})\n"
            info_text += f"- Historia: {len(current['hp_history'])} próbek\n"
            info_text += f"- Wygładzanie: {'ON' if current['smoothing_enabled'] else 'OFF'}\n\n"

            info_text += "🚨 EMERGENCY HEAL:\n"
            info_text += f"- Wyzwolone: {self.hp_stats['emergency_heals_triggered']}\n"
            if hasattr(self.combat_controller, 'emergency_heal_active'):
                info_text += f"- Status: {'AKTYWNY' if self.combat_controller.emergency_heal_active else 'Nieaktywny'}\n"

            self.hp_info_text.delete(1.0, tk.END)
            self.hp_info_text.insert(1.0, info_text)

        except Exception as e:
            self.log_message(f"Błąd aktualizacji HP info: {str(e)}", "ERROR")

    def setup_preview_tab(self):
        """Zakładka podglądu z wykryciami YOLO + HP"""
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
                                 text="🎯 Podgląd z wykrywaniami YOLO + HP",
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
        """Zakładka ustawień YOLOv8 + HP"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="⚙️ Ustawienia")

        # Ustawienia wykrywania YOLO
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

        # Ustawienia HP Analysis
        hp_settings_frame = ttk.LabelFrame(settings_frame, text="💚 HP Analysis Settings", padding=15)
        hp_settings_frame.pack(fill='x', pady=(10, 10), padx=10)

        # HP Analysis interval
        ttk.Label(hp_settings_frame, text="Częstotliwość analizy HP (ms):").pack(anchor='w')
        self.hp_interval_scale = ttk.Scale(hp_settings_frame, from_=50, to=500, orient='horizontal')
        self.hp_interval_scale.set(100)
        self.hp_interval_scale.pack(fill='x', pady=(5, 10))

        # HP smoothing
        self.hp_smoothing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(hp_settings_frame, text="Włącz wygładzanie wyników HP",
                       variable=self.hp_smoothing_var, command=self.apply_hp_settings).pack(anchor='w')

        ttk.Button(hp_settings_frame, text="✅ Zastosuj ustawienia HP",
                  command=self.apply_hp_settings).pack(pady=(10, 0))

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
        ttk.Button(test_frame, text="💚 Test HP",
                  command=self.test_hp_analysis).pack(side='left', padx=(0, 5))
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

        self.diagnostic_text.pack(side='left', fill='both', expand=True)
        diagnostic_scrollbar.pack(side='right', fill='y')

    def apply_optimization(self):
        """Aplikuje wybrany tryb optymalizacji"""
        try:
            level = self.optimization_var.get()
            self.yolo_detector.set_optimization_level(level)
            self.log_message(f"⚡ Zastosowano optymalizację: {level}")
        except Exception as e:
            self.log_message(f"Błąd aplikowania optymalizacji: {str(e)}", "ERROR")

    def apply_hp_settings(self):
        """Aplikuje ustawienia HP Analysis"""
        try:
            # HP analysis interval
            interval_ms = float(self.hp_interval_scale.get())
            self.hp_analysis_interval = interval_ms / 1000.0  # Convert to seconds

            # HP smoothing
            smoothing_enabled = self.hp_smoothing_var.get()
            self.hp_analyzer.configure_smoothing(enabled=smoothing_enabled)

            self.log_message(f"💚 HP settings: interval {interval_ms}ms, smoothing: {smoothing_enabled}")

        except Exception as e:
            self.log_message(f"Błąd ustawień HP: {str(e)}", "ERROR")

    # === BRAKUJĄCE FUNKCJE ZE STAREGO PLIKU ===

    def select_window(self):
        """Wybiera okno do przechwytywania i konfiguruje HP analyzer"""
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

        # === KONFIGURUJ HP ANALYZER ===
        self.hp_analyzer.configure_screen_size(window_data['width'], window_data['height'])

        # Zastosuj aktualną pozycję z UI
        self.apply_hp_position()

        # Integruj z combat controller jeśli nie był zintegrowany
        if not self.hp_analyzer_integrated:
            add_hp_analysis_to_combat_controller(self.combat_controller, self.hp_analyzer)
            self.hp_analyzer_integrated = True
            self.log_message("🔗 HP Analyzer zintegrowany z Combat Controller")

        self.log_message(f"Wybrano okno: {window_data['title']} (ID: {window_data['hwnd']})")
        self.hp_status_label.config(text="💚 HP Analyzer skonfigurowany", foreground='green')

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
        if hasattr(self, 'yolo_progress'):
            self.yolo_progress.start()

        self.detection_thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.detection_thread.start()

        self.log_message("🤖 YOLOv8 Detection uruchomiony")

    def stop_yolo_detection(self):
        """Zatrzymuje wykrywanie YOLOv8"""
        self.yolo_active = False
        self.yolo_status_label.config(text="🟢 YOLOv8: Model załadowany", foreground='green')
        self.yolo_toggle_btn.config(text="▶️ Włącz YOLOv8")
        if hasattr(self, 'yolo_progress'):
            self.yolo_progress.stop()

        self.log_message("⏹️ YOLOv8 Detection zatrzymany")

    def toggle_preview(self):
        """Przełącza podgląd"""
        if self.preview_active:
            self.stop_preview()
        else:
            self.start_preview()

    def toggle_combat_mode(self):
        """Przełącza tryb walki z HP emergency"""
        if not self.yolo_active and not self.combat_mode:
            messagebox.showwarning("Błąd", "Najpierw włącz YOLOv8 Detection!")
            return

        self.combat_mode = not self.combat_mode

        if self.combat_mode:
            if not self.yolo_active:
                self.toggle_yolo()

            # Ustaw próg emergency z UI
            self.hp_emergency_threshold = float(self.hp_emergency_threshold_scale.get())
            self.combat_controller.configure_emergency_heal(self.hp_emergency_threshold)

            # NAPRAW: Wymuś integrację HP
            if not self.hp_analyzer_integrated or not hasattr(self.combat_controller, 'update_player_hp'):
                add_hp_analysis_to_combat_controller(self.combat_controller, self.hp_analyzer)
                self.hp_analyzer_integrated = True
                self.log_message("🔗 Wymuszona integracja HP→Combat przy włączaniu walki")

            self.combat_status_label.config(text="🟢 Walka + Emergency Heal: Włączona", foreground='green')
            self.combat_toggle_btn.config(text="⏹️ Wyłącz walkę")
            self.log_message(f"⚔️ Tryb walki włączony (Emergency heal < {self.hp_emergency_threshold:.0f}%)")

            # DEBUG: Sprawdź stan emergency heal
            self.debug_emergency_heal_status()

        else:
            self.combat_status_label.config(text="🔴 Walka: Wyłączona", foreground='red')
            self.combat_toggle_btn.config(text="⚔️ Włącz walkę")

            if self.selected_window:
                self.combat_controller.emergency_stop(self.selected_window['hwnd'])

            self.log_message("⏹️ Tryb walki wyłączony")

    def detection_loop(self):
        """Pętla wykrywania YOLO + HP analysis"""
        detection_count = 0
        hp_analysis_count = 0

        self.log_message(f"🤖 Enhanced YOLO + HP Detection uruchomiony")

        while self.yolo_active:
            try:
                if not self.selected_window:
                    break

                current_time = time.time()
                frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

                if frame is not None and frame.size > 0:
                    try:
                        self.frame_count += 1
                        self.last_frame_time = current_time

                        # === ANALIZA HP GRACZA ===
                        if (self.hp_analysis_enabled and
                                current_time - self.last_hp_analysis_time >= self.hp_analysis_interval):

                            try:
                                hp_result = self.hp_analyzer.analyze_player_hp(frame)
                                self.last_hp_analysis_time = current_time
                                hp_analysis_count += 1

                                if hp_result['success']:
                                    hp_percent = hp_result['hp_percentage']
                                    self.hp_stats['successful_hp_detections'] += 1
                                    self.hp_stats['last_hp_value'] = hp_percent
                                    self.hp_stats['last_hp_color'] = hp_result['dominant_color']

                                    # Update HP status label
                                    color_emoji = {'green': '💚', 'yellow': '💛', 'red': '❤️'}.get(
                                        hp_result['dominant_color'], '💚')
                                    self.hp_status_label.config(
                                        text=f"{color_emoji} HP: {hp_percent:.1f}% ({hp_result['dominant_color']})",
                                        foreground='green' if hp_percent > 25 else 'red'
                                    )

                                    # === NAPRAW: WYMUŚ UPDATE HP W COMBAT CONTROLLER ===
                                    if self.combat_mode:
                                        try:
                                            # Upewnij się że threshold jest ustawiony
                                            current_threshold = float(self.hp_emergency_threshold_scale.get())
                                            if abs(current_threshold - self.hp_emergency_threshold) > 1:
                                                self.hp_emergency_threshold = current_threshold
                                                self.combat_controller.configure_emergency_heal(current_threshold)
                                                self.log_message(f"🎯 Threshold updated: {current_threshold}%")

                                            # KLUCZOWE: Wymuś update HP
                                            if hasattr(self.combat_controller, 'update_player_hp'):
                                                self.combat_controller.update_player_hp(
                                                    hp_percent,
                                                    hp_result['dominant_color']
                                                )

                                                # Debug co 10 analiz
                                                if hp_analysis_count % 10 == 0:
                                                    self.log_message(
                                                        f"🔄 HP→Combat: {hp_percent:.1f}% (threshold: {self.hp_emergency_threshold:.0f}%)")
                                            else:
                                                # Wymuś integrację jeśli nie ma metody
                                                add_hp_analysis_to_combat_controller(self.combat_controller,
                                                                                     self.hp_analyzer)
                                                self.hp_analyzer_integrated = True
                                                self.log_message("🔗 Wymuszona integracja HP→Combat")

                                        except Exception as combat_hp_error:
                                            self.log_message(f"❌ Błąd HP→Combat: {str(combat_hp_error)}", "ERROR")

                                    # Log HP co 30 analiz
                                    if hp_analysis_count % 30 == 0:
                                        green_data = hp_result['green_data']
                                        self.log_message(
                                            f"💚 HP: {hp_percent:.1f}% "
                                            f"(zielone: {green_data['green_percentage']:.1f}%)")

                                self.hp_stats['total_hp_checks'] += 1

                            except Exception as hp_error:
                                self.log_message(f"HP Analysis error: {str(hp_error)}", "ERROR")

                        # === YOLO DETECTION ===
                        confidence_threshold = float(self.confidence_scale.get()) if hasattr(self,
                                                                                             'confidence_scale') else 0.25
                        detections = self.yolo_detector.detect(frame, confidence_threshold)

                        if detections is None:
                            detections = []

                        if len(detections) > 0:
                            detection_count += 1
                            self.detection_count += len(detections)

                            if detection_count % 30 == 0:
                                self.log_message(f"🤖 YOLO: {len(detections)} wykryć (#{detection_count})")

                        # === COMBAT MODE ===
                        if self.combat_mode:
                            try:
                                # Update combat controller
                                self.combat_controller.update(self.selected_window['hwnd'], detections)

                            except Exception as combat_error:
                                self.log_message(f"Combat controller error: {str(combat_error)}", "ERROR")

                        # Zapisz wykrycia dla podglądu
                        self.latest_detections = detections.copy() if detections else []

                    except Exception as detection_error:
                        self.log_message(f"Detection loop error: {str(detection_error)}", "ERROR")

                else:
                    # NAWET BEZ RAMKI WYŚLIJ PUSTĄ LISTĘ
                    if self.combat_mode:
                        try:
                            self.combat_controller.update(self.selected_window['hwnd'], [])
                        except Exception as combat_error:
                            self.log_message(f"Combat controller error (no frame): {str(combat_error)}", "ERROR")

                time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                self.log_message(f"Main loop error: {str(e)}", "ERROR")
                time.sleep(1)

        self.log_message("🏁 Detection loop zakończony")

    def start_preview(self):
        """Uruchamia podgląd"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        self.preview_active = True
        self.preview_status_label.config(text="▶️ Podgląd aktywny")
        self.notebook.select(2)  # Przełącz na zakładkę podglądu

        preview_thread = threading.Thread(target=self.preview_loop, daemon=True)
        preview_thread.start()

        self.log_message("👁️ Podgląd uruchomiony")

    def stop_preview(self):
        """Zatrzymuje podgląd"""
        self.preview_active = False
        self.preview_status_label.config(text="⏹️ Podgląd zatrzymany")
        self.log_message("⏹️ Podgląd zatrzymany")

    def preview_loop(self):
        """Pętla podglądu z wykryciami YOLO i HP"""
        while self.preview_active:
            try:
                if not self.selected_window:
                    break

                frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

                if frame is not None:
                    self.current_image = frame
                    self.frame_count += 1
                    self.last_frame_time = time.time()

                    # Przekaż ramkę do wyświetlenia
                    self.root.after(0, self.scale_and_display_image, frame)
                else:
                    self.log_message("⚠️ Podgląd: Nie udało się przechwycić ramki", "WARNING")

                time.sleep(1/30)  # ~30 FPS

            except Exception as e:
                self.log_message(f"Błąd podglądu: {str(e)}", "ERROR")
                time.sleep(1)

    def on_canvas_configure(self, event):
        """Obsługuje zmianę rozmiaru canvas"""
        if self.current_image is not None:
            self.scale_and_display_image(self.current_image)

    def scale_and_display_image(self, img_array):
        """Wyświetla obraz z wykryciami YOLO i HP"""
        try:
            self.preview_canvas.delete("preview_image")
            self.preview_canvas.delete("no_preview")

            if img_array is None or img_array.size == 0:
                return

            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            if canvas_width <= 1 or canvas_height <= 1:
                return

            display_image = img_array.copy()

            # Dodaj wykrycia YOLO jeśli są dostępne
            if hasattr(self, 'yolo_active') and self.yolo_active and hasattr(self, 'latest_detections'):
                if self.latest_detections and len(self.latest_detections) > 0:
                    try:
                        display_image = self.draw_detections_on_image(display_image, self.latest_detections)
                    except Exception as draw_error:
                        self.log_message(f"Błąd rysowania wykryć: {str(draw_error)}", "ERROR")

            # Dodaj HP overlay jeśli HP analyzer jest aktywny
            if self.hp_analysis_enabled:
                try:
                    hp_result = self.hp_analyzer.analyze_player_hp(display_image)
                    if hp_result['success']:
                        display_image = self.draw_hp_overlay(display_image, hp_result)
                except Exception as hp_error:
                    self.log_message(f"Błąd overlay HP: {str(hp_error)}", "DEBUG")

            # Przeskaluj obraz do canvas
            img_height, img_width = display_image.shape[:2]
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            scale = min(scale_x, scale_y, 1.0)

            new_width = max(1, int(img_width * scale))
            new_height = max(1, int(img_height * scale))

            # Upewnij się że obraz jest uint8
            if display_image.dtype != np.uint8:
                if display_image.max() <= 1.0:
                    display_image = (display_image * 255).astype(np.uint8)
                else:
                    display_image = display_image.astype(np.uint8)

            # Konwertuj do PIL i wyświetl
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

        except Exception as e:
            self.log_message(f"Błąd wyświetlania obrazu: {str(e)}", "ERROR")

    def draw_detections_on_image(self, image, detections):
        """Rysuje wykrycia YOLO na obrazie"""
        if not detections or len(detections) == 0:
            return image

        try:
            result_image = image.copy()

            # Kolory dla różnych typów wykryć
            colors = {
                'health_bar': (0, 255, 0),  # Zielony
                'healthbar': (0, 255, 0),
                'health': (0, 255, 0),
                'bar': (0, 255, 0),
                'mob': (255, 255, 0),       # Żółty
                'enemy': (255, 0, 0),       # Czerwony
                'monster': (255, 0, 0),
                'target': (255, 0, 255),    # Magenta
                'unknown': (255, 255, 255)  # Biały
            }

            for detection in detections:
                try:
                    x1 = detection.get('x1', 0)
                    y1 = detection.get('y1', 0)
                    x2 = detection.get('x2', 0)
                    y2 = detection.get('y2', 0)
                    name = detection.get('name', 'unknown')
                    confidence = detection.get('confidence', 0.0)

                    if x2 <= x1 or y2 <= y1:
                        continue

                    # Przytnij do granic obrazu
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(result_image.shape[1] - 1, x2)
                    y2 = min(result_image.shape[0] - 1, y2)

                    # Wybierz kolor
                    color = colors.get(name.lower(), colors['unknown'])

                    # Narysuj prostokąt
                    cv2.rectangle(result_image, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)

                    # Tekst
                    text = f"{name}: {confidence:.2f}"
                    text_y = int(y1) - 10 if y1 > 30 else int(y2) + 25

                    # Tło dla tekstu
                    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(result_image,
                                  (int(x1), text_y - text_height - 3),
                                  (int(x1) + text_width + 3, text_y + 3),
                                  (0, 0, 0), -1)

                    cv2.putText(result_image, text, (int(x1), text_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                except Exception as draw_error:
                    continue

            return result_image

        except Exception as e:
            self.log_message(f"Błąd rysowania wykryć: {str(e)}", "ERROR")
            return image

    def draw_hp_overlay(self, image, hp_result):
        """Rysuje overlay HP na obrazie"""
        try:
            if not hp_result['success']:
                return image

            x1, y1, x2, y2 = hp_result['region']
            hp_percentage = hp_result['hp_percentage']
            dominant_color = hp_result['dominant_color']

            # Kolory dla HP
            if dominant_color == 'green' or hp_percentage > 60:
                color = (0, 255, 0)
            elif hp_percentage > 25:
                color = (0, 255, 255)  # Żółty
            else:
                color = (0, 0, 255)    # Czerwony

            # Narysuj ramkę HP
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            # Tekst HP
            text = f"HP: {hp_percentage:.1f}%"
            text_y = y1 - 10 if y1 > 30 else y2 + 25

            # Tło dla tekstu
            (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(image,
                         (x1, text_y - text_height - 5),
                         (x1 + text_width + 5, text_y + 5),
                         (0, 0, 0), -1)

            cv2.putText(image, text, (x1, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            return image

        except Exception as e:
            return image

    def take_screenshot(self):
        """Zapisuje screenshot z overlay"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        try:
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
            if frame is not None:
                # Dodaj overlay
                if hasattr(self, 'latest_detections') and self.latest_detections:
                    frame = self.draw_detections_on_image(frame, self.latest_detections)

                if self.hp_analysis_enabled:
                    hp_result = self.hp_analyzer.analyze_player_hp(frame)
                    if hp_result['success']:
                        frame = self.draw_hp_overlay(frame, hp_result)

                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_enhanced_{timestamp}.png"

                img = Image.fromarray(frame)
                img.save(filename)

                self.log_message(f"📸 Screenshot zapisany: {filename}")
                messagebox.showinfo("Sukces", f"Screenshot zapisany jako {filename}")
            else:
                raise Exception("Nie udało się przechwycić obrazu")

        except Exception as e:
            self.log_message(f"Błąd zapisywania screenshot: {str(e)}", "ERROR")
            messagebox.showerror("Błąd", f"Nie można zapisać screenshot:\n{str(e)}")

    def test_window_capture(self):
        """Test przechwytywania okna z diagnostyką"""
        if not self.selected_window:
            messagebox.showwarning("Błąd", "Najpierw wybierz okno")
            return

        self.log_message("🧪 Rozpoczynam test przechwytywania okna...")

        try:
            success = self.window_capture.test_capture(self.selected_window['hwnd'])

            if success:
                self.log_message("✅ Test przechwytywania: SUKCES")

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
                    messagebox.showerror("Test przechwytywania", "❌ BŁĄD\n\nProblem z ponownym przechwyceniem.")
            else:
                stats = self.window_capture.get_capture_stats()
                error_msg = f"❌ BŁĄD przechwytywania\n\nStatystyki:\nPróby: {stats['total_attempts']}\nSukces: {stats['successful_captures']}\nBłędy: {stats['failed_captures']}"
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
            frame = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])
            if frame is None:
                messagebox.showerror("Test YOLO", "❌ Nie udało się przechwycić obrazu")
                return

            detections = self.yolo_detector.test_detection(frame)

            result_msg = f"🤖 Test YOLO zakończony\n\nWykrycia: {len(detections)}\n\n"

            for i, det in enumerate(detections):
                result_msg += f"{i+1}. {det['name']}: {det['confidence']:.2f}\n"
                result_msg += f"   Pozycja: ({det['center_x']}, {det['center_y']})\n"
                result_msg += f"   Rozmiar: {det['width']}x{det['height']}\n\n"

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

            # HP Analyzer
            if self.hp_analyzer:
                hp_stats = self.hp_analyzer.get_stats()
                stats_text += "💚 HP ANALYZER:\n"
                for key, value in hp_stats.items():
                    stats_text += f"  {key}: {value}\n"
                stats_text += "\n"

            # YOLO Detector
            if self.yolo_detector.model_loaded:
                model_info = self.yolo_detector.get_model_info()
                stats_text += "🤖 YOLO DETECTOR:\n"
                stats_text += f"  Model: {model_info.get('model_type', 'Unknown')}\n"
                stats_text += f"  Klasy: {model_info.get('classes_count', 0)}\n"
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

            messagebox.showinfo("Szczegółowe statystyki", stats_text)

        except Exception as e:
            self.log_message(f"Błąd wyświetlania statystyk: {str(e)}", "ERROR")

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

    def __del__(self):
        """Cleanup przy zamykaniu"""
        try:
            if hasattr(self, 'diagnostic_timer') and self.diagnostic_timer:
                self.root.after_cancel(self.diagnostic_timer)
        except:
            pass