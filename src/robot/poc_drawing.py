import sys
import os
import time
import math
import numpy as np
from src.common.logger import get_logger

# Initialize logger for POC drawing
logger = get_logger("POCDrawing")

def get_drawing_inputs(radius: float = 0.0, theta: float = 0.0, default_radius: float = 0.03, default_theta: float = 180.0) -> tuple[float, float]:
    """
    Queries the operator for the circle radius (meters) and sweep angle (degrees).
    Only prompts for values that are not already specified (i.e. equal to 0.0).
    Defaults to default_radius and default_theta on invalid inputs.
    """
    if radius <= 0.0:
        try:
            radius_input = input(f"Enter circle radius in meters (e.g. {default_radius}): ").strip()
            radius = float(radius_input) if radius_input else default_radius
        except ValueError:
            logger.warning(f"Invalid input. Defaulting to {default_radius}m radius.")
            radius = default_radius
            
    if theta == 0.0:
        try:
            theta_input = input(f"Enter sweep angle in degrees (e.g. {default_theta}): ").strip()
            theta = float(theta_input) if theta_input else default_theta
        except ValueError:
            logger.warning(f"Invalid input. Defaulting to {default_theta} degrees.")
            theta = default_theta
            
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
    
    steps_per_meter = controller.cfg.get('poc_steps_per_meter', 1000)
    min_steps = controller.cfg.get('poc_min_steps', 10)
    
    # Calculate sweep arc length in meters to set step resolution
    theta_rad = math.radians(theta)
    arc_length = radius * abs(theta_rad)
    
    # steps_per_meter steps per meter = 1 step per millimeter (minimum min_steps steps)
    num_steps = max(min_steps, int(arc_length * steps_per_meter))
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
        
    angle_tolerance = controller.cfg.get('poc_angle_tolerance', 1e-3)
    # Edge case: If 360 degrees, start and end points overlap at P_start
    if abs(abs(theta) - 360.0) < angle_tolerance:
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

def run_poc_drawing(controller, radius: float = 0.0, theta: float = 0.0, start_position: str = None, line_start_at: str = None):
    """
    Coordinates parameters collection, path generation, and controller drawing.
    """
    if start_position is None:
        start_position = controller.cfg.get('poc_start_position', 'left')
    if line_start_at is None:
        line_start_at = controller.cfg.get('poc_line_start_at', 'end')
        
    if radius == 0.0 and theta == 0.0:
        default_radius = controller.cfg.get('poc_default_radius', 0.03)
        default_theta = controller.cfg.get('poc_default_theta', 180.0)
        radius, theta = get_drawing_inputs(radius, theta, default_radius, default_theta)
        
    logger.info(f"Generating POC paths: Radius = {radius * 100:.1f} cm, Theta = {theta:.1f} deg, Start = {start_position}, Line = {line_start_at}...")
    
    # Generate paths
    semicircle_path = generate_semicircle_path(controller, radius, theta, start_position)
    line_path = generate_diameter_path(controller, radius, theta, semicircle_path, line_start_at)
    
    # Run drawing
    execute_drawing(controller, [semicircle_path, line_path])

def run_poc(controller, radius: float = None, theta: float = None, start_position: str = None, line_start_at: str = None):
    """
    Homes to P0 hover and executes the POC drawing paths.
    """
    if radius is None:
        radius = controller.cfg.get('poc_default_radius', 0.05)
    if theta is None:
        theta = controller.cfg.get('poc_default_theta', 180.0)
    if start_position is None:
        start_position = controller.cfg.get('poc_start_position', 'left')
    if line_start_at is None:
        line_start_at = controller.cfg.get('poc_line_start_at', 'end')
        
    post_home_delay = controller.cfg.get('poc_post_home_delay', 1.0)
    
    try:
        # Home the robot linearly to safe P0 hover configuration
        controller.home()
        time.sleep(post_home_delay)
        
        # Execute the POC drawing paths
        run_poc_drawing(controller, radius, theta, start_position, line_start_at)
        logger.success("POC drawing routine completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during POC execution: {e}")
