import time
import threading
try:
    import RPi.GPIO as GPIO
except ImportError:
    # Mock GPIO for development on non-Raspberry Pi systems
    class MockGPIO:
        BCM = "BCM"
        IN = "IN"
        OUT = "OUT"
        HIGH = True
        LOW = False
        
        def setmode(self, mode):
            pass
        
        def setup(self, pin, mode):
            pass
        
        def output(self, pin, value):
            pass
        
        def input(self, pin):
            return False
        
        def cleanup(self):
            pass
    
    GPIO = MockGPIO()
    print("Warning: RPi.GPIO not available. Using mock GPIO for development.")

class UltrasonicSensor:
    """Ultrasonic sensor class for distance measurement"""
    
    def __init__(self, trig_pin, echo_pin):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.distance = float('inf')
        self.is_running = False
        self.monitor_thread = None
        self.lock = threading.Lock()
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        
        # Initialize trigger to low
        GPIO.output(self.trig_pin, GPIO.LOW)
        time.sleep(0.1)
    
    def measure_distance(self):
        """Measure distance using ultrasonic sensor"""
        try:
            # Send trigger pulse
            GPIO.output(self.trig_pin, GPIO.HIGH)
            time.sleep(0.00001)  # 10 microseconds
            GPIO.output(self.trig_pin, GPIO.LOW)
            
            # Wait for echo start
            pulse_start = time.time()
            timeout = pulse_start + 0.1  # 100ms timeout
            
            while GPIO.input(self.echo_pin) == GPIO.LOW:
                pulse_start = time.time()
                if pulse_start > timeout:
                    return float('inf')
            
            # Wait for echo end
            pulse_end = time.time()
            timeout = pulse_end + 0.1  # 100ms timeout
            
            while GPIO.input(self.echo_pin) == GPIO.HIGH:
                pulse_end = time.time()
                if pulse_end > timeout:
                    return float('inf')
            
            # Calculate distance
            pulse_duration = pulse_end - pulse_start
            distance = (pulse_duration * 34300) / 2  # Speed of sound = 343 m/s
            
            return distance
            
        except Exception as e:
            print(f"Error measuring distance: {e}")
            return float('inf')
    
    def monitor_distance(self):
        """Continuously monitor distance in background thread"""
        while self.is_running:
            new_distance = self.measure_distance()
            
            with self.lock:
                self.distance = new_distance
            
            time.sleep(0.1)  # Update every 100ms
    
    def start_monitoring(self):
        """Start background distance monitoring"""
        if not self.is_running:
            self.is_running = True
            self.monitor_thread = threading.Thread(target=self.monitor_distance)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop background distance monitoring"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def get_distance(self):
        """Get current distance reading"""
        with self.lock:
            return self.distance
    
    def is_object_detected(self, threshold):
        """Check if object is detected within threshold distance"""
        current_distance = self.get_distance()
        return current_distance != float('inf') and current_distance <= threshold
    
    def cleanup(self):
        """Clean up GPIO resources"""
        self.stop_monitoring()
        GPIO.cleanup()