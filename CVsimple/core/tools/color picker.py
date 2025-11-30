"""
Color Picker Tool - Standalone Application
Narzędzie do wybierania koordynatów i kolorów dla ColorTriggerSystem
"""
import tkinter as tk
from tkinter import ttk, messagebox
import time
from PIL import Image, ImageTk
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32api
from ctypes import windll


class WindowCapture:
    """Ulepszona klasa do przechwytywania okien"""

    def __init__(self):
        self.windows = []

    def get_window_list(self):
        """Pobiera listę dostępnych okien"""
        windows = []

        def enum_windows_proc(hwnd, param):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and len(title) > 3:
                    try:
                        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                        width = right - left
                        height = bottom - top

                        if width > 100 and height > 100:
                            windows.append({
                                'hwnd': hwnd,
                                'title': title,
                                'width': width,
                                'height': height,
                                'rect': (left, top, right, bottom)
                            })
                    except:
                        pass
            return True

        win32gui.EnumWindows(enum_windows_proc, None)
        self.windows = windows
        return windows

    def capture_window_screenshot(self, hwnd):
        """Przechwytuje screenshot okna - NAPRAWIONA WERSJA"""
        try:
            # Sprawdź czy okno jest zminimalizowane
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)

            # Przenieś okno na pierwszy plan
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)

            # Pobierz współrzędne okna (względem całego ekranu)
            window_rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = window_rect

            # Pobierz współrzędne części klienta (bez ramek okna)
            client_rect = win32gui.GetClientRect(hwnd)
            client_left, client_top, client_right, client_bottom = client_rect

            # Oblicz przesunięcie dla paska tytułowego i ramek
            point = win32gui.ClientToScreen(hwnd, (0, 0))
            client_left_screen, client_top_screen = point

            # Rozmiary części klienta
            client_width = client_right - client_left
            client_height = client_bottom - client_top

            print(f"Window rect: {window_rect}")
            print(f"Client rect: {client_rect}")
            print(f"Client screen pos: {client_left_screen}, {client_top_screen}")
            print(f"Client size: {client_width}x{client_height}")

            # Metoda 1: Spróbuj PrintWindow (najlepsza dla większości aplikacji)
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, client_width, client_height)
            saveDC.SelectObject(saveBitMap)

            # Spróbuj różne flagi PrintWindow
            result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)  # PW_CLIENTONLY

            if not result:
                result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0)  # Cała zawartość

            if not result:
                result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)  # PW_RENDERFULLCONTENT

            if result:
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)

                img = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1
                )

                img_array = np.array(img)
                screenshot = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

                # Cleanup
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)

                return screenshot, (client_left_screen, client_top_screen)

            # Cleanup w przypadku niepowodzenia PrintWindow
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

            # Metoda 2: Fallback - screenshot całego ekranu i wycinanie
            print("PrintWindow failed, using screen capture fallback")

            # Screenshot całego ekranu
            import pyautogui
            full_screenshot = pyautogui.screenshot()
            full_array = np.array(full_screenshot)
            full_array = cv2.cvtColor(full_array, cv2.COLOR_RGB2BGR)

            # Wytnij obszar okna (część klienta)
            cropped = full_array[
                client_top_screen:client_top_screen + client_height,
                client_left_screen:client_left_screen + client_width
            ]

            return cropped, (client_left_screen, client_top_screen)

        except Exception as e:
            print(f"Błąd przechwytywania: {e}")
            return None, None


