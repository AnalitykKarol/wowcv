# CV Simple - Projekt Automatyzacji Gier

## Zakres Pracy
**Folder projektu:** `E:\Work\fun\yolo-V8\CVsimple`
**Focus:** Praca wyłącznie w obrębie tego folderu

## Struktura Projektu

```
CVsimple/
├── main.py                     # Główny entry point aplikacji
├── gui/
│   ├── main_window.py         # Główne okno GUI z podglądem i kontrolami
│   └── __init__.py
├── core/
│   ├── hp_bar_analyzer.py     # Analiza pasków HP/MP (42KB)
│   ├── window_capture.py      # Przechwytywanie ekranu
│   ├── yolo_detector.py      # Detekcja obiektów YOLO
│   ├── combat_controller.py   # Automatyzacja walki
│   └── __init__.py
├── templates/
│   ├── advanced_template_creator.py  # Tworzenie szablonów
│   ├── *.png (hp1.png, hp2.png, etc.)   # Szablony pasków HP
│   └── templates/
├── configs/
│   └── bar_presets.json       # Presety dla pasków HP/MP
├── app_utils/
│   └── logger.py              # System logowania
└── screenshots/               # Zrzuty ekranu
```

## Główne Funkcjonalności

### ✅ Już Zaimplementowane:
1. **HP/MP Bar Analysis** - `core/hp_bar_analyzer.py`
   - Pełny system analizy z callbackami
   - Współrzędne przechowywane w słownikach
   - Progi i stany ostrzeżeń
   - Emergency heal przy niskim HP

2. **GUI z Podglądem** - `gui/main_window.py`
   - Tkinter interface z zakładkami
   - Live preview z canvas
   - Pola tekstowe dla współrzędnych
   - Testowanie pozycji HP/MP

3. **System Presetów** - `configs/bar_presets.json`
   - 2 presety: 1920x1080, 2560x1440
   - Koordynaty w pikselach
   - Podstawowa struktura JSON

4. **Window Capture** - `core/window_capture.py`
   - Przechwytywanie ekranu
   - Walidacja obrazów
   - Wsparcie dla wielomonitorów

5. **YOLO Detection** - `core/yolo_detector.py`
   - Detekcja obiektów w grze
   - Integracja z systemem walki

### 🔧 Potrzebne Ulepszenia:
1. **Rozszerzenie presetów** - więcej rozdzielczości, względne współrzędne
2. **Interaktywny edytor** - edycja współrzędnych na podglądzie na żywo
3. **Automatyzacja** - detekcja rozdzielczości, skalowanie

## Kluczowe Pliki do Modyfikacji

### Priorytet Wysoki:
- `configs/bar_presets.json` - rozszerzenie systemu presetów
- `gui/main_window.py` - interaktywny edytor w podglądzie
- `core/hp_bar_analyzer.py` - wsparcie dla względnych współrzędnych

### Priorytet Średni:
- `core/window_capture.py` - detekcja rozdzielczości
- `main.py` - integracja nowych funkcji

## Aktualne Współrzędne (domyślne)

**HP Bar:**
- X: 112px, Y: 87px
- Width: 119px, Height: 5px

**Mana Bar:**
- X: 112px, Y: 99px
- Width: 120px, Height: 5px

## Proponowane Ulepszenia

### 1. Rozszerzenie Systemu Presetów
- Dodanie presetów dla popularnych rozdzielczości (1366x768, 3840x2160)
- Względne współrzędne (%) zamiast pikseli
- Metadane presetów (typ gry, opis)

### 2. Interaktywny Edytor Współrzędnych
- Mouse event handlers na canvasie podglądu
- Przeciąganie i skalowanie regionów
- Real-time update pól tekstowych

### 3. Automatyczna Detekcja Rozdzielczości
- Wykrywanie rozdzielczości ekranu
- Przeliczanie względnych współrzędnych na piksele
- Automatyczne skalowanie presetów

## Instrukcje Pracy

1. **Ogranicz się** wyłącznie do folderu `CVsimple`
2. **Nie modyfikuj** plików poza tym folderem
3. **Pracuj sekwencyjnie** - najpierw presety, potem GUI, potem automatyzacja
4. **Testuj każą zmianę** przed przejściem do następnej

## Environment

- **Python:** zalecany 3.8+
- **GUI:** Tkinter
- **Dependencies:** opencv-python, pillow, numpy, pywin32, ultralytics

## Notes

- Projekt jest już w dużej mierze funkcjonalny
- Focus na usprawnieniach istniejącego kodu
- Zachowanie kompatybilności wstecznej
- Testowanie na różnych rozdzielczościach ekranu