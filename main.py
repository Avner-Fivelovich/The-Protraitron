#!/usr/bin/env python3
import sys
import os
import time
import datetime
import argparse
import xml.etree.ElementTree as ET

# -------------------------------------------------------------
# Add root folder to sys.path so we can import src modules
# -------------------------------------------------------------
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.common.logger import get_logger
from src.robot.controller import UR5eController
from src.robot.poc_drawing import run_poc
from src.robot.text_drawing import run_text_drawing
from src.robot.svg_drawing import load_svg_file, normalize_svg_strokes
from src.robot.path_optimization import optimize_strokes_tsp, log_optimization_stats, merge_close_strokes
from src.robot.swiftsketch_integration import run_swiftsketch_inference
from src.robot.mask_filtering import (
    load_binary_mask, filter_strokes_with_mask, plot_mask_filtering_results,
    load_swiftsketch_config, get_mask_foreground_bbox
)
from src.vision.camera_capture import (
    capture_image_from_camera, detect_and_crop_face, apply_background_removal_vignette
)
from src.robot.paper_handler import PaperHandler

# Initialize main system logger
logger = get_logger("MainSystem")

def log_event(event_name: str):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    logger.info(f"[TIMESTAMP] {now_str} - Event: {event_name}")

import yaml



# Load File Paths Config
FILES_PATHES_CONFIG = os.path.join(os.path.dirname(__file__), "config", "files_pathes.yaml")
paths_cfg = {}
if os.path.exists(FILES_PATHES_CONFIG):
    with open(FILES_PATHES_CONFIG, "r") as f:
        paths_cfg = yaml.safe_load(f)

# Extract config paths
server_config_path = paths_cfg.get("paths", {}).get("server_config", "config/server.yaml")
robot_logic_path = paths_cfg.get("paths", {}).get("robot_logic_config", "config/robot_logic.yaml")
CALIBRATION_PATH = paths_cfg.get("paths", {}).get("calibration_config", "config/calibration.yaml")
MARKER_CONFIG_PATH = paths_cfg.get("paths", {}).get("marker_config", "config/marker.yaml")

server_cfg = {}
if os.path.exists(server_config_path):
    with open(server_config_path, "r") as f:
        server_cfg = yaml.safe_load(f)
ROBOT_IP = server_cfg.get("hardware", {}).get("robot_ip", "192.168.57.101")

robot_logic_cfg = {}
if os.path.exists(robot_logic_path):
    with open(robot_logic_path, "r") as f:
        robot_logic_cfg = yaml.safe_load(f)

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

def parse_args():
    """
    Parses command-line arguments for the Portraitron 3000 control interface.
    """
    proc_cfg = robot_logic_cfg.get("processing", {})
    hw_cfg = robot_logic_cfg.get("hardware", {})
    
    parser = argparse.ArgumentParser(description="Portraitron 3000 - Main Control Interface")
    parser.add_argument("--text", "-t", type=str, help="Text to write (one-shot mode)")
    parser.add_argument("--POC", "-p", type=str, nargs='?', const='left', choices=["left", "right", "above", "below"], help="Start position of the semicircle for POC (one-shot mode)")
    parser.add_argument("--radius", "-r", type=float, default=5.0, help="Semicircle radius in cm (default: 5.0)")
    parser.add_argument("--angle", "-a", type=float, default=180.0, help="Sweep angle in degrees (default: 180.0)")
    parser.add_argument("--svg", "-s", type=str, help="Path to SVG file to draw (one-shot mode)")
    parser.add_argument("--sketch", "-k", type=str, help="Path to portrait image to sketch using SwiftSketch and draw (one-shot mode)")
    parser.add_argument("--capture", "-c", action="store_true", help="Capture photo from webcam, crop face, remove background, and sketch (one-shot mode)")
    parser.add_argument("--dryrun", "-d", action="store_true", help="Perform a dry run (plot expected drawing via matplotlib without connecting to the robot)")
    
    parser.add_argument("--optimize", dest="optimize", action="store_true", default=proc_cfg.get("optimize_strokes", True), help="Optimize SVG stroke drawing order using TSP")
    parser.add_argument("--no-optimize", dest="optimize", action="store_false", help="Disable SVG stroke optimization")
    parser.add_argument("--merge-threshold", type=float, default=proc_cfg.get("merge_threshold", 0.002), help="Distance threshold in meters for stroke merging")
    parser.add_argument("--mask", type=str, default=None, help="Path to binary mask image to filter noisy strokes (default: None)")
    parser.add_argument("--mask-keep-ratio", type=float, default=proc_cfg.get("mask_keep_ratio", 0.7), help="Minimum ratio of points inside mask to keep a stroke")
    parser.add_argument("--approve", action="store_true", default=proc_cfg.get("approve", False), help="Display drawing preview and require approval before starting physical robot drawing")
    parser.add_argument("--paper-swap", action="store_true", default=hw_cfg.get("paper_swap", False), help="Execute the hardware paper swap sequence after drawing completes")
    
    args = parser.parse_args()
    
    # If dryrun is enabled and no explicit approve flag is given, fallback to true
    if args.dryrun and not any(arg == "--approve" for arg in sys.argv):
        args.approve = True
        
    return args

