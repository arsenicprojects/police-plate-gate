import cv2
import json
import time
from pathlib import Path
from datetime import datetime

try:
    from ultrasonic_sensor import UltrasonicSensor
except ImportError:
    print("Warning: Ultrasonic sensor module not found")
    UltrasonicSensor = None

class GateController:
    """Controls gate operations and access management"""
    
    def __init__(self, config, logger, use_ultrasonic=True):
        self.config = config
        self.logger = logger
        self.use_ultrasonic = use_ultrasonic and UltrasonicSensor is not None
        self.ultrasonic_sensor = None
        
        # Access control
        self.homeowner_plates = config.get('homeowner_plates', [])
        self.guest_plates = config.get('guest_plates', [])
        
        # Verification system
        self.verification_buffer = []
        self.verification_count = config.get('verification_count', 3)
        self.last_verified_plate = ""
        
        # Timing
        self.last_scan_time = 0
        self.scan_cooldown = config.get('scan_cooldown', 2.0)
        
        # Ultrasonic settings
        self.ultrasonic_threshold = config.get('ultrasonic_threshold', 15)
        self.trig_pin = config.get('trig_pin', 18)
        self.echo_pin = config.get('echo_pin', 24)
        
        # Display colors (BGR format)
        self.colors = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'green': (0, 255, 0),
            'red': (0, 0, 255),
            'yellow': (0, 255, 255),
            'orange': (0, 165, 255),
            'blue': (255, 0, 0)
        }
        
        # Last access result for display
        self.last_access_result = None
        
    def initialize(self):
        """Initialize gate controller"""
        if self.use_ultrasonic:
            try:
                self.ultrasonic_sensor = UltrasonicSensor(self.trig_pin, self.echo_pin)
                self.ultrasonic_sensor.start_monitoring()
                self.logger.info(f"Ultrasonic sensor initialized - Threshold: {self.ultrasonic_threshold}cm")
            except Exception as e:
                self.logger.warning(f"Failed to initialize ultrasonic sensor: {e}")
                self.use_ultrasonic = False
        
        self.logger.info("Gate controller initialized")
    
    def should_process_frame(self):
        """Check if frame should be processed based on ultrasonic sensor"""
        if not self.use_ultrasonic or not self.ultrasonic_sensor:
            return True
        
        current_time = time.time()
        object_detected = self.ultrasonic_sensor.is_object_detected(self.ultrasonic_threshold)
        cooldown_passed = (current_time - self.last_scan_time) > self.scan_cooldown
        
        if object_detected and cooldown_passed:
            self.last_scan_time = current_time
            distance = self.ultrasonic_sensor.get_distance()
            self.logger.info(f"Object detected at {distance:.1f}cm - Processing frame")
            return True
        
        return False
    
    def check_access(self, plate):
        """Check if plate has access permission"""
        if not plate:
            return {
                'access_granted': False,
                'message': 'No plate detected',
                'color': self.colors['red'],
                'type': 'error'
            }
        
        if plate in self.homeowner_plates:
            result = {
                'access_granted': True,
                'message': f'ACCESS GRANTED - Homeowner: {plate}',
                'color': self.colors['green'],
                'type': 'homeowner'
            }
        elif plate in self.guest_plates:
            result = {
                'access_granted': True,
                'message': f'ACCESS GRANTED - Guest: {plate}',
                'color': self.colors['blue'],
                'type': 'guest'
            }
        else:
            result = {
                'access_granted': False,
                'message': f'ACCESS DENIED - Unknown: {plate}',
                'color': self.colors['red'],
                'type': 'unknown'
            }
        
        self.last_access_result = result
        return result
    
    def update_verification(self, plate):
        """Update verification buffer"""
        if len(self.verification_buffer) >= self.verification_count:
            self.verification_buffer.pop(0)
        self.verification_buffer.append(plate)
    
    def is_plate_verified(self):
        """Check if plate is verified (appears N times consecutively)"""
        if len(self.verification_buffer) < self.verification_count:
            return False
        
        # Check if all plates in buffer are the same
        unique_plates = set(self.verification_buffer)
        if len(unique_plates) == 1:
            current_plate = list(unique_plates)[0]
            if current_plate != self.last_verified_plate:
                self.last_verified_plate = current_plate
                return True
        
        return False
    
    def open_gate(self):
        """Open the gate (placeholder for actual gate control)"""
        self.logger.info("GATE OPENED")
        # Here you would add actual gate control logic
        # For example: GPIO control, servo motor, relay activation, etc.
        
        # Simulate gate opening time
        time.sleep(0.5)
        
        # Schedule gate closing (you might want to implement this properly)
        # self.schedule_gate_close()
    
    def save_result(self, frame, recognition_result, access_result):
        """Save recognition result to file"""
        try:
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plate = recognition_result.get('plate', 'unknown')
            filename = f"{timestamp}_{plate}.jpg"
            
            # Save to recognized_plates directory
            save_dir = Path(self.config['directories']['recognized_plates'])
            save_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = save_dir / filename
            
            # Draw results on frame before saving
            display_frame = self.draw_results(frame, recognition_result, access_result)
            
            success = cv2.imwrite(str(filepath), display_frame)
            if success:
                self.logger.info(f"Result saved: {filepath}")
                
                # Also save metadata
                metadata = {
                    'timestamp': timestamp,
                    'plate': plate,
                    'raw_text': recognition_result.get('raw_text', ''),
                    'confidence': recognition_result.get('confidence', 0),
                    'access_granted': access_result['access_granted'],
                    'access_type': access_result['type']
                }
                
                metadata_file = save_dir / f"{timestamp}_{plate}.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to save result: {e}")
            return False
    
    def draw_results(self, frame, recognition_result, access_result):
        """Draw recognition and access results on frame"""
        display_frame = frame.copy()
        
        # Draw detection area rectangle
        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2
        rect_w, rect_h = 460, 160
        
        cv2.rectangle(display_frame, 
                     (center_x - rect_w//2, center_y - rect_h//2),
                     (center_x + rect_w//2, center_y + rect_h//2),
                     self.colors['green'], 2)
        
        # Draw ultrasonic sensor status
        if self.use_ultrasonic and self.ultrasonic_sensor:
            self.draw_sensor_status(display_frame)
        
        # Draw recognition results
        if recognition_result and recognition_result.get('success'):
            self.draw_plate_info(display_frame, recognition_result)
        
        # Draw access results
        if access_result:
            self.draw_access_message(display_frame, access_result)
        
        # Draw homeowner plates list
        self.draw_homeowner_list(display_frame)
        
        # Draw instructions
        cv2.putText(display_frame, "Press 's' to save, 'ESC' to exit", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['white'], 1)
        
        return display_frame
    
    def draw_standby_status(self, frame):
        """Draw standby status when no object detected"""
        display_frame = frame.copy()
        
        # Draw sensor status
        if self.use_ultrasonic and self.ultrasonic_sensor:
            self.draw_sensor_status(display_frame)
        
        # Draw standby message
        cv2.putText(display_frame, "SYSTEM STANDBY - NO OBJECT DETECTED", 
                   (10, frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.6, self.colors['yellow'], 2)
        
        return display_frame
    
    def draw_sensor_status(self, frame):
        """Draw ultrasonic sensor status"""
        if not self.ultrasonic_sensor:
            return
        
        distance = self.ultrasonic_sensor.get_distance()
        is_detected = self.ultrasonic_sensor.is_object_detected(self.ultrasonic_threshold)
        
        # Status text
        if distance == float('inf'):
            status_text = "Ultrasonic: No Object"
            color = self.colors['white']
        else:
            status_text = f"Ultrasonic: {distance:.1f}cm"
            color = self.colors['green'] if is_detected else self.colors['orange']
        
        cv2.putText(frame, status_text, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.6, color, 2)
        
        # Detection status
        detection_text = "OBJECT DETECTED" if is_detected else "WAITING..."
        detection_color = self.colors['green'] if is_detected else self.colors['yellow']
        cv2.putText(frame, detection_text, (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.6, detection_color, 1)
    
    def draw_plate_info(self, frame, recognition_result):
        """Draw plate recognition information"""
        y_offset = 200
        
        # Raw text
        raw_text = recognition_result.get('raw_text', '')
        cv2.putText(frame, f"Raw: {raw_text}", (10, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['white'], 1)
        
        # Cleaned text
        plate = recognition_result.get('plate', '')
        cv2.putText(frame, f"Cleaned: {plate}", (10, y_offset + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['yellow'], 1)
        
        # Validity
        is_valid = recognition_result.get('is_valid', False)
        status_color = self.colors['green'] if is_valid else self.colors['red']
        status_text = "VALID" if is_valid else "INVALID"
        cv2.putText(frame, f"Status: {status_text}", (10, y_offset + 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 1)
        
        # Confidence
        confidence = recognition_result.get('confidence', 0)
        cv2.putText(frame, f"Confidence: {confidence:.2f}", (10, y_offset + 75), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['white'], 1)
    
    def draw_access_message(self, frame, access_result):
        """Draw access control message"""
        message = access_result['message']
        color = access_result['color']
        
        # Calculate text size for background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
        
        # Position
        x, y = 50, 350
        padding = 10
        
        # Draw background
        cv2.rectangle(frame, 
                     (x - padding, y - text_size[1] - padding),
                     (x + text_size[0] + padding, y + padding),
                     (0, 0, 0), -1)
        
        # Draw border
        cv2.rectangle(frame, 
                     (x - padding, y - text_size[1] - padding),
                     (x + text_size[0] + padding, y + padding),
                     color, 2)
        
        # Draw text
        cv2.putText(frame, message, (x, y), font, font_scale, color, thickness)
    
    def draw_homeowner_list(self, frame):
        """Draw list of homeowner plates"""
        plates_text = f"Homeowner plates: {', '.join(self.homeowner_plates)}"
        cv2.putText(frame, plates_text, (10, frame.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['white'], 1)
    
    def get_last_access_result(self):
        """Get the last access result for display"""
        return self.last_access_result
    
    def cleanup(self):
        """Clean up resources"""
        if self.ultrasonic_sensor:
            self.ultrasonic_sensor.cleanup()
            self.logger.info("Ultrasonic sensor cleaned up")
