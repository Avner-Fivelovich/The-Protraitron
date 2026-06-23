'''
This code is me playing around with the force mode
with a horizontal line rather than a circle
'''

import os
import sys
import math
import time

# Add root folder to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rtde_control import RTDEControlInterface, Path, PathEntry
from rtde_receive import RTDEReceiveInterface
from src.common.robot_utils import wait_for_motion_complete

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

try:
    # -------------------------------------------------------------
    # BLOCK 3: Connection Phase
    # Establishes TCP/IP socket connections to control port 30003 and receive port 30004.
    # -------------------------------------------------------------
    print(f"Connecting to RTDE Control Interface at {ROBOT_IP}...")
    rtde_c = RTDEControlInterface(ROBOT_IP)
    print("RTDE Control Interface connected successfully.")
    
    print(f"Connecting to RTDE Receive Interface at {ROBOT_IP}...")
    rtde_r = RTDEReceiveInterface(ROBOT_IP)
    print("RTDE Receive Interface connected successfully.")

    FORWARD_FORCE = 0.5     # Force in Newtons (0.5 N) for sliding compliance
    
    print("Zeroing FT sensor...")
    rtde_c.zeroFtSensor()
    time.sleep(0.5)

    print("Reading current robot position...")
    start_pose = rtde_r.getActualTCPPose()
    print(f"Start Pose: {start_pose}")

    # -------------------------------------------------------------
    # BLOCK 5: Wall Approach (X-Axis)
    # Moves slowly forward along Base X-axis. Loops and polls force sensor.
    # Stops motion when contact force exceeds 0.3 N for 2 consecutive readings.
    # Verifies contact by checking if 10 out of 20 readings are >= 0.3 N.
    # If 5 consecutive readings drop below 0.3 N, it continues moving slower and restarts the search.
    # -------------------------------------------------------------
    target_pose_forward = list(start_pose)
    target_pose_forward[0] -= 0.15  # Max search distance of 15 cm
    
    print(f"Target Forward Pose: {target_pose_forward}")
    
    approach_speed = 0.01  # Initial approach speed (1 cm/s)
    approach_acceleration = 0.05
    FORCE_THRESHOLD = 0.3  # 0.3 Newton
    contact_detected = False
    
    while True:
        curr_pose = rtde_r.getActualTCPPose()
        dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_forward[:3])))
        
        if dist < 0.001:
            print("Reached target forward pose without detecting contact.")
            break
            
        print(f"Starting/resuming approach at speed {approach_speed:.4f} m/s...")
        rtde_c.moveL(target_pose_forward, approach_speed, approach_acceleration, True)
        
        # Phase 1: Search for 2 consecutive readings >= 0.3 N
        consecutive_high_readings = 0
        search_success = False
        
        while True:
            curr_pose = rtde_r.getActualTCPPose()
            dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_forward[:3])))
            
            actual_forces = rtde_r.getActualTCPForce()
            measured_force_x = actual_forces[0]
            force_val = abs(measured_force_x)
            
            print(f"Approaching... Pose X: {curr_pose[0]:.4f} | Force X: {measured_force_x:.2f}N | Count: {consecutive_high_readings}/2")
            
            if force_val >= FORCE_THRESHOLD:
                consecutive_high_readings += 1
            else:
                consecutive_high_readings = 0
                
            if consecutive_high_readings >= 2:
                print(f"Initial contact threshold reached (2 readings >= {FORCE_THRESHOLD} N). Stopping motion...")
                rtde_c.stopL(2.0)
                wait_for_motion_complete(rtde_c)
                search_success = True
                break
                
            if dist < 0.001:
                print("Reached target forward pose during search.")
                break
                
            time.sleep(0.01)  # ~100Hz sampling rate
            
        if not search_success:
            break
            
        # Phase 2: Verify contact (wait for 10 out of 20 readings >= 0.3 N)
        print("Verifying contact while stopped...")
        readings = []
        consecutive_low_readings = 0
        failed_verification = False
        
        for i in range(20):
            time.sleep(0.05)  # Sample every 50ms (total ~1s)
            actual_forces = rtde_r.getActualTCPForce()
            measured_force_x = actual_forces[0]
            force_val = abs(measured_force_x)
            
            readings.append(force_val)
            
            if force_val < FORCE_THRESHOLD:
                consecutive_low_readings += 1
            else:
                consecutive_low_readings = 0
                
            print(f"Verify reading {i+1}/20: Force X: {measured_force_x:.2f}N | Consecutive Low: {consecutive_low_readings}/5")
            
            if consecutive_low_readings >= 5:
                print(f"Verification failed: force dropped below {FORCE_THRESHOLD} N for 5 consecutive readings.")
                failed_verification = True
                break
                
        if not failed_verification:
            high_count = sum(1 for f in readings if f >= FORCE_THRESHOLD)
            print(f"Verification results: High count = {high_count}/20. Readings = {[round(f, 2) for f in readings]}")
            if high_count >= 10:
                print("Contact confirmed!")
                contact_detected = True
                break
            else:
                print(f"Verification failed: only {high_count} out of 20 readings were >= {FORCE_THRESHOLD} N.")
                failed_verification = True
                
        if failed_verification:
            # Continue moving but slower
            # approach_speed = approach_speed * 0.5
            print(f"Slowing down. New approach speed: {approach_speed:.4f} m/s. Resuming search...")
        
    if contact_detected:
        # -------------------------------------------------------------
        # BLOCK 6: Force Compliance Activation
        # Configures and starts Force Mode on the compliance axis (index 0/X)
        # to dynamically adapt height/pressure to the surface during slide.
        # -------------------------------------------------------------
        print("Waiting for robot to settle...")
        time.sleep(0.5)
        
        contact_pose = rtde_r.getActualTCPPose()
        print(f"Contact Pose: {contact_pose}")
        
        # Activate force mode to maintain compliance
        tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        tool_selection_vector = [1, 0, 0, 0, 0, 0] # Compliance ONLY on Z axis (but actually index 0 is X)
        tool_wrench = [FORWARD_FORCE, 0.0, 0.0, 0.0, 0.0, 0.0]
        FORCE_TYPE_TOOL = 2
        rtde_c.forceModeSetDamping(0.1)
        limits = [0.005, 0.05, 0.05, 0.2, 0.2, 0.2]
        
        rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, FORCE_TYPE_TOOL, limits)
        print("Force mode activated, waiting for force to stabilize...")
        
        stabilize_start = time.time()
        while time.time() - stabilize_start < 2.0:
            actual_forces = rtde_r.getActualTCPForce()
            print(f"Stabilizing... Live Force: Fx={actual_forces[0]:.2f}N, Fy={actual_forces[1]:.2f}N, Fz={actual_forces[2]:.2f}N")
            time.sleep(0.1)
            
        # -------------------------------------------------------------
        # BLOCK 7: Compliant Lateral Slide
        # Slides the tool left (-Y axis) by 5 cm while maintaining normal force contact.
        # Monitors force and position in real-time.
        # -------------------------------------------------------------
        target_pose_left = list(contact_pose)
        target_pose_left[1] -= 0.05  # Move 5 cm left (-Y)
        
        print(f"Target Slide Pose: {target_pose_left}")
        print("Moving left 5 cm under force compliance...")
        
        slide_speed = 0.02  # Safe sliding speed (2 cm/s)
        slide_acceleration = 0.1
        slide_accuracy = 0.003 # 3mm accuracy 
        
        rtde_c.moveL(target_pose_left, slide_speed, slide_acceleration, True)
        
        while True:
            curr_pose = rtde_r.getActualTCPPose()
            dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_left[:3])))
            actual_forces = rtde_r.getActualTCPForce()
            print(f"Sliding... Dist to Target: {dist:.4f}m | Live Force: Fx={actual_forces[0]:.2f}N, Fy={actual_forces[1]:.2f}N, Fz={actual_forces[2]:.2f}N")
            if dist < slide_accuracy:
                break
            time.sleep(0.1)
            
        # Wait for the motion to complete
        wait_for_motion_complete(rtde_c)

        print("Asynchronous motion is fully complete!")
        print("Slide movement complete!")
        
        time.sleep(1)
        
        # -------------------------------------------------------------
        # BLOCK 8: Retraction Phase
        # Disables Force Mode and safely pulls the tool back 3 cm away from the wall.
        # -------------------------------------------------------------
        print("Moving back from the wall...")
        rtde_c.forceModeStop()
        retract_pose = list(rtde_r.getActualTCPPose())
        retract_pose[0] += 0.05  # Pull back 5 cm
        rtde_c.moveL(retract_pose, 0.5, 0.25)
        print("Retraction complete.")
    else:
        print("Aborting sliding motion since contact was not detected.")

finally:
    # -------------------------------------------------------------
    # BLOCK 9: Safe Disconnect Cleanup
    # Guarantees that TCP connections are closed even if errors or interrupts occur.
    # -------------------------------------------------------------
    print("Initiating safety disconnect sequence...")
    if rtde_c is not None:
        try:
            rtde_c.stopL(2.0)
        except Exception as e:
            print(f"Error stopping robot: {e}")
        try:
            rtde_c.disconnect()
            print("RTDE Control Interface disconnected.")
        except Exception as e:
            print(f"Error disconnecting RTDE Control: {e}")
    if rtde_r is not None:
        try:
            rtde_r.disconnect()
            print("RTDE Receive Interface disconnected.")
        except Exception as e:
            print(f"Error disconnecting RTDE Receive: {e}")
    print("Disconnected safely.")