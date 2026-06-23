'''
This code is me playing around with the force mode
with a horizontal line rather than a circle
'''

import os
import sys
import math
import time
import yaml

# Add root folder to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rtde_control import RTDEControlInterface, Path, PathEntry
from rtde_receive import RTDEReceiveInterface
from src.common.robot_utils import wait_for_motion_complete
from src.common.config_utils import load_config_from_yaml

# -------------------------------------------------------------
# BLOCK 1: Robot IP Configuration
# Specifies the network address of the Universal Robot controller.
# -------------------------------------------------------------
ROBOT_IP = "192.168.57.101"

# -------------------------------------------------------------
# BLOCK 2: Interface Initializer
# Placeholders for Control and Receive interfaces so they can be safely cleared in 'finally'.
# -------------------------------------------------------------
rtde_c = None
rtde_r = None


def connect_robot(ip):
    """
    BLOCK 3: Connection Phase
    Establishes TCP/IP socket connections to control port 30003 and receive port 30004.
    """
    print(f"Connecting to RTDE Control Interface at {ip}...")
    rtde_control_obj = RTDEControlInterface(ip)
    print("RTDE Control Interface connected successfully.")
    
    print(f"Connecting to RTDE Receive Interface at {ip}...")
    rtde_receive_obj = RTDEReceiveInterface(ip)
    print("RTDE Receive Interface connected successfully.")
    return rtde_control_obj, rtde_receive_obj


def zero_sensor_and_get_pose(rtde_control_obj, rtde_receive_obj, zero_sleep):
    """
    BLOCK 4b: Sensor Calibration & Home Reading
    Zeroes the F/T sensor bias and reads the starting TCP coordinates.
    """
    print("Zeroing FT sensor...")
    rtde_control_obj.zeroFtSensor()
    time.sleep(zero_sleep)

    print("Reading current robot position...")
    start_pose = rtde_receive_obj.getActualTCPPose()
    print(f"Start Pose: {start_pose}")
    return start_pose


