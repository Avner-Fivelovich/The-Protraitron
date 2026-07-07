import os
import yaml
from src.common.logger import get_logger

# Initialize a config-specific logger
logger = get_logger("Config")

def load_config_from_yaml(config_path: str) -> dict:
    """
    Loads configuration parameters from the specified YAML configuration file.
    Flattens nested sections (calibration, approach, verification, compliance, 
    slide, retraction, cleanup) and falls back to default values.
    """
    # -------------------------------------------------------------
    # Default parameters for calibration, probing, sliding, and cleanup
    # -------------------------------------------------------------
    defaults = {
        'forward_force': 0.5,
        'sensor_zero_sleep': 0.5,
        'search_distance': 0.15,
        'initial_approach_speed': 0.001,
        'approach_acceleration': 0.005,
        'force_threshold': 0.9,
        'target_reached_tolerance': 0.001,
        'required_consecutive_high': 1,
        'stop_deceleration': 2.0,
        'polling_interval_search': 0.01,
        'force_verification': 0.5,
        'total_verify_readings': 5,
        'required_verify_high': 3,
        'max_consecutive_low': 2,
        'polling_interval_verify': 0.05,
        'speed_slowdown_factor': 0.5,
        'settle_sleep': 0.5,
        'force_damping': 0.5,
        'force_limits': [0.15, 0.15, 0.15, 0.2, 0.2, 0.2],
        'stabilize_timeout': 2.0,
        'stabilize_poll_interval': 0.1,
        'force_type_tool': 2,
        'tool_task_frame': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        'tool_selection_vector': [1, 0, 0, 0, 0, 0],
        'slide_distance': 0.05,
        'slide_speed': 0.02,
        'slide_acceleration': 0.1,
        'slide_accuracy': 0.003,
        'slide_poll_interval': 0.1,
        'post_slide_sleep': 1.0,
        'm_to_cm_multiplier': 100.0,
        'retract_distance': 0.03,
        'retract_speed': 0.5,
        'retract_acceleration': 0.25,
        'disconnect_stop_deceleration': 2.0,
        'blend_radius': 0.002,
        'draw_depth_offset': 0.0
    }

    # -------------------------------------------------------------
    # Attempt to load from custom file and override defaults
    # -------------------------------------------------------------
    if os.path.exists(config_path):
        logger.info(f"Loading parameters from {config_path}...")
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Flatten nested sections into defaults
            if config:
                sections = ['calibration', 'approach', 'verification', 'compliance', 'slide', 'retraction', 'cleanup', 'drawing']
                for section in sections:
                    if section in config and isinstance(config[section], dict):
                        for k, v in config[section].items():
                            if k in defaults:
                                defaults[k] = v
            logger.info("Successfully loaded configuration parameters.")
        except Exception as e:
            logger.error(f"Failed to parse config, using default values: {e}")
    else:
        logger.warning(f"Configuration file not found at {config_path}, using default parameters.")
    return defaults
