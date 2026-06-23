#!/usr/bin/env python3
import os
import sys
import yaml
import time
import numpy as np

# Add root folder to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.logger import get_logger
from src.common.config_utils import load_config_from_yaml
from src.common.robot_utils import wait_for_motion_complete

# Initialize logger
logger = get_logger("Calibration")

try:
    import rtde_control
    import rtde_receive
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    sys.exit(1)

# Default Robot IP - match physical UR5e controller IP
ROBOT_IP = "192.168.57.101"
OUTPUT_PATH = "config/calibration.yaml"

def rotation_vector_to_matrix(rv: np.ndarray) -> np.ndarray:
    """
    Converts a 3D rotation vector (axis-angle) to a 3x3 rotation matrix
    using Rodrigues' rotation formula.
    """
    angle = np.linalg.norm(rv)
    if angle < 1e-6:
        return np.eye(3)
    k = rv / angle
    K = np.array([
        [0.0, -k[2], k[1]],
        [k[2], 0.0, -k[0]],
        [-k[1], k[0], 0.0]
    ])
    R = np.eye(3) + np.sin(angle) * K + (1.0 - np.cos(angle)) * np.dot(K, K)
    return R

def probe_surface_point(rtde_c, rtde_r, p_start_pose: list, cfg: dict) -> list:
    """
    BLOCK 5: Contact Probing (X-Axis) Logic
    Moves the tool tip slowly along the robot base X-axis (pointing forward towards the board)
    until contact force along that axis is detected and verified.
    Returns the exact contact pose [X, Y, Z, Rx, Ry, Rz].
    """
    # -------------------------------------------------------------
    # Step 1: Zero the force sensor to clear residual drift
    # -------------------------------------------------------------
    logger.info("Zeroing force/torque sensor...")
    rtde_c.zeroFtSensor()
    time.sleep(cfg['sensor_zero_sleep'])
    
    # -------------------------------------------------------------
    # Step 2: Compute target forward pose based on search distance
    # -------------------------------------------------------------
    target_pose = list(p_start_pose)
    target_pose[0] -= cfg['search_distance']
    
    logger.info(f"Target Probing Pose: {[round(c, 4) for c in target_pose[:3]]}")
    
    # -------------------------------------------------------------
    # Step 3: Extract approach, verification, and safety parameters
    # -------------------------------------------------------------
    approach_speed = cfg['initial_approach_speed']
    accel = cfg['approach_acceleration']
    force_threshold = cfg['force_threshold']
    required_consecutive_high = cfg['required_consecutive_high']
    total_verify_readings = cfg['total_verify_readings']
    required_verify_high = cfg['required_verify_high']
    max_consecutive_low = cfg['max_consecutive_low']
    polling_interval_search = cfg['polling_interval_search']
    polling_interval_verify = cfg['polling_interval_verify']
    speed_slowdown_factor = cfg['speed_slowdown_factor']
    stop_deceleration = cfg['stop_deceleration']
    target_reached_tolerance = cfg['target_reached_tolerance']
    
    contact_pose = None
    start_time = time.time()
    
    try:
        while True:
            # -------------------------------------------------------------
            # Safety timeout check (max 30 seconds per probe point)
            # -------------------------------------------------------------
            if time.time() - start_time > 30.0:
                logger.error("Probing timeout reached (30s) without confirming contact.")
                break
                
            curr_pose = rtde_r.getActualTCPPose()
            dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose[:3])))
            
            if dist < target_reached_tolerance:
                logger.warning("Reached target forward pose without detecting contact.")
                break
                
            logger.info(f"Starting/resuming approach at speed {approach_speed * 1000.0:.2f} mm/s...")
            # Move towards target pose asynchronously using moveL
            rtde_c.moveL(target_pose, approach_speed, accel, True)
            
            # -------------------------------------------------------------
            # Phase 1: Search for consecutive readings >= force_threshold
            # -------------------------------------------------------------
            consecutive_high_readings = 0
            search_success = False
            
            import math
            
            while True:
                # -------------------------------------------------------------
                # Inner loop timeout and distance safety checks
                # -------------------------------------------------------------
                if time.time() - start_time > 30.0:
                    break
                    
                curr_pose = rtde_r.getActualTCPPose()
                dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose[:3])))
                if dist < target_reached_tolerance:
                    logger.warning("Reached target forward pose during search.")
                    break
                    
                forces_base = np.array(rtde_r.getActualTCPForce()[:3])
                measured_force_x = forces_base[0]  # Force along base X
                
                # Check consecutive readings
                if abs(measured_force_x) >= force_threshold:
                    consecutive_high_readings += 1
                else:
                    consecutive_high_readings = 0
                    
                if consecutive_high_readings >= required_consecutive_high:
                    logger.info(f"Initial contact threshold reached ({required_consecutive_high} readings >= {force_threshold} N). Stopping motion...")
                    rtde_c.stopL(stop_deceleration)
                    wait_for_motion_complete(rtde_c)
                    search_success = True
                    break
                    
                time.sleep(polling_interval_search)
                
            if not search_success:
                break
                
            # -------------------------------------------------------------
            # Phase 2: Verify contact while stopped to filtering out noise/impacts
            # -------------------------------------------------------------
            logger.info("Verifying contact while stopped...")
            readings = []
            consecutive_low_readings = 0
            failed_verification = False
            
            for i in range(total_verify_readings):
                time.sleep(polling_interval_verify)
                forces_base = np.array(rtde_r.getActualTCPForce()[:3])
                measured_force_x = forces_base[0]
                force_val = abs(measured_force_x)
                
                readings.append(force_val)
                
                if force_val < force_threshold:
                    consecutive_low_readings += 1
                else:
                    consecutive_low_readings = 0
                    
                logger.info(f"Verify reading {i+1}/{total_verify_readings}: Force X: {measured_force_x:.2f}N | Consecutive Low: {consecutive_low_readings}/{max_consecutive_low}")
                
                if consecutive_low_readings >= max_consecutive_low:
                    logger.warning(f"Verification failed: force dropped below {force_threshold} N for {max_consecutive_low} consecutive readings.")
                    failed_verification = True
                    break
                    
            if not failed_verification:
                high_count = sum(1 for f in readings if f >= force_threshold)
                logger.info(f"Verification results: High count = {high_count}/{total_verify_readings}. Readings = {[round(f, 2) for f in readings]}")
                if high_count >= required_verify_high:
                    logger.success("Contact confirmed!")
                    contact_pose = rtde_r.getActualTCPPose()
                    break
                else:
                    logger.warning(f"Verification failed: only {high_count} out of {total_verify_readings} readings were >= {force_threshold} N.")
                    failed_verification = True
                    
            # -------------------------------------------------------------
            # Step 4: Scale down search speed and resume if verification failed
            # -------------------------------------------------------------
            if failed_verification:
                approach_speed = approach_speed * speed_slowdown_factor
                logger.info(f"Slowing down. New approach speed: {approach_speed * 1000.0:.2f} mm/s. Resuming search...")
                
    except Exception as e:
        logger.error(f"Error during probing search: {e}")
    finally:
        # In case of any error or exiting, guarantee we stop the robot
        try:
            rtde_c.stopL(stop_deceleration)
        except Exception:
            pass
        
    return contact_pose

