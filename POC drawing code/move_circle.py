'''
This code moves the robot in a circle or part of a circel using moveL
without attempting to maintain a constant force
top_left, top_right, bottom_right are the corners of the paper
I mean to use them to calculate the center of the page and move there first before drawing the circle
but have not yet implemented that part
'''

import math
import time
from rtde_control import RTDEControlInterface, Path, PathEntry
from rtde_receive import RTDEReceiveInterface

ROBOT_IP = "192.168.57.101"

# 

# Initialize interfaces
rtde_c = RTDEControlInterface(ROBOT_IP)
rtde_r = RTDEReceiveInterface(ROBOT_IP)

# left top edge of paper: [-0.8046515373512508, 0.16976353854942355, 0.5326811488473898, 1.9314077101103273, -0.04856983675111516, -1.9931750803028117]
top_left = [-0.8046515373512508, 0.16976353854942355, 0.5326811488473898, 1.9314077101103273, -0.04856983675111516, -1.9931750803028117]
top_right = [-0.806821593059755, 0.33901158746792137, 0.5388440153790324, -2.235421105543309, 0.10743113314972795, 2.186535600589356]
bottom_right =[-0.8087181837665622, 0.3375989149987425, 0.2473693146296782, 2.16978420893891, -0.20866730000699552, -2.0706793288220995]

page_center = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
page_center[1] = (top_left[1] + bottom_right[1]) / 2
page_center[2] = (top_left[2] + bottom_right[2]) / 2

# move to the center of the page first
rtde_c.moveL(page_center, 0.1, 0.2)

try:
    print("Reading center position...")
    # Get current pose to use as our circle's center: [X, Y, Z, Rx, Ry, Rz]
    center_pose = rtde_r.getActualTCPPose()
    
    # --- Circle Parameters ---
    RADIUS = 0.03       # 5 centimeters radius (0.05 meters)
    ANGLE = 180         # Angle of the circle to execute in degrees (180 for a half circle, 360 for a full circle)
    NUM_STEPS = 100     # Number of waypoints to divide the circle into
    SPEED = 0.1         # Linear speed (m/s)
    ACCELERATION = 0.2  # Linear acceleration (m/s^2)
    BLEND = 0.002       # Blend radius in meters (allows smooth blending between waypoints)

    print(f"Generating waypoints for a circle of radius {RADIUS*100} cm on the Y-Z plane...")
    
    raw_waypoints = []
    for i in range(NUM_STEPS + 1):
        # Calculate angle theta from 0 to 2*pi
        theta = (math.radians(ANGLE) * i) / NUM_STEPS
        #theta = (2.0 * math.pi * i) / NUM_STEPS
        
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

    # --- Execute the path sequence seamlessly ---
    print("Executing smooth circle via native controller path utility...")
    rtde_c.movePath(circle_path, False)
    print("Circle complete!")

    # --- Move back to starting position ---
    print("Moving back to center position...")
    rtde_c.moveL(center_pose, SPEED, ACCELERATION)
    print("Returned to center position.")

finally:
    # Safely disconnect
    rtde_c.stopL(2.0)
    rtde_c.disconnect()
    rtde_r.disconnect()
    print("Disconnected safely.")