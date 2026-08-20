import os
import re
import xml.etree.ElementTree as ET
import numpy as np
from src.common.logger import get_logger
from src.common.config_utils import load_config_from_yaml

# Initialize logger for SVG drawing
logger = get_logger("SVGDrawing")

# Load SVG drawing configurations
DRAWING_CFG = load_config_from_yaml("config/marker.yaml")
BEZIER_STEPS_DEFAULT = DRAWING_CFG.get("bezier_steps", 15)
CANVAS_WIDTH_DEFAULT = DRAWING_CFG.get("canvas_width", 0.19)
CANVAS_HEIGHT_DEFAULT = DRAWING_CFG.get("canvas_height", 0.27)
PADDING_DEFAULT = DRAWING_CFG.get("padding", 0.01)

def safe_float(val: str) -> float:
    """
    Safely converts a string to float. If it fails, logs a warning and returns 0.0.
    """
    try:
        return float(val)
    except ValueError:
        logger.warning(f"Invalid numeric token '{val}' in SVG path. Defaulting to 0.0.")
        return 0.0

def interpolate_bezier_quadratic(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, steps: int) -> list:
    """
    Interpolates a quadratic Bezier curve from p0 to p2 with control point p1.
    Returns a list of [x, y] coordinates.
    """
    t = np.linspace(0.0, 1.0, steps + 1)[1:, np.newaxis]
    points = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2
    return points.tolist()

def interpolate_bezier_cubic(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, steps: int) -> list:
    """
    Interpolates a cubic Bezier curve from p0 to p3 with control points p1 and p2.
    Returns a list of [x, y] coordinates.
    """
    t = np.linspace(0.0, 1.0, steps + 1)[1:, np.newaxis]
    points = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
    return points.tolist()

def tokenize_path(d_string: str) -> list:
    """
    Splits the SVG path 'd' string into commands and coordinate tokens.
    Handles negative numbers, scientific notation, and omission of spaces.
    """
    pattern = re.compile(r'([A-Za-z]|-?\d*\.?\d+(?:[eE][-+]?\d+)?)')
    return pattern.findall(d_string)

