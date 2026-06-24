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

def configure_and_run_poc(controller):
    """
    Displays the second-level menu for selecting the POC configuration parameters,
    and runs the trajectory.
    """
    print("\n" + "=" * 50)
    print("PORTRAITRON 3000 - POC RUN PARAMETERS")
    print("=" * 50)
    print("1. Run Default Configuration")
    print("   (Radius: 5cm, Sweep: 180°, Left start, Chord from end)")
    print("2. Run Custom Configuration (Multi-Page Selection)")
    print("3. Return to Main Menu")
    print("=" * 50)
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        run_poc(controller, radius=0.05, theta=180.0, start_position='left', line_start_at='end')
    elif choice == "2":
        # ---------------------------------------------------------
        # PAGE 1/3: Select start location
        # ---------------------------------------------------------
        print("\n" + "=" * 50)
        print("POC CUSTOM CONFIGURATION - PAGE 1/3 (START LOCATION)")
        print("=" * 50)
        print("Select starting position of the semicircle:")
        print("  1. Left of center (default)")
        print("  2. Right of center")
        print("  3. Above center")
        print("  4. Below center")
        print("=" * 50)
        start_choice = input("Enter choice (1-4): ").strip()
        start_position = 'left'
        if start_choice == '2':
            start_position = 'right'
        elif start_choice == '3':
            start_position = 'above'
        elif start_choice == '4':
            start_position = 'below'
            
        # ---------------------------------------------------------
        # PAGE 2/3: Select radius and sweep degree
        # ---------------------------------------------------------
        print("\n" + "=" * 50)
        print("POC CUSTOM CONFIGURATION - PAGE 2/3 (GEOMETRY)")
        print("=" * 50)
        print("Select circle radius:")
        print("  1. 3 cm (0.03 m)")
        print("  2. 5 cm (0.05 m) (default)")
        print("  3. 7 cm (0.07 m)")
        print("  4. Enter custom radius in meters")
        print("=" * 50)
        radius_choice = input("Enter choice (1-4): ").strip()
        
        radius = 0.05
        if radius_choice == '1':
            radius = 0.03
        elif radius_choice == '3':
            radius = 0.07
        elif radius_choice == '4':
            try:
                rad_input = input("Enter custom circle radius in meters (default 0.05): ").strip()
                radius = float(rad_input) if rad_input else 0.05
            except ValueError:
                logger.warning("Invalid input. Defaulting to 0.05m radius.")
                radius = 0.05
                
        print("\nSelect sweep angle (negative values for counter-clockwise):")
        print("  1. 90 degrees")
        print("  2. 180 degrees (default)")
        print("  3. 270 degrees")
        print("  4. 360 degrees")
        print("  5. Enter custom sweep angle in degrees")
        print("=" * 50)
        theta_choice = input("Enter choice (1-5): ").strip()
        
        theta = 180.0
        if theta_choice == '1':
            theta = 90.0
        elif theta_choice == '3':
            theta = 270.0
        elif theta_choice == '4':
            theta = 360.0
        elif theta_choice == '5':
            try:
                theta_input = input("Enter custom sweep angle in degrees (negative for counter-clockwise): ").strip()
                theta = float(theta_input) if theta_input else 180.0
            except ValueError:
                logger.warning("Invalid input. Defaulting to 180 degrees.")
                theta = 180.0
                
        # ---------------------------------------------------------
        # PAGE 3/3: Select chord start and end
        # ---------------------------------------------------------
        print("\n" + "=" * 50)
        print("POC CUSTOM CONFIGURATION - PAGE 3/3 (CHORD DIRECTION)")
        print("=" * 50)
        print("Select direction of the second chord line:")
        print("  1. Start from the END of the semicircle (default)")
        print("  2. Start from the BEGINNING of the semicircle")
        print("=" * 50)
        line_choice = input("Enter choice (1-2): ").strip()
        line_start_at = 'end'
        if line_choice == '2':
            line_start_at = 'beginning'
            
        run_poc(controller, radius=radius, theta=theta, start_position=start_position, line_start_at=line_start_at)
        
    elif choice == "3":
        logger.info("Returning to main menu.")
    else:
        logger.warning(f"Option '{choice}' is not recognized.")

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
            print("1. POC")
            print("Press Control+C to exit")
            print("=" * 50)
            
            choice = input("Enter choice: ").strip()
            
            # Dispatch choice
            if choice == "1":
                configure_and_run_poc(controller)
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
