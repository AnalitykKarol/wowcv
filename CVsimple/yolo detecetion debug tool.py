"""
Narzędzie do debugowania wykrywania YOLO
Sprawdza dlaczego model nie wykrywa obiektów
"""
import cv2
import numpy as np
from pathlib import Path
import time
import os


def test_yolo_model_detailed():
    """Szczegółowy test modelu YOLO"""
    print("=== SZCZEGÓŁOWY TEST MODELU YOLO ===\n")

    try:
        from ultralytics import YOLO
        import torch
        print("✅ Ultralytics załadowane")
        print(f"✅ PyTorch: {torch.__version__}")
        print(f"✅ CUDA dostępne: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"   GPU: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        print(f"❌ Błąd importu: {str(e)}")
        return False

    # Znajdź model
    model_paths = [
        r"E:\Work\fun\yolo-V8\runs\detect\train8\weights\best.pt",
        r"E:\Work\fun\yolo-V8\runs\detect\train10\weights\best.pt"
    ]

    model_path = None
    for path in model_paths:
        if os.path.exists(path):
            model_path = path
            print(f"✅ Znaleziono model: {path}")
            break

    if not model_path:
        print("❌ Nie znaleziono modelu!")
        return False

    # Załaduj model
    try:
        print(f"\n📁 Ładowanie modelu...")
        model = YOLO(model_path)
        print(f"✅ Model załadowany")

        # Informacje o modelu
        print(f"\n📊 INFORMACJE O MODELU:")
        print(f"   Nazwy klas: {model.names}")
        print(f"   Liczba klas: {len(model.names)}")
        print(f"   Model device: {model.device}")

        # Sprawdź czy model został wytrenowany
        if hasattr(model.model, 'nc'):
            print(f"   Klasy w modelu: {model.model.nc}")

        # Model summary (jeśli dostępne)
        try:
            print(f"   Model summary: {model.model}")
        except:
            pass

    except Exception as e:
        print(f"❌ Błąd ładowania modelu: {str(e)}")
        return False

    return model


def test_image_with_different_settings(model, img_array):
    """Testuje różne ustawienia YOLO"""
    print(f"\n=== TEST RÓŻNYCH USTAWIEŃ YOLO ===")
    print(f"Obraz: {img_array.shape}, typ: {img_array.dtype}, min/max: {img_array.min()}/{img_array.max()}")

    # Lista różnych progów pewności
    confidence_levels = [0.01, 0.05, 0.1, 0.25, 0.5]

    for conf in confidence_levels:
        print(f"\n🔍 Test z confidence = {conf}")

        try:
            start_time = time.time()
            results = model(img_array, conf=conf, verbose=False)
            inference_time = (time.time() - start_time) * 1000

            print(f"   Czas inference: {inference_time:.1f}ms")
            print(f"   Liczba wyników: {len(results)}")

            total_detections = 0
            for i, result in enumerate(results):
                if result.boxes is not None and len(result.boxes) > 0:
                    boxes = result.boxes.cpu().numpy()
                    total_detections += len(boxes)
                    print(f"   Result {i}: {len(boxes)} detekcji")

                    # Pokaż szczegóły pierwszych 3 detekcji
                    for j, box in enumerate(boxes[:3]):
                        x1, y1, x2, y2 = box.xyxy[0]
                        confidence = float(box.conf[0])
                        class_id = int(box.cls[0])
                        class_name = model.names.get(class_id, f"class_{class_id}")

                        print(
                            f"     #{j + 1}: {class_name} conf={confidence:.3f} box=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f})")

                    if len(boxes) > 3:
                        print(f"     ... i {len(boxes) - 3} więcej")
                else:
                    print(f"   Result {i}: Brak detekcji")

            print(f"   ŁĄCZNIE DETEKCJI: {total_detections}")

            if total_detections > 0:
                print(f"   🎉 ZNALEZIONO DETEKCJE przy confidence = {conf}!")
                return True

        except Exception as e:
            print(f"   ❌ Błąd: {str(e)}")

    return False


def save_test_image_with_preprocessing(img_array):
    """Zapisuje obraz testowy z różnymi preprocessing"""
    print(f"\n=== ZAPISYWANIE OBRAZÓW TESTOWYCH ===")

    try:
        # Oryginał
        cv2.imwrite("debug_original.png", cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
        print("💾 Zapisano: debug_original.png")

        # Przeskalowany do standardowych rozmiarów YOLO
        resized_640 = cv2.resize(img_array, (640, 640))
        cv2.imwrite("debug_resized_640.png", cv2.cvtColor(resized_640, cv2.COLOR_RGB2BGR))
        print("💾 Zapisano: debug_resized_640.png")

        # Małe crop (środek obrazu)
        h, w = img_array.shape[:2]
        crop_size = min(640, h // 2, w // 2)
        start_y = h // 2 - crop_size // 2
        start_x = w // 2 - crop_size // 2
        cropped = img_array[start_y:start_y + crop_size, start_x:start_x + crop_size]
        cv2.imwrite("debug_cropped_center.png", cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR))
        print("💾 Zapisano: debug_cropped_center.png")

        # Statystyki obrazu
        print(f"\n📊 STATYSTYKI OBRAZU:")
        print(f"   Rozmiar: {img_array.shape}")
        print(f"   Średnia jasność: {img_array.mean():.1f}")
        print(f"   Odchylenie std: {img_array.std():.1f}")
        print(f"   Zakres wartości: {img_array.min()} - {img_array.max()}")

        # Histogram kanałów
        for i, color in enumerate(['R', 'G', 'B']):
            channel_mean = img_array[:, :, i].mean()
            print(f"   Kanał {color}: średnia {channel_mean:.1f}")

        return True

    except Exception as e:
        print(f"❌ Błąd zapisywania: {str(e)}")
        return False


def test_with_known_image(model):
    """Test z obrazem, który na pewno powinien być wykryty"""
    print(f"\n=== TEST Z OBRAZEM TRENINGOWYM ===")

    # Spróbuj znaleźć obrazy treningowe
    train_paths = [
        r"E:\Work\fun\yolo-V8\ultralytics_c\assets\dataset\images\train",
        r"E:\Work\fun\yolo-V8\runs\detect\train10\train",
        r"E:\Work\fun\yolo-V8\datasets",
        r"E:\Work\fun\yolo-V8\data"
    ]

    test_images = []
    for base_path in train_paths:
        if os.path.exists(base_path):
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        test_images.append(os.path.join(root, file))
                        if len(test_images) >= 3:  # Max 3 obrazy testowe
                            break
                if len(test_images) >= 3:
                    break
            if len(test_images) >= 3:
                break

    if not test_images:
        print("⚠️ Nie znaleziono obrazów treningowych")
        return False

    print(f"Znaleziono {len(test_images)} obrazów testowych")

    for img_path in test_images:
        print(f"\n📷 Test z: {os.path.basename(img_path)}")

        try:
            # Wczytaj obraz
            img_bgr = cv2.imread(img_path)
            if img_bgr is None:
                print(f"   ❌ Nie można wczytać obrazu")
                continue

            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            print(f"   Rozmiar: {img_rgb.shape}")

            # Test z niskim progiem
            results = model(img_rgb, conf=0.01, verbose=False)

            total_detections = 0
            for result in results:
                if result.boxes is not None:
                    total_detections += len(result.boxes)

            print(f"   Detekcji: {total_detections}")

            if total_detections > 0:
                print(f"   ✅ Model DZIAŁA na obrazie treningowym!")
                return True

        except Exception as e:
            print(f"   ❌ Błąd: {str(e)}")

    print(f"❌ Model nie wykrywa nawet na obrazach treningowych!")
    return False


def main():
    """Główna funkcja debugowania"""
    print("🔍 YOLO DETECTION DEBUG TOOL")
    print("=" * 50)

    # Test 1: Załaduj model
    model = test_yolo_model_detailed()
    if not model:
        return

    # Test 2: Test z obrazem treningowym
    if test_with_known_image(model):
        print(f"\n✅ Model działa poprawnie na obrazach treningowych")
    else:
        print(f"\n❌ Problem z modelem - nie wykrywa nawet obrazów treningowych")
        return

    # Test 3: Spróbuj z obrazem z aplikacji
    print(f"\n" + "=" * 50)
    print("TERAZ PRZETESTUJ W APLIKACJI:")
    print("1. Uruchom main.py")
    print("2. Wybierz okno")
    print("3. Kliknij '🧪 Test YOLO'")
    print("4. Sprawdź wyniki w logach")
    print("=" * 50)


if __name__ == "__main__":
    main()