def run_one_shot_text(controller, text: str):
    """
    Executes a one-shot custom text drawing.
    """
    logger.info(f"One-shot text mode: writing '{text}'")
    run_text_drawing(controller, text)

def run_one_shot_poc(controller, start_position: str, radius_cm: float, angle_deg: float):
    """
    Executes a one-shot POC semicircle/diameter drawing.
    """
    logger.info(f"One-shot POC mode: position='{start_position}', radius={radius_cm}cm, angle={angle_deg}°")
    run_poc(controller, radius=radius_cm / 100.0, theta=angle_deg, start_position=start_position, line_start_at='end')

def run_one_shot_svg(controller, svg_path: str, optimize: bool = None, merge_threshold: float = 0.002, mask_path: str = None, mask_keep_ratio: float = 0.7, approve: bool = False, paper_swap: bool = False, paper_handler: PaperHandler = None):
    """
    Executes a one-shot SVG vector drawing.
    """
    log_event(f"SVG file load started for: {svg_path}")
    try:
        if not os.path.exists(svg_path):
            logger.error(f"SVG file not found: {svg_path}")
            return
        raw_strokes = load_svg_file(svg_path)
        log_event("SVG file load completed")

        # Read SVG viewBox dimensions for mask coordinate mapping
        try:
            _svg_root = ET.parse(svg_path).getroot()
            svg_w = float(_svg_root.get('width', 512))
            svg_h = float(_svg_root.get('height', 512))
        except Exception:
            svg_w, svg_h = 512.0, 512.0
            logger.warning("Could not parse SVG dimensions; defaulting to 512×512.")

        # ── Optional background mask filtering (in raw SVG pixel space) ──────
        # The mask PNG and the raw SVG strokes share the same pixel coordinate
        # system (Y=0 at top), so filtering here avoids aspect-ratio distortion.
        raw_filtered = raw_strokes
        if mask_path:
            log_event(f"Mask filtering started using: {mask_path} (keep ratio: {mask_keep_ratio})")
            try:
                binary_mask = load_binary_mask(mask_path)
                raw_filtered, raw_deleted = filter_strokes_with_mask(
                    raw_strokes,
                    binary_mask,
                    svg_width=svg_w,
                    svg_height=svg_h,
                    keep_ratio=mask_keep_ratio,
                    svg_path=svg_path,
                )
                log_event(
                    f"Mask filtering completed: Kept {len(raw_filtered)}/{len(raw_strokes)} strokes "
                    f"(pruned {len(raw_deleted)} noise strokes)"
                )

                # Plots directory structured as plots/{orig_lifts}_{base_name}/{date}/{time}/
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                time_str = datetime.datetime.now().strftime("%H-%M")
                base_name = os.path.splitext(os.path.basename(svg_path))[0]
                orig_lifts = len([s for s in raw_strokes if len(s) > 0])
                plot_dir = os.path.join("plots", f"{orig_lifts}_{base_name}", date_str, time_str)
                os.makedirs(plot_dir, exist_ok=True)

                # Main filtering preview
                filter_plot_prefix = os.path.join(plot_dir, "mask_filtering_preview")
                plot_mask_filtering_results(
                    raw_strokes, raw_filtered, raw_deleted,
                    mask_path, filter_plot_prefix,
                    svg_width=svg_w, svg_height=svg_h,
                    svg_path=svg_path,
                    keep_ratio=mask_keep_ratio,
                )

                # Threshold comparison: 80 / 85 / 90 / 95 %
                logger.info("Generating mask threshold comparisons (80%, 85%, 90%, 95%)...")
                for comp_ratio in [0.80, 0.85, 0.90, 0.95]:
                    comp_kept, comp_del = filter_strokes_with_mask(
                        raw_strokes, binary_mask,
                        svg_width=svg_w, svg_height=svg_h,
                        keep_ratio=comp_ratio,
                        svg_path=svg_path,
                    )
                    logger.info(
                        f"Threshold comparison: at keep_ratio={comp_ratio:.2f}, "
                        f"Kept {len(comp_kept)}/{len(raw_strokes)} strokes (pruned {len(comp_del)})"
                    )
                    comp_plot_prefix = os.path.join(
                        plot_dir, f"mask_filtering_preview_ratio_{int(comp_ratio*100)}"
                    )
                    plot_mask_filtering_results(
                        raw_strokes, comp_kept, comp_del,
                        mask_path, comp_plot_prefix,
                        svg_width=svg_w, svg_height=svg_h,
                        svg_path=svg_path,
                        keep_ratio=comp_ratio,
                    )
            except Exception as e:
                logger.error(f"Failed to apply mask filtering: {e}")

        # ── Compute Fixed BBox for consistent scaling ────────────────────────
        fixed_bbox = None
        if mask_path:
            config = load_swiftsketch_config(svg_path)
            if config:
                scale_w = config.get('scale_w')
                scale_h = config.get('scale_h')
                orig_cx = config.get('original_center_x')
                orig_cy = config.get('original_center_y')
                if all(x is not None for x in [scale_w, scale_h, orig_cx, orig_cy]):
                    try:
                        b_mask = load_binary_mask(mask_path)
                        mfx_min, mfx_max, mfy_min, mfy_max = get_mask_foreground_bbox(b_mask)
                        cx, cy = svg_w / 2.0, svg_h / 2.0
                        s_min_x = (mfx_min - cx) / scale_w + orig_cx * svg_w
                        s_max_x = (mfx_max - cx) / scale_w + orig_cx * svg_w
                        s_min_y = (mfy_min - cy) / scale_h + orig_cy * svg_h
                        s_max_y = (mfy_max - cy) / scale_h + orig_cy * svg_h
                        fixed_bbox = (s_min_x, s_max_x, s_min_y, s_max_y)
                        logger.info("Using precise Mask Foreground BBox for consistent physical scaling.")
                    except Exception as e:
                        logger.warning(f"Could not compute fixed_bbox: {e}")

        # ── Normalize filtered raw strokes to physical canvas coords ──────────
        log_event("SVG stroke normalization started")
        normalized_strokes = normalize_svg_strokes(
            raw_filtered,
            canvas_width=controller.width,
            canvas_height=controller.height,
            fixed_bbox=fixed_bbox
        )
        log_event("SVG stroke normalization completed")

        if not normalized_strokes:
            logger.warning("No strokes remaining after mask filtering / normalization.")
            return

        filtered_strokes = normalized_strokes
            
        if optimize is None:
            optimize = controller.cfg.get('optimize_strokes', True)
            
        merged_strokes = filtered_strokes
        opt_strokes = filtered_strokes
        connections = []
        optimization_time = 0.0

        if optimize:
            start_time = time.time()
            
            # Step 1: Pre-TSP to group close strokes consecutively
            log_event("Pre-TSP stroke order optimization started")
            pre_tsp_strokes = optimize_strokes_tsp(filtered_strokes)
            log_event("Pre-TSP stroke order optimization completed")
            
            # Step 2: Merge close strokes
            log_event("Stroke merging (continuous chains) started")
            merged_strokes, connections = merge_close_strokes(
                pre_tsp_strokes, 
                merge_threshold, 
                canvas_width=controller.width, 
                canvas_height=controller.height
            )
            log_event("Stroke merging (continuous chains) completed")
            
            # Step 3: Post-TSP optimize the merged strokes
            log_event("TSP stroke order optimization started")
            opt_strokes = optimize_strokes_tsp(merged_strokes)
            log_event("TSP stroke order optimization completed")
            
            optimization_time = time.time() - start_time
        else:
            # Merging is still run even if TSP ordering is disabled, if threshold > 0
            if merge_threshold > 0.0:
                log_event("Stroke merging (continuous chains) started")
                merged_strokes, connections = merge_close_strokes(
                    filtered_strokes, 
                    merge_threshold, 
                    canvas_width=controller.width, 
                    canvas_height=controller.height
                )
                log_event("Stroke merging (continuous chains) completed")
                opt_strokes = merged_strokes

        log_optimization_stats(logger, filtered_strokes, merged_strokes, opt_strokes, optimization_time, merge_threshold, optimize)
            
        # Organize the plots directory and file naming using nested directories
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.datetime.now().strftime("%H-%M")
        base_name = os.path.splitext(os.path.basename(svg_path))[0]
        # Calculate orig_lifts consistently from raw_strokes
        orig_lifts = len([s for s in raw_strokes if len(s) > 0])
        
        plot_dir = os.path.join("plots", f"{orig_lifts}_{base_name}", date_str, time_str)
        os.makedirs(plot_dir, exist_ok=True)
        plot_path_prefix = os.path.join(plot_dir, "expected_drawing_preview")

        # Handle manual user approval flag (if approve is True and dryrun is False)
        if approve and not controller.dryrun:
            log_event("Approval verification started: displaying expected drawing preview")
            logger.info("Displaying expected drawing preview. Please close the plot window to see the confirmation prompt.")
            controller.plot_expected_drawing(opt_strokes, plot_path_prefix=plot_path_prefix, connections=connections, original_strokes=filtered_strokes)
            
            # Request confirmation in terminal if interactive
            if sys.stdin.isatty():
                ans = input("\n[PROMPT] Do you want to proceed with physical drawing on the robot? [y/N]: ").strip().lower()
                if ans not in ['y', 'yes']:
                    logger.warning("Drawing cancelled by user.")
                    log_event("Approval verification completed: Drawing cancelled")
                    return
            else:
                logger.warning("Non-interactive terminal detected. Auto-cancelling drawing execution for safety.")
                log_event("Approval verification completed: Drawing cancelled (non-interactive)")
                return
            log_event("Approval verification completed: Drawing approved")

        log_event("Robot homing started")
        controller.home()
        log_event("Robot homing completed")
        time.sleep(1.0)
        
        speed = controller.cfg.get('slide_speed', 0.04)
        accel = controller.cfg.get('slide_acceleration', 0.08)
        blend_radius = controller.cfg.get('blend_radius', 0.002)
        draw_depth_offset = controller.cfg.get('draw_depth_offset', 0.0)
        
        log_event(f"Executing SVG drawing of '{svg_path}' with {len(opt_strokes)} strokes...")
        controller.execute_drawing_path(
            strokes_2d=opt_strokes,
            speed=speed,
            accel=accel,
            blend_radius=blend_radius,
            draw_depth_offset=draw_depth_offset,
            plot_path_prefix=plot_path_prefix,
            connections=connections,
            original_strokes=filtered_strokes
        )
        log_event("All drawing paths completed successfully")
        
        if paper_swap and not controller.dryrun:
            log_event("Starting paper swap sequence...")
            if paper_handler is None:
                paper_handler = PaperHandler(controller.rtde_c, controller.rtde_r)
            success = paper_handler.execute_paper_swap()
            if not success:
                logger.warning("Paper swap sequence failed.")
            
    except Exception as e:
        logger.error(f"Error during SVG execution: {e}")

