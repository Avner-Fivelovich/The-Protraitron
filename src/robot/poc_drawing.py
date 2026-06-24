import sys
import os
import time
import math
import numpy as np
from src.common.logger import get_logger

# Initialize logger for POC drawing
logger = get_logger("POCDrawing")

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

def generate_semicircle_path(controller, radius: float, theta: float, start_position: str = 'left') -> list:
    """
    Computes normalized canvas coordinates for a semicircle centered on the canvas (0.5, 0.5).
    Scales resolution dynamically based on arc length to ensure smooth ~1mm waypoint spacing.
    Supports start positions: 'left', 'right', 'above', 'below'.
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
    
    # Determine starting angle based on start position
    start_pos_lower = start_position.lower().strip()
    if start_pos_lower == 'right':
        start_angle = 0.0
    elif start_pos_lower == 'above':
        start_angle = math.pi / 2.0
    elif start_pos_lower == 'below':
        start_angle = -math.pi / 2.0
    else:  # 'left'
        start_angle = math.pi
        
    angles = np.linspace(start_angle, start_angle - theta_rad, num_steps)
    circle_x = 0.5 + rx * np.cos(angles)
    circle_y = 0.5 + ry * np.sin(angles)
    
    return np.column_stack((circle_x, circle_y)).tolist()

def generate_diameter_path(controller, radius: float, theta: float, semicircle_path: list, line_start_at: str = 'end') -> list:
    """
    Generates a straight line connecting the endpoints of the semicircle.
    - If line_start_at is 'end', it runs from the end of the semicircle back to the start.
    - If line_start_at is 'beginning', it runs from the start of the semicircle to the end.
    Implements a 360-degree fallback that draws a diameter passing through the center.
    """
    rx = radius / controller.width
    ry = radius / controller.height
    x_start, y_start = semicircle_path[0]
    x_end, y_end = semicircle_path[-1]
    
    # Determine straight line endpoints based on line_start_at parameter
    line_start_lower = line_start_at.lower().strip()
    if line_start_lower == 'beginning':
        line_start = [x_start, y_start]
        line_end = [x_end, y_end]
    else:  # default 'end'
        line_start = [x_end, y_end]
        line_end = [x_start, y_start]
        
    # Edge case: If 360 degrees, start and end points overlap at P_start
    if abs(abs(theta) - 360.0) < 1e-3:
        logger.info("360 degree detected. Drawing full diameter chord.")
        P_start = [x_start, y_start]
        P_opp = [1.0 - x_start, 1.0 - y_start]
        
        if line_start_lower == 'beginning':
            line_start = P_start
            line_end = P_opp
        else:
            line_start = P_opp
            line_end = P_start
            
    return [line_start, line_end]

def execute_drawing(controller, paths: list):
    """
    Extracts speed, acceleration, blend, and depth parameters from the YAML configuration,
    and runs the strokes under compliance control.
    """
    speed = controller.cfg.get('slide_speed', 0.04)
    accel = controller.cfg.get('slide_acceleration', 0.08)
    blend_radius = controller.cfg.get('blend_radius', 0.002)
    draw_depth_offset = controller.cfg.get('draw_depth_offset', 0.0)
    
    logger.info(f"Executing paths (speed={speed} m/s, accel={accel} m/s^2, blend={blend_radius} m, depth={draw_depth_offset} m)...")
    controller.execute_drawing_path(
        strokes_2d=paths,
        speed=speed,
        accel=accel,
        blend_radius=blend_radius,
        draw_depth_offset=draw_depth_offset
    )

def run_poc_drawing(controller, radius: float = 0.0, theta: float = 0.0, start_position: str = 'left', line_start_at: str = 'end'):
    """
    Coordinates parameters collection, path generation, and controller drawing.
    """
    if radius == 0.0 and theta == 0.0:
        radius, theta = get_drawing_inputs()
        
    logger.info(f"Generating POC paths: Radius = {radius * 100:.1f} cm, Theta = {theta:.1f} deg, Start = {start_position}, Line = {line_start_at}...")
    
    # Generate paths
    semicircle_path = generate_semicircle_path(controller, radius, theta, start_position)
    line_path = generate_diameter_path(controller, radius, theta, semicircle_path, line_start_at)
    
    # Run drawing
    execute_drawing(controller, [semicircle_path, line_path])

def run_poc(controller, radius: float = 0.05, theta: float = 180.0, start_position: str = 'left', line_start_at: str = 'end'):
    """
    Homes to P0 hover and executes the POC drawing paths.
    """
    try:
        # Home the robot linearly to safe P0 hover configuration
        controller.home()
        time.sleep(1.0)
        
        # Execute the POC drawing paths
        run_poc_drawing(controller, radius, theta, start_position, line_start_at)
        logger.success("POC drawing routine completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during POC execution: {e}")