def approach_wall(rtde_control_obj, rtde_receive_obj, start_pose, cfg):
    """
    BLOCK 5: Wall Approach (X-Axis) Logic
    Moves slowly forward along Base X-axis. Loops and polls force sensor.
    Stops motion when contact force exceeds 0.3 N for 2 consecutive readings.
    Verifies contact by checking if 10 out of 20 readings are >= 0.3 N.
    If 5 consecutive readings drop below 0.3 N, it continues moving slower and restarts the search.
    """
    target_pose_forward = list(start_pose)
    target_pose_forward[0] -= cfg['search_distance']
    
    print(f"Target Forward Pose: {target_pose_forward}")
    
    approach_speed = cfg['initial_approach_speed']
    contact_detected = False
    
    while True:
        curr_pose = rtde_receive_obj.getActualTCPPose()
        dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_forward[:3])))
        
        if dist < cfg['target_reached_tolerance']:
            print("Reached target forward pose without detecting contact.")
            break
            
        print(f"Starting/resuming approach at speed {approach_speed:.4f} m/s...")
        rtde_control_obj.moveL(target_pose_forward, approach_speed, cfg['approach_acceleration'], True)
        
        # Phase 1: Search for consecutive readings >= force_threshold
        consecutive_high_readings = 0
        search_success = False
        
        while True:
            curr_pose = rtde_receive_obj.getActualTCPPose()
            dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_forward[:3])))
            
            actual_forces = rtde_receive_obj.getActualTCPForce()
            measured_force_x = actual_forces[0]
            force_val = measured_force_x
            
            print(f"Approaching... Pose X: {curr_pose[0]:.4f} | Force X: {measured_force_x:.2f}N | Count: {consecutive_high_readings}/{cfg['required_consecutive_high']}")
            
            if force_val >= cfg['force_threshold']:
                consecutive_high_readings += 1
            else:
                consecutive_high_readings = 0
                
            if consecutive_high_readings >= cfg['required_consecutive_high']:
                print(f"Initial contact threshold reached ({cfg['required_consecutive_high']} readings >= {cfg['force_threshold']} N). Stopping motion...")
                rtde_control_obj.stopL(cfg['stop_deceleration'])
                wait_for_motion_complete(rtde_control_obj)
                search_success = True
                break
                
            if dist < cfg['target_reached_tolerance']:
                print("Reached target forward pose during search.")
                break
                
            time.sleep(cfg['polling_interval_search'])
            
        if not search_success:
            break
            
        # Phase 2: Verify contact (wait for required_verify_high out of total_verify_readings)
        print("Verifying contact while stopped...")
        readings = []
        consecutive_low_readings = 0
        failed_verification = False
        
        for i in range(cfg['total_verify_readings']):
            time.sleep(cfg['polling_interval_verify'])
            actual_forces = rtde_receive_obj.getActualTCPForce()
            measured_force_x = actual_forces[0]
            force_val = abs(measured_force_x)
            
            readings.append(force_val)
            
            if force_val < cfg['force_threshold']:
                consecutive_low_readings += 1
            else:
                consecutive_low_readings = 0
                
            print(f"Verify reading {i+1}/{cfg['total_verify_readings']}: Force X: {measured_force_x:.2f}N | Consecutive Low: {consecutive_low_readings}/{cfg['max_consecutive_low']}")
            
            if consecutive_low_readings >= cfg['max_consecutive_low']:
                print(f"Verification failed: force dropped below {cfg['force_threshold']} N for {cfg['max_consecutive_low']} consecutive readings.")
                failed_verification = True
                break
                
        if not failed_verification:
            high_count = sum(1 for f in readings if f >= cfg['force_threshold'])
            print(f"Verification results: High count = {high_count}/{cfg['total_verify_readings']}. Readings = {[round(f, 2) for f in readings]}")
            if high_count >= cfg['required_verify_high']:
                print("Contact confirmed!")
                contact_detected = True
                break
            else:
                print(f"Verification failed: only {high_count} out of {cfg['total_verify_readings']} readings were >= {cfg['force_threshold']} N.")
                failed_verification = True
                
        if failed_verification:
            # Continue moving but slower
            # approach_speed = approach_speed * cfg['speed_slowdown_factor']
            print(f"Slowing down. New approach speed: {approach_speed:.4f} m/s. Resuming search...")
            
    return contact_detected


def activate_force_compliance(rtde_control_obj, rtde_receive_obj, cfg):
    """
    BLOCK 6: Force Compliance Activation Logic
    Configures and starts Force Mode on the compliance axis to maintain contact.
    """
    print("Waiting for robot to settle...")
    time.sleep(cfg['settle_sleep'])
    
    contact_pose = rtde_receive_obj.getActualTCPPose()
    print(f"Contact Pose: {contact_pose}")
    
    # Activate force mode to maintain compliance
    tool_wrench = [cfg['forward_force'], 0.0, 0.0, 0.0, 0.0, 0.0]
    rtde_control_obj.forceModeSetDamping(cfg['force_damping'])
    rtde_control_obj.forceMode(cfg['tool_task_frame'], cfg['tool_selection_vector'], tool_wrench, cfg['force_type_tool'], cfg['force_limits'])
    print("Force mode activated, waiting for force to stabilize...")
    
    stabilize_start = time.time()
    while time.time() - stabilize_start < cfg['stabilize_timeout']:
        actual_forces = rtde_receive_obj.getActualTCPForce()
        print(f"Stabilizing... Live Force: Fx={actual_forces[0]:.2f}N, Fy={actual_forces[1]:.2f}N, Fz={actual_forces[2]:.2f}N")
        time.sleep(cfg['stabilize_poll_interval'])
    return contact_pose


