import json
import logging
import os
from pathlib import Path
from datetime import datetime

def load_config(config_path):
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return get_default_config()
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in config file: {e}")
        return get_default_config()

def get_default_config():
    """Get default configuration"""
    return {
        "frame_width": 620,
        "homeowner_plates": ["R3944FG", "R5477DP"],
        "guest_plates": [],
        "verification_count": 3,
        "scan_cooldown": 2.0,
        "ultrasonic_threshold": 15,
        "trig_pin": 18,
        "echo_pin": 24,
        "known_plates": {
            "3944FG": "R",
            "5477DP": "R"
        },
        "directories": {
            "recognized_plates": "data/recognized_plates",
            "debug_frames": "data/debug_frames",
            "training_data": "data/training_data"
        },
        "logging": {
            "level": "INFO",
            "file": "data/system.log"
        }
    }

def setup_logging():
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    log_filename = log_dir / f"gate_system_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger('GateSystem')
    logger.info("Logging system initialized")
    return logger

def create_directories(config):
    """Create necessary directories"""
    directories = config.get('directories', {})
    
    for dir_name, dir_path in directories.items():
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Also create logs directory
    Path("data/logs").mkdir(parents=True, exist_ok=True)

def save_config(config, config_path):
    """Save configuration to JSON file"""
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save config: {e}")
        return False