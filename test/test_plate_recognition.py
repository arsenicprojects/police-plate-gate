import unittest
import cv2
import numpy as np
import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from plate_recognition import PlateRecognizer
from utils import get_default_config, setup_logging

class TestPlateRecognition(unittest.TestCase):
    """Test cases for plate recognition module"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = get_default_config()
        self.logger = setup_logging()
        self.recognizer = PlateRecognizer(self.config, self.logger)
        
        # Create test image
        self.test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        self.test_image.fill(255)  # White background
    
    def test_initialization(self):
        """Test recognizer initialization"""
        self.assertFalse(self.recognizer.is_initialized)
        # Note: Full initialization requires trained models
    
    def test_clean_plate_text(self):
        """Test plate text cleaning"""
        # Test basic cleaning
        result = self.recognizer.clean_plate_text("R 3944 FG")
        self.assertEqual(result, "R3944FG")
        
        # Test with dots and dashes
        result = self.recognizer.clean_plate_text("R-3944.FG")
        self.assertEqual(result, "R3944FG")
        
        # Test lowercase conversion
        result = self.recognizer.clean_plate_text("r3944fg")
        self.assertEqual(result, "R3944FG")
    
    def test_validate_plate_format(self):
        """Test plate format validation"""
        # Valid formats
        valid_plates = ["R3944FG", "B1234AB", "AA1234BC"]
        for plate in valid_plates:
            self.assertTrue(self.recognizer.validate_plate_format(plate))
        
        # Invalid formats
        invalid_plates = ["123", "ABCD", "1234567890", ""]
        for plate in invalid_plates:
            self.assertFalse(self.recognizer.validate_plate_format(plate))
    
    def test_recognize_plate_uninitialized(self):
        """Test recognition when not initialized"""
        result = self.recognizer.recognize_plate(self.test_image)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Not initialized')
    
    def tearDown(self):
        """Clean up test environment"""
        pass

class TestPlateRecognitionIntegration(unittest.TestCase):
    """Integration tests for plate recognition"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.config = get_default_config()
        self.logger = setup_logging()
        self.recognizer = PlateRecognizer(self.config, self.logger)
        
        # Create test data directory
        self.test_data_dir = Path("test_data")
        self.test_data_dir.mkdir(exist_ok=True)
    
    def test_full_recognition_pipeline(self):
        """Test complete recognition pipeline"""
        # This would require actual test images and trained models
        # For now, we'll test the pipeline structure
        
        # Create a dummy image
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Test recognition (will fail without proper initialization)
        result = self.recognizer.recognize_plate(test_image)
        self.assertIn('success', result)
        self.assertIn('error', result)
    
    def tearDown(self):
        """Clean up integration test environment"""
        # Clean up test data
        import shutil
        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)

if __name__ == '__main__':
    unittest.main()