def run_one_shot_sketch(controller, image_path: str, optimize: bool = None, merge_threshold: float = 0.002, approve: bool = False, paper_swap: bool = False, paper_handler: PaperHandler = None):
    """
    Runs SwiftSketch to generate a vector portrait, then draws it.
    """
    logger.info(f"One-shot sketch mode: processing '{image_path}'...")
    
    # Define output SVG path
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_svg_path = os.path.join("plots", "generated_sketches", f"{base_name}_sketch.svg")
    
    # Run inference
    success = run_swiftsketch_inference(image_path, output_svg_path, controller.cfg)
    if not success:
        logger.error("Failed to generate sketch using SwiftSketch.")
        return
        
    # Draw the generated SVG
    logger.info("SwiftSketch generation completed. Proceeding to draw...")
    run_one_shot_svg(controller, output_svg_path, optimize, merge_threshold, approve=approve, paper_swap=paper_swap, paper_handler=paper_handler)

def run_camera_capture_and_sketch(controller, optimize: bool = None, merge_threshold: float = 0.002, approve: bool = False):
    """
    Runs interactive camera capture, face cropping, background removal,
    and then executes SwiftSketch drawing.
    """
    logger.info("Starting camera capture session...")
    os.makedirs("plots", exist_ok=True)
    raw_path = os.path.join("plots", "captured_raw.png")
    cropped_path = os.path.join("plots", "captured_cropped.png")
    final_path = os.path.join("plots", "captured_final.png")
    
    # 1. Capture image
    if not capture_image_from_camera(raw_path):
        logger.error("Camera capture failed or was cancelled.")
        return
        
    # 2. Crop face
    success, face_rect = detect_and_crop_face(raw_path, cropped_path)
    
    # 3. Apply background removal and vignette edge blending
    if not apply_background_removal_vignette(cropped_path, final_path, face_rect if success else None):
        logger.error("Background removal/masking failed.")
        return
        
    # 4. Run SwiftSketch drawing pipeline
    logger.info("Captured subject successfully preprocessed. Forwarding to SwiftSketch...")
    run_one_shot_sketch(controller, final_path, optimize, merge_threshold, approve=approve)

