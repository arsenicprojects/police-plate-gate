# Pintu Gerbang Otomatis (Automatic Gate System)

Sistem pintu gerbang otomatis dengan pengenalan plat nomor kendaraan menggunakan OpenCV dan Python untuk Raspberry Pi.

## Fitur Utama

- **Pengenalan Plat Nomor**: Menggunakan OpenCV untuk mendeteksi dan membaca plat nomor kendaraan
- **Kontrol Akses**: Sistem otorisasi berdasarkan daftar plat yang diizinkan
- **Sensor Ultrasonik**: Deteksi kehadiran kendaraan untuk optimasi pemrosesan
- **Kontrol Servo**: Pembukaan dan penutupan gerbang otomatis
- **Logging**: Pencatatan semua aktivitas sistem
- **Verifikasi Berganda**: Sistem verifikasi untuk mengurangi false positive

## Struktur Proyek

```
PintuGerbangOtomatis/
├── src/                    # Kode sumber utama
│   ├── main.py            # File utama aplikasi
│   ├── camera.py          # Modul manajemen kamera
│   ├── plate_recognition.py # Modul pengenalan plat
│   ├── gate_control.py    # Modul kontrol gerbang
│   ├── ultrasonic_sensor.py # Modul sensor ultrasonik
│   └── utils.py           # Fungsi utilitas
├── data/                  # Data dan konfigurasi
│   ├── config.json        # File konfigurasi
│   ├── recognized_plates/ # Hasil pengenalan tersimpan
│   └── training_data/     # Data training (opsional)
├── models/               # Model ML (jika diperlukan)
├── tests/               # Unit tests
├── docs/                # Dokumentasi
└── requirements.txt     # Dependencies
```

## Persyaratan Sistem

### Hardware

- Raspberry Pi 4 (atau yang lebih baru)
- Kamera Raspberry Pi atau USB camera
- Sensor ultrasonik HC-SR04
- Servo motor untuk kontrol gerbang
- Breadboard dan kabel jumper

### Software

- Python 3.8+
- OpenCV 4.5+
- Raspberry Pi OS

## Instalasi

1. **Clone repository**

```bash
git clone https://github.com/username/PintuGerbangOtomatis.git
cd PintuGerbangOtomatis
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Setup hardware**

- Hubungkan kamera ke Raspberry Pi
- Hubungkan sensor ultrasonik (Trig: GPIO 18, Echo: GPIO 24)
- Hubungkan servo motor (Signal: GPIO 12)

4. **Konfigurasi**

```bash
cp data/config.json.example data/config.json
nano data/config.json
```

## Penggunaan

### Menjalankan Sistem

```bash
# Jalankan dengan kamera default
python src/main.py

# Jalankan dengan file video
python src/main.py -v path/to/video.mp4

# Jalankan dengan gambar tunggal
python src/main.py -i path/to/image.jpg

# Jalankan tanpa sensor ultrasonik
python src/main.py --no-ultrasonic

# Gunakan konfigurasi custom
python src/main.py --config path/to/config.json
```

### Konfigurasi Plat Nomor

Edit file `data/config.json`:

```json
{
  "homeowner_plates": ["R3944FG", "R5477DP"],
  "guest_plates": ["G1234AB"],
  "verification_count": 3,
  "ultrasonic_threshold": 15
}
```

### Kontrol Keyboard

- `ESC`: Keluar dari sistem
- `s`: Simpan frame saat ini
- `q`: Quit (alternatif ESC)

## Konfigurasi

### File Konfigurasi Utama (`data/config.json`)

```json
{
  "frame_width": 620,
  "homeowner_plates": ["R3944FG", "R5477DP"],
  "guest_plates": [],
  "verification_count": 3,
  "scan_cooldown": 2.0,
  "ultrasonic_threshold": 15,
  "trig_pin": 18,
  "echo_pin": 24,
  "gate_control": {
    "servo_pin": 12,
    "servo_open_angle": 90,
    "servo_close_angle": 0,
    "gate_open_time": 5.0
  }
}
```

### Parameter Penting

- `homeowner_plates`: Daftar plat pemilik rumah
- `guest_plates`: Daftar plat tamu
- `verification_count`: Jumlah deteksi berturut-turut untuk verifikasi
- `ultrasonic_threshold`: Jarak deteksi sensor (cm)
- `scan_cooldown`: Waktu tunggu antar scan (detik)

## Testing

```bash
# Jalankan semua test
python -m pytest tests/

# Test specific module
python -m pytest tests/test_plate_recognition.py

