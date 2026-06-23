'''
Compliant Circular Arc Script
Approaches a surface, detects contact, and draws an arc of a user-defined angle.
'''

import math
import time
from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface

# -------------------------------------------------------------
# BLOCK 0: User Input (Gathered before robot moves)
# -------------------------------------------------------------
try:
    user_angle_input = float(input("Enter the angle for the circular arc (in degrees, e.g., 90, 180): "))
except ValueError:
    print("Invalid input. Defaulting to 90 degrees.")
    user_angle_input = 90.0

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

    FORWARD_FORCE = 0.5     # Force in Newtons for sliding compliance
    
    print("Zeroing FT sensor...")
    rtde_c.zeroFtSensor()
    time.sleep(0.5)

    print("Reading current robot position...")
    start_pose = rtde_r.getActualTCPPose()

    # -------------------------------------------------------------
    # BLOCK 5: Wall Approach (X-Axis)
    # -------------------------------------------------------------
    target_pose_forward = list(start_pose)
    target_pose_forward[0] -= 0.15  # Max search distance of 15 cm
    
    print("Moving slowly forward to the wall along X axis...")
    approach_speed = 0.01  
    approach_acceleration = 0.1
    
    rtde_c.moveL(target_pose_forward, approach_speed, approach_acceleration, True)
    
    consecutive_readings = 0
    REQUIRED_READINGS = 2
    FORCE_THRESHOLD = 1.0  
    contact_detected = False
    
    while True:
        curr_pose = rtde_r.getActualTCPPose()
        dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], target_pose_forward[:3])))
        
        actual_forces = rtde_r.getActualTCPForce()
        measured_force_x = actual_forces[0]
        
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
        
        # Activate force mode to maintain compliance
        tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        tool_selection_vector = [1, 0, 0, 0, 0, 0] 
        tool_wrench = [FORWARD_FORCE, 0.0, 0.0, 0.0, 0.0, 0.0]
        FORCE_TYPE_TOOL = 2
        
        # Depending on UR_RTDE version, you might need to comment this out if it throws an error
        rtde_c.forceModeSetDamping(0.1) 
        
        limits = [0.005, 0.05, 0.05, 0.2, 0.2, 0.2]
        
        rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, FORCE_TYPE_TOOL, limits)
        print("Force mode activated, waiting for force to stabilize...")
        
        time.sleep(2.0)
            
        # -------------------------------------------------------------
        # BLOCK 7: Compliant Circular Arc
        # Generates a blended path array based on the user's angle 
        # and executes it seamlessly under background force compliance.
        # -------------------------------------------------------------
        print(f"Generating circular arc for {user_angle_input} degrees...")
        
        RADIUS = 0.05         # 5 cm radius
        slide_speed = 0.02    # 2 cm/s
        slide_accel = 0.1
        blend_radius = 0.005  # 5 mm blend for smooth curves
        
        # Calculate the center of the circle so the arc starts perfectly at contact_pose
        # Starting angle is Pi/2 (90 deg) so the initial movement vector points exactly along -Y
        center_y = contact_pose[1]
        center_z = contact_pose[2] - RADIUS
        START_ANGLE = math.pi / 2 
        
        # Create a waypoint every ~10 degrees (minimum 5 steps to ensure smoothness)
        NUM_STEPS = max(int(abs(user_angle_input) / 10), 5)
        
        arc_waypoints = []
        
        for i in range(1, NUM_STEPS + 1):
            # Calculate the current angle in the sweep
            sweep_fraction = i / NUM_STEPS
            theta = START_ANGLE + math.radians(user_angle_input * sweep_fraction)
            
            wp = list(contact_pose)
            wp[1] = center_y + RADIUS * math.cos(theta)
            wp[2] = center_z + RADIUS * math.sin(theta)
            
            # UR controller expects: [X, Y, Z, Rx, Ry, Rz, speed, accel, blend]
            # The final point must have a blend radius of 0.0 to stop cleanly
            current_blend = blend_radius if i < NUM_STEPS else 0.0
            wp.extend([slide_speed, slide_accel, current_blend])
            
            arc_waypoints.append(wp)
            
        print("Executing arc under force compliance...")
        
        # Execute the blended path asynchronously so we can monitor forces in the loop
        rtde_c.moveL(arc_waypoints, True)
        
        # We track progress by looking at the distance to the very last waypoint
        final_wp = arc_waypoints[-1][:6] 
        
        while True:
            curr_pose = rtde_r.getActualTCPPose()
            dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr_pose[:3], final_wp[:3])))
            
            actual_forces = rtde_r.getActualTCPForce()
            print(f"Drawing Arc... Dist to End: {dist:.4f}m | Live Force: Fx={actual_forces[0]:.2f}N")
            
            # Break loop when we are within 1 cm of the final destination
            if dist < 0.01:
                break
            time.sleep(0.1)
            
        rtde_c.waitForMotionComplete()
        print("Arc movement complete!")
        
        time.sleep(1)
        
        # -------------------------------------------------------------
        # BLOCK 8: Retraction Phase
        # -------------------------------------------------------------
        print("Moving back from the wall...")
        rtde_c.forceModeStop()
        retract_pose = list(rtde_r.getActualTCPPose())
        retract_pose[0] += 0.09  # Pull back
        rtde_c.moveL(retract_pose, 0.05, 0.2)
        print("Retraction complete.")
    else:
        print("Aborting drawing motion since contact was not detected.")

finally:
    # -------------------------------------------------------------
    # BLOCK 9: Safe Disconnect Cleanup
    # -------------------------------------------------------------
    print("Initiating safety disconnect sequence...")
    if rtde_c is not None:
        try:
            rtde_c.forceModeStop()
            rtde_c.stopL(2.0)
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