def main():
    """
    Displays interactive options to the user and dispatches actions based on selection,
    or runs in one-shot mode if arguments are provided.
    """
    args = parse_args()

    if not os.path.exists(CALIBRATION_PATH):
        if not args.dryrun:
            logger.critical("Cannot run: Calibration file is missing. Please run calibrate_workspace.py first.")
            sys.exit(1)
        else:
            logger.warning("Calibration file is missing. Using default settings for dry run.")
        
    logger.info("Initializing UR5e Controller...")
    controller = UR5eController(ROBOT_IP, calibration_path=CALIBRATION_PATH, marker_config_path=MARKER_CONFIG_PATH)
    controller.dryrun = args.dryrun
    
    if not controller.connect():
        logger.error("Connection failed. Aborting.")
        sys.exit(1)
        
    paper_handler = None
    if not controller.dryrun:
        paper_handler = PaperHandler(controller.rtde_c, controller.rtde_r)
        
    try:
        if args.text is not None:
            run_one_shot_text(controller, args.text)
            if paper_handler: paper_handler.disconnect()
            controller.disconnect()
            sys.exit(0)
            
        elif args.POC is not None:
            run_one_shot_poc(controller, args.POC, args.radius, args.angle)
            if paper_handler: paper_handler.disconnect()
            controller.disconnect()
            sys.exit(0)

        elif args.svg is not None:
            run_one_shot_svg(controller, args.svg, args.optimize, args.merge_threshold, args.mask, args.mask_keep_ratio, args.approve, args.paper_swap, paper_handler=paper_handler)
            if paper_handler: paper_handler.disconnect()
            controller.disconnect()
            sys.exit(0)
            
        elif args.sketch is not None:
            run_one_shot_sketch(controller, args.sketch, args.optimize, args.merge_threshold, args.approve, args.paper_swap, paper_handler=paper_handler)
            if paper_handler: paper_handler.disconnect()
            controller.disconnect()
            sys.exit(0)
            
        elif args.capture:
            run_camera_capture_and_sketch(controller, args.optimize, args.merge_threshold, args.approve)
            if paper_handler: paper_handler.disconnect()
            controller.disconnect()
            sys.exit(0)
            
        # Otherwise, run interactive menu loop
        while True:
            # Display menu banner
            print("\n" + "=" * 50)
            print("PORTRAITRON 3000 - MAIN CONTROL INTERFACE")
            print("=" * 50)
            print("1. POC (Semicircle & Diameter)")
            print("2. Write Custom Text")
            print("3. Draw SVG file")
            print("4. Sketch & Draw Portrait (SwiftSketch)")
            print("5. Capture Photo from Webcam & Sketch")
            print("6. Batch Draw with Paper Swap (SVG)")
            print("Press Control+C to exit")
            print("=" * 50)
            
            choice = input("Enter choice (1-6): ").strip()
            
            # Dispatch choice
            if choice == "1":
                configure_and_run_poc(controller)
            elif choice == "2":
                text = input("Enter text to write (default: 'doofenshmirtz evil inc.'): ").strip()
                if not text:
                    text = "doofenshmirtz evil inc."
                run_text_drawing(controller, text)
            elif choice == "3":
                svg_path = input("Enter SVG file path: ").strip()
                if not svg_path:
                    logger.warning("SVG file path cannot be empty.")
                    continue
                run_one_shot_svg(controller, svg_path, args.optimize, args.merge_threshold, args.mask, args.mask_keep_ratio, args.approve, paper_handler=paper_handler)
            elif choice == "4":
                image_path = input("Enter portrait image file path: ").strip()
                if not image_path:
                    logger.warning("Image file path cannot be empty.")
                    continue
                run_one_shot_sketch(controller, image_path, args.optimize, args.merge_threshold, args.approve, paper_handler=paper_handler)
            elif choice == "5":
                run_camera_capture_and_sketch(controller, args.optimize, args.merge_threshold, args.approve)
            elif choice == "6":
                svg_path = input("Enter SVG file path for batch mode: ").strip()
                if not svg_path:
                    logger.warning("SVG file path cannot be empty.")
                    continue
                run_one_shot_svg(controller, svg_path, args.optimize, args.merge_threshold, args.mask, args.mask_keep_ratio, args.approve, paper_swap=True, paper_handler=paper_handler)
            elif choice == "":
                # Ignore empty presses
                continue
            else:
                logger.warning(f"Option '{choice}' is not recognized. Please choose option 1, 2, 3, 4, 5, or 6.")
                
    except KeyboardInterrupt:
        print("\n\nExiting main system menu safely. Goodbye!")
        if paper_handler: paper_handler.disconnect()
        controller.disconnect()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Encountered a system menu exception: {e}")
        if paper_handler: paper_handler.disconnect()
        controller.disconnect()
        sys.exit(1)

if __name__ == "__main__":
    main()