# Test dengan coverage
python -m pytest tests/ --cov=src/
```

## Troubleshooting

### Masalah Umum

1. **Kamera tidak terdeteksi**

   - Pastikan kamera terhubung dengan benar
   - Coba ganti camera index: `python src/main.py -c 1`

2. **Sensor ultrasonik tidak berfungsi**

   - Periksa koneksi GPIO
   - Jalankan dengan `--no-ultrasonic` untuk debug

3. **Pengenalan plat tidak akurat**
   - Periksa pencahayaan
   - Sesuaikan posisi kamera
   - Update training data jika diperlukan

### Log Files

Log sistem tersimpan di `data/logs/gate_system_YYYYMMDD.log`

## Kontribusi

1. Fork repository
2. Buat feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit perubahan (`git commit -m 'Add some AmazingFeature'`)
4. Push ke branch (`git push origin feature/AmazingFeature`)
5. Buat Pull Request

## Lisensi

Distributed under the MIT License. See `LICENSE` for more information.

## Kontak

Email: developer@example.com
Project Link: https://github.com/username/PintuGerbangOtomatis

# ========== /docs/setup_guide.md ==========

# Panduan Setup Pintu Gerbang Otomatis

## Persiapan Hardware

### Komponen yang Diperlukan

1. **Raspberry Pi 4** (minimum 4GB RAM)
2. **Kamera Raspberry Pi** atau USB Camera
3. **Sensor Ultrasonik HC-SR04**
4. **Servo Motor SG90** (atau yang kompatibel)
5. **Breadboard** dan kabel jumper
6. **Catu daya 5V** untuk Raspberry Pi
7. **MicroSD Card** (minimum 32GB, Class 10)

### Skema Koneksi

#### Sensor Ultrasonik HC-SR04

```
HC-SR04    Raspberry Pi
VCC    ->  5V (Pin 2)
GND    ->  Ground (Pin 6)
Trig   ->  GPIO 18 (Pin 12)
Echo   ->  GPIO 24 (Pin 18)
```

#### Servo Motor

```
Servo      Raspberry Pi
VCC    ->  5V (Pin 4)
GND    ->  Ground (Pin 14)
Signal ->  GPIO 12 (Pin 32)
```

#### Kamera

- Gunakan ribbon cable untuk Raspberry Pi Camera
- Atau koneksi USB untuk USB Camera

## Instalasi Software

### 1. Persiapan Raspberry Pi OS

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dan pip
sudo apt install python3 python3-pip -y

# Install sistem dependencies
sudo apt install libopencv-dev python3-opencv -y
sudo apt install libatlas-base-dev libjasper-dev -y
sudo apt install libqtgui4 libqt4-test -y
```

### 2. Enable Camera dan GPIO

```bash
# Enable camera
sudo raspi-config
# Navigation: Interface Options > Camera > Yes

# Enable I2C, SPI (optional)
sudo raspi-config
# Navigation: Interface Options > I2C > Yes
# Navigation: Interface Options > SPI > Yes

# Reboot
sudo reboot
```

### 3. Install Project Dependencies

```bash
# Clone project
git clone https://github.com/username/PintuGerbangOtomatis.git
cd PintuGerbangOtomatis

# Install Python dependencies
pip3 install -r requirements.txt

# Install additional OpenCV dependencies
pip3 install opencv-contrib-python

# Install RPi.GPIO
pip3 install RPi.GPIO
```

### 4. Verifikasi Instalasi

```bash
# Test camera
python3 -c "import cv2; print('OpenCV version:', cv2.__version__)"

# Test GPIO
python3 -c "import RPi.GPIO as GPIO; print('GPIO imported successfully')"

# Test sensor
python3 tests/test_hardware.py
```

## Konfigurasi Sistem

### 1. Setup Konfigurasi Dasar

```bash
# Copy dan edit konfigurasi
cp data/config.json.example data/config.json
nano data/config.json
```

### 2. Konfigurasi Plat Nomor

Edit `data/config.json`:

```json
{
  "homeowner_plates": ["R3944FG", "R5477DP"],
  "guest_plates": ["G1234AB", "G5678CD"]
}
```

### 3. Kalibrasi Sensor

```bash
# Jalankan kalibrasi sensor
python3 src/calibrate_sensor.py
```

### 4. Test Kamera

```bash
# Test kamera
python3 src/test_camera.py
```

## Optimasi Performa

### 1. Pengaturan Memory

Edit `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Tambahkan:

```
# Increase GPU memory
gpu_mem=128

# Enable camera
start_x=1

# Overclock (optional, hati-hati dengan suhu)
arm_freq=1750
over_voltage=6
```

### 2. Optimasi OpenCV

```bash
# Install optimized OpenCV (optional)
pip3 uninstall opencv-python
pip3 install opencv-contrib-python==4.5.5.64
```

### 3. Pengaturan Swap

```bash
# Increase swap size
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

## Kalibrasi Sistem

### 1. Kalibrasi Kamera

```bash
# Jalankan kalibrasi kamera
python3 src/calibrate_camera.py
```

### 2. Kalibrasi Sensor Ultrasonik

```bash
# Test jarak sensor
python3 src/test_ultrasonic.py

# Sesuaikan threshold di config.json
"ultrasonic_threshold": 15
```

### 3. Kalibrasi Servo

```bash
# Test servo
python3 src/test_servo.py

# Sesuaikan sudut di config.json
"gate_control": {
  "servo_open_angle": 90,
  "servo_close_angle": 0
}
```

## Setup Otomatis (Systemd)

### 1. Buat Service File

```bash
sudo nano /etc/systemd/system/gate-system.service
```

Isi file:

```ini
[Unit]
Description=Automatic Gate System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/PintuGerbangOtomatis
ExecStart=/usr/bin/python3 /home/pi/PintuGerbangOtomatis/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Enable Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable gate-system.service

# Start service
sudo systemctl start gate-system.service

# Check status
sudo systemctl status gate-system.
```