def execute_slide_left(rtde_control_obj, rtde_receive_obj, contact_pose, cfg):
    """
    BLOCK 7: Compliant Lateral Slide Logic
    Slides the tool left (-Y axis) by 5 cm while maintaining normal force contact.
    """
    target_pose_left = list(contact_pose)
    target_pose_left[1] -= cfg['slide_distance']
    
    print(f"Target Slide Pose: {target_pose_left}")
    print(f"Moving left {cfg['slide_distance']*cfg['m_to_cm_multiplier']:.0f} cm under force compliance...")
    
    rtde_control_obj.moveL(target_pose_left, cfg['slide_speed'], cfg['slide_acceleration'], True)
    
    while True:
        curr_pose = rtde_receive_obj.getActualTCPPose()
        dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_left[:3])))
        actual_forces = rtde_receive_obj.getActualTCPForce()
        print(f"Sliding... Dist to Target: {dist:.4f}m | Live Force: Fx={actual_forces[0]:.2f}N, Fy={actual_forces[1]:.2f}N, Fz={actual_forces[2]:.2f}N")
        if dist < cfg['slide_accuracy']:
            break
        time.sleep(cfg['slide_poll_interval'])
        
    # Wait for the motion to complete
    wait_for_motion_complete(rtde_control_obj)

    print("Asynchronous motion is fully complete!")
    print("Slide movement complete!")
    
    time.sleep(cfg['post_slide_sleep'])


def retract_from_wall(rtde_control_obj, rtde_receive_obj, cfg):
    """
    BLOCK 8: Retraction Phase Logic
    Disables Force Mode and safely pulls the tool back away from the wall.
    """
    print("Moving back from the wall...")
    rtde_control_obj.forceModeStop()
    retract_pose = list(rtde_receive_obj.getActualTCPPose())
    retract_pose[0] += cfg['retract_distance']
    rtde_control_obj.moveL(retract_pose, cfg['retract_speed'], cfg['retract_acceleration'])
    print("Retraction complete.")


def safe_cleanup(rtde_control_obj, rtde_receive_obj, stop_decel):
    """
    BLOCK 9: Safe Disconnect Cleanup Logic
    Guarantees that TCP connections are closed even if errors or interrupts occur.
    """
    print("Initiating safety disconnect sequence...")
    if rtde_control_obj is not None:
        try:
            rtde_control_obj.stopL(stop_decel)
        except Exception as e:
            print(f"Error stopping robot: {e}")
        try:
            rtde_control_obj.disconnect()
            print("RTDE Control Interface disconnected.")
        except Exception as e:
            print(f"Error disconnecting RTDE Control: {e}")
    if rtde_receive_obj is not None:
        try:
            rtde_receive_obj.disconnect()
            print("RTDE Receive Interface disconnected.")
        except Exception as e:
            print(f"Error disconnecting RTDE Receive: {e}")
    print("Disconnected safely.")


def main():
    global rtde_c, rtde_r
    
    # Get config name/path from command line argument, defaulting to "marker"
    config_name = "marker"
    if len(sys.argv) > 1:
        config_name = sys.argv[1]
        
    # Resolve to config/{config_name}.yaml if simple name is provided, else use directly
    if not config_name.endswith(".yaml") and "/" not in config_name and "\\" not in config_name:
        config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../config/{config_name}.yaml"))
    else:
        config_file_path = os.path.abspath(config_name)
        
    cfg = load_config_from_yaml(config_file_path)
    
    try:
        # Connect to robot
        rtde_c, rtde_r = connect_robot(ROBOT_IP)
        
        # Zero sensor and get start pose
        start_pose = zero_sensor_and_get_pose(rtde_c, rtde_r, cfg['sensor_zero_sleep'])
        
        # Phase 1 & 2: Wall Approach with contact search & verification
        contact_detected = approach_wall(rtde_c, rtde_r, start_pose, cfg)
        
        if contact_detected:
            # Settle and activate force compliance
            contact_pose = activate_force_compliance(rtde_c, rtde_r, cfg)
            
            # Slide left 5 cm
            execute_slide_left(rtde_c, rtde_r, contact_pose, cfg)
            
            # Retract tool
            retract_from_wall(rtde_c, rtde_r, cfg)
        else:
            print("Aborting sliding motion since contact was not detected.")
            
    finally:
        # Cleanup
        safe_cleanup(rtde_c, rtde_r, cfg['disconnect_stop_deceleration'])


if __name__ == "__main__":
    main()