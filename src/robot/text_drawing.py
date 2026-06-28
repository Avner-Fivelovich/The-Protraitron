import os
import sys
import time
import numpy as np
import matplotlib.textpath as textpath
import matplotlib.font_manager as font_manager
from src.common.logger import get_logger

# Initialize logger for text drawing
logger = get_logger("TextDrawing")

def text_to_strokes(text: str, size: float = 0.1) -> list:
    """
    Converts a text string into a list of strokes using matplotlib's font engine.
    Each stroke is a list of [x, y] coordinates.
    """
    fp = font_manager.FontProperties(family='sans-serif', weight='normal')
    tp = textpath.TextPath((0, 0), text, size=size, prop=fp)
    
    vertices = tp.vertices
    codes = tp.codes
    
    strokes = []
    current_stroke = []
    
    for vertex, code in zip(vertices, codes):
        x, y = vertex
        if code == 1:  # MOVETO (start new stroke)
            if current_stroke:
                strokes.append(current_stroke)
            current_stroke = [[x, y]]
        elif code in (2, 3, 4):  # LINETO / CURVE
            current_stroke.append([x, y])
        elif code == 79:  # CLOSEPOLY
            if current_stroke:
                current_stroke.append(current_stroke[0])
                strokes.append(current_stroke)
                current_stroke = []
                
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

def run_text_drawing(controller, text: str, target_width: float = 0.8, target_height: float = 0.2):
    """
    Homes the robot, generates text paths, and executes compliant strokes.
    """
    try:
        logger.info(f"Generating compliant text paths for: '{text}'")
        raw_strokes = text_to_strokes(text)
        strokes_2d = normalize_strokes(raw_strokes, target_width=target_width, target_height=target_height)
        
        if not strokes_2d:
            logger.warning("No strokes generated. Text might be empty.")
            return
            
        # Home the robot linearly to safe P0 hover configuration
        controller.home()
        time.sleep(1.0)
        
        # Get parameters from controller configuration
        speed = controller.cfg.get('slide_speed', 0.04)
        accel = controller.cfg.get('slide_acceleration', 0.08)
        blend_radius = controller.cfg.get('blend_radius', 0.002)
        draw_depth_offset = controller.cfg.get('draw_depth_offset', 0.0)
        
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
