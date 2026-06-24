import time
import math
import numpy as np

# -------------------------------------------------------------
# Import the custom project logger
# -------------------------------------------------------------
from src.common.logger import get_logger

# Initialize a logger specific to probing operations
logger = get_logger("Probing")

def wait_for_motion_complete(rtde_c, poll_interval: float = 0.01):
    """
    Blocks execution until the current asynchronous motion on the UR robot controller completes.
    Uses getAsyncOperationProgress() to query progress status.
    """
    while rtde_c.getAsyncOperationProgress() >= 0:
        time.sleep(poll_interval)

def _search_for_contact(rtde_c, rtde_r, target_pose: list, cfg: dict, approach_speed: float, start_time: float) -> bool:
    """
    Helper function to run the approach and search for contact.
    Returns True if threshold is crossed consecutively, False if target is reached or search fails/times out.
    """
    accel = cfg['approach_acceleration']
    force_threshold = cfg['force_threshold']
    required_consecutive_high = cfg['required_consecutive_high']
    polling_interval_search = cfg['polling_interval_search']
    target_reached_tolerance = cfg['target_reached_tolerance']
    stop_deceleration = cfg['stop_deceleration']
    
    # Start motion asynchronously towards target pose
    rtde_c.moveL(target_pose, approach_speed, accel, True)
    
    consecutive_high_readings = 0
    search_success = False
    
    while True:
        # Check overall probing timeout (max 30s)
        if time.time() - start_time > 30.0:
            break
            
        curr_pose = rtde_r.getActualTCPPose()
        dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose[:3])))
        
        # Stop search if target pose is reached within tolerance
        if dist < target_reached_tolerance:
            logger.warning("Reached target forward pose during search.")
            break
            
        forces_base = np.array(rtde_r.getActualTCPForce()[:3])
        measured_force_x = forces_base[0]
        
        # Monitor consecutive readings exceeding force threshold
        if measured_force_x >= force_threshold:
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
        
    return search_success

def _verify_contact(rtde_r, cfg: dict) -> bool:
    """
    Helper function to perform stopped contact verification.
    Returns True if confirmed, False if verification fails.
    """
    force_threshold = cfg['force_threshold']
    total_verify_readings = cfg['total_verify_readings']
    required_verify_high = cfg['required_verify_high']
    max_consecutive_low = cfg['max_consecutive_low']
    polling_interval_verify = cfg['polling_interval_verify']
    
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
        
        # Check for consecutive low readings
        if force_val < force_threshold:
            consecutive_low_readings += 1
        else:
            consecutive_low_readings = 0
            
        logger.info(f"Verify reading {i+1}/{total_verify_readings}: Force X: {measured_force_x:.2f}N | Consecutive Low: {consecutive_low_readings}/{max_consecutive_low}")
        
        if consecutive_low_readings >= max_consecutive_low:
            logger.warning(f"Verification failed: force dropped below {force_threshold} N for {max_consecutive_low} consecutive readings.")
            failed_verification = True
            break
            
    if failed_verification:
        return False
        
    high_count = sum(1 for f in readings if f >= force_threshold)
    logger.info(f"Verification results: High count = {high_count}/{total_verify_readings}. Readings = {[round(f, 2) for f in readings]}")
    if high_count >= required_verify_high:
        logger.success("Contact confirmed!")
        return True
    else:
        logger.warning(f"Verification failed: only {high_count} out of {total_verify_readings} readings were >= {force_threshold} N.")
        return False

def probe_surface_point(rtde_c, rtde_r, p_start_pose: list, cfg: dict) -> list:
    """
    Moves the tool tip slowly along the robot base X-axis (pointing forward towards the board)
    until contact force along that axis is detected and verified.
    Returns the exact contact pose [X, Y, Z, Rx, Ry, Rz] or None if failed.
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
    
    approach_speed = cfg['initial_approach_speed']
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
                
            # -------------------------------------------------------------
            # Phase 1: Search for contact
            # -------------------------------------------------------------
            logger.info(f"Starting/resuming approach at speed {approach_speed * 1000.0:.2f} mm/s...")
            search_success = _search_for_contact(rtde_c, rtde_r, target_pose, cfg, approach_speed, start_time)
            
            if not search_success:
                break
                
            # -------------------------------------------------------------
            # Phase 2: Verify contact stability
            # -------------------------------------------------------------
            verified = _verify_contact(rtde_r, cfg)
            if verified:
                contact_pose = rtde_r.getActualTCPPose()
                break
            else:
                # approach_speed = approach_speed * speed_slowdown_factor
                logger.info(f"Slowing down. New approach speed: {approach_speed * 1000.0:.2f} mm/s. Resuming search...")
                
    except Exception as e:
        logger.error(f"Error during probing search: {e}")
    finally:
        # Guarantee stop on failure or completion
        try:
            rtde_c.stopL(stop_deceleration)
        except Exception:
            pass
            
    return contact_pose
