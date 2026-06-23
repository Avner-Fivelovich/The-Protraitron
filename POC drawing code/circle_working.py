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
# -------------------------------------------------------------
ROBOT_IP = "192.168.57.101"

rtde_c = None
rtde_r = None

try:
    # -------------------------------------------------------------
    # BLOCK 3: Connection Phase
    # -------------------------------------------------------------
    print(f"Connecting to RTDE Control Interface at {ROBOT_IP}...")
    rtde_c = RTDEControlInterface(ROBOT_IP)
    print("RTDE Control Interface connected successfully.")
    
    print(f"Connecting to RTDE Receive Interface at {ROBOT_IP}...")
    rtde_r = RTDEReceiveInterface(ROBOT_IP)
    print("RTDE Receive Interface connected successfully.")

    # USER PARAMETERS FOR THE CIRCLE
    # ---------------------------------------------------------
    try:
        USER_ANGLE = float(input("Enter the arc angle to draw in degrees (e.g., 90, 180, 360): "))
    except ValueError:
        print("Invalid input. Defaulting to 180 degrees.")
        USER_ANGLE = 180.0

    RADIUS = 0.03          # 3 cm radius for the drawing arc
    FORWARD_FORCE = 0.5    # Force in Newtons (0.5 N) for sliding compliance
    
    print("Zeroing FT sensor...")
    rtde_c.zeroFtSensor()
    time.sleep(0.5)

    print("Reading current robot position...")
    start_pose = rtde_r.getActualTCPPose()
    print(f"Start Pose: {start_pose}")

    # -------------------------------------------------------------
    # BLOCK 5: Wall Approach (X-Axis)
    # -------------------------------------------------------------
    target_pose_forward = list(start_pose)
    target_pose_forward[0] -= 0.15  # Max search distance of 15 cm
    
    print(f"Target Forward Pose: {target_pose_forward}")
    print("Moving slowly forward to the wall along X axis...")
    
    approach_speed = 0.01  
    approach_acceleration = 0.1
    
    rtde_c.moveL(target_pose_forward, approach_speed, approach_acceleration, True)
    
    consecutive_readings = 0
    REQUIRED_READINGS = 2
    FORCE_THRESHOLD = 0.5  
    contact_detected = False
    
    while True:
        curr_pose = rtde_r.getActualTCPPose()
        dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_forward[:3])))
        
        actual_forces = rtde_r.getActualTCPForce()
        measured_force_x = actual_forces[0]
        
        print(f"Approaching... Pose X: {curr_pose[0]:.4f} | Force X: {measured_force_x:.2f}N | Count: {consecutive_readings}/{REQUIRED_READINGS}")
        
        if abs(measured_force_x) >= FORCE_THRESHOLD:
            consecutive_readings += 1
        else:
            consecutive_readings = 0
            
        if consecutive_readings >= REQUIRED_READINGS:
            print(f"Contact detected! Force exceeded {FORCE_THRESHOLD}N.")
            rtde_c.stopL(2.0)
            contact_detected = True
            break
            
        if dist < 0.001:
            print("Reached target forward pose without detecting contact.")
            break
            
        time.sleep(0.01)  
        
    if contact_detected:
        # -------------------------------------------------------------
        # BLOCK 6: Force Compliance Activation
        # -------------------------------------------------------------
        print("Waiting for robot to settle...")
        time.sleep(0.5)
        
        contact_pose = rtde_r.getActualTCPPose()
        print(f"Contact Pose (Surface Baseline): {contact_pose}")
        
        # Calculate the center point of the circle on the Y-Z plane.
        # Starting at contact_pose assumes the circle starts at angle theta = 0.
        # We shift down by RADIUS on the Z axis so contact_pose rests at the top edge of the circle profile.
        circle_center_y = contact_pose[1]
        circle_center_z = contact_pose[2] - RADIUS
        
        # Activate force mode
        tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        tool_selection_vector = [1, 0, 0, 0, 0, 0] # Compliance ONLY on Base X axis
        tool_wrench = [FORWARD_FORCE, 0.0, 0.0, 0.0, 0.0, 0.0]
        FORCE_TYPE_TOOL = 2
        
        rtde_c.forceModeSetDamping(0.1)
        limits = [0.005, 0.05, 0.05, 0.2, 0.2, 0.2]
        
        rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, FORCE_TYPE_TOOL, limits)
        print("Force mode activated, waiting for force to stabilize...")
        
        stabilize_start = time.time()
        while time.time() - stabilize_start < 2.0:
            actual_forces = rtde_r.getActualTCPForce()
            print(f"Stabilizing... Live Force Fx={actual_forces[0]:.2f}N")
            time.sleep(0.1)
            
        # -------------------------------------------------------------
        # BLOCK 7: Compliant Circular Slide (Replaces the linear block)
        # -------------------------------------------------------------
        print(f"Executing circular arc of {USER_ANGLE} degrees on the Y-Z plane...")
        
        DT = 0.002             # 500Hz real-time frequency
        TOTAL_TIME = 6.0       # Duration of the drawing arc path execution
        NUM_STEPS = int(TOTAL_TIME / DT)
        
        for i in range(NUM_STEPS + 1):
            # Calculate current angle step in radians
            theta = (math.radians(USER_ANGLE) * i) / NUM_STEPS
            
            # Recompute target waypoint relative to the circle origin
            wp = list(contact_pose)
            wp[1] = circle_center_y + RADIUS * math.sin(theta)
            wp[2] = circle_center_z + RADIUS * math.cos(theta)
            
            # Continuously maintain background force while streaming positions
            rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, FORCE_TYPE_TOOL, limits)
            rtde_c.servoL(wp, 0.0, 0.0, DT, 0.03, 2000)
            
            # Sample telemetry logging at roughly 10Hz
            if i % 50 == 0:
                actual_forces = rtde_r.getActualTCPForce()
                print(f"Drawing... Step: {i}/{NUM_STEPS} | Live Force Fx: {actual_forces[0]:.2f}N")
                
            time.sleep(DT)
            
        # Clear the trajectory streaming buffers cleanly
        rtde_c.servoStop()
        print("Circular slide movement complete!")
        time.sleep(1)
        
        # -------------------------------------------------------------
        # BLOCK 8: Retraction Phase
        # -------------------------------------------------------------
        print("Moving back from the wall...")
        rtde_c.forceModeStop()
        time.sleep(0.2)
        
        retract_pose = list(rtde_r.getActualTCPPose())
        retract_pose[0] += 0.05  # Pull back 5 cm away along X
        rtde_c.moveL(retract_pose, 0.05, 0.1)
        print("Retraction complete.")
    else:
        print("Aborting sliding motion since contact was not detected.")

finally:
    # -------------------------------------------------------------
    # BLOCK 9: Safe Disconnect Cleanup
    # -------------------------------------------------------------
    print("Initiating safety disconnect sequence...")
    if rtde_c is not None:
        try:
            rtde_c.forceModeStop()
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