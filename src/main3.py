import cv2
import numpy as np
import pytesseract
import time
from threading import Thread
import RPi.GPIO as GPIO
from datetime import datetime
import re
import json

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
    
    # File log
    LOG_FILE = 'access_log.json'
    
    # Daftar plat nomor yang diizinkan (statis dalam kode)
    AUTHORIZED_PLATES = ["R5477DP", "R6978SF"]

class PlateDetector:
    def __init__(self):
        self.plate_patterns = [
            r'^[A-Z]{1,2}\d{1,4}[A-Z]{1,3}$',  # Format plat Indonesia
        ]
    
    def preprocess_for_detection(self, image):
        """Preprocessing untuk deteksi area plat"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        return edges
    
    def detect_plate_areas(self, edges):
        """Deteksi area yang mungkin plat nomor"""
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        plate_candidates = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > Config.MIN_PLATE_AREA:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                
                if (Config.MIN_ASPECT_RATIO <= aspect_ratio <= Config.MAX_ASPECT_RATIO 
                    and w > Config.MIN_PLATE_WIDTH and h > Config.MIN_PLATE_HEIGHT):
                    plate_candidates.append((x, y, w, h))
        
        # Urutkan berdasarkan luas area (terbesar ke terkecil)
        plate_candidates.sort(key=lambda rect: rect[2]*rect[3], reverse=True)
        return plate_candidates[:Config.MAX_PLATE_CANDIDATES]
    
    def preprocess_for_ocr(self, plate_roi):
        """Preprocessing khusus untuk OCR"""
        gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
        # Thresholding adaptif untuk mengatasi variasi pencahayaan
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
        # Resize untuk meningkatkan akurasi OCR
        resized = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        return resized
    
    def extract_plate_text(self, image, bbox):
        """Ekstrak teks dari area plat yang terdeteksi"""
        x, y, w, h = bbox
        plate_roi = image[y:y+h, x:x+w]
        
        # Preprocessing khusus OCR
        ocr_ready = self.preprocess_for_ocr(plate_roi)
        
        try:
            text = pytesseract.image_to_string(ocr_ready, config=Config.OCR_CONFIG)
            # Normalisasi teks: uppercase dan hilangkan spasi
            clean_text = text.strip().upper().replace(' ', '')
            print(f"Raw OCR: '{text}' => Cleaned: '{clean_text}'")  # Debugging
            return clean_text
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""
    
    def validate_plate_format(self, plate_text):
        """Validasi format plat nomor"""
        if not plate_text or len(plate_text) < 4:
            return False
        
        for pattern in self.plate_patterns:
            if re.match(pattern, plate_text):
                return True
        return False

class PlateRecognitionSystem:
    def __init__(self):
        self.stepper_motor = StepperMotor()
        self.plate_detector = PlateDetector()
        self.logger = Logger()
        self.cap = cv2.VideoCapture(Config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
        self.is_gate_open = False
        self.last_detection_time = 0
        pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_PATH
    
    def process_frame(self, frame):
        """Proses frame untuk deteksi plat nomor"""
        # Deteksi area plat terlebih dahulu
        edges = self.plate_detector.preprocess_for_detection(frame)
        plate_areas = self.plate_detector.detect_plate_areas(edges)
        
        detected_plates = []
        
        for area in plate_areas:
            x, y, w, h = area
            # Gambar bounding box hijau untuk area terdeteksi
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Ekstrak teks hanya dari area yang terdeteksi sebagai plat
            plate_text = self.plate_detector.extract_plate_text(frame, area)
            
            if plate_text and self.plate_detector.validate_plate_format(plate_text):
                detected_plates.append({
                    'text': plate_text,
                    'bbox': (x, y, w, h)
                })
                # Tampilkan teks plat di atas bounding box
                cv2.putText(frame, plate_text, (x, y-10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return frame, detected_plates
    
    def run(self):
        """Jalankan sistem utama"""
        print("=== Sistem Pengenalan Plat Nomor ===")
        print("Daftar plat yang diizinkan:")
        for plate in Config.AUTHORIZED_PLATES:
            print(f"- {plate}")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Error: Gagal membaca frame kamera")
                    break
                
                processed_frame, detected_plates = self.process_frame(frame)
                
                # Proses setiap plat yang terdeteksi
                for plate_info in detected_plates:
                    self.handle_plate_detection(plate_info['text'])
                
                # Tampilkan status gerbang
                status_text = "GERBANG TERBUKA" if self.is_gate_open else "GERBANG TERTUTUP"
                color = (0, 255, 0) if self.is_gate_open else (0, 0, 255)
                cv2.putText(processed_frame, status_text, (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                cv2.imshow('Plate Recognition', processed_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.cleanup()
    
    # ... (method lainnya tetap sama seperti sebelumnya)

if __name__ == "__main__":
    prs = PlateRecognitionSystem()
    prs.run()