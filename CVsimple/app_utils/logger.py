"""
System logowania dla aplikacji
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_level=logging.INFO, log_to_file=True, log_dir="logs"):
        self.log_level = log_level
        self.log_to_file = log_to_file
        self.log_dir = Path(log_dir)

        # Utwórz katalog logów jeśli nie istnieje
        if self.log_to_file:
            self.log_dir.mkdir(exist_ok=True)

        # Konfiguruj logger
        self.logger = logging.getLogger("YOLOGameController")
        self.logger.setLevel(log_level)

        # Usuń poprzednie handlery jeśli istnieją
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Dodaj handlery
        self._setup_handlers()

    def _setup_handlers(self):
        """Konfiguruje handlery logowania"""
        # Format logów
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Handler konsoli
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Handler pliku (jeśli włączony)
        if self.log_to_file:
            # Nazwa pliku z datą
            log_filename = f"yolo_controller_{datetime.now().strftime('%Y%m%d')}.log"
            log_filepath = self.log_dir / log_filename

            file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def info(self, message):
        """Loguje wiadomość informacyjną"""
        self.logger.info(message)

    def info_with_fix(self, message):
        """Loguje wiadomość informacyjną z naprawą polskich znaków"""
        # Usuń polskie znaki diakrytyczne które powodują błędy w konsoli Windows
        clean_message = message.replace('ó', 'o').replace('ę', 'e').replace('ą', 'a').replace('ś', 's').replace('ć', 'c').replace('ź', 'z').replace('ń', 'n').replace('ł', 'l')
        self.logger.info(clean_message)

    def warning(self, message):
        """Loguje ostrzeżenie"""
        self.logger.warning(message)

    def error(self, message):
        """Loguje błąd"""
        self.logger.error(message)

    def debug(self, message):
        """Loguje wiadomość debugową"""
        self.logger.debug(message)

    def critical(self, message):
        """Loguje krytyczny błąd"""
        self.logger.critical(message)

    def log_detection(self, detections, window_title):
        """Specjalne logowanie wykryć YOLO"""
        if detections:
            detection_summary = []
            for det in detections:
                detection_summary.append(
                    f"{det['name']}({det['confidence']:.2f})"
                )

            message = f"DETECTION [{window_title}]: {', '.join(detection_summary)}"
            self.info(message)

    def log_attack(self, pattern_name, target_info, success):
        """Specjalne logowanie ataków"""
        status = "SUCCESS" if success else "FAILED"
        target = target_info.get('name', 'unknown') if target_info else 'unknown'
        confidence = target_info.get('confidence', 0) if target_info else 0

        message = f"ATTACK {status}: {pattern_name} -> {target}({confidence:.2f})"
        self.info(message)

    def log_performance(self, fps, detection_time, processing_time):
        """Loguje metryki wydajności"""
        message = f"PERFORMANCE: FPS={fps:.1f}, Detection={detection_time:.3f}s, Processing={processing_time:.3f}s"
        self.debug(message)

    def cleanup_old_logs(self, days_to_keep=7):
        """Usuwa stare pliki logów"""
        if not self.log_to_file:
            return

        try:
            current_time = time.time()
            cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)

            removed_count = 0
            for log_file in self.log_dir.glob("yolo_controller_*.log"):
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    removed_count += 1

            if removed_count > 0:
                self.info(f"Usunięto {removed_count} starych plików logów")

        except Exception as e:
            self.error(f"Błąd czyszczenia logów: {str(e)}")

    def get_log_stats(self):
        """Zwraca statystyki logów"""
        if not self.log_to_file:
            return {"file_logging": False}

        try:
            log_files = list(self.log_dir.glob("yolo_controller_*.log"))
            total_size = sum(f.stat().st_size for f in log_files)

            return {
                "file_logging": True,
                "log_directory": str(self.log_dir),
                "log_files_count": len(log_files),
                "total_size_mb": total_size / (1024 * 1024),
                "latest_log": max(log_files, key=lambda f: f.stat().st_mtime).name if log_files else None
            }

        except Exception as e:
            return {"file_logging": True, "error": str(e)}