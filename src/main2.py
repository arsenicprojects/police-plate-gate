import sys
import json
import os
import re
import cv2
import numpy as np
import pytesseract
import time
from threading import Thread
import RPi.GPIO as GPIO
from datetime import datetime

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
    
    # File paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOG_FILE = os.path.join(BASE_DIR, 'logs', 'access_log.json')
    
    # Buat folder jika belum ada
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

    # Daftar plat nomor default (statis)
    DEFAULT_PLATES = ["B1234ABC", "D5678XYZ", "AB1234CD", "L9876EFG"]

class StepperMotor:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(Config.STEP_PIN, GPIO.OUT)
        GPIO.setup(Config.DIR_PIN, GPIO.OUT)
        GPIO.setup(Config.ENABLE_PIN, GPIO.OUT)
        GPIO.output(Config.ENABLE_PIN, GPIO.HIGH)
    
    def step_motor(self, steps, direction):
        GPIO.output(Config.DIR_PIN, direction)
        GPIO.output(Config.ENABLE_PIN, GPIO.LOW)
        
        for _ in range(steps):
            GPIO.output(Config.STEP_PIN, GPIO.HIGH)
            time.sleep(Config.MOTOR_STEP_DELAY)
            GPIO.output(Config.STEP_PIN, GPIO.LOW)
            time.sleep(Config.MOTOR_STEP_DELAY)
        
        GPIO.output(Config.ENABLE_PIN, GPIO.HIGH)
    
    def open_gate(self):
        self.step_motor(Config.GATE_OPEN_STEPS, GPIO.HIGH)
    
    def close_gate(self):
        self.step_motor(Config.GATE_OPEN_STEPS, GPIO.LOW)
    
    def cleanup(self):
        GPIO.cleanup()

class Logger:
    def __init__(self):
        self.log_file = Config.LOG_FILE
    
    def log_access(self, plate_text, status):
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

class PlateDetector:
    def __init__(self):
        self.plate_patterns = [
            r'^[A-Z]{1,2}\d{1,4}[A-Z]{1,3}$',
            r'^[A-Z]\d{1,4}[A-Z]{2,3}$',
        ]
    
    def preprocess_image(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        return edges
    
    def detect_plate_contours(self, edges):
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
        return plate_candidates[:3]
    
    def extract_text_from_plate(self, image, bbox):
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
        for pattern in self.plate_patterns:
            if re.match(pattern, plate_text):
                return True
        return False
    
    def detect_plates(self, frame):
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
        detected_plates = self.plate_detector.detect_plates(frame)
        
        for plate_info in detected_plates:
            x, y, w, h = plate_info['bbox']
            plate_text = plate_info['text']
            
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, plate_text, (x, y-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return frame, detected_plates
    
    def handle_plate_detection(self, plate_text):
        current_time = time.time()
        if current_time - self.last_detection_time < Config.DETECTION_COOLDOWN:
            return
        
        print(f"Plat nomor terdeteksi: {plate_text}")
        if plate_text in Config.DEFAULT_PLATES:
            print(f"✓ Plat nomor {plate_text} diizinkan!")
            self.open_gate()
            self.logger.log_access(plate_text, 'authorized')
            self.last_detection_time = current_time
        else:
            print(f"✗ Plat nomor {plate_text} tidak diizinkan!")
            self.logger.log_access(plate_text, 'unauthorized')
    
    def open_gate(self):
        if not self.is_gate_open:
            print("Membuka gerbang...")
            self.stepper_motor.open_gate()
            self.is_gate_open = True
            print("Gerbang terbuka!")
            Thread(target=self.auto_close_gate, daemon=True).start()
    
    def close_gate(self):
        if self.is_gate_open:
            print("Menutup gerbang...")
            self.stepper_motor.close_gate()
            self.is_gate_open = False
            print("Gerbang tertutup!")
    
    def auto_close_gate(self):
        time.sleep(Config.AUTO_CLOSE_DELAY)
        self.close_gate()
    
    def run(self):
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Error: Tidak bisa membaca frame dari kamera")
                    break
                
                processed_frame, detected_plates = self.process_frame(frame)
                
                for plate_info in detected_plates:
                    self.handle_plate_detection(plate_info['text'])
                
                status_text = "GERBANG TERBUKA" if self.is_gate_open else "GERBANG TERTUTUP"
                color = (0, 255, 0) if self.is_gate_open else (0, 0, 255)
                cv2.putText(processed_frame, status_text, (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                cv2.imshow('Sistem Pengenalan Plat Nomor', processed_frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        print("Membersihkan resource...")
        if self.is_gate_open:
            self.close_gate()
        
        self.cap.release()
        cv2.destroyAllWindows()
        self.stepper_motor.cleanup()
        print("Resource dibersihkan!")

def main():
    system = PlateRecognitionSystem()
    system.run()

if __name__ == "__main__":
    main()