#!/usr/bin/env python3
import os
import sys
import yaml
import time
import math
import numpy as np

# -------------------------------------------------------------
# Add root folder to sys.path so we can import src modules
# -------------------------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.logger import get_logger
from src.common.config_utils import load_config_from_yaml
from src.common.robot_utils import wait_for_motion_complete, probe_surface_point

# Initialize logger
logger = get_logger("Calibration")

# -------------------------------------------------------------
# Attempt to import RTDE control/receive libraries
# -------------------------------------------------------------
try:
    import rtde_control
    import rtde_receive
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    sys.exit(1)

def main():
    # -------------------------------------------------------------
    # Print welcome banner
    # -------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PORTRAITRON 3000 - SINGLE-POINT WORKSPACE CALIBRATION")
    logger.info("=" * 60)
    
    # Resolve config YAML file path
    config_name = "marker"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        config_name = sys.argv[1]
        
    if not config_name.endswith(".yaml") and "/" not in config_name and "\\" not in config_name:
        config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../config/{config_name}.yaml"))
    else:
        config_file_path = os.path.abspath(config_name)
        
    cfg = load_config_from_yaml(config_file_path)
    
    # Load parameters from config
    robot_ip = cfg.get("robot_ip", "192.168.57.100")
    output_path = "config/paper_manipulation.yaml"
    paper_width = cfg.get("paper_width", 0.19)
    paper_height = cfg.get("paper_height", 0.27)
    hover_distance = cfg.get("hover_distance", 0.003)
    move_speed = cfg.get("move_speed", 0.05)
    move_accel = cfg.get("move_accel", 0.1)

    # Ensure config directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    rtde_c = None
    rtde_r = None

    # -------------------------------------------------------------
    # Establish connection with the robot
    # -------------------------------------------------------------
    logger.info(f"Connecting to UR5e at IP: {robot_ip}...")
    try:
        rtde_c = rtde_control.RTDEControlInterface(robot_ip)
        rtde_r = rtde_receive.RTDEReceiveInterface(robot_ip)
        logger.success("Sockets connected successfully.")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        sys.exit(1)
        
    try:
        # -------------------------------------------------------------
        # Show setup instructions to the user and capture p0
        # -------------------------------------------------------------
        logger.info(
            "INSTRUCTIONS:\n"
            "1. Use the teach pendant to jog the robot arm.\n"
            "2. Place the pen tip hovering approximately 1.5 cm normal to the\n"
            "   Bottom-Left corner of your drawing sheet (1cm margins) (this is hover pose P0).\n"
            "3. Ensure the tool is oriented perpendicular to the paper surface."
        )
        
        input("\nPress [ENTER] when ready to capture P0...")
        p0_joints = rtde_r.getActualQ()
        p0_pose = rtde_r.getActualTCPPose()
        logger.info(f"Recorded P0 Pose: {[round(c, 4) for c in p0_pose[:3]]}")
        logger.info(f"Recorded P0 Joints: {[round(c, 4) for c in p0_joints]}")
        
        # -------------------------------------------------------------
        # Save initial P0 results to calibration file
        # -------------------------------------------------------------
        logger.info(f"Saving initial draw_home to {output_path}...")
        
        with open(output_path, "r") as f:
            cal_data = yaml.safe_load(f) or {}
            
        if "locations" not in cal_data:
            cal_data["locations"] = {}
            
        cal_data["locations"]["draw_home"] = [float(p) for p in p0_pose]
        cal_data["p0_joints"] = [float(q) for q in p0_joints]
        cal_data["width"] = paper_width
        cal_data["height"] = paper_height
        
        with open(output_path, "w") as f:
            yaml.safe_dump(cal_data, f, default_flow_style=False)
        
        # -------------------------------------------------------------
        # Probe surface to determine physical corner position P1
        # -------------------------------------------------------------
        logger.info("Probing Bottom-Left Surface (P1)...")
        p1_surface = probe_surface_point(rtde_c, rtde_r, p_start_pose=p0_pose, cfg=cfg)
        if not p1_surface:
            logger.error("Probing P1 failed. Aborting calibration.")
            return
            
        # -------------------------------------------------------------
        # Retract to hover_distance above P1 in the X-axis (P0 hover) using moveL
        # -------------------------------------------------------------
        p0_pose_new = list(p1_surface)
        p0_pose_new[0] += hover_distance  # hover_distance above/away from P1 along X-axis
        logger.info(f"Moving to final P0 hover ({hover_distance}m above P1 in X): {[round(c, 4) for c in p0_pose_new[:3]]}...")
        rtde_c.moveL(p0_pose_new, move_speed, move_accel)
        time.sleep(0.5)
        
        # Capture final P0 joints and pose at this position
        p0_joints_final = rtde_r.getActualQ()
        p0_pose_final = rtde_r.getActualTCPPose()
        logger.info(f"Final P0 Pose ({hover_distance}m above P1): {[round(c, 4) for c in p0_pose_final[:3]]}")
        logger.info(f"Final P0 Joints: {[round(c, 4) for c in p0_joints_final]}")
        
        # -------------------------------------------------------------
        # Save results (rewriting P0 and adding P1) to calibration file
        # -------------------------------------------------------------
        with open(output_path, "r") as f:
            cal_data_final = yaml.safe_load(f) or {}
            
        if "locations" not in cal_data_final:
            cal_data_final["locations"] = {}
            
        cal_data_final["locations"]["draw_home"] = [float(p) for p in p0_pose_final]
        cal_data_final["p0_joints"] = [float(q) for q in p0_joints_final]
        cal_data_final["p1"] = [float(p) for p in p1_surface]
        cal_data_final["width"] = paper_width
        cal_data_final["height"] = paper_height
        
        with open(output_path, "w") as f:
            yaml.safe_dump(cal_data_final, f, default_flow_style=False)
            
        logger.success(f"Workspace calibration updated and saved to {output_path}!")
        
    finally:
        # Safe disconnect
        if rtde_c:
            rtde_c.disconnect()
        if rtde_r:
            rtde_r.disconnect()
        logger.info("Calibration script finished.")

if __name__ == "__main__":
    main()
