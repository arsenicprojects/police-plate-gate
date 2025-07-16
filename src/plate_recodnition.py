import cv2
import re
import numpy as np
from pathlib import Path

# Import original modules (these would need to be adapted)
try:
    import DetectChars
    import DetectPlates
    import Preprocess as pp
    import imutils
except ImportError:
    print("Warning: Original detection modules not found. Please ensure they are available.")

class PlateRecognizer:
    """Handles license plate recognition and validation"""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.is_initialized = False
        self.validation_patterns = [
            r'^[A-Z]{1,2}\d{1,4}[A-Z]{1,3}$',
            r'^[A-Z]\d{4}[A-Z]{2}$',
        ]
        
    def initialize(self):
        """Initialize the plate recognition system"""
        try:
            # Load KNN data for character recognition
            if 'DetectChars' in globals():
                success = DetectChars.loadKNNDataAndTrainKNN()
                if not success:
                    self.logger.error("Failed to load KNN data")
                    return False
            
            self.is_initialized = True
            self.logger.info("Plate recognizer initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize plate recognizer: {e}")
            return False
    
    def recognize_plate(self, frame):
        """Recognize license plate from frame"""
        if not self.is_initialized:
            return {'success': False, 'error': 'Not initialized'}
        
        try:
            # Preprocess the image
            _, img_thresh = pp.preprocess(frame)
            
            # Transform image
            frame_transformed = imutils.transform(frame)
            
            # Detect plates
            possible_plates = DetectPlates.detectPlatesInScene(frame_transformed)
            
            # Detect characters in plates
            possible_plates = DetectChars.detectCharsInPlates(possible_plates)
            
            if len(possible_plates) == 0:
                return {'success': False, 'error': 'No plates detected'}
            
            # Sort by number of characters (most likely candidate first)
            possible_plates.sort(key=lambda plate: len(plate.strChars), reverse=True)
            best_plate = possible_plates[0]
            
            if len(best_plate.strChars) == 0:
                return {'success': False, 'error': 'No characters detected'}
            
            # Clean and validate the detected text
            raw_text = best_plate.strChars
            cleaned_text = self.clean_plate_text(raw_text)
            
            is_valid = self.validate_plate_format(cleaned_text)
            
            result = {
                'success': True,
                'plate': cleaned_text,
                'raw_text': raw_text,
                'confidence': len(best_plate.strChars) / 7.0,  # Normalized confidence
                'is_valid': is_valid,
                'plate_object': best_plate
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in plate recognition: {e}")
            return {'success': False, 'error': str(e)}
    
    def clean_plate_text(self, raw_text):
        """Clean and normalize plate text"""
        if not raw_text:
            return ""
        
        # Remove spaces, dots, and dashes
        cleaned = raw_text.replace(" ", "").replace(".", "").replace("-", "").upper()
        
        # Handle known patterns for missing letters
        if cleaned and cleaned[0].isdigit():
            # Check for specific known plates
            known_plates = self.config.get('known_plates', {})
            for pattern, prefix in known_plates.items():
                if cleaned == pattern:
                    return prefix + cleaned
            
            # Apply general pattern for plates starting with digits
            if len(cleaned) >= 6 and re.match(r'^\d{4}[A-Z]{2}$', cleaned):
                return "R" + cleaned
        
        return cleaned
    
    def validate_plate_format(self, plate_text):
        """Validate if plate text matches expected format"""
        if not plate_text or len(plate_text) < 5:
            return False
        
        for pattern in self.validation_patterns:
            if re.match(pattern, plate_text):
                return True
        
        return False
