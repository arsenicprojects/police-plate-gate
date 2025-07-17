import cv2
import numpy as np
import pytesseract
import time
from threading import Thread, Lock
import RPi.GPIO as GPIO
from datetime import datetime
import re
import json

# --- Konfigurasi Sistem ---
class Config:
    """Konfigurasi sistem"""
    
    # GPIO Pins untuk motor stepper
    # Pastikan pin ini sesuai dengan koneksi fisik Anda
    STEP_PIN = 18
    DIR_PIN = 19
    ENABLE_PIN = 20 # HIGH = Disabled, LOW = Enabled
    
    # Konfigurasi kamera
    CAMERA_INDEX = 0 # Biasanya 0 untuk webcam bawaan atau kamera USB pertama
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    
    # Konfigurasi OCR (Tesseract)
    # Pastikan Tesseract sudah terinstal dan path-nya benar
    TESSERACT_PATH = '/usr/bin/tesseract'
    # --oem 3: Menggunakan engine Tesseract terbaru (LSTM)
    # --psm 8: Page Segmentation Mode untuk single word/line of text (cocok untuk plat)
    # -c tessedit_char_whitelist: Membatasi karakter yang dikenali hanya pada huruf kapital dan angka
    OCR_CONFIG = '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    
    # Konfigurasi deteksi plat nomor (berbasis kontur)
    MIN_PLATE_AREA = 1000 # Luas area minimum untuk dianggap sebagai kandidat plat
    MIN_PLATE_WIDTH = 100 # Lebar minimum kandidat plat
    MIN_PLATE_HEIGHT = 25 # Tinggi minimum kandidat plat
    MIN_ASPECT_RATIO = 2.0 # Rasio aspek (lebar/tinggi) minimum plat
    MAX_ASPECT_RATIO = 4.5 # Rasio aspek maksimum plat
    
    # Konfigurasi motor stepper
    MOTOR_STEPS_PER_REVOLUTION = 200 # Jumlah langkah per putaran penuh motor
    MOTOR_STEP_DELAY = 0.002 # Penundaan antar langkah (semakin kecil, semakin cepat tapi bisa kehilangan langkah)
    GATE_OPEN_STEPS = 200 # Jumlah langkah untuk membuka/menutup gerbang
    AUTO_CLOSE_DELAY = 5  # Detik: Waktu tunda sebelum gerbang otomatis tertutup
    
    # Konfigurasi sistem kontrol
    DETECTION_COOLDOWN = 3  # Detik: Waktu tunggu setelah deteksi valid sebelum deteksi berikutnya diproses
    MAX_PLATE_CANDIDATES = 3 # Jumlah kandidat plat teratas yang akan diproses OCR
    
    # File log
    LOG_FILE = 'access_log.json'
    
    # Daftar plat nomor yang diizinkan (DIUBAH MENJADI SET UNTUK PENCARIAN LEBIH CEPAT)
    AUTHORIZED_PLATES = {"R5477DP", "R6978SF"} # Menggunakan set literal {}

