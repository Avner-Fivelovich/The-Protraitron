import numpy as np
from src.common.config_utils import load_config_from_yaml

# Load configuration for default parameters
calib_cfg = load_config_from_yaml("config/paper_manipulation.yaml")
logic_cfg = load_config_from_yaml("config/robot_logic.yaml")

DEFAULT_CANVAS_WIDTH = calib_cfg.get("width", 0.19)
DEFAULT_CANVAS_HEIGHT = calib_cfg.get("height", 0.27)
DEFAULT_MERGE_THRESHOLD = logic_cfg.get("merge_threshold", 0.002)

def calculate_drawing_distance(strokes: list) -> float:
    """
    Calculates the total drawing distance (sum of segment lengths within all strokes).
    """
    total_dist = 0.0
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        pts = np.array(stroke)
        dists = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
        total_dist += float(np.sum(dists))
    return total_dist

def calculate_air_distance(strokes: list) -> float:
    """
    Calculates the total transition (air) distance (sum of distances between consecutive strokes).
    """
    cleaned = [s for s in strokes if len(s) > 0]
    if len(cleaned) < 2:
        return 0.0
    
    total_dist = 0.0
    for s1, s2 in zip(cleaned[:-1], cleaned[1:]):
        total_dist += float(np.linalg.norm(np.array(s1[-1]) - np.array(s2[0])))
    return total_dist

def optimize_strokes_tsp(strokes: list) -> list:
    """
    Optimizes the order and direction of strokes to minimize the transition (air) distance
    using a Double-Ended Nearest Neighbor (TSP) heuristic.
    
    Each stroke can be traversed in its original direction or reversed.
    """
    if not strokes:
        return []
        
    # Filter out empty strokes to prevent index errors
    cleaned_strokes = [s for s in strokes if len(s) > 0]
    if not cleaned_strokes:
        return []
        
    optimized = [cleaned_strokes[0]]
    unused_indices = list(range(1, len(cleaned_strokes)))
    current_point = np.array(cleaned_strokes[0][-1])
    
    while unused_indices:
        best_idx, best_reverse = _find_nearest_stroke(current_point, cleaned_strokes, unused_indices)
        
        # Add the selected stroke
        selected_stroke = cleaned_strokes[best_idx]
        if best_reverse:
            # Reverse the stroke points
            optimized.append(selected_stroke[::-1])
            current_point = np.array(selected_stroke[0])
        else:
            optimized.append(selected_stroke)
            current_point = np.array(selected_stroke[-1])
            
        unused_indices.remove(best_idx)
        
    return optimized

def _find_nearest_stroke(current_point: np.ndarray, strokes: list, unused_indices: list) -> tuple:
    """
    Finds the index of the nearest stroke in unused_indices to current_point,
    and returns whether it needs to be reversed.
    """
    best_idx = -1
    best_dist = float('inf')
    best_reverse = False
    
    for idx in unused_indices:
        stroke = strokes[idx]
        pt_start = np.array(stroke[0])
        pt_end = np.array(stroke[-1])
        
        # Distance to start (normal traversal)
        d_start = np.linalg.norm(current_point - pt_start)
        if d_start < best_dist:
            best_dist = d_start
            best_idx = idx
            best_reverse = False
            
        # Distance to end (reversed traversal)
        d_end = np.linalg.norm(current_point - pt_end)
        if d_end < best_dist:
            best_dist = d_end
            best_idx = idx
            best_reverse = True
            
    return best_idx, best_reverse

