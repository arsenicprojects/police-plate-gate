# ===== FILE 1: main.py =====
"""
File utama untuk menjalankan sistem pengenalan plat nomor
"""

from plate_recognition import PlateRecognitionSystem
from database_manager import DatabaseManager
from config import Config
import sys
import signal

def signal_handler(sig, frame):
    """Handler untuk menangani Ctrl+C"""
    print('\nSistem dihentikan oleh pengguna')
    sys.exit(0)

def main():
    """Fungsi utama"""
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Inisialisasi database manager
    db_manager = DatabaseManager()
    
    # Inisialisasi sistem
    system = PlateRecognitionSystem(db_manager)
    
    print("=" * 50)
    print("SISTEM PENGENALAN PLAT NOMOR MOTOR")
    print("=" * 50)
    print(f"Database plat nomor: {len(db_manager.get_authorized_plates())} entries")
    print("Tekan Ctrl+C untuk keluar")
    print("=" * 50)
    
    # Jalankan sistem
    system.run()

if __name__ == "__main__":
    main()

# ===== FILE 2: config.py =====
"""
Konfigurasi untuk sistem pengenalan plat nomor
"""

import os

class Config:
    """Konfigurasi sistem"""
    
    # GPIO Pins untuk motor stepper
    STEP_PIN = 18
    DIR_PIN = 19
    ENABLE_PIN = 20
    
    # Konfigurasi kamera
    CAMERA_INDEX = 0
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    
    # Konfigurasi OCR
    TESSERACT_PATH = '/usr/bin/tesseract'
    OCR_CONFIG = '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    
    # Konfigurasi deteksi plat nomor
    MIN_PLATE_AREA = 1000
    MIN_PLATE_WIDTH = 100
    MIN_PLATE_HEIGHT = 25
    MIN_ASPECT_RATIO = 2.0
    MAX_ASPECT_RATIO = 4.5
    
    # Konfigurasi motor stepper
    MOTOR_STEPS_PER_REVOLUTION = 200
    MOTOR_STEP_DELAY = 0.002
    GATE_OPEN_STEPS = 200
    AUTO_CLOSE_DELAY = 5  # detik
    
    # Konfigurasi sistem
    DETECTION_COOLDOWN = 3  # detik
    MAX_PLATE_CANDIDATES = 3
    
    # File paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_FILE = os.path.join(BASE_DIR, 'data', 'authorized_plates.json')
    LOG_FILE = os.path.join(BASE_DIR, 'logs', 'access_log.json')
    
    # Buat folder jika belum ada
    os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# ===== FILE 3: plate_recognition.py =====
"""
Modul utama untuk pengenalan plat nomor
"""

import cv2
import numpy as np
import pytesseract
import time
from threading import Thread
from config import Config
from stepper_motor import StepperMotor
from plate_detector import PlateDetector
from logger import Logger

