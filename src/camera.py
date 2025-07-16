import cv2
import os
import time
import imutils
from pathlib import Path

class CameraManager:
    """Manages camera operations including initialization, frame capture, and processing"""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.cap = None
        self.mode = None
        self.image_path = None
        self.frame_width = config.get('frame_width', 620)
        self.save_counter = 0
        
    def initialize_camera(self, camera_index=0):
        """Initialize camera capture"""
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            self.logger.error(f"Failed to open camera {camera_index}")
            return False
        self.mode = 'camera'
        self.logger.info(f"Camera {camera_index} initialized")
        return True
    
    def initialize_video(self, video_path):
        """Initialize video file capture"""
        if not os.path.exists(video_path):
            self.logger.error(f"Video file not found: {video_path}")
            return False
        
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            self.logger.error(f"Failed to open video: {video_path}")
            return False
        self.mode = 'video'
        self.logger.info(f"Video file {video_path} initialized")
        return True
    
    def initialize_image(self, image_path):
        """Initialize single image processing"""
        if not os.path.exists(image_path):
            self.logger.error(f"Image file not found: {image_path}")
            return False
        
        self.image_path = image_path
        self.mode = 'image'
        self.logger.info(f"Image file {image_path} initialized")
        return True
    
    def get_frame(self):
        """Get next frame based on mode"""
        if self.mode == 'image':
            frame = cv2.imread(self.image_path)
            return frame
        elif self.mode in ['camera', 'video']:
            if self.cap is None:
                return None
            ret, frame = self.cap.read()
            if not ret:
                return None
            return frame
        return None
    
    def resize_frame(self, frame):
        """Resize frame to standard width"""
        if frame is None:
            return None
        return imutils.resize(frame, width=self.frame_width)
    
    def save_frame(self, frame):
        """Save current frame to file"""
        if frame is None:
            return False
        
        save_dir = Path(self.config['directories']['debug_frames'])
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"frame_{self.save_counter:04d}_{int(time.time())}.jpg"
        filepath = save_dir / filename
        
        success = cv2.imwrite(str(filepath), frame)
        if success:
            self.save_counter += 1
            self.logger.info(f"Frame saved: {filepath}")
        return success
    
    def cleanup(self):
        """Clean up camera resources"""
        if self.cap is not None:
            self.cap.release()
            self.logger.info("Camera resources cleaned up")
