'''
This code is an attempt to draw a circle using
forceMode
movePath
'''

import math
import time
from rtde_control import RTDEControlInterface, Path, PathEntry
from rtde_receive import RTDEReceiveInterface

ROBOT_IP = "192.168.57.101"

# Initialize interfaces
rtde_c = RTDEControlInterface(ROBOT_IP)
rtde_r = RTDEReceiveInterface(ROBOT_IP)

try:
    print("Reading center position...")
    # Get current pose to use as our circle's center: [X, Y, Z, Rx, Ry, Rz]
    center_pose = rtde_r.getActualTCPPose()
    
    # --- Circle Parameters ---
    RADIUS = 0.03       # 5 centimeters radius (0.05 meters)
    NUM_STEPS = 100     # Number of waypoints to divide the circle into
    SPEED = 0.1         # Linear speed (m/s)
    ACCELERATION = 0.2  # Linear acceleration (m/s^2)
    BLEND = 0.002       # Blend radius in meters (allows smooth blending between waypoints)

    FORWARD_FORCE = 5.0         # Force in Newtons (0.5 N)

    print(f"Generating waypoints for a circle of radius {RADIUS*100} cm on the Y-Z plane...")
    
    raw_waypoints = []
    for i in range(NUM_STEPS + 1):
        # Calculate angle theta from 0 to 2*pi
        theta = (2.0 * math.pi * i) / NUM_STEPS
        
        # Copy the center pose structure
        wp = list(center_pose)
        
        # Apply circle math to Y (index 1) and Z (index 2)
        wp[1] = center_pose[1] + RADIUS * math.cos(theta)
        wp[2] = center_pose[2] + RADIUS * math.sin(theta)
        
        # Append waypoint along with individual speed, acceleration, and blend radius
        # The UR controller expects: [X, Y, Z, Rx, Ry, Rz, speed, acceleration, blend]
        wp.extend([SPEED, ACCELERATION, BLEND])
        raw_waypoints.append(wp)

    # --- INDENTATION FIXED: Initialize the path outside of the math generation loop ---
    circle_path = Path()

    print("Building native Path entries...")
    for point in raw_waypoints:
        # According to your error message, 'parameters' must be a single flat list of floats.
        # point already contains exactly: [X, Y, Z, Rx, Ry, Rz, speed, acceleration, blend]
        parameters_list = point 
        
        # Build PathEntry using the exact 3 supported arguments:
        # 1. move_type (PathEntry.MoveL)
        # 2. position_type (PathEntry.PositionTCP)
        # 3. parameters (list of floats)
        entry = PathEntry(
            PathEntry.eMoveType.MoveL, 
            PathEntry.ePositionType.PositionTcpPose, 
            parameters_list
        )
        
        circle_path.addEntry(entry)

    # --- Move to the starting point smoothly before launching the path ---
    print("Moving to starting waypoint...")
    first_point_pose = raw_waypoints[0][:6]
    rtde_c.moveL(first_point_pose, SPEED, ACCELERATION)
    time.sleep(1)

    
    # --- Activate force mode ---
    # --- Tool Frame Force Configurations ---
    tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    tool_selection_vector = [0, 0, 1, 0, 0, 0] # Compliance ONLY on Z axis
    tool_wrench = [FORWARD_FORCE, 0.0, 0.0, 0.0, 0.0, 0.0] # Target force on Z
    FORCE_TYPE_TOOL = 1
    limits = [0.05, 0.05, 0.05, 0.2, 0.2, 0.2]
    rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, FORCE_TYPE_TOOL, limits)
    print("Force mode activated, waiting for force to stabilize...")
    time.sleep(5) # Allow some time for force mode to stabilize before moving
    print("Force stabilized. Executing smooth circle via native controller path utility...")
    # --- Execute the path sequence seamlessly ---
    print("Executing smooth circle via native controller path utility...")
    rtde_c.movePath(circle_path, False)
    print("Circle complete!")

finally:
    # Safely disconnect
    rtde_c.stopL(2.0)
    rtde_c.disconnect()
    rtde_r.disconnect()
    print("Disconnected safely.")