def main():
    logger.info("=" * 60)
    logger.info("PORTRAITRON 3000 - SEMI-AUTOMATED 3-POINT PLANE CALIBRATION")
    logger.info("=" * 60)
    
    # Ensure config directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    # Load config file (default to config/marker.yaml, or arg if passed)
    config_name = "marker"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        config_name = sys.argv[1]
        
    if not config_name.endswith(".yaml") and "/" not in config_name and "\\" not in config_name:
        config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../config/{config_name}.yaml"))
    else:
        config_file_path = os.path.abspath(config_name)
        
    cfg = load_config_from_yaml(config_file_path)
    
    logger.info(f"Connecting to UR5e at IP: {ROBOT_IP}...")
    try:
        rtde_c = rtde_control.RTDEControlInterface(ROBOT_IP)
        rtde_r = rtde_receive.RTDEReceiveInterface(ROBOT_IP)
        logger.success("Sockets connected successfully.")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        sys.exit(1)
        
    try:
        logger.info(
            "INSTRUCTIONS:\n"
            "1. Use the teach pendant to jog the robot arm.\n"
            "2. Place the pen tip hovering approximately 1.5 cm normal to the\n"
            "   Bottom-Left corner of your A4 drawing sheet (this is hover pose P0).\n"
            "3. Ensure the tool is oriented perpendicular to the paper surface."
        )
        
        p0_joints = rtde_r.getActualQ()
        p0_pose = rtde_r.getActualTCPPose()
        logger.info(f"Recorded P0 Pose: {[round(c, 4) for c in p0_pose[:3]]}")
        logger.info(f"Recorded P0 Joints: {[round(c, 4) for c in p0_joints]}")
        
        # 1. Probing P1 (Bottom-Left Surface)
        logger.info("Probing Bottom-Left Surface (P1)...")
        # Probing forward from current P0 hover along tool Z axis
        p1_surface = probe_surface_point(rtde_c, rtde_r, p_start_pose=p0_pose, cfg=cfg)
        if not p1_surface:
            logger.error("Probing P1 failed. Aborting calibration.")
            return
            
        # Retract back to hover pose P0 using moveJ with recorded joint coordinates to avoid numerical IK calculations
        logger.info("Retracting to P0 hover...")
        rtde_c.moveJ(p0_joints, 0.2, 0.1)
        time.sleep(0.5)
        
        # 2. Probing P2 (Bottom-Right Surface)
        logger.info("Moving to Bottom-Right and probing (P2)...")
        # Shift 19 cm to the right (+Y direction in base frame)
        p2_hover = list(p0_pose)
        p2_hover[1] += 0.19
        
        # Move to P2 hover using Cartesian moveL to avoid heavy IK solver loops on the controller
        logger.info("Moving to P2 hover...")
        rtde_c.moveL(p2_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        p2_surface = probe_surface_point(rtde_c, rtde_r, p_start_pose=p2_hover, cfg=cfg)
        if not p2_surface:
            logger.error("Probing P2 failed. Aborting calibration.")
            return
            
        logger.info("Retracting to P2 hover...")
        rtde_c.moveL(p2_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        # 3. Probing P3 (Top-Left Surface)
        logger.info("Moving to Top-Left and probing (P3)...")
        # Return to P0 using safe joint joints, then shift 27 cm up (+Z direction in base frame)
        logger.info("Returning to P0 hover...")
        rtde_c.moveJ(p0_joints, 0.2, 0.1)
        time.sleep(0.5)
        
        p3_hover = list(p0_pose)
        p3_hover[2] += 0.27
        
        logger.info("Moving to P3 hover...")
        rtde_c.moveL(p3_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        p3_surface = probe_surface_point(rtde_c, rtde_r, p_start_pose=p3_hover, cfg=cfg)
        if not p3_surface:
            logger.error("Probing P3 failed. Aborting calibration.")
            return
            
        logger.info("Retracting to P3 hover...")
        rtde_c.moveL(p3_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        # Return to safety start pose
        logger.info("Calibration probing completed. Returning to starting hover P0...")
        rtde_c.moveJ(p0_joints, 0.2, 0.1)
        
        # Write calibration configuration to yaml
        cal_data = {
            "p0_joints": [float(q) for q in p0_joints],
            "p0_pose": [float(p) for p in p0_pose],
            "p1": [float(p) for p in p1_surface],
            "p2": [float(p) for p in p2_surface],
            "p3": [float(p) for p in p3_surface],
            "width": 0.19,
            "height": 0.27,
            "# spring_compression_depth": 0.000 # Disabled: no spring available
        }
        
        with open(OUTPUT_PATH, "w") as f:
            yaml.safe_dump(cal_data, f, default_flow_style=False)
            
        logger.success(f"Workspace calibration saved to {OUTPUT_PATH}!")
        
    finally:
        # Safe disconnect
        rtde_c.disconnect()
        rtde_r.disconnect()
        logger.info("Calibration script finished.")

if __name__ == "__main__":
    main()
