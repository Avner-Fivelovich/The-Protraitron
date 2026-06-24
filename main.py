#!/usr/bin/env python3
import sys
import os
import time
import math
import numpy as np

# -------------------------------------------------------------
# Add root folder to sys.path so we can import src modules
# -------------------------------------------------------------
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.common.logger import get_logger
from src.robot.controller import UR5eController
from src.robot.poc_drawing import run_poc

# Initialize main system logger
logger = get_logger("MainSystem")

# Sockets and configurations defaults
ROBOT_IP = "192.168.57.101"
CALIBRATION_PATH = "config/calibration.yaml"
MARKER_CONFIG_PATH = "config/marker.yaml"

def main():
    """
    Displays interactive options to the user and dispatches actions based on selection.
    """
    if not os.path.exists(CALIBRATION_PATH):
        logger.critical("Cannot run POC: Calibration file is missing. Please run calibrate_workspace.py first.")
        sys.exit(1)
        
    logger.info("Initializing UR5e Controller...")
    controller = UR5eController(ROBOT_IP, calibration_path=CALIBRATION_PATH, marker_config_path=MARKER_CONFIG_PATH)
    
    if not controller.connect():
        logger.error("Connection failed. Aborting POC drawing.")
        sys.exit(1)
        
    try:
        while True:
            # Display menu banner
            print("\n" + "=" * 50)
            print("PORTRAITRON 3000 - MAIN CONTROL INTERFACE")
            print("=" * 50)
            print("1. run default POC")
            print("2. run POC with custom parameters")
            print("Press Control+C to exit")
            print("=" * 50)
            
            choice = input("Enter choice: ").strip()
            
            # Dispatch choice
            if choice == "1":
                run_poc(controller)
            elif choice == "2":
                run_poc(controller, radius=0, theta=0)
            elif choice == "":
                # Ignore empty presses
                continue
            else:
                logger.warning(f"Option '{choice}' is not recognized. Please choose option 1.")
                
    except KeyboardInterrupt:
        print("\n\nExiting main system menu safely. Goodbye!")
        controller.disconnect()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Encountered a system menu exception: {e}")
        controller.disconnect()
        sys.exit(1)

if __name__ == "__main__":
    main()