class ColorPickerTool:
    def __init__(self, root):
        self.root = root
        self.window_capture = WindowCapture()
        self.selected_window = None
        self.current_image = None
        self.current_image_array = None
        self.window_offset = (0, 0)  # Przesunięcie okna na ekranie
        self.scale_factor = 1.0
        self.picked_points = []

        # Ustawienia
        self.region_size = 5
        self.tolerance = 30

        self.setup_window()
        self.setup_ui()
        self.refresh_windows()

    def setup_window(self):
        """Konfiguracja okna głównego"""
        self.root.title("🎯 Color Picker Tool - Game Automation (FIXED)")
        self.root.geometry("1400x900")
        self.root.minsize(800, 600)

    def setup_ui(self):
        """Tworzenie interfejsu użytkownika"""
        # Główny container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Panel górny - kontrole
        control_frame = ttk.LabelFrame(main_frame, text="🎮 Kontrole", padding=10)
        control_frame.pack(fill='x', pady=(0, 10))

        # Wybór okna
        window_frame = ttk.Frame(control_frame)
        window_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(window_frame, text="Wybierz okno:").pack(side='left')

        self.window_combo = ttk.Combobox(window_frame, width=50, state='readonly')
        self.window_combo.pack(side='left', padx=(10, 10))

        ttk.Button(window_frame, text="🔄 Odśwież", command=self.refresh_windows).pack(side='left', padx=(0, 10))
        ttk.Button(window_frame, text="📸 Screenshot", command=self.take_screenshot).pack(side='left', padx=(0, 10))
        ttk.Button(window_frame, text="🧹 Wyczyść punkty", command=self.clear_points).pack(side='left')

        # Ustawienia
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(fill='x', pady=(10, 0))

        ttk.Label(settings_frame, text="Region:").pack(side='left')
        self.region_var = tk.StringVar(value="5")
        region_spin = ttk.Spinbox(settings_frame, from_=3, to=15, width=5, textvariable=self.region_var,
                                 command=self.update_settings)
        region_spin.pack(side='left', padx=(5, 20))

        ttk.Label(settings_frame, text="Tolerancja:").pack(side='left')
        self.tolerance_var = tk.StringVar(value="30")
        tolerance_spin = ttk.Spinbox(settings_frame, from_=5, to=100, width=5, textvariable=self.tolerance_var,
                                   command=self.update_settings)
        tolerance_spin.pack(side='left', padx=(5, 20))

        # Status
        self.status_label = ttk.Label(settings_frame, text="🔴 Brak obrazu", foreground='red')
        self.status_label.pack(side='right')

        # Panel środkowy - podział na obraz i szczegóły
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill='both', expand=True)

        # Lewa strona - obraz
        image_frame = ttk.LabelFrame(middle_frame, text="🖼️ Screenshot (kliknij aby wybrać punkt)", padding=5)
        image_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

        # Canvas z scrollbarami
        canvas_frame = ttk.Frame(image_frame)
        canvas_frame.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg='black', cursor='crosshair')
        h_scroll = ttk.Scrollbar(canvas_frame, orient='horizontal', command=self.canvas.xview)
        v_scroll = ttk.Scrollbar(canvas_frame, orient='vertical', command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        self.canvas.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')

        # Bind kliknięcia
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<Motion>', self.on_canvas_motion)

        # Prawa strona - szczegóły
        details_frame = ttk.Frame(middle_frame)
        details_frame.pack(side='right', fill='y', padx=(5, 0))

        # Podgląd regionu
        preview_frame = ttk.LabelFrame(details_frame, text="🔍 Podgląd regionu (zoom 10x)", padding=10)
        preview_frame.pack(fill='x', pady=(0, 10))

        self.preview_canvas = tk.Canvas(preview_frame, width=150, height=150, bg='gray')
        self.preview_canvas.pack()

        # Informacje o kolorze
        color_frame = ttk.LabelFrame(details_frame, text="🎨 Informacje o kolorze", padding=10)
        color_frame.pack(fill='x', pady=(0, 10))

        self.coord_label = ttk.Label(color_frame, text="Koordynaty: -")
        self.coord_label.pack(anchor='w')

        self.screen_coord_label = ttk.Label(color_frame, text="Ekran: -")
        self.screen_coord_label.pack(anchor='w')

        self.rgb_label = ttk.Label(color_frame, text="RGB: -")
        self.rgb_label.pack(anchor='w')

        self.hsv_label = ttk.Label(color_frame, text="HSV: -")
        self.hsv_label.pack(anchor='w')

        # Próbka koloru
        self.color_sample = tk.Frame(color_frame, width=50, height=30, bg='gray')
        self.color_sample.pack(pady=5)

        # Lista wybranych punktów
        points_frame = ttk.LabelFrame(details_frame, text="📍 Wybrane punkty", padding=10)
        points_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Lista punktów
        list_container = ttk.Frame(points_frame)
        list_container.pack(fill='both', expand=True)

        self.points_listbox = tk.Listbox(list_container, height=8, font=('Consolas', 9))
        points_scroll = ttk.Scrollbar(list_container, orient='vertical', command=self.points_listbox.yview)
        self.points_listbox.configure(yscrollcommand=points_scroll.set)

        self.points_listbox.pack(side='left', fill='both', expand=True)
        points_scroll.pack(side='right', fill='y')

        # Przyciski dla punktów
        points_btn_frame = ttk.Frame(points_frame)
        points_btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(points_btn_frame, text="❌ Usuń", command=self.remove_selected_point).pack(side='left', padx=(0, 5))
        ttk.Button(points_btn_frame, text="💾 Generuj kod", command=self.generate_config_code).pack(side='left')

        # Panel dolny - generowany kod
        code_frame = ttk.LabelFrame(main_frame, text="⚙️ Generowany kod konfiguracji", padding=10)
        code_frame.pack(fill='x', pady=(10, 0))

        code_container = ttk.Frame(code_frame)
        code_container.pack(fill='both', expand=True)

        self.code_text = tk.Text(code_container, height=8, font=('Consolas', 9), wrap='word')
        code_scroll = ttk.Scrollbar(code_container, orient='vertical', command=self.code_text.yview)
        self.code_text.configure(yscrollcommand=code_scroll.set)

        self.code_text.pack(side='left', fill='both', expand=True)
        code_scroll.pack(side='right', fill='y')

        code_btn_frame = ttk.Frame(code_frame)
        code_btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(code_btn_frame, text="📋 Kopiuj do schowka", command=self.copy_to_clipboard).pack(side='left')

    def refresh_windows(self):
        """Odświeża listę dostępnych okien"""
        try:
            windows = self.window_capture.get_window_list()

            window_titles = []
            self.windows_data = {}

            for window in windows:
                display_text = f"{window['title']} ({window['width']}x{window['height']})"
                window_titles.append(display_text)
                self.windows_data[display_text] = window

            self.window_combo['values'] = window_titles
            if window_titles:
                self.window_combo.set(window_titles[0])

            print(f"Znaleziono {len(windows)} okien")

        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można odświeżyć listy okien:\n{str(e)}")

    def take_screenshot(self):
        """Robi screenshot wybranego okna - NAPRAWIONA WERSJA"""
        selected = self.window_combo.get()
        if not selected or selected not in self.windows_data:
            messagebox.showwarning("Błąd", "Wybierz okno z listy")
            return

        self.selected_window = self.windows_data[selected]

        try:
            # Przechwytywanie obrazu z informacją o przesunięciu
            result = self.window_capture.capture_window_screenshot(self.selected_window['hwnd'])

            if result[0] is not None:
                image_array, window_offset = result
                self.window_offset = window_offset

                print(f"Window offset: {self.window_offset}")

                # Konwertuj BGR->RGB dla PIL
                image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
                self.current_image_array = image_rgb

                # Stwórz obraz PIL
                self.current_image = Image.fromarray(image_rgb)

                # Wyświetl na canvas
                self.display_image_on_canvas()

                # Aktualizuj status
                self.status_label.config(text="🟢 Obraz załadowany - koordynaty względem okna", foreground='green')

                print(f"Screenshot: {image_rgb.shape}, offset: {self.window_offset}")

            else:
                messagebox.showerror("Błąd", "Nie udało się zrobić screenshot")

        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd podczas screenshot:\n{str(e)}")

    def display_image_on_canvas(self):
        """Wyświetla obraz na canvas z automatycznym skalowaniem"""
        if self.current_image is None:
            return

        # Usuń poprzedni obraz
        self.canvas.delete("all")

        # Pobierz rozmiary canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            self.root.after(100, self.display_image_on_canvas)
            return

        # Oblicz skalowanie
        img_width, img_height = self.current_image.size
        scale_x = canvas_width / img_width
        scale_y = canvas_height / img_height
        self.scale_factor = min(scale_x, scale_y, 1.0)  # Nie powiększaj ponad oryginał

        # Przeskaluj obraz
        new_width = int(img_width * self.scale_factor)
        new_height = int(img_height * self.scale_factor)

        displayed_image = self.current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(displayed_image)

        # Wyświetl na canvas
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo, tags="image")

        # Narysuj istniejące punkty
        self.draw_picked_points()

        # Ustaw scroll region
        self.canvas.configure(scrollregion=(0, 0, new_width, new_height))

    def on_canvas_click(self, event):
        """Obsługuje kliknięcie na canvas"""
        if self.current_image_array is None:
            return

        # Przelicz koordynaty na oryginalne (względem okna)
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        orig_x = int(canvas_x / self.scale_factor)
        orig_y = int(canvas_y / self.scale_factor)

        # Sprawdź czy w granicach obrazu
        img_height, img_width = self.current_image_array.shape[:2]
        if 0 <= orig_x < img_width and 0 <= orig_y < img_height:
            self.pick_color_at_point(orig_x, orig_y)

    def on_canvas_motion(self, event):
        """Obsługuje ruch myszy nad canvas - podgląd na żywo"""
        if self.current_image_array is None:
            return

        # Przelicz koordynaty
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        orig_x = int(canvas_x / self.scale_factor)
        orig_y = int(canvas_y / self.scale_factor)

        # Sprawdź czy w granicach
        img_height, img_width = self.current_image_array.shape[:2]
        if 0 <= orig_x < img_width and 0 <= orig_y < img_height:
            self.preview_color_at_point(orig_x, orig_y)

    def pick_color_at_point(self, x, y):
        """Wybiera kolor w punkcie i dodaje do listy"""
        color_info = self.analyze_color_region(x, y)
        if color_info:
            # Oblicz koordynaty na ekranie
            screen_x = x + self.window_offset[0]
            screen_y = y + self.window_offset[1]

            # Dodaj do listy punktów
            point_data = {
                'x': x,  # Koordynaty względem okna
                'y': y,
                'screen_x': screen_x,  # Koordynaty na ekranie
                'screen_y': screen_y,
                'rgb': color_info['avg_rgb'],
                'hsv': color_info['avg_hsv'],
                'name': f"point_{len(self.picked_points)+1}"
            }

            self.picked_points.append(point_data)
            self.update_points_list()
            self.draw_picked_points()

            print(f"Wybrano punkt: okno({x}, {y}) ekran({screen_x}, {screen_y}) RGB{color_info['avg_rgb']}")

    def preview_color_at_point(self, x, y):
        """Podgląd koloru w punkcie (bez dodawania do listy)"""
        color_info = self.analyze_color_region(x, y)
        if color_info:
            # Oblicz koordynaty na ekranie
            screen_x = x + self.window_offset[0]
            screen_y = y + self.window_offset[1]

            # Aktualizuj labele
            self.coord_label.config(text=f"Okno: ({x}, {y})")
            self.screen_coord_label.config(text=f"Ekran: ({screen_x}, {screen_y})")
            self.rgb_label.config(text=f"RGB: {color_info['avg_rgb']}")
            self.hsv_label.config(text=f"HSV: {color_info['avg_hsv']}")

            # Aktualizuj próbkę koloru
            rgb = color_info['avg_rgb']
            color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            self.color_sample.config(bg=color_hex)

            # Pokaż region w podglądzie
            self.show_region_preview(color_info['region'])

    def analyze_color_region(self, center_x, center_y):
        """Analizuje region wokół punktu"""
        if self.current_image_array is None:
            return None

        img_height, img_width = self.current_image_array.shape[:2]
        region_size = int(self.region_var.get())
        half_size = region_size // 2

        # Oblicz granice regionu
        x1 = max(0, center_x - half_size)
        y1 = max(0, center_y - half_size)
        x2 = min(img_width, center_x + half_size + 1)
        y2 = min(img_height, center_y + half_size + 1)

        # Wytnij region
        region = self.current_image_array[y1:y2, x1:x2]

        if region.size == 0:
            return None

        # Oblicz średni kolor
        avg_rgb = np.mean(region, axis=(0, 1)).astype(int)

        # Konwertuj do HSV
        hsv_region = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
        avg_hsv = np.mean(hsv_region, axis=(0, 1)).astype(int)

        return {
            'avg_rgb': tuple(avg_rgb),
            'avg_hsv': tuple(avg_hsv),
            'region': region,
            'bounds': (x1, y1, x2, y2)
        }

    def show_region_preview(self, region):
        """Pokazuje powiększony region w podglądzie"""
        if region is None or region.size == 0:
            return

        try:
            # Powiększ region 10x
            zoom_factor = 10
            region_height, region_width = region.shape[:2]

            zoomed = cv2.resize(region,
                              (region_width * zoom_factor, region_height * zoom_factor),
                              interpolation=cv2.INTER_NEAREST)

            # Konwertuj do PIL
            region_pil = Image.fromarray(zoomed)

            # Przeskaluj do canvas (150x150)
            region_pil = region_pil.resize((150, 150), Image.Resampling.NEAREST)

            # Wyświetl
            self.preview_photo = ImageTk.PhotoImage(region_pil)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(75, 75, image=self.preview_photo)

        except Exception as e:
            print(f"Błąd podglądu regionu: {e}")

    def draw_picked_points(self):
        """Rysuje wybrane punkty na canvas"""
        # Usuń poprzednie punkty
        self.canvas.delete("point")

        for i, point in enumerate(self.picked_points):
            # Przelicz na koordynaty canvas
            canvas_x = point['x'] * self.scale_factor
            canvas_y = point['y'] * self.scale_factor

            # Narysuj krzyżyk
            size = 8
            self.canvas.create_line(canvas_x - size, canvas_y, canvas_x + size, canvas_y,
                                  fill='red', width=3, tags="point")
            self.canvas.create_line(canvas_x, canvas_y - size, canvas_x, canvas_y + size,
                                  fill='red', width=3, tags="point")

            # Numer punktu
            self.canvas.create_text(canvas_x + 15, canvas_y - 15, text=str(i+1),
                                  fill='yellow', font=('Arial', 12, 'bold'), tags="point")

    def update_points_list(self):
        """Aktualizuje listę wybranych punktów"""
        self.points_listbox.delete(0, tk.END)

        for i, point in enumerate(self.picked_points):
            rgb = point['rgb']
            text = f"{i+1}. W({point['x']}, {point['y']}) S({point['screen_x']}, {point['screen_y']}) RGB{rgb}"
            self.points_listbox.insert(tk.END, text)

    def remove_selected_point(self):
        """Usuwa wybrany punkt z listy"""
        selection = self.points_listbox.curselection()
        if selection:
            index = selection[0]
            del self.picked_points[index]
            self.update_points_list()
            self.draw_picked_points()

    def clear_points(self):
        """Czyści wszystkie punkty"""
        self.picked_points.clear()
        self.update_points_list()
        self.draw_picked_points()
        self.code_text.delete(1.0, tk.END)

    def update_settings(self):
        """Aktualizuje ustawienia tolerancji i regionu"""
        try:
            self.region_size = int(self.region_var.get())
            self.tolerance = int(self.tolerance_var.get())
        except:
            pass

    def generate_config_code(self):
        """Generuje kod konfiguracyjny"""
        if not self.picked_points:
            messagebox.showwarning("Błąd", "Najpierw wybierz punkty na obrazie")
            return

        tolerance = int(self.tolerance_var.get())

        code = f"""# Color Trigger System Configuration
# Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}
# Window: {self.selected_window['title'] if self.selected_window else 'Unknown'}
# Window offset: {self.window_offset}

TRIGGER_POINTS = [
"""

        for i, point in enumerate(self.picked_points):
            rgb = point['rgb']
            name = f"trigger_{i+1}"
            key = "0x39"  # Klawisz '9' domyślnie

            code += f"""    {{
        # Koordynaty względem okna aplikacji
        "x": {point['x']},
        "y": {point['y']}, 
        # Koordynaty na ekranie (dla weryfikacji)
        "screen_x": {point['screen_x']},
        "screen_y": {point['screen_y']},
        "color": {rgb},
        "key": {key},  # Klawisz '9' - zmień jeśli potrzebujesz
        "tolerance": {tolerance},
        "name": "{name}",
        "enabled": True
    }},
"""

        code += f"""]

# Ustawienia systemu
REGION_SIZE = {self.region_var.get()}  # Rozmiar regionu do sprawdzania
DEFAULT_TOLERANCE = {tolerance}  # Domyślna tolerancja kolorów
WINDOW_OFFSET = {self.window_offset}  # Przesunięcie okna na ekranie

# Przykład użycia w ColorTriggerSystem:
# trigger_system = ColorTriggerSystem(combat_controller)
# trigger_system.load_config(TRIGGER_POINTS)

# UWAGA: Koordynaty są podane względem okna aplikacji.
# Jeśli okno zostanie przesunięte, koordynaty ekranowe zmienią się,
# ale koordynaty względem okna pozostaną prawidłowe.
"""

        self.code_text.delete(1.0, tk.END)
        self.code_text.insert(1.0, code)

        print("Kod konfiguracyjny wygenerowany")

    def copy_to_clipboard(self):
        """Kopiuje kod do schowka"""
        code = self.code_text.get(1.0, tk.END)
        if code.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            messagebox.showinfo("Sukces", "Kod skopiowany do schowka!")
        else:
            messagebox.showwarning("Błąd", "Brak kodu do skopiowania")