def merge_close_strokes(strokes: list, threshold_m: float = None, canvas_width: float = None, canvas_height: float = None) -> tuple:
    """
    Connects sequential strokes that are close to each other in coordinate space.
    If the end of stroke i and start of stroke i+1 are within threshold_m (in meters),
    they are merged into a single continuous stroke to reduce pen lifts.
    
    Returns a tuple of (merged_strokes, connection_lines).
    """
    if threshold_m is None:
        threshold_m = DEFAULT_MERGE_THRESHOLD
    if canvas_width is None:
        canvas_width = DEFAULT_CANVAS_WIDTH
    if canvas_height is None:
        canvas_height = DEFAULT_CANVAS_HEIGHT

    if not strokes:
        return [], []
    if threshold_m <= 0.0:
        return strokes, []
        
    cleaned_strokes = [s for s in strokes if len(s) > 0]
    if not cleaned_strokes:
        return [], []
        
    merged = []
    connections = []
    current_stroke = list(cleaned_strokes[0])
    
    scale = np.array([canvas_width, canvas_height])
    
    for next_stroke in cleaned_strokes[1:]:
        p_end = np.array(current_stroke[-1]) * scale
        p_start = np.array(next_stroke[0]) * scale
        dist = np.linalg.norm(p_end - p_start)
        
        if dist <= threshold_m:
            # Record connection line (normalized canvas coordinates)
            connections.append((list(current_stroke[-1]), list(next_stroke[0])))
            # Merge: extend current_stroke with the points of next_stroke
            current_stroke.extend(next_stroke)
        else:
            merged.append(current_stroke)
            current_stroke = list(next_stroke)
            
    merged.append(current_stroke)
    return merged, connections

def log_optimization_stats(logger, orig_strokes: list, merged_strokes: list, opt_strokes: list, optimization_time: float, merge_threshold: float, optimize_enabled: bool) -> None:
    """
    Logs a comparison report of path lengths, pen lifts, and distances before and after optimizations.
    """
    orig_drawing_dist = calculate_drawing_distance(orig_strokes)
    orig_air_dist = calculate_air_distance(orig_strokes)
    orig_total_dist = orig_drawing_dist + orig_air_dist
    orig_lifts = len([s for s in orig_strokes if len(s) > 0])

    merged_drawing_dist = calculate_drawing_distance(merged_strokes)
    merged_air_dist = calculate_air_distance(merged_strokes)
    merged_total_dist = merged_drawing_dist + merged_air_dist
    merged_lifts = len([s for s in merged_strokes if len(s) > 0])

    opt_drawing_dist = calculate_drawing_distance(opt_strokes)
    opt_air_dist = calculate_air_distance(opt_strokes)
    opt_total_dist = opt_drawing_dist + opt_air_dist
    opt_lifts = len([s for s in opt_strokes if len(s) > 0])

    logger.info("=" * 60)
    logger.info("PORTRAITRON DRAWING PATH OPTIMIZATION REPORT")
    logger.info("=" * 60)
    logger.info(f"Optimization Time: {optimization_time*1000:.2f} ms")
    logger.info(f"Drawing Distance (constant): {orig_drawing_dist:.4f} m ({orig_drawing_dist*100:.2f} cm)")
    
    logger.info("Pen Lifts (Strokes Count):")
    logger.info(f"  - Original:  {orig_lifts}")
    logger.info(f"  - Merged:    {merged_lifts} (Threshold: {merge_threshold*1000:.1f} mm | Saved {orig_lifts - merged_lifts} lifts)")
    logger.info(f"  - Final TSP: {opt_lifts}")

    logger.info("Transition (Air) Distance:")
    logger.info(f"  - Original:  {orig_air_dist:.4f} m ({orig_air_dist*100:.2f} cm)")
    logger.info(f"  - Merged:    {merged_air_dist:.4f} m ({merged_air_dist*100:.2f} cm)")
    logger.info(f"  - Final TSP: {opt_air_dist:.4f} m ({opt_air_dist*100:.2f} cm)")
    
    air_saved = orig_air_dist - opt_air_dist
    reduction_pct = (air_saved / orig_air_dist * 100) if orig_air_dist > 0 else 0.0
    logger.info(f"  - Net Air Distance Saved: {air_saved:.4f} m ({air_saved*100:.2f} cm) | {reduction_pct:.1f}% reduction")
    
    logger.info("Total Travel Distance:")
    logger.info(f"  - Original:  {orig_total_dist:.4f} m ({orig_total_dist*100:.2f} cm)")
    logger.info(f"  - Final TSP: {opt_total_dist:.4f} m ({opt_total_dist*100:.2f} cm)")
    logger.info(f"  - Net Saved: {orig_total_dist - opt_total_dist:.4f} m ({(orig_total_dist - opt_total_dist)*100:.2f} cm)")
    logger.info("=" * 60)
