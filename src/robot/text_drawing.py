import os
import sys
import time
import numpy as np
import matplotlib.textpath as textpath
import matplotlib.font_manager as font_manager
from src.common.logger import get_logger

# Initialize logger for text drawing
logger = get_logger("TextDrawing")

def interpolate_bezier_quadratic(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, steps: int) -> list:
    """
    Interpolates a quadratic Bezier curve from p0 to p2 with control point p1.
    Returns a list of [x, y] coordinates.
    """
    t = np.linspace(0.0, 1.0, steps + 1)[1:]
    points = []
    for val in t:
        pt = (1 - val) ** 2 * p0 + 2 * (1 - val) * val * p1 + val ** 2 * p2
        points.append(pt.tolist())
    return points

def interpolate_bezier_cubic(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, steps: int) -> list:
    """
    Interpolates a cubic Bezier curve from p0 to p3 with control points p1 and p2.
    Returns a list of [x, y] coordinates.
    """
    t = np.linspace(0.0, 1.0, steps + 1)[1:]
    points = []
    for val in t:
        pt = (1 - val) ** 3 * p0 + 3 * (1 - val) ** 2 * val * p1 + 3 * (1 - val) * val ** 2 * p2 + val ** 3 * p3
        points.append(pt.tolist())
    return points

def parse_curve3(i: int, codes: np.ndarray, vertices: np.ndarray, current_stroke: list, bezier_steps: int) -> tuple:
    """
    Parses a quadratic Bezier (CURVE3) segment, interpolates it, and appends to the stroke.
    Returns the next index and the updated stroke.
    """
    p1 = vertices[i]
    p2 = vertices[i+1]
    if current_stroke:
        p0 = np.array(current_stroke[-1])
        points = interpolate_bezier_quadratic(p0, p1, p2, bezier_steps)
        current_stroke.extend(points)
    else:
        current_stroke.append(p2.tolist())
    return i + 2, current_stroke

def parse_curve4(i: int, codes: np.ndarray, vertices: np.ndarray, current_stroke: list, bezier_steps: int) -> tuple:
    """
    Parses a cubic Bezier (CURVE4) segment, interpolates it, and appends to the stroke.
    Returns the next index and the updated stroke.
    """
    p1 = vertices[i]
    p2 = vertices[i+1]
    p3 = vertices[i+2]
    if current_stroke:
        p0 = np.array(current_stroke[-1])
        points = interpolate_bezier_cubic(p0, p1, p2, p3, bezier_steps)
        current_stroke.extend(points)
    else:
        current_stroke.append(p3.tolist())
    return i + 3, current_stroke

def text_to_strokes(text: str, size: float = 0.1, bezier_steps: int = 15, font_family: str = 'sans-serif', font_weight: str = 'normal') -> list:
    """
    Converts a text string into a list of strokes using matplotlib's font engine.
    Interpolates quadratic (CURVE3) and cubic (CURVE4) Bezier curves into smooth
    linear segments using helper parsing functions.
    """
    fp = font_manager.FontProperties(family=font_family, weight=font_weight)
    tp = textpath.TextPath((0, 0), text, size=size, prop=fp)
    
    vertices = tp.vertices
    codes = tp.codes
    
    strokes = []
    current_stroke = []
    
    i = 0
    while i < len(codes):
        code = codes[i]
        vertex = vertices[i]
        
        if code == 1:  # MOVETO (start new stroke)
            if current_stroke:
                strokes.append(current_stroke)
            current_stroke = [vertex.tolist()]
            i += 1
        elif code == 2:  # LINETO
            current_stroke.append(vertex.tolist())
            i += 1
        elif code == 3:  # CURVE3 (quadratic bezier)
            if i + 1 < len(codes) and codes[i+1] == 3:
                i, current_stroke = parse_curve3(i, codes, vertices, current_stroke, bezier_steps)
            else:
                current_stroke.append(vertex.tolist())
                i += 1
        elif code == 4:  # CURVE4 (cubic bezier)
            if i + 2 < len(codes) and codes[i+1] == 4 and codes[i+2] == 4:
                i, current_stroke = parse_curve4(i, codes, vertices, current_stroke, bezier_steps)
            else:
                current_stroke.append(vertex.tolist())
                i += 1
        elif code == 79:  # CLOSEPOLY
            if current_stroke:
                # Close the polygon by returning to the start point
                current_stroke.append(current_stroke[0])
                strokes.append(current_stroke)
                current_stroke = []
            i += 1
        else:
            i += 1
            
    if current_stroke:
        strokes.append(current_stroke)
        
    return strokes

