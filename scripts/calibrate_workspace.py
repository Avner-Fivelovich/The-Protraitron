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

# Default Robot IP - match physical UR5e controller IP
ROBOT_IP = "192.168.57.101"
OUTPUT_PATH = "config/calibration.yaml"


def main():
    # -------------------------------------------------------------
    # Print welcome banner
    # -------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PORTRAITRON 3000 - SINGLE-POINT WORKSPACE CALIBRATION")
    logger.info("=" * 60)
    
    # Ensure config directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    # Resolve config YAML file path
    config_name = "marker"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        config_name = sys.argv[1]
        
    if not config_name.endswith(".yaml") and "/" not in config_name and "\\" not in config_name:
        config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../config/{config_name}.yaml"))
    else:
        config_file_path = os.path.abspath(config_name)
        
    cfg = load_config_from_yaml(config_file_path)
    
    rtde_c = None
    rtde_r = None

    # -------------------------------------------------------------
    # Establish connection with the robot
    # -------------------------------------------------------------
    logger.info(f"Connecting to UR5e at IP: {ROBOT_IP}...")
    try:
        rtde_c = rtde_control.RTDEControlInterface(ROBOT_IP)
        rtde_r = rtde_receive.RTDEReceiveInterface(ROBOT_IP)
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
        # Save initial P0 results to config/calibration.yaml
        # -------------------------------------------------------------
        logger.info("Saving initial P0 to calibration.yaml...")
        cal_data = {
            "p0_joints": [float(q) for q in p0_joints],
            "p0_pose": [float(p) for p in p0_pose],
            "width": 0.19,
            "height": 0.27
        }
        with open(OUTPUT_PATH, "w") as f:
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
        # Retract to 3 mm above P1 in the X-axis (P0 hover) using moveL
        # -------------------------------------------------------------
        p0_pose_new = list(p1_surface)
        p0_pose_new[0] += 0.003  # 3 mm above/away from P1 along X-axis
        logger.info(f"Moving to final P0 hover (3mm above P1 in X): {[round(c, 4) for c in p0_pose_new[:3]]}...")
        rtde_c.moveL(p0_pose_new, 0.05, 0.1)
        time.sleep(0.5)
        
        # Capture final P0 joints and pose at this position
        p0_joints_final = rtde_r.getActualQ()
        p0_pose_final = rtde_r.getActualTCPPose()
        logger.info(f"Final P0 Pose (3mm above P1): {[round(c, 4) for c in p0_pose_final[:3]]}")
        logger.info(f"Final P0 Joints: {[round(c, 4) for c in p0_joints_final]}")
        
        # -------------------------------------------------------------
        # Save results (rewriting P0 and adding P1) to config/calibration.yaml
        # -------------------------------------------------------------
        cal_data_final = {
            "p0_joints": [float(q) for q in p0_joints_final],
            "p0_pose": [float(p) for p in p0_pose_final],
            "p1": [float(p) for p in p1_surface],
            "width": 0.19,
            "height": 0.27
        }
        
        with open(OUTPUT_PATH, "w") as f:
            yaml.safe_dump(cal_data_final, f, default_flow_style=False)
            
        logger.success(f"Workspace calibration updated and saved to {OUTPUT_PATH}!")
        
    finally:
        # Safe disconnect
        if rtde_c:
            rtde_c.disconnect()
        if rtde_r:
            rtde_r.disconnect()
        logger.info("Calibration script finished.")

if __name__ == "__main__":
    main()
