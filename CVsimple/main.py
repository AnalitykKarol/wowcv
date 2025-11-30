"""
Enhanced YOLO Game Controller - Główny plik aplikacji
Z ulepszoną diagnostyką i obsługą błędów + HP Analyzer integration
"""
import tkinter as tk
from tkinter import messagebox
import sys
import os
import traceback

# Dodaj ścieżkę do modułów
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """Sprawdza czy wszystkie wymagane biblioteki są zainstalowane"""
    missing_deps = []
    dep_status = {}

    # Lista zależności do sprawdzenia
    dependencies = [
        ('cv2', 'opencv-python'),
        ('win32gui', 'pywin32'),
        ('PIL', 'pillow'),
        ('numpy', 'numpy'),
        ('ultralytics', 'ultralytics')
    ]

    print("=== SPRAWDZANIE ZALEŻNOŚCI ===")

    for module_name, pip_name in dependencies:
        try:
            __import__(module_name)
            print(f"[OK] {pip_name}: OK")
            dep_status[pip_name] = True
        except ImportError:
            print(f"[BRAK] {pip_name}: MISSING")
            missing_deps.append(pip_name)
            dep_status[pip_name] = False

    # Dodatkowe sprawdzenia
    try:
        import torch
        print(f"[OK] torch: OK")
        if torch.cuda.is_available():
            print(f"[CUDA] torch: Dostepne ({torch.cuda.get_device_name(0)})")
        else:
            print(f"[CPU] torch: Niedostepne (CPU only)")
        dep_status['torch'] = True
    except ImportError:
        print(f"[OPTIONAL] torch: BRAK (opcjonalne dla YOLOv8)")
        dep_status['torch'] = False

    if missing_deps:
        error_msg = f"Brakujące biblioteki: {', '.join(missing_deps)}\n\n"
        error_msg += "Zainstaluj za pomocą:\n"
        for dep in missing_deps:
            error_msg += f"pip install {dep}\n"

        # Dodaj informacje o środowisku
        error_msg += f"\nŚrodowisko Python: {sys.version}\n"
        error_msg += f"Ścieżka: {sys.executable}\n"

        print("\n" + error_msg)
        messagebox.showerror("Błąd zależności", error_msg)
        return False, dep_status

    print("[OK] Wszystkie zaleznosci spelnione!")
    return True, dep_status


def test_imports():
    """Testuje importy głównych modułów"""
    print("\n=== TESTOWANIE IMPORTÓW ===")

    import_results = {}

    # Test podstawowych importów z HP integration
    modules_to_test = [
        ('gui.main_window', 'MainWindow'),  # ← Zaktualizowany main_window z HP
        ('app_utils.logger', 'Logger'),
        ('core.window_capture', 'WindowCapture'),
        ('core.yolo_detector', 'OptimizedYOLODetector'),
        ('core.combat_controller', 'ReactiveCombatController'),  # ← Z emergency heal
        ('core.hp_bar_analyzer', 'PlayerBarsAnalyzer')  # ← NOWY: HP Analyzer
    ]

    for module_path, class_name in modules_to_test:
        try:
            if '.' in module_path:
                module = __import__(module_path, fromlist=[class_name])
            else:
                module = __import__(module_path)
            cls = getattr(module, class_name)
            print(f"[OK] {module_path}.{class_name}: OK")
            import_results[f"{module_path}.{class_name}"] = True
        except Exception as e:
            print(f"[ERROR] {module_path}.{class_name}: BLAD - {str(e)}")
            import_results[f"{module_path}.{class_name}"] = False
            # Dla HP analyzer - pokaż szczegóły błęduw
            if 'hp_bar_analyzer' in module_path:
                print(f"   [INFO] Upewnij sie ze plik hp_bar_analyzer.py istnieje i zawiera PlayerHPBarAnalyzer")
            traceback.print_exc()

    return import_results