class SVGPathParser:
    """
    A stateful parser for parsing tokenized SVG path strings.
    """
    def __init__(self, bezier_steps: int = BEZIER_STEPS_DEFAULT):
        self.bezier_steps = bezier_steps
        self.strokes = []
        self.current_stroke = []
        self.current_point = np.array([0.0, 0.0])
        self.start_point = np.array([0.0, 0.0])
        
        # Control points tracking for smooth curves
        self.last_cubic_control = None
        self.last_quad_control = None

    def add_point(self, pt: np.ndarray):
        self.current_stroke.append(list(pt))

    def close_subpath(self):
        if self.current_stroke:
            self.strokes.append(self.current_stroke)
            self.current_stroke = []

    def _reset_controls(self):
        self.last_cubic_control = None
        self.last_quad_control = None

    def _handle_move(self, tokens: list, i: int, is_relative: bool) -> tuple:
        x = safe_float(tokens[i])
        y = safe_float(tokens[i+1])
        
        offset = self.current_point if is_relative else np.array([0.0, 0.0])
        self.current_point = offset + np.array([x, y])
        
        self.close_subpath()
        self.add_point(self.current_point)
        self.start_point = np.copy(self.current_point)
        
        self._reset_controls()
        next_cmd = 'l' if is_relative else 'L'
        return i + 2, next_cmd

    def _handle_line(self, tokens: list, i: int, is_relative: bool) -> int:
        x = safe_float(tokens[i])
        y = safe_float(tokens[i+1])
        
        offset = self.current_point if is_relative else np.array([0.0, 0.0])
        self.current_point = offset + np.array([x, y])
        
        self.add_point(self.current_point)
        self._reset_controls()
        return i + 2

    def _handle_horizontal(self, tokens: list, i: int, is_relative: bool) -> int:
        val = safe_float(tokens[i])
        if is_relative:
            self.current_point[0] += val
        else:
            self.current_point[0] = val
        self.add_point(self.current_point)
        self._reset_controls()
        return i + 1

    def _handle_vertical(self, tokens: list, i: int, is_relative: bool) -> int:
        val = safe_float(tokens[i])
        if is_relative:
            self.current_point[1] += val
        else:
            self.current_point[1] = val
        self.add_point(self.current_point)
        self._reset_controls()
        return i + 1

    def _handle_cubic(self, tokens: list, i: int, is_relative: bool) -> int:
        x1, y1 = safe_float(tokens[i]), safe_float(tokens[i+1])
        x2, y2 = safe_float(tokens[i+2]), safe_float(tokens[i+3])
        x, y = safe_float(tokens[i+4]), safe_float(tokens[i+5])
        
        offset = self.current_point if is_relative else np.array([0.0, 0.0])
        cp1 = offset + np.array([x1, y1])
        cp2 = offset + np.array([x2, y2])
        end_pt = offset + np.array([x, y])
        
        points = interpolate_bezier_cubic(self.current_point, cp1, cp2, end_pt, self.bezier_steps)
        for pt in points:
            self.add_point(pt)
            
        self.current_point = end_pt
        self.last_cubic_control = cp2
        self.last_quad_control = None
        return i + 6

    def _handle_smooth_cubic(self, tokens: list, i: int, is_relative: bool) -> int:
        x2, y2 = safe_float(tokens[i]), safe_float(tokens[i+1])
        x, y = safe_float(tokens[i+2]), safe_float(tokens[i+3])
        
        if self.last_cubic_control is not None:
            cp1 = 2 * self.current_point - self.last_cubic_control
        else:
            cp1 = np.copy(self.current_point)
            
        offset = self.current_point if is_relative else np.array([0.0, 0.0])
        cp2 = offset + np.array([x2, y2])
        end_pt = offset + np.array([x, y])
        
        points = interpolate_bezier_cubic(self.current_point, cp1, cp2, end_pt, self.bezier_steps)
        for pt in points:
            self.add_point(pt)
            
        self.current_point = end_pt
        self.last_cubic_control = cp2
        self.last_quad_control = None
        return i + 4

    def _handle_quad(self, tokens: list, i: int, is_relative: bool) -> int:
        x1, y1 = safe_float(tokens[i]), safe_float(tokens[i+1])
        x, y = safe_float(tokens[i+2]), safe_float(tokens[i+3])
        
        offset = self.current_point if is_relative else np.array([0.0, 0.0])
        cp1 = offset + np.array([x1, y1])
        end_pt = offset + np.array([x, y])
        
        points = interpolate_bezier_quadratic(self.current_point, cp1, end_pt, self.bezier_steps)
        for pt in points:
            self.add_point(pt)
            
        self.current_point = end_pt
        self.last_quad_control = cp1
        self.last_cubic_control = None
        return i + 4

    def _handle_smooth_quad(self, tokens: list, i: int, is_relative: bool) -> int:
        x, y = safe_float(tokens[i]), safe_float(tokens[i+1])
        
        if self.last_quad_control is not None:
            cp1 = 2 * self.current_point - self.last_quad_control
        else:
            cp1 = np.copy(self.current_point)
            
        offset = self.current_point if is_relative else np.array([0.0, 0.0])
        end_pt = offset + np.array([x, y])
        
        points = interpolate_bezier_quadratic(self.current_point, cp1, end_pt, self.bezier_steps)
        for pt in points:
            self.add_point(pt)
            
        self.current_point = end_pt
        self.last_quad_control = cp1
        self.last_cubic_control = None
        return i + 2

    def _handle_close(self) -> None:
        if not np.allclose(self.current_point, self.start_point):
            self.current_point = np.copy(self.start_point)
            self.add_point(self.current_point)
        self.close_subpath()
        self._reset_controls()
        return None

    def parse_tokens(self, tokens: list):
        i = 0
        cmd = None
        while i < len(tokens):
            token = tokens[i]
            if token.isalpha():
                cmd = token
                i += 1
            elif cmd is None:
                logger.warning(f"Unexpected number token '{token}' before any command.")
                i += 1
                continue

            cmd_upper = cmd.upper()
            is_relative = cmd.islower()

            if cmd_upper == 'M':
                i, cmd = self._handle_move(tokens, i, is_relative)
            elif cmd_upper == 'L':
                i = self._handle_line(tokens, i, is_relative)
            elif cmd_upper == 'H':
                i = self._handle_horizontal(tokens, i, is_relative)
            elif cmd_upper == 'V':
                i = self._handle_vertical(tokens, i, is_relative)
            elif cmd_upper == 'C':
                i = self._handle_cubic(tokens, i, is_relative)
            elif cmd_upper == 'S':
                i = self._handle_smooth_cubic(tokens, i, is_relative)
            elif cmd_upper == 'Q':
                i = self._handle_quad(tokens, i, is_relative)
            elif cmd_upper == 'T':
                i = self._handle_smooth_quad(tokens, i, is_relative)
            elif cmd_upper == 'Z':
                cmd = self._handle_close()
            else:
                logger.warning(f"Unsupported SVG path command '{cmd}'. Skipping.")
                i += 1
        self.close_subpath()