def normalize_strokes(strokes: list, target_width: float = 0.8, target_height: float = 0.2, center_x: float = 0.5, center_y: float = 0.5) -> list:
    """
    Scales and centers text strokes within the [0, 1] canvas coordinate system.
    Keeps the aspect ratio of the text.
    """
    all_pts = []
    for stroke in strokes:
        for pt in stroke:
            all_pts.append(pt)
            
    if not all_pts:
        return []
        
    all_pts = np.array(all_pts)
    min_x, min_y = np.min(all_pts, axis=0)
    max_x, max_y = np.max(all_pts, axis=0)
    
    text_w = max_x - min_x
    text_h = max_y - min_y
    
    if text_w == 0 or text_h == 0:
        return strokes
        
    # Scale to fit target dimensions while preserving aspect ratio
    scale = min(target_width / text_w, target_height / text_h)
    
    normalized_strokes = []
    for stroke in strokes:
        norm_stroke = []
        for pt in stroke:
            # Shift to origin, scale, and translate to center
            nx = (pt[0] - min_x - text_w / 2.0) * scale + center_x
            ny = (pt[1] - min_y - text_h / 2.0) * scale + center_y
            norm_stroke.append([nx, ny])
        normalized_strokes.append(norm_stroke)
        
    return normalized_strokes

def run_text_drawing(controller, text: str, target_width: float = None, target_height: float = None):
    """
    Homes the robot, generates text paths, and executes compliant strokes.
    """
    try:
        # Load configuration parameters
        bezier_steps = controller.cfg.get('text_bezier_steps', 15)
        speed = controller.cfg.get('slide_speed', 0.04)
        accel = controller.cfg.get('slide_acceleration', 0.08)
        blend_radius = controller.cfg.get('blend_radius', 0.002)
        draw_depth_offset = controller.cfg.get('draw_depth_offset', 0.0)
        
        tw = target_width if target_width is not None else controller.cfg.get('text_target_width', 0.8)
        th = target_height if target_height is not None else controller.cfg.get('text_target_height', 0.2)
        cx = controller.cfg.get('text_center_x', 0.5)
        cy = controller.cfg.get('text_center_y', 0.5)
        font_family = controller.cfg.get('text_font_family', 'sans-serif')
        font_weight = controller.cfg.get('text_font_weight', 'normal')
        font_size = controller.cfg.get('text_font_size', 0.1)
        home_delay = controller.cfg.get('home_delay', 1.0)

        logger.info(f"Generating compliant text paths for: '{text}' (using bezier_steps={bezier_steps})")
        raw_strokes = text_to_strokes(text, size=font_size, bezier_steps=bezier_steps, font_family=font_family, font_weight=font_weight)
        strokes_2d = normalize_strokes(raw_strokes, target_width=tw, target_height=th, center_x=cx, center_y=cy)
        
        if not strokes_2d:
            logger.warning("No strokes generated. Text might be empty.")
            return
            
        # Home the robot linearly to safe P0 hover configuration
        controller.home()
        time.sleep(home_delay)
        
        logger.info(f"Executing text drawing of '{text}' with {len(strokes_2d)} strokes...")
        controller.execute_drawing_path(
            strokes_2d=strokes_2d,
            speed=speed,
            accel=accel,
            blend_radius=blend_radius,
            draw_depth_offset=draw_depth_offset
        )
        logger.success(f"Text drawing routine for '{text}' completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during text execution: {e}")
