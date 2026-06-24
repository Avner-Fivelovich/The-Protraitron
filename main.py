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

# Initialize main system logger
logger = get_logger("MainSystem")

# Sockets and configurations defaults
ROBOT_IP = "192.168.57.101"
CALIBRATION_PATH = "config/calibration.yaml"
MARKER_CONFIG_PATH = "config/marker.yaml"

def get_drawing_inputs(radius: float = 0.0, theta: float = 0.0) -> tuple[float, float]:
    """
    Queries the operator for the circle radius (meters) and sweep angle (degrees).
    Only prompts for values that are not already specified (i.e. equal to 0.0).
    Defaults to 0.03m and 180 degrees on invalid inputs.
    """
    if radius <= 0.0:
        try:
            radius_input = input("Enter circle radius in meters (e.g. 0.03): ").strip()
            radius = float(radius_input) if radius_input else 0.03
        except ValueError:
            logger.warning("Invalid input. Defaulting to 0.03m radius.")
            radius = 0.03
            
    if theta == 0.0:
        try:
            theta_input = input("Enter sweep angle in degrees (e.g. 180): ").strip()
            theta = float(theta_input) if theta_input else 180.0
        except ValueError:
            logger.warning("Invalid input. Defaulting to 180 degrees.")
            theta = 180.0
            
    return radius, theta

def generate_semicircle_path(controller, radius: float, theta: float) -> list:
    """
    Computes normalized canvas coordinates for a semicircle centered on the canvas (0.5, 0.5).
    Scales resolution dynamically based on arc length to ensure smooth ~1mm waypoint spacing.
    """
    # Calculate scale factors relative to canvas width and height
    rx = radius / controller.width
    ry = radius / controller.height
    
    # Calculate sweep arc length in meters to set step resolution
    theta_rad = math.radians(theta)
    arc_length = radius * abs(theta_rad)
    
    # 1000 steps per meter = 1 step per millimeter (minimum 10 steps)
    num_steps = max(10, int(arc_length * 1000))
    logger.info(f"Generating semicircle sweep path with {num_steps} interpolation steps.")
    
    # Sweep clockwise starting at pi (left edge)
    angles = np.linspace(math.pi, math.pi - theta_rad, num_steps)
    circle_x = 0.5 + rx * np.cos(angles)
    circle_y = 0.5 + ry * np.sin(angles)
    
    return np.column_stack((circle_x, circle_y)).tolist()

def generate_diameter_path(controller, radius: float, theta: float, semicircle_path: list) -> list:
    """
    Generates a straight line connecting the end point of the sweep back to the start.
    Implements a 360-degree fallback to draw a full diameter chord from right to left.
    """
    rx = radius / controller.width
    x_start, y_start = semicircle_path[0]
    x_end, y_end = semicircle_path[-1]
    
    line_start = [x_end, y_end]
    line_end = [x_start, y_start]
    
    # Edge case: If 360 degrees (clockwise or counter-clockwise), start/end match, so draw a horizontal diameter instead
    if abs(abs(theta) - 360.0) < 1e-3:
        logger.info("360 degree detected. Drawing full diameter chord from right to left.")
        line_start = [x_start + 2 * rx, y_start]
        line_end = [x_start, y_start]
        
    return [line_start, line_end]

def execute_drawing(controller, paths: list):
    """
    Extracts speed, acceleration, blend, and depth parameters from the YAML configuration,
    and runs the strokes under compliance control.
    """
    speed = controller.cfg.get('slide_speed', 0.04)
    accel = controller.cfg.get('slide_acceleration', 0.08)
    blend_radius = controller.cfg.get('blend_radius', 0.002)
    
    logger.info(f"Executing paths (speed={speed} m/s, accel={accel} m/s^2, blend={blend_radius} m)...")
    controller.execute_drawing_path(
        strokes_2d=paths,
        speed=speed,
        accel=accel,
        blend_radius=blend_radius
    )

def run_poc_drawing(controller, radius: float = 0.0, theta: float = 0.0):
    """
    Coordinates parameters collection, path generation, and controller drawing.
    """
    # -------------------------------------------------------------
    # Step 1: Collect inputs
    # -------------------------------------------------------------
    if radius == 0.0 and theta == 0.0:
        radius, theta = get_drawing_inputs()
        
    logger.info(f"Generating POC paths: Radius = {radius * 100:.1f} cm, Theta = {theta:.1f} deg...")
    
    # -------------------------------------------------------------
    # Step 2: Generate paths
    # -------------------------------------------------------------
    semicircle_path = generate_semicircle_path(controller, radius, theta)
    line_path = generate_diameter_path(controller, radius, theta, semicircle_path)
    
    # -------------------------------------------------------------
    # Step 3: Run drawing
    # -------------------------------------------------------------
    execute_drawing(controller, [semicircle_path, line_path])

def run_poc(controller, radius: float = 0.05, theta: float = 180):
    """
    Homes to P0 hover and executes the POC drawing paths.
    """
    try:
        # Home the robot linearly to safe P0 hover configuration
        controller.home()
        time.sleep(1.0)
        
        # Execute the POC drawing paths
        run_poc_drawing(controller, radius, theta)
        logger.success("POC drawing routine completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during POC execution: {e}")

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
