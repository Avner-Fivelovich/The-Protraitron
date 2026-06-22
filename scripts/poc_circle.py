#!/usr/bin/env python3
import os
import sys
import argparse
import time
import yaml
import numpy as np
import matplotlib.pyplot as plt

# Add root folder to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.geometry import PlaneCalibrator, generate_semicircle_canvas
from src.robot.controller import UR5eController

def plot_offline(strokes_2d: list, width: float, height: float, title: str, save_formats: list = None, base_filename: str = None):
    """Plots the trajectory in physical coordinates (cm) to verify shape dimensions and optionally saves files."""
    plt.figure(figsize=(7, 9))
    
    # Convert page dimensions to centimeters
    width_cm = width * 100
    height_cm = height * 100
    
    # Draw A4 canvas boundaries in cm
    plt.plot([0, width_cm, width_cm, 0, 0], [0, 0, height_cm, height_cm, 0], 'r--', label="Page boundaries")
    
    for i, stroke in enumerate(strokes_2d):
        # Convert stroke coordinates to cm
        stroke_cm = np.zeros_like(stroke)
        stroke_cm[:, 0] = stroke[:, 0] * width_cm
        stroke_cm[:, 1] = stroke[:, 1] * height_cm
        
        plt.plot(stroke_cm[:, 0], stroke_cm[:, 1], 'b-', marker='o', markersize=3, label=f"Stroke {i+1}")
        # Mark start with green, end with red
        plt.plot(stroke_cm[0, 0], stroke_cm[0, 1], 'go', label="Start point" if i == 0 else "")
        plt.plot(stroke_cm[-1, 0], stroke_cm[-1, 1], 'ro', label="End point" if i == 0 else "")
        
    plt.title(f"{title}\nPhysical Coordinates (cm) - Page Size: {width_cm:.1f}x{height_cm:.1f} cm")
    plt.xlabel("X Coordinate (cm)")
    plt.ylabel("Y Coordinate (cm)")
    plt.grid(True)
    plt.axis("equal")
    plt.xlim(-1, width_cm + 1)
    plt.ylim(-1, height_cm + 1)
    plt.legend()
    
    if save_formats and base_filename:
        # Create output directory if it doesn't exist
        dir_name = os.path.dirname(base_filename)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        for fmt in save_formats:
            filepath = f"{base_filename}.{fmt}"
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"Saved trajectory plot to {filepath}")
            
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="Portraitron Semicircle Drawing POC")
    parser.add_argument("--radius", type=float, default=0.04, help="Radius of semicircle in meters (default: 0.04)")
    parser.add_argument("--theta", type=float, default=180.0, help="Semicircle span angle in degrees (default: 180)")
    parser.add_argument("--plot-only", action="store_true", help="Plot trajectory offline and exit")
    parser.add_argument("--save-plot", type=str, default="plots/trajectory_preview", help="Base filename to save plot (formats: png, svg, pdf)")
    parser.add_argument("--air-run", action="store_true", help="Dry run +50mm normal offset above page surface")
    parser.add_argument("--robot-ip", type=str, default="192.168.57.101", help="Robot IP (default: 192.168.57.101)")
    parser.add_argument("--config", type=str, default="config/calibration.yaml", help="Calibration yaml path")
    args = parser.parse_args()
    
    # 1. Load Calibration values
    width = 0.19
    height = 0.27
    calibration_exists = os.path.exists(args.config)
    
    if calibration_exists:
        try:
            with open(args.config, "r") as f:
                cal_data = yaml.safe_load(f)
            width = cal_data.get("width", 0.19)
            height = cal_data.get("height", 0.27)
            print(f"Loaded calibration. Width={width:.3f}m, Height={height:.3f}m")
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
    else:
        print("Calibration file not found. Using default page margins (19x27 cm).")
        
    # 2. Generate Semicircle coordinates
    # local X-axis: starts at center minus radius to the left
    stroke_canvas = generate_semicircle_canvas(
        radius=args.radius,
        width=width,
        height=height,
        theta_deg=args.theta,
        num_steps=100
    )
    strokes_list = [stroke_canvas]
    
    # 3. Matplotlib Offline Verification
    if args.plot_only:
        print("Running offline plotting...")
        plot_offline(
            strokes_list, 
            width, 
            height, 
            "Offline Semicircle Verification",
            save_formats=["png", "svg", "pdf"],
            base_filename=args.save_plot
        )
        sys.exit(0)
        
    # 4. Robot execution setup
    if not calibration_exists:
        print("❌ Cannot execute on robot: calibration file is missing. Please run calibrate_workspace.py first.")
        sys.exit(1)
        
    controller = UR5eController(ip_address=args.robot_ip, config_path=args.config)
    
    if not controller.connect():
        sys.exit(1)
        
    try:
        # Ask operator confirmation
        mode_str = "DRY RUN (AIR RUN, +50mm normal offset)" if args.air_run else "REAL INK DRAWING"
        print("\n" + "="*50)
        print(f"MODE: {mode_str}")
        print(f"Radius: {args.radius * 100:.1f} cm")
        print(f"Angle: {args.theta:.1f} degrees")
        print("="*50)
        
        confirm = input("\nProceed to home and execute path? [y/N]: ")
        if confirm.lower() != 'y':
            print("Execution canceled by user.")
            return
            
        # Home the robot using safe P0 joints
        controller.home()
        time.sleep(1.0)
        
        # Set draw depth offset (air run draws 5 cm normal to the surface)
        draw_depth = -0.050 if args.air_run else 0.000
        
        print("Executing path...")
        controller.execute_drawing_path(
            strokes_2d=strokes_list,
            speed=0.04,
            accel=0.08,
            blend_radius=0.002,
            draw_depth_offset=draw_depth
        )
        print("Execution complete.")
        
    finally:
        # Clean shutdown of sockets
        controller.disconnect()

if __name__ == "__main__":
    main()
