"""
Zaawansowany kreator szablonów HP barów - dla dokładnych wycinków
"""
import cv2
import numpy as np
from pathlib import Path


def create_multiple_templates():
    """Tworzy wiele szablonów z jednego obrazu HP bara"""

    # Twoje obrazy HP barów
    hp_images = [
        "hp1.png",  # Zmień na swoje nazwy
        "hp2.png",
        "hp3.png",
        "hp4.png"
    ]

    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)

    print("🎨 ADVANCED HP TEMPLATE CREATOR")
    print("=" * 50)

    template_counter = 1

    for hp_file in hp_images:
        if not Path(hp_file).exists():
            print(f"⚠️ Plik {hp_file} nie istnieje - pomijam")
            continue

        print(f"\n🖼️ Przetwarzam: {hp_file}")

        img = cv2.imread(hp_file)
        if img is None:
            print(f"❌ Nie można wczytać {hp_file}")
            continue

        print(f"📐 Rozmiar: {img.shape[1]}x{img.shape[0]}")

        # Wykryj czerwone obszary (HP)
        red_templates = extract_red_hp_parts(img)

        # Zapisz różne warianty
        for i, template in enumerate(red_templates):
            if template is not None and template.size > 0:
                # Określ typ na podstawie rozmiaru czerwonego obszaru
                height, width = template.shape[:2]
                area = width * height

                if area > 3000:  # Duży HP bar
                    template_name = f"hp_full_{template_counter}.png"
                elif area > 1500:  # Średni HP bar
                    template_name = f"hp_medium_{template_counter}.png"
                else:  # Mały HP bar
                    template_name = f"hp_low_{template_counter}.png"

                template_path = templates_dir / template_name
                cv2.imwrite(str(template_path), template)
                print(f"   ✅ Zapisano: {template_name} (rozmiar: {width}x{height})")
                template_counter += 1

        # Dodatkowo - zapisz cały pasek jako szablon
        whole_bar_name = f"hp_bar_whole_{template_counter}.png"
        whole_bar_path = templates_dir / whole_bar_name
        cv2.imwrite(str(whole_bar_path), img)
        print(f"   ✅ Zapisano całość: {whole_bar_name}")
        template_counter += 1

    print(f"\n🎯 Utworzono {template_counter - 1} szablonów w folderze 'templates/'")
    print("\n💡 TIPS:")
    print("1. Sprawdź folder 'templates/' - powinny być różne rozmiary")
    print("2. Usuń szablony które wyglądają źle")
    print("3. Zmień nazwy na: hp1.png, hp4.png, hp3.png")
    print("4. Ustaw próg confidence na 0.3-0.5 w aplikacji")


def extract_red_hp_parts(img):
    """Wyciąga czerwone części HP bara"""
    templates = []

    # Konwertuj do HSV dla lepszego wykrywania czerwonego
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Maski dla czerwonego koloru (dwa zakresy bo czerwony jest na brzegach HSV)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = mask1 + mask2

    # Znajdź kontury czerwonych obszarów
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        # Sprawdź czy kontur jest wystarczająco duży
        area = cv2.contourArea(contour)
        if area < 100:  # Pomijaj małe obszary
            continue

        # Prostokąt otaczający czerwony obszar
        x, y, w, h = cv2.boundingRect(contour)

        # Dodaj margines
        margin = 5
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img.shape[1], x + w + margin)
        y2 = min(img.shape[0], y + h + margin)

        # Wytnij szablon
        template = img[y1:y2, x1:x2]

        # Sprawdź czy szablon jest sensowny (nie za mały/duży)
        if template.shape[0] > 5 and template.shape[1] > 20:
            templates.append(template)

    # Jeśli nie znalazł czerwonych obszarów, zwróć cały obraz
    if not templates:
        templates.append(img)

    return templates


def interactive_template_creator():
    """Interaktywny kreator - kliknij i przeciągnij"""

    hp_images = ["hp1.png", "hp2.png", "hp3.png", "hp4.png"]  # Zmień nazwy

    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)

    print("🖱️ INTERACTIVE TEMPLATE CREATOR")
    print("Instrukcje:")
    print("1. Kliknij i przeciągnij żeby zaznaczyć HP bar")
    print("2. Naciśnij SPACJĘ żeby zapisać szablon")
    print("3. Naciśnij ESC żeby przejść do następnego obrazu")
    print("4. Wpisz nazwę szablonu w konsoli")

    for hp_file in hp_images:
        if not Path(hp_file).exists():
            continue

        img = cv2.imread(hp_file)
        if img is None:
            continue

        print(f"\n📸 Zaznacz HP bar na: {hp_file}")

        # ROI selection
        roi = cv2.selectROI(f"Select HP Bar - {hp_file}", img, False)
        cv2.destroyAllWindows()

        if roi[2] > 0 and roi[3] > 0:  # Jeśli coś zaznaczono
            x, y, w, h = roi
            template = img[y:y + h, x:x + w]

            # Pokaż szablon
            cv2.imshow("Template Preview", template)
            cv2.waitKey(500)
            cv2.destroyAllWindows()

            # Nazwa szablonu
            template_name = input(f"Nazwa szablonu (np. hp_full): ").strip()
            if template_name:
                if not template_name.endswith('.png'):
                    template_name += '.png'

                template_path = templates_dir / template_name
                cv2.imwrite(str(template_path), template)
                print(f"✅ Zapisano: {template_name}")


if __name__ == "__main__":
    print("Wybierz tryb:")
    print("1. Automatyczny (wykrywa czerwone obszary)")
    print("2. Interaktywny (zaznaczasz ręcznie)")

    choice = input("Wybór (1 lub 2): ").strip()

    if choice == "1":
        create_multiple_templates()
    elif choice == "2":
        interactive_template_creator()
    else:
        print("❌ Nieprawidłowy wybór!")