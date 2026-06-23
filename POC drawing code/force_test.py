'''
This code is me playing around with the force mode
with a horizontal line rather than a circle
'''

import math
import time
from rtde_control import RTDEControlInterface, Path, PathEntry
from rtde_receive import RTDEReceiveInterface

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
    # Stops motion when contact force exceeds 0.5 N for 20 consecutive readings.
    # -------------------------------------------------------------
    target_pose_forward = list(start_pose)
    target_pose_forward[0] -= 0.15  # Max search distance of 15 cm
    
    print(f"Target Forward Pose: {target_pose_forward}")
    print("Moving slowly forward to the wall along X axis...")
    
    approach_speed = 0.01  # Slow approach speed (1 cm/s)
    approach_acceleration = 0.1
    
    # Execute linear movement asynchronously to allow monitoring force
    rtde_c.moveL(target_pose_forward, approach_speed, approach_acceleration, True)
    
    consecutive_readings = 0
    REQUIRED_READINGS = 2
    FORCE_THRESHOLD = 1.0  # 1 Newton
    contact_detected = False
    
    while True:
        curr_pose = rtde_r.getActualTCPPose()
        dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_forward[:3])))
        
        # Read the current force on the compliance axis (index 0)
        actual_forces = rtde_r.getActualTCPForce()
        measured_force_x = actual_forces[0]
        
        print(f"Approaching... Pose X: {curr_pose[0]:.4f} | Force X: {measured_force_x:.2f}N | Count: {consecutive_readings}/{REQUIRED_READINGS}")
        
        if abs(measured_force_x) >= FORCE_THRESHOLD:
            consecutive_readings += 1
        else:
            consecutive_readings = 0
            
        if consecutive_readings >= REQUIRED_READINGS:
            print(f"Contact detected! Force exceeded {FORCE_THRESHOLD}N for {REQUIRED_READINGS} consecutive readings.")
            rtde_c.stopL(2.0)
            contact_detected = True
            break
            
        if dist < 0.001:
            print("Reached target forward pose without detecting contact.")
            break
            
        time.sleep(0.01)  # ~100Hz sampling rate
        
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
        
        rtde_c.moveL(target_pose_left, slide_speed, slide_acceleration, True)
        
        while True:
            curr_pose = rtde_r.getActualTCPPose()
            dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_left[:3])))
            actual_forces = rtde_r.getActualTCPForce()
            print(f"Sliding... Dist to Target: {dist:.4f}m | Live Force: Fx={actual_forces[0]:.2f}N, Fy={actual_forces[1]:.2f}N, Fz={actual_forces[2]:.2f}N")
            if dist < 0.01:
                break
            time.sleep(0.1)
            
        rtde_c.waitForMotionComplete()
        print("Slide movement complete!")
        
        time.sleep(1)
        
        # -------------------------------------------------------------
        # BLOCK 8: Retraction Phase
        # Disables Force Mode and safely pulls the tool back 3 cm away from the wall.
        # -------------------------------------------------------------
        print("Moving back from the wall...")
        rtde_c.forceModeStop()
        retract_pose = list(rtde_r.getActualTCPPose())
        retract_pose[0] += 0.09  # Pull back 3 cm
        rtde_c.moveL(retract_pose, 0.05, 0.2)
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