def test_hp_analyzer():
    """Dodatkowy test HP Analyzer"""
    print("\n=== TEST HP ANALYZER ===")
    try:
        from core.hp_bar_analyzer import PlayerBarsAnalyzer

        # Test tworzenia obiektu
        analyzer = PlayerBarsAnalyzer()
        print("[OK] PlayerBarsAnalyzer: Obiekt utworzony")

        # Test podstawowych metod
        print("[OK] PlayerBarsAnalyzer: Obiekt utworzony bez bledow")

        analyzer.set_hp_position_px(5, 5, 15, 3)
        print("[OK] set_hp_position_px: OK")

        stats = analyzer.get_combined_stats()
        print(f"[OK] get_stats: OK (total_analyses: {stats.get('hp_stats', {}).get('total_analyses', 0)})")

        return True

    except Exception as e:
        print(f"[ERROR] HP Analyzer test failed: {str(e)}")
        print("   [INFO] Sprawdz czy hp_bar_analyzer.py zawiera kod PlayerHPBarAnalyzer")
        traceback.print_exc()
        return False


def create_emergency_logger():
    """Tworzy awaryjny logger jeśli główny nie działa"""
    class EmergencyLogger:
        def info(self, msg):
            print(f"[INFO] {msg}")
        def warning(self, msg):
            print(f"[WARNING] {msg}")
        def error(self, msg):
            print(f"[ERROR] {msg}")
        def debug(self, msg):
            print(f"[DEBUG] {msg}")

    return EmergencyLogger()


def main():
    """Główna funkcja aplikacji z lepszą obsługą błędów + HP integration"""
    # Fix encoding for Windows console
    import sys
    import locale
    if sys.platform.startswith('win'):
        # Set console to UTF-8 mode for Windows
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # UTF-8 code page
        except:
            pass  # If this fails, continue without UTF-8 console

    print("Enhanced YOLO Game Controller v7.0 + HP Analyzer")
    print("=" * 55)

    try:
        # Sprawdź zależności
        deps_ok, dep_status = check_dependencies()
        if not deps_ok:
            return 1

        # Test importów
        import_results = test_imports()
        failed_imports = [k for k, v in import_results.items() if not v]

        # Importowanie głównych komponentów
        from gui.main_window import MainWindow

        if failed_imports:
            error_msg = f"Błędy importu modułów:\n" + "\n".join(failed_imports)
            print(f"\n[ERROR] {error_msg}")

            # Specjalne sprawdzenie dla HP analyzer
            if any('hp_bar_analyzer' in imp for imp in failed_imports):
                print("\n[INFO] INSTRUKCJE HP ANALYZER:")
                print("1. Skopiuj kod PlayerHPBarAnalyzer do pliku hp_bar_analyzer.py")
                print("2. Lub zmień nazwę hp_bar_analyzer_enhanced.py na hp_bar_analyzer.py")
                print("3. Upewnij się że zawiera klasę PlayerHPBarAnalyzer")

            messagebox.showerror("Błąd importu", error_msg)
            return 1

        # Test HP Analyzer
        hp_test_ok = test_hp_analyzer()
        if not hp_test_ok:
            print("[WARNING] HP Analyzer nie przeszedł testów - funkcja może być ograniczona")

        # Importuj komponenty
        try:
            from gui.main_window import MainWindow
            from app_utils.logger import Logger
            print("[OK] Glowne moduly zaimportowane")
        except Exception as e:
            print(f"[ERROR] Krytyczny blad importu: {str(e)}")
            traceback.print_exc()
            messagebox.showerror("Błąd krytyczny", f"Nie można zaimportować głównych modułów:\n{str(e)}")
            return 1

        # Inicjalizacja loggera
        try:
            logger = Logger()
            logger.info("Uruchamianie Enhanced YOLO Game Controller v7.0 + HP Analyzer...")
            self.logger.info_with_fix("Uruchamianie Enhanced YOLO Game Controller v7.0 + HP Analyzer...")
            logger.info(f"Python: {sys.version}")
            logger.info(f"Ścieżka: {sys.executable}")

            # Log dependency status
            for dep, status in dep_status.items():
                logger.info(f"Dependency {dep}: {'OK' if status else 'MISSING'}")

            # Log HP analyzer status
            logger.info(f"HP Analyzer: {'OK' if hp_test_ok else 'LIMITED'}")

        except Exception as e:
            print(f"[WARNING] Nie mozna utworzyc loggera: {str(e)}")
            logger = create_emergency_logger()
            logger.warning(f"Używam awaryjnego loggera: {str(e)}")

        # Tworzenie głównego okna
        try:
            print("\n=== URUCHAMIANIE GUI ===")
            root = tk.Tk()

            # Test czy Tkinter działa
            root.withdraw()  # Ukryj na chwilę
            root.update()
            root.deiconify()  # Pokaż z powrotem

            logger.info("Tkinter: OK")

        except Exception as e:
            error_msg = f"Błąd inicjalizacji Tkinter: {str(e)}"
            print(f"[ERROR] {error_msg}")
            logger.error(error_msg)
            messagebox.showerror("Błąd GUI", error_msg)
            return 1

        # Tworzenie aplikacji
        try:
            logger.info("Tworzenie głównego okna aplikacji z HP integration...")
            app = MainWindow(root, logger)
            logger.info("Aplikacja utworzona pomyślnie")

            # Sprawdź czy HP analyzer jest dostępny
            if hasattr(app, 'hp_analyzer'):
                logger.info("HP Analyzer zintegrowany pomyślnie")
            else:
                logger.warning("HP Analyzer nie został zintegrowany")

        except Exception as e:
            error_msg = f"Błąd tworzenia aplikacji: {str(e)}"
            print(f"[ERROR] {error_msg}")
            logger.error(error_msg)
            traceback.print_exc()

            # Sprawdź czy to błąd HP analyzer
            if 'hp_bar_analyzer' in str(e).lower() or 'PlayerBarsAnalyzer' in str(e):
                additional_info = "\n\n[INFO] Moze to byc problem z HP Analyzer.\nSprawdz czy plik hp_bar_analyzer.py zawiera PlayerBarsAnalyzer"
                messagebox.showerror("Błąd aplikacji", f"Nie można utworzyć aplikacji:\n{str(e)}{additional_info}")
            else:
                messagebox.showerror("Błąd aplikacji", f"Nie można utworzyć aplikacji:\n{str(e)}")
            return 1

        # Uruchomienie głównej pętli
        try:
            logger.info("Uruchamianie głównej pętli GUI...")
            print("[OK] Aplikacja uruchomiona pomyslnie!")
            print("[GAME] Sprawdz okno aplikacji")
            print("[HP] HP Analyzer: Emergency heal przy HP < 50%")

            # Dodaj handler dla zamykania okna
            def on_closing():
                try:
                    logger.info("Zamykanie aplikacji...")

                    # Cleanup YOLO detector
                    if hasattr(app, 'yolo_detector'):
                        app.yolo_detector.stop_inference_thread()
                        logger.info("YOLO detector zatrzymany")

                    # Cleanup combat controller (z emergency heal)
                    if hasattr(app, 'combat_controller'):
                        if hasattr(app, 'selected_window') and app.selected_window:
                            app.combat_controller.emergency_stop(app.selected_window['hwnd'])
                        logger.info("Combat controller zatrzymany")

                    # Cleanup HP analyzer
                    if hasattr(app, 'hp_analyzer'):
                        logger.info("HP analyzer zatrzymany")

                    logger.info("Cleanup zakończony")
                except Exception as cleanup_error:
                    logger.error(f"Błąd cleanup: {str(cleanup_error)}")
                finally:
                    root.quit()
                    root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_closing)

            # Uruchom główną pętlę
            root.mainloop()

            logger.info("Aplikacja zakończona normalnie")
            return 0

        except KeyboardInterrupt:
            print("\n[INFO] Przerwano przez użytkownika (Ctrl+C)")
            logger.info("Aplikacja przerwana przez użytkownika")
            return 0

        except Exception as e:
            error_msg = f"Błąd głównej pętli: {str(e)}"
            print(f"[ERROR] {error_msg}")
            logger.error(error_msg)
            traceback.print_exc()
            messagebox.showerror("Błąd runtime", error_msg)
            return 1

    except Exception as e:
        # Catch-all dla nieoczekiwanych błędów
        error_msg = f"Nieoczekiwany błąd krytyczny: {str(e)}"
        print(f"[CRITICAL] {error_msg}")
        traceback.print_exc()

        try:
            messagebox.showerror("Błąd krytyczny", f"Krytyczny błąd aplikacji:\n\n{str(e)}\n\nSprawdź konsolę dla szczegółów.")
        except:
            pass  # Messagebox może nie działać w niektórych przypadkach

        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except SystemExit:
        pass
    except Exception as e:
        print(f"[CRITICAL] KRYTYCZNY BLAD: {str(e)}")
        traceback.print_exc()
        sys.exit(1)