def parse_svg_path(d_string: str, bezier_steps: int = BEZIER_STEPS_DEFAULT) -> list:
    """
    Parses SVG path data (d attribute) and returns a list of strokes.
    Each stroke is a list of [x, y] coordinates.
    Supports M/m, L/l, H/h, V/v, C/c, S/s, Q/q, T/t, Z/z commands.
    """
    tokens = tokenize_path(d_string)
    if not tokens:
        return []

    parser = SVGPathParser(bezier_steps)
    parser.parse_tokens(tokens)
    return parser.strokes

def normalize_svg_strokes(strokes: list, canvas_width: float = CANVAS_WIDTH_DEFAULT, canvas_height: float = CANVAS_HEIGHT_DEFAULT, padding: float = PADDING_DEFAULT, fixed_bbox: tuple = None) -> list:
    """
    Normalizes SVG strokes to fit within [0, 1] x [0, 1] canvas coordinates,
    ensuring that the physical drawing preserves the SVG's aspect ratio
    and fits entirely within the physical canvas boundaries (canvas_width x canvas_height)
    minus the specified padding (in meters).
    
    Y-axis is inverted to match standard SVG (Y down) to physical workspace (Z/Y up).
    """
    if not strokes:
        return []

    # 1. Invert Y coordinate because SVG Y-axis points down
    inverted_strokes = [[[pt[0], -pt[1]] for pt in stroke] for stroke in strokes]

    # 2. Find bounding box
    all_pts = np.vstack(inverted_strokes)
    if fixed_bbox is not None:
        min_x, max_x, min_y, max_y = fixed_bbox
        # Need to invert Y of the fixed_bbox because we inverted Y of the strokes
        min_y, max_y = -max_y, -min_y
    else:
        min_x, min_y = np.min(all_pts, axis=0)
        max_x, max_y = np.max(all_pts, axis=0)

    svg_w = max_x - min_x
    svg_h = max_y - min_y

    if svg_w == 0 or svg_h == 0:
        return inverted_strokes

    # 3. Target dimensions in meters
    target_w_max = canvas_width - 2.0 * padding
    target_h_max = canvas_height - 2.0 * padding

    # 4. Aspect-ratio scaling
    scale = min(target_w_max / svg_w, target_h_max / svg_h)

    # 5. Translate and map back to normalized coordinates
    center_phys_x = canvas_width / 2.0
    center_phys_y = canvas_height / 2.0

    svg_center_x = min_x + svg_w / 2.0
    svg_center_y = min_y + svg_h / 2.0

    normalized_strokes = []
    for stroke in inverted_strokes:
        stroke_np = np.array(stroke)
        px = (stroke_np[:, 0] - svg_center_x) * scale + center_phys_x
        py = (stroke_np[:, 1] - svg_center_y) * scale + center_phys_y
        
        # Clip to physical canvas boundaries to avoid robot kinematic exceptions
        px = np.clip(px, 0.0, canvas_width)
        py = np.clip(py, 0.0, canvas_height)
        
        nx = px / canvas_width
        ny = py / canvas_height
        normalized_strokes.append(np.column_stack((nx, ny)).tolist())

    return normalized_strokes

def load_svg_file(svg_path: str, bezier_steps: int = BEZIER_STEPS_DEFAULT) -> list:
    """
    Parses an SVG file and extracts all path elements.
    Returns a list of raw strokes.
    """
    if not os.path.exists(svg_path):
        raise FileNotFoundError(f"SVG file not found: {svg_path}")

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except Exception as e:
        raise ValueError(f"Failed to parse SVG XML: {e}")

    strokes = []
    # Iterate through elements, finding tags that end with 'path'
    for elem in root.iter():
        if elem.tag.endswith('path'):
            d = elem.get('d')
            if d:
                path_strokes = parse_svg_path(d, bezier_steps)
                strokes.extend(path_strokes)

    return strokes
