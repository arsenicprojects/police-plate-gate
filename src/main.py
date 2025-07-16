import argparse
import cv2
import os
import sys
import time
from pathlib import Path

# Import local modules
from camera import CameraManager
from plate_recognition import PlateRecognizer
from gate_control import GateController
from utils import load_config, setup_logging, create_directories

def main():
    """Main function to run the automatic gate system"""
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Automatic Gate System")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Automatic Gate System')
    parser.add_argument('-v', '--video', help='Path to video file')
    parser.add_argument('-i', '--image', help='Path to image file')
    parser.add_argument('-c', '--camera', type=int, default=0, help='Camera index (default: 0)')
    parser.add_argument('--no-ultrasonic', action='store_true', help='Disable ultrasonic sensor')
    parser.add_argument('--config', default='data/config.json', help='Config file path')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Create necessary directories
    create_directories(config)
    
    # Initialize components
    camera_manager = CameraManager(config, logger)
    plate_recognizer = PlateRecognizer(config, logger)
    gate_controller = GateController(config, logger, not args.no_ultrasonic)
    
    try:
        # Initialize camera source
        if args.video:
            camera_manager.initialize_video(args.video)
        elif args.image:
            camera_manager.initialize_image(args.image)
        else:
            camera_manager.initialize_camera(args.camera)
        
        # Initialize plate recognizer
        if not plate_recognizer.initialize():
            logger.error("Failed to initialize plate recognizer")
            return
        
        # Initialize gate controller
        gate_controller.initialize()
        
        # Run main processing loop
        if args.image:
            process_single_image(camera_manager, plate_recognizer, gate_controller, logger)
        else:
            process_video_stream(camera_manager, plate_recognizer, gate_controller, logger)
            
    except KeyboardInterrupt:
        logger.info("System interrupted by user")
    except Exception as e:
        logger.error(f"System error: {e}")
    finally:
        # Cleanup
        camera_manager.cleanup()
        gate_controller.cleanup()
        cv2.destroyAllWindows()
        logger.info("System shutdown complete")

def process_single_image(camera_manager, plate_recognizer, gate_controller, logger):
    """Process a single image"""
    frame = camera_manager.get_frame()
    if frame is None:
        logger.error("Failed to load image")
        return
    
    # Resize frame
    frame = camera_manager.resize_frame(frame)
    
    # Recognize plate
    result = plate_recognizer.recognize_plate(frame)
    
    if result['success']:
        logger.info(f"Plate detected: {result['plate']}")
        
        # Check access
        access_result = gate_controller.check_access(result['plate'])
        
        # Display results
        display_frame = gate_controller.draw_results(frame, result, access_result)
        
        cv2.imshow("Automatic Gate System", display_frame)
        cv2.waitKey(0)
    else:
        logger.info("No plate detected")
        cv2.imshow("Automatic Gate System", frame)
        cv2.waitKey(0)

def process_video_stream(camera_manager, plate_recognizer, gate_controller, logger):
    """Process video stream (camera or video file)"""
    logger.info("Starting video processing...")
    
    while True:
        frame = camera_manager.get_frame()
        if frame is None:
            break
        
        # Resize frame
        frame = camera_manager.resize_frame(frame)
        
        # Check if object is detected (ultrasonic sensor)
        if not gate_controller.should_process_frame():
            # Display standby status
            display_frame = gate_controller.draw_standby_status(frame)
            cv2.imshow("Automatic Gate System", display_frame)
            
            if cv2.waitKey(1) & 0xFF == 27:  # ESC key
                break
            continue
        
        # Process frame for plate recognition
        result = plate_recognizer.recognize_plate(frame)
        
        if result['success']:
            # Check access
            access_result = gate_controller.check_access(result['plate'])
            
            # Update verification buffer
            gate_controller.update_verification(result['plate'])
            
            # Check if plate is verified
            if gate_controller.is_plate_verified():
                logger.info(f"Verified plate: {result['plate']}")
                
                # Save result
                gate_controller.save_result(frame, result, access_result)
                
                # Control gate if access granted
                if access_result['access_granted']:
                    gate_controller.open_gate()
        
        # Display results
        display_frame = gate_controller.draw_results(frame, result, gate_controller.get_last_access_result())
        cv2.imshow("Automatic Gate System", display_frame)
        
        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC key
            break
        elif key == ord('s'):  # Save frame
            camera_manager.save_frame(frame)

if __name__ == "__main__":
    main()