if __name__ == "__main__":
    # Sprawdź czy wymagane biblioteki są dostępne
    try:
        import pyautogui
    except ImportError:
        print("BŁĄD: Wymagana biblioteka pyautogui nie jest zainstalowana")
        print("Zainstaluj przez: pip install pyautogui")
        input("Naciśnij Enter aby zakończyć...")
        exit(1)

    root = tk.Tk()
    app = ColorPickerTool(root)

    # Instrukcja w konsoli
    print("""
🎯 COLOR PICKER TOOL - NAPRAWIONA WERSJA - INSTRUKCJA:

NAPRAWY:
✅ Prawidłowe przechwytywanie zawartości okna (nie całego ekranu)
✅ Koordynaty względem okna aplikacji  
✅ Fallback do screenshot ekranu jeśli PrintWindow nie działa
✅ Wyświetlanie koordynatów okna i ekranu
✅ Lepsze debugowanie przesunięć okna

INSTRUKCJA:
1. Wybierz okno z listy i naciśnij 'Screenshot'
2. Kliknij na obrazie w miejsca które chcesz monitorować  
3. Dostosuj region i tolerancję w ustawieniach
4. Naciśnij 'Generuj kod' aby otrzymać konfigurację
5. Skopiuj kod i wklej do ColorTriggerSystem

UWAGI:
- Koordynaty "W" to pozycja względem okna aplikacji
- Koordynaty "S" to pozycja na ekranie (dla weryfikacji)
- Czerwone krzyżyki pokazują wybrane punkty
- Jeśli PrintWindow nie działa, używany jest fallback screenshot

WYMAGANIA:
- pip install pyautogui (dla fallback screenshot)
- Pozostałe biblioteki: opencv-python, pillow, pywin32
    """)

    root.mainloop()