class PlateRecognitionSystem:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.stepper_motor = StepperMotor()
        self.plate_detector = PlateDetector()
        self.logger = Logger()
        
        # Inisialisasi kamera
        self.cap = cv2.VideoCapture(Config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
        
        # Status sistem
        self.is_gate_open = False
        self.last_detection_time = 0
        
        # Konfigurasi Tesseract
        pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_PATH
    
    def process_frame(self, frame):
        """Proses frame untuk deteksi plat nomor"""
        detected_plates = self.plate_detector.detect_plates(frame)
        
        for plate_info in detected_plates:
            x, y, w, h = plate_info['bbox']
            plate_text = plate_info['text']
            
            # Gambar bounding box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, plate_text, (x, y-10), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return frame, detected_plates
    
    def handle_plate_detection(self, plate_text):
        """Tangani deteksi plat nomor"""
        # Hindari deteksi berulang
        current_time = time.time()
        if current_time - self.last_detection_time < Config.DETECTION_COOLDOWN:
            return
        
        print(f"Plat nomor terdeteksi: {plate_text}")
        
        # Cek autorisasi
        if self.db_manager.is_authorized(plate_text):
            print(f"✓ Plat nomor {plate_text} diizinkan!")
            self.open_gate()
            self.logger.log_access(plate_text, 'authorized')
            self.last_detection_time = current_time
        else:
            print(f"✗ Plat nomor {plate_text} tidak diizinkan!")
            self.logger.log_access(plate_text, 'unauthorized')
    
    def open_gate(self):
        """Buka gerbang dengan motor stepper"""
        if not self.is_gate_open:
            print("Membuka gerbang...")
            self.stepper_motor.open_gate()
            self.is_gate_open = True
            print("Gerbang terbuka!")
            
            # Auto close setelah delay
            Thread(target=self.auto_close_gate, daemon=True).start()
    
    def close_gate(self):
        """Tutup gerbang dengan motor stepper"""
        if self.is_gate_open:
            print("Menutup gerbang...")
            self.stepper_motor.close_gate()
            self.is_gate_open = False
            print("Gerbang tertutup!")
    
    def auto_close_gate(self):
        """Auto close gerbang setelah delay"""
        time.sleep(Config.AUTO_CLOSE_DELAY)
        self.close_gate()
    
    def run(self):
        """Jalankan sistem pengenalan plat nomor"""
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Error: Tidak bisa membaca frame dari kamera")
                    break
                
                # Proses frame
                processed_frame, detected_plates = self.process_frame(frame)
                
                # Handle deteksi plat nomor
                for plate_info in detected_plates:
                    self.handle_plate_detection(plate_info['text'])
                
                # Tampilkan status gerbang
                status_text = "GERBANG TERBUKA" if self.is_gate_open else "GERBANG TERTUTUP"
                color = (0, 255, 0) if self.is_gate_open else (0, 0, 255)
                cv2.putText(processed_frame, status_text, (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                # Tampilkan frame
                cv2.imshow('Sistem Pengenalan Plat Nomor', processed_frame)
                
                # Keluar jika 'q' ditekan
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Bersihkan resource"""
        print("Membersihkan resource...")
        if self.is_gate_open:
            self.close_gate()
        
        self.cap.release()
        cv2.destroyAllWindows()
        self.stepper_motor.cleanup()
        print("Resource dibersihkan!")

# ===== FILE 4: plate_detector.py =====
"""
Modul untuk deteksi dan pengenalan plat nomor
"""

import cv2
import numpy as np
import pytesseract
import re
from config import Config

class PlateDetector:
    def __init__(self):
        self.plate_patterns = [
            r'^[A-Z]{1,2}\d{1,4}[A-Z]{1,3}$',  # B1234ABC, AB1234CD
            r'^[A-Z]\d{1,4}[A-Z]{2,3}$',       # B1234AB
        ]
    
    def preprocess_image(self, image):
        """Preprocessing gambar untuk deteksi plat nomor"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        return edges
    
    def detect_plate_contours(self, edges):
        """Deteksi kontur yang mungkin adalah plat nomor"""
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        plate_candidates = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if area > Config.MIN_PLATE_AREA:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                
                if (Config.MIN_ASPECT_RATIO <= aspect_ratio <= Config.MAX_ASPECT_RATIO 
                    and w > Config.MIN_PLATE_WIDTH and h > Config.MIN_PLATE_HEIGHT):
                    plate_candidates.append((x, y, w, h, area))
        
        plate_candidates.sort(key=lambda x: x[4], reverse=True)
        return plate_candidates[:Config.MAX_PLATE_CANDIDATES]
    
    def extract_text_from_plate(self, image, bbox):
        """Ekstrak teks dari area plat nomor"""
        x, y, w, h = bbox
        plate_roi = image[y:y+h, x:x+w]
        
        gray_plate = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray_plate, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
        
        resized = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        try:
            text = pytesseract.image_to_string(resized, config=Config.OCR_CONFIG)
            return text.strip().replace(' ', '').upper()
        except Exception as e:
            print(f"Error OCR: {e}")
            return ""
    
    def validate_plate_format(self, plate_text):
        """Validasi format plat nomor Indonesia"""
        for pattern in self.plate_patterns:
            if re.match(pattern, plate_text):
                return True
        return False
    
    def detect_plates(self, frame):
        """Deteksi plat nomor dalam frame"""
        edges = self.preprocess_image(frame)
        plate_candidates = self.detect_plate_contours(edges)
        
        detected_plates = []
        
        for bbox in plate_candidates:
            x, y, w, h, area = bbox
            plate_text = self.extract_text_from_plate(frame, (x, y, w, h))
            
            if plate_text and len(plate_text) > 4:
                if self.validate_plate_format(plate_text):
                    detected_plates.append({
                        'text': plate_text,
                        'bbox': (x, y, w, h),
                        'confidence': area
                    })
        
        return detected_plates

# ===== FILE 5: stepper_motor.py =====
"""
Modul untuk kontrol motor stepper
"""

import RPi.GPIO as GPIO
import time
from config import Config

class StepperMotor:
    def __init__(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(Config.STEP_PIN, GPIO.OUT)
        GPIO.setup(Config.DIR_PIN, GPIO.OUT)
        GPIO.setup(Config.ENABLE_PIN, GPIO.OUT)
        
        # Disable motor saat startup
        GPIO.output(Config.ENABLE_PIN, GPIO.HIGH)
    
    def step_motor(self, steps, direction):
        """Gerakkan motor stepper"""
        GPIO.output(Config.DIR_PIN, direction)
        GPIO.output(Config.ENABLE_PIN, GPIO.LOW)  # Enable motor
        
        for _ in range(steps):
            GPIO.output(Config.STEP_PIN, GPIO.HIGH)
            time.sleep(Config.MOTOR_STEP_DELAY)
            GPIO.output(Config.STEP_PIN, GPIO.LOW)
            time.sleep(Config.MOTOR_STEP_DELAY)
        
        GPIO.output(Config.ENABLE_PIN, GPIO.HIGH)  # Disable motor
    
    def open_gate(self):
        """Buka gerbang"""
        self.step_motor(Config.GATE_OPEN_STEPS, GPIO.HIGH)
    
    def close_gate(self):
        """Tutup gerbang"""
        self.step_motor(Config.GATE_OPEN_STEPS, GPIO.LOW)
    
    def cleanup(self):
        """Bersihkan GPIO"""
        GPIO.cleanup()

# ===== FILE 6: database_manager.py =====
"""
Modul untuk manajemen database plat nomor
"""

import json
import os
from config import Config

class DatabaseManager:
    def __init__(self):
        self.db_file = Config.DATABASE_FILE
        self.authorized_plates = self.load_database()
    
    def load_database(self):
        """Muat database dari file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            else:
                # Database default
                default_plates = ["B1234ABC", "D5678XYZ", "AB1234CD", "L9876EFG"]
                self.save_database(default_plates)
                return default_plates
        except Exception as e:
            print(f"Error loading database: {e}")
            return []
    
    def save_database(self, plates=None):
        """Simpan database ke file"""
        if plates is None:
            plates = self.authorized_plates
        
        try:
            with open(self.db_file, 'w') as f:
                json.dump(plates, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving database: {e}")
            return False
    
    def is_authorized(self, plate_text):
        """Cek apakah plat nomor diizinkan"""
        return plate_text in self.authorized_plates
    
    def add_plate(self, plate_text):
        """Tambah plat nomor baru"""
        plate_text = plate_text.upper().replace(' ', '')
        if plate_text not in self.authorized_plates:
            self.authorized_plates.append(plate_text)
            self.save_database()
            return True
        return False
    
    def remove_plate(self, plate_text):
        """Hapus plat nomor"""
        if plate_text in self.authorized_plates:
            self.authorized_plates.remove(plate_text)
            self.save_database()
            return True
        return False
    
    def get_authorized_plates(self):
        """Dapatkan daftar plat nomor yang diizinkan"""
        return self.authorized_plates.copy()

# ===== FILE 7: logger.py =====
"""
Modul untuk logging akses
"""

import json
from datetime import datetime
from config import Config

class Logger:
    def __init__(self):
        self.log_file = Config.LOG_FILE
    
    def log_access(self, plate_text, status):
        """Log akses ke file"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'plate_number': plate_text,
            'status': status,
            'gate_action': 'opened' if status == 'authorized' else 'remained_closed'
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error logging: {e}")
    
    def get_recent_logs(self, count=10):
        """Dapatkan log terbaru"""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-count:]
                return [json.loads(line.strip()) for line in recent_lines if line.strip()]
        except Exception as e:
            print(f"Error reading logs: {e}")
            return []

# ===== FILE 8: plate_manager.py =====
"""
Script untuk manajemen plat nomor (CLI)
"""

import sys
from database_manager import DatabaseManager
from plate_detector import PlateDetector

def main():
    db_manager = DatabaseManager()
    plate_detector = PlateDetector()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python plate_manager.py add <plate_number>")
        print("  python plate_manager.py remove <plate_number>") 
        print("  python plate_manager.py list")
        print("  python plate_manager.py validate <plate_number>")
        return
    
    command = sys.argv[1]
    
    if command == "add" and len(sys.argv) == 3:
        plate_text = sys.argv[2].upper().replace(' ', '')
        if plate_detector.validate_plate_format(plate_text):
            if db_manager.add_plate(plate_text):
                print(f"✓ Plat nomor {plate_text} berhasil ditambahkan!")
            else:
                print(f"✗ Plat nomor {plate_text} sudah ada!")
        else:
            print(f"✗ Format plat nomor {plate_text} tidak valid!")
    
    elif command == "remove" and len(sys.argv) == 3:
        plate_text = sys.argv[2].upper().replace(' ', '')
        if db_manager.remove_plate(plate_text):
            print(f"✓ Plat nomor {plate_text} berhasil dihapus!")
        else:
            print(f"✗ Plat nomor {plate_text} tidak ditemukan!")
    
    elif command == "list":
        plates = db_manager.get_authorized_plates()
        print(f"Daftar plat nomor yang diizinkan ({len(plates)} entries):")
        for i, plate in enumerate(plates, 1):
            print(f"{i:2d}. {plate}")
    
    elif command == "validate" and len(sys.argv) == 3:
        plate_text = sys.argv[2].upper().replace(' ', '')
        if plate_detector.validate_plate_format(plate_text):
            print(f"✓ Format plat nomor {plate_text} valid!")
        else:
            print(f"✗ Format plat nomor {plate_text} tidak valid!")
    
    else:
        print("Command tidak dikenali!")

if __name__ == "__main__":
    main()

# ===== FILE 9: requirements.txt =====
"""
opencv-python>=4.5.0
pytesseract>=0.3.8
numpy>=1.21.0
RPi.GPIO>=0.7.0
"""

# ===== FILE 10: install.sh =====
"""
#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Installing Tesseract OCR..."
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng

echo "Creating directories..."
mkdir -p data
mkdir -p logs

echo "Setup complete!"
echo "Run: python main.py"
"""

# ===== FILE 11: README.md =====
"""
# Sistem Pengenalan Plat Nomor Motor

Sistem otomatis untuk mengenali plat nomor motor dan mengontrol gerbang menggunakan motor stepper.

## Struktur Folder
```
plate_recognition_system/
├── main.py                 # File utama
├── config.py              # Konfigurasi sistem
├── plate_recognition.py   # Sistem pengenalan utama
├── plate_detector.py      # Modul deteksi plat nomor
├── stepper_motor.py       # Kontrol motor stepper
├── database_manager.py    # Manajemen database
├── logger.py              # Logging sistem
├── plate_manager.py       # CLI untuk manajemen plat
├── requirements.txt       # Dependencies
├── install.sh            # Script instalasi
├── data/                 # Folder database
│   └── authorized_plates.json
└── logs/                 # Folder log
    └── access_log.json
```

## Instalasi
```bash
chmod +x install.sh
./install.sh
```

## Penggunaan

### Menjalankan sistem:
```bash
python main.py
```

### Manajemen plat nomor:
```bash
# Tambah plat nomor
python plate_manager.py add B1234XYZ

# Hapus plat nomor
python plate_manager.py remove B1234XYZ

# Lihat daftar plat nomor
python plate_manager.py list

# Validasi format
python plate_manager.py validate B1234XYZ
```

## Konfigurasi Hardware
- STEP_PIN: GPIO 18
- DIR_PIN: GPIO 19
- ENABLE_PIN: GPIO 20

## Fitur
- Deteksi plat nomor real-time
- Validasi format plat nomor Indonesia
- Kontrol motor stepper untuk gerbang
- Database plat nomor yang diizinkan
- Logging akses lengkap
- Auto-close gerbang
- Interface CLI untuk manajemen

## Troubleshooting
- Pastikan kamera terhubung
- Periksa koneksi GPIO motor stepper
- Install Tesseract OCR dengan benar
- Sesuaikan path Tesseract di config.py
"""