# --- Kelas Stepper Motor ---
class StepperMotor:
    def __init__(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(Config.STEP_PIN, GPIO.OUT)
        GPIO.setup(Config.DIR_PIN, GPIO.OUT)
        GPIO.setup(Config.ENABLE_PIN, GPIO.OUT)
        
        # Disable motor saat startup untuk menghemat daya dan mencegah gerakan tak terduga
        GPIO.output(Config.ENABLE_PIN, GPIO.HIGH)
        self.motor_lock = Lock() # Lock untuk mencegah multiple thread mengakses motor bersamaan

    def step_motor(self, steps, direction):
        """
        Gerakkan motor stepper sejumlah langkah tertentu.
        Menggunakan lock untuk memastikan hanya satu operasi motor pada satu waktu.
        """
        with self.motor_lock:
            GPIO.output(Config.DIR_PIN, direction)
            GPIO.output(Config.ENABLE_PIN, GPIO.LOW)  # Enable motor
            
            for _ in range(steps):
                GPIO.output(Config.STEP_PIN, GPIO.HIGH)
                time.sleep(Config.MOTOR_STEP_DELAY)
                GPIO.output(Config.STEP_PIN, GPIO.LOW)
                time.sleep(Config.MOTOR_STEP_DELAY)
            
            GPIO.output(Config.ENABLE_PIN, GPIO.HIGH)  # Disable motor setelah selesai
    
    def open_gate_thread(self):
        """Fungsi untuk membuka gerbang, dijalankan di thread terpisah."""
        print("Membuka gerbang...")
        self.step_motor(Config.GATE_OPEN_STEPS, GPIO.HIGH) # HIGH atau LOW tergantung arah buka
        print("Gerbang terbuka.")
    
    def close_gate_thread(self):
        """Fungsi untuk menutup gerbang, dijalankan di thread terpisah."""
        print("Menutup gerbang...")
        self.step_motor(Config.GATE_OPEN_STEPS, GPIO.LOW) # HIGH atau LOW tergantung arah tutup
        print("Gerbang tertutup.")
    
    def cleanup(self):
        """Bersihkan konfigurasi GPIO."""
        GPIO.cleanup()

# --- Kelas Logger ---
class Logger:
    def __init__(self):
        self.log_file = Config.LOG_FILE
    
    def log_access(self, plate_text, status):
        """Log akses ke file JSON."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'plate_number': plate_text,
            'status': status,
            'gate_action': 'opened' if status == 'authorized' else 'remained_closed'
        }
        
        try:
            # Menggunakan 'a+' untuk memastikan file dibuat jika belum ada
            # Membaca seluruh konten, menambahkan entri baru, lalu menulis ulang
            # Ini lebih aman untuk format JSON array, meskipun kurang efisien untuk file sangat besar
            with open(self.log_file, 'a+') as f:
                f.seek(0) # Pindah ke awal file
                content = f.read().strip() # Baca semua konten
                
                data = []
                if content:
                    try:
                        # Jika file tidak kosong, coba parse sebagai JSON array
                        # Jika tidak dalam format array, asumsikan itu adalah objek JSON per baris
                        if content.startswith('[') and content.endswith(']'):
                            data = json.loads(content)
                        else:
                            # Jika bukan array, coba parse setiap baris sebagai objek JSON
                            data = [json.loads(line) for line in content.split('\n') if line.strip()]
                    except json.JSONDecodeError:
                        print(f"Warning: Log file '{self.log_file}' contains invalid JSON. Starting fresh.")
                        data = [] # Jika error, mulai dari array kosong
                
                data.append(log_entry)
                
                f.seek(0) # Pindah lagi ke awal file
                f.truncate() # Hapus semua konten lama
                json.dump(data, f, indent=4) # Tulis ulang seluruh data sebagai JSON array
                
        except Exception as e:
            print(f"Error logging: {e}")

# --- Kelas Plate Detector ---
class PlateDetector:
    def __init__(self):
        # Pola regex untuk validasi format plat nomor Indonesia
        # Contoh: B 1234 ABC, D 1234 AB, AB 1234 CD
        # Regex sudah dikompilasi untuk sedikit peningkatan performa (opsional tapi baik)
        self.plate_patterns = [
            re.compile(r'^[A-Z]{1,2}\d{1,4}[A-Z]{1,3}$'), 
            re.compile(r'^[A-Z]{1,2}\s?\d{1,4}\s?[A-Z]{1,3}$') # Dengan spasi opsional
        ]
    
    def preprocess_for_detection(self, image):
        """
        Preprocessing gambar untuk deteksi area plat nomor.
        Menggunakan grayscale, Gaussian blur, dan Canny edge detection.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Gaussian blur untuk mengurangi noise sebelum deteksi tepi
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Canny edge detection untuk menemukan tepi objek
        edges = cv2.Canny(blurred, 50, 150)
        # Operasi morfologi 'CLOSE' untuk menutup celah pada tepi yang terdeteksi
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        return edges
    
    def detect_plate_areas(self, edges):
        """
        Deteksi area yang mungkin merupakan plat nomor berdasarkan kontur.
        Filter berdasarkan area, rasio aspek, lebar, dan tinggi.
        """
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        plate_candidates = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            # Filter berdasarkan luas area minimum
            if area > Config.MIN_PLATE_AREA:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                
                # Filter berdasarkan rasio aspek, lebar, dan tinggi minimum
                if (Config.MIN_ASPECT_RATIO <= aspect_ratio <= Config.MAX_ASPECT_RATIO 
                    and w > Config.MIN_PLATE_WIDTH and h > Config.MIN_PLATE_HEIGHT):
                    plate_candidates.append((x, y, w, h))
        
        # Urutkan kandidat berdasarkan luas area (terbesar ke terkecil)
        # dan ambil hanya sejumlah kandidat teratas (MAX_PLATE_CANDIDATES)
        plate_candidates.sort(key=lambda rect: rect[2]*rect[3], reverse=True)
        return plate_candidates[:Config.MAX_PLATE_CANDIDATES]
    
    def preprocess_for_ocr(self, plate_roi):
        """
        Preprocessing khusus untuk gambar ROI plat nomor sebelum dikirim ke OCR.
        Menggunakan grayscale, adaptive thresholding, dan resizing.
        """
        gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
        # Adaptive thresholding sangat efektif untuk mengatasi variasi pencahayaan
        # Ini membuat gambar menjadi biner (hitam-putih) secara adaptif
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
        # Resize gambar untuk meningkatkan akurasi OCR.
        # Tesseract seringkali bekerja lebih baik pada gambar dengan resolusi lebih tinggi.
        resized = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        return resized
    
    def extract_plate_text(self, image, bbox):
        """
        Ekstrak teks dari area plat yang terdeteksi menggunakan Tesseract OCR.
        Melakukan preprocessing khusus OCR dan normalisasi teks.
        """
        x, y, w, h = bbox
        # Pastikan ROI tidak keluar dari batas gambar
        y_max = min(y + h, image.shape[0])
        x_max = min(x + w, image.shape[1])
        plate_roi = image[y:y_max, x:x_max]
        
        if plate_roi.shape[0] == 0 or plate_roi.shape[1] == 0:
            return "" # ROI kosong, abaikan
        
        # Preprocessing khusus OCR
        ocr_ready = self.preprocess_for_ocr(plate_roi)
        
        try:
            # Panggil Tesseract untuk mengenali teks
            text = pytesseract.image_to_string(ocr_ready, config=Config.OCR_CONFIG)
            # Normalisasi teks: hapus spasi awal/akhir, ubah ke huruf kapital, hilangkan semua spasi di tengah
            clean_text = text.strip().upper().replace(' ', '').replace('\n', '')
            print(f"Raw OCR: '{text.strip()}' => Cleaned: '{clean_text}'")  # Debugging
            return clean_text
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""
    
    def validate_plate_format(self, plate_text):
        """
        Validasi format plat nomor menggunakan regex yang sudah dikompilasi.
        Ini membantu memfilter hasil OCR yang salah format.
        """
        if not plate_text or len(plate_text) < 4: # Plat nomor minimal 4 karakter (e.g., B 1 A)
            return False
        
        for pattern in self.plate_patterns:
            if pattern.match(plate_text): # Menggunakan .match() pada objek regex yang sudah dikompilasi
                return True
        return False

# --- Kelas Sistem Pengenalan Plat Nomor Utama ---
class PlateRecognitionSystem:
    def __init__(self):
        self.stepper_motor = StepperMotor()
        self.plate_detector = PlateDetector()
        self.logger = Logger()
        self.cap = cv2.VideoCapture(Config.CAMERA_INDEX)
        
        # Atur resolusi kamera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
        
        if not self.cap.isOpened():
            raise IOError("Tidak dapat membuka kamera. Pastikan kamera terhubung dan indeks benar.")

        self.is_gate_open = False
        self.last_detection_time = 0 # Waktu terakhir plat nomor valid terdeteksi
        self.gate_close_timer = None # Timer untuk menutup gerbang otomatis
        self.gate_action_lock = Lock() # Lock untuk mencegah race condition pada state gerbang
        
        # Set path Tesseract
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

    def handle_plate_detection(self, plate_text):
        """
        Menangani logika setelah plat nomor terdeteksi dan divalidasi.
        Mengontrol gerbang dan logging.
        """
        current_time = time.time()
        
        # Gunakan lock untuk memastikan hanya satu thread yang memproses deteksi pada satu waktu
        with self.gate_action_lock:
            # Cek cooldown untuk mencegah deteksi berulang terlalu cepat
            if current_time - self.last_detection_time < Config.DETECTION_COOLDOWN:
                return # Masih dalam masa cooldown, abaikan deteksi ini
            
            # Validasi plat nomor menggunakan set untuk pencarian O(1) yang lebih cepat
            is_authorized = plate_text in Config.AUTHORIZED_PLATES
            
            if is_authorized:
                if not self.is_gate_open:
                    print(f"Plat '{plate_text}' terdeteksi. DISETUJUI. Membuka gerbang...")
                    self.logger.log_access(plate_text, 'authorized')
                    
                    # Jalankan operasi gerbang di thread terpisah
                    open_thread = Thread(target=self._open_gate_and_schedule_close)
                    open_thread.start()
                    self.is_gate_open = True
                else:
                    print(f"Plat '{plate_text}' terdeteksi. Gerbang sudah terbuka.")
                    # Reset timer penutup otomatis jika plat yang diizinkan terdeteksi lagi
                    if self.gate_close_timer and self.gate_close_timer.is_alive():
                        self.gate_close_timer.cancel()
                        self.gate_close_timer = None
                        self._schedule_gate_close() # Jadwalkan ulang
            else:
                if not self.is_gate_open:
                    print(f"Plat '{plate_text}' terdeteksi. TIDAK DISETUJUI. Gerbang tetap tertutup.")
                    self.logger.log_access(plate_text, 'unauthorized')
                else:
                    print(f"Plat '{plate_text}' terdeteksi (tidak diizinkan). Gerbang sudah terbuka.")
                    # Jika gerbang terbuka dan plat tidak diizinkan terdeteksi, biarkan timer auto-close berjalan
            
            self.last_detection_time = current_time # Update waktu deteksi terakhir

    def _open_gate_and_schedule_close(self):
        """Membuka gerbang dan menjadwalkan penutupan otomatis."""
        self.stepper_motor.open_gate_thread()
        self._schedule_gate_close()

    def _schedule_gate_close(self):
        """Menjadwalkan penutupan gerbang otomatis setelah delay."""
        if self.gate_close_timer and self.gate_close_timer.is_alive():
            self.gate_close_timer.cancel() # Batalkan timer sebelumnya jika ada
        
        self.gate_close_timer = Thread(target=self._auto_close_gate_task)
        self.gate_close_timer.daemon = True # Agar thread berhenti saat program utama berhenti
        self.gate_close_timer.start()

    def _auto_close_gate_task(self):
        """Tugas untuk menutup gerbang otomatis setelah delay."""
        time.sleep(Config.AUTO_CLOSE_DELAY)
        with self.gate_action_lock:
            if self.is_gate_open: # Pastikan gerbang masih terbuka sebelum menutup
                self.stepper_motor.close_gate_thread()
                self.is_gate_open = False
                print("Gerbang otomatis tertutup.")

    def run(self):
        """Jalankan sistem pengenalan plat nomor utama."""
        print("=== Sistem Pengenalan Plat Nomor ===")
        print("Daftar plat yang diizinkan:")
        for plate in Config.AUTHORIZED_PLATES:
            print(f"- {plate}")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Error: Gagal membaca frame kamera. Pastikan kamera berfungsi.")
                    break
                
                # Proses frame untuk deteksi plat nomor
                processed_frame, detected_plates = self.process_frame(frame)
                
                # Proses setiap plat yang terdeteksi
                for plate_info in detected_plates:
                    self.handle_plate_detection(plate_info['text'])
                
                # Tampilkan status gerbang pada frame
                status_text = "GERBANG TERBUKA" if self.is_gate_open else "GERBANG TERTUTUP"
                color = (0, 255, 0) if self.is_gate_open else (0, 0, 255) # Hijau jika terbuka, Merah jika tertutup
                cv2.putText(processed_frame, status_text, (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)
                
                # Tampilkan frame di jendela
                cv2.imshow('Plate Recognition', processed_frame)
                
                # Tekan 'q' untuk keluar
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except Exception as e:
            print(f"Terjadi kesalahan fatal: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Bersihkan sumber daya sebelum keluar."""
        print("Membersihkan sumber daya...")
        if self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()
        self.stepper_motor.cleanup()
        print("Sistem dimatikan.")

# --- Main Execution ---
if __name__ == "__main__":
    # Pastikan Tesseract executable ada di path yang benar
    # Jika Anda menjalankan di lingkungan yang berbeda, sesuaikan Config.TESSERACT_PATH
    # Misalnya, di Windows: r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    # Inisialisasi dan jalankan sistem
    prs = PlateRecognitionSystem()
    prs.run()
