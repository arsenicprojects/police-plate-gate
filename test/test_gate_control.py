import unittest
import cv2
import numpy as np
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gate_control import GateController
from utils import get_default_config, setup_logging

class TestGateController(unittest.TestCase):
    """Test cases for gate control module"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = get_default_config()
        self.logger = setup_logging()
        self.controller = GateController(self.config, self.logger, use_ultrasonic=False)
        
        # Create test image
        self.test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        self.test_image.fill(255)  # White background
    
    def test_initialization(self):
        """Test controller initialization"""
        self.assertIsNotNone(self.controller.homeowner_plates)
        self.assertIsNotNone(self.controller.guest_plates)
        self.assertEqual(self.controller.verification_count, 3)
        self.assertFalse(self.controller.use_ultrasonic)
    
    def test_check_access_homeowner(self):
        """Test access check for homeowner plates"""
        result = self.controller.check_access("R3944FG")
        self.assertTrue(result['access_granted'])
        self.assertEqual(result['type'], 'homeowner')
        self.assertIn('Homeowner', result['message'])
    
    def test_check_access_guest(self):
        """Test access check for guest plates"""
        # Add guest plate
        self.controller.guest_plates.append("G1234AB")
        
        result = self.controller.check_access("G1234AB")
        self.assertTrue(result['access_granted'])
        self.assertEqual(result['type'], 'guest')
        self.assertIn('Guest', result['message'])
    
    def test_check_access_unknown(self):
        """Test access check for unknown plates"""
        result = self.controller.check_access("X9999XX")
        self.assertFalse(result['access_granted'])
        self.assertEqual(result['type'], 'unknown')
        self.assertIn('Unknown', result['message'])
    
    def test_check_access_empty(self):
        """Test access check for empty plate"""
        result = self.controller.check_access("")
        self.assertFalse(result['access_granted'])
        self.assertEqual(result['type'], 'error')
        self.assertIn('No plate', result['message'])
    
    def test_verification_buffer(self):
        """Test verification buffer functionality"""
        # Add plates to buffer
        self.controller.update_verification("R3944FG")
        self.controller.update_verification("R3944FG")
        self.assertFalse(self.controller.is_plate_verified())
        
        self.controller.update_verification("R3944FG")
        self.assertTrue(self.controller.is_plate_verified())
        
        # Test buffer overflow
        self.controller.update_verification("R5477DP")
        self.assertFalse(self.controller.is_plate_verified())
    
    def test_should_process_frame_no_ultrasonic(self):
        """Test frame processing decision without ultrasonic"""
        # Without ultrasonic, should always process
        self.assertTrue(self.controller.should_process_frame())
    
    @patch('gate_control.UltrasonicSensor')
    def test_should_process_frame_with_ultrasonic(self, mock_sensor):
        """Test frame processing decision with ultrasonic"""
        # Mock ultrasonic sensor
        mock_sensor_instance = Mock()
        mock_sensor_instance.is_object_detected.return_value = True
        mock_sensor_instance.get_distance.return_value = 10.0
        mock_sensor.return_value = mock_sensor_instance
        
        # Create controller with ultrasonic
        controller = GateController(self.config, self.logger, use_ultrasonic=True)
        controller.ultrasonic_sensor = mock_sensor_instance
        
        # Should process when object detected
        self.assertTrue(controller.should_process_frame())
    
    def test_draw_results(self):
        """Test drawing results on frame"""
        # Create recognition and access results
        recognition_result = {
            'success': True,
            'plate': 'R3944FG',
            'raw_text': 'R 3944 FG',
            'confidence': 0.85,
            'is_valid': True
        }
        
        access_result = {
            'access_granted': True,
            'message': 'ACCESS GRANTED - Homeowner: R3944FG',
            'color': (0, 255, 0),
            'type': 'homeowner'
        }
        
        # Draw results
        result_frame = self.controller.draw_results(
            self.test_image, recognition_result, access_result
        )
        
        # Check that frame was modified
        self.assertFalse(np.array_equal(self.test_image, result_frame))
        self.assertEqual(result_frame.shape, self.test_image.shape)
    
    def test_draw_standby_status(self):
        """Test drawing standby status"""
        standby_frame = self.controller.draw_standby_status(self.test_image)
        
        # Check that frame was modified
        self.assertFalse(np.array_equal(self.test_image, standby_frame))
        self.assertEqual(standby_frame.shape, self.test_image.shape)
    
    @patch('cv2.imwrite')
    @patch('builtins.open')
    def test_save_result(self, mock_open, mock_imwrite):
        """Test saving recognition result"""
        mock_imwrite.return_value = True
        mock_open.return_value.__enter__.return_value = Mock()
        
        recognition_result = {
            'plate': 'R3944FG',
            'raw_text': 'R 3944 FG',
            'confidence': 0.85
        }
        
        access_result = {
            'access_granted': True,
            'type': 'homeowner'
        }
        
        result = self.controller.save_result(
            self.test_image, recognition_result, access_result
        )
        
        self.assertTrue(result)
        mock_imwrite.assert_called_once()
    
    def test_open_gate(self):
        """Test gate opening functionality"""
        # This is a placeholder test since actual gate control
        # would require hardware
        try:
            self.controller.open_gate()
            # If no exception, test passes
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Gate opening failed: {e}")
    
    def tearDown(self):
        """Clean up test environment"""
        self.controller.cleanup()

class TestGateControllerIntegration(unittest.TestCase):
    """Integration tests for gate controller"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.config = get_default_config()
        self.logger = setup_logging()
        self.controller = GateController(self.config, self.logger, use_ultrasonic=False)
        
        # Create test directories
        self.test_dir = Path("test_output")
        self.test_dir.mkdir(exist_ok=True)
        
        # Update config for testing
        self.config['directories']['recognized_plates'] = str(self.test_dir)
    
    def test_full_access_control_flow(self):
        """Test complete access control flow"""
        # Test homeowner access
        plate = "R3944FG"
        
        # Check access
        access_result = self.controller.check_access(plate)
        self.assertTrue(access_result['access_granted'])
        
        # Update verification
        for _ in range(3):
            self.controller.update_verification(plate)
        
        # Check verification
        self.assertTrue(self.controller.is_plate_verified())
        
        # Test gate opening (without hardware)
        try:
            self.controller.open_gate()
            self.assertTrue(True)
        except Exception:
            self.fail("Gate control flow failed")
    
    def tearDown(self):
        """Clean up integration test environment"""
        # Clean up test directories
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        self.controller.cleanup()

if __name__ == '__main__':
    unittest.main()
