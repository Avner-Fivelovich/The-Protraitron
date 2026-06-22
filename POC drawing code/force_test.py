'''
This code is me playing around with the force mode
with a horizontal line rather than a circle
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
    FORWARD_FORCE = -0.2      # Force in Newtons (0.5 N)

    # --- Activate force mode ---
    # --- Tool Frame Force Configurations ---
    tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    tool_selection_vector = [1, 0, 0, 0, 0, 0] # Compliance ONLY on Z axis
    tool_wrench = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] # Target force on Z
    FORCE_TYPE_TOOL = 2
    rtde_c.forceModeSetDamping(0.1)      # High damping slows down sudden spikes
    #rtde_c.forceModeSetGainScaling(0.4)   # Lower gain stops the loop from overreacting
    limits = [0.005, 0.05, 0.05, 0.2, 0.2, 0.2]
    rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, FORCE_TYPE_TOOL, limits)
    print("Force mode activated, waiting for force to stabilize...")
    time.sleep(5) # Allow some time for force mode to stabilize before moving
    print("Force stabilized. Executing smooth circle via native controller path utility...")
    print("Reading current robot position...")
    # getActualTCPPose() returns [X, Y, Z, Rx, Ry, Rz]
    # X, Y, Z are in meters. Rx, Ry, Rz are rotation vectors in radians.
    start_pose = rtde_r.getActualTCPPose()
    print(f"Start Pose: {start_pose}")
    # Start Pose: [-0.8527237664755836, 0.1571307208270486, 0.4876231179134238, 2.15051266415504, -0.02765766917600443, -2.2237520239915205]

    # Create the target pose for a horizontal line
    # We copy the exact current position, height (Z), and tilt (Rx, Ry, Rz)
    target_pose = list(start_pose)
    
    # Modify ONLY the Y-coordinate to slide horizontally to the side
    # Moving +10 centimeters (0.10 meters) to the robot's left
    target_pose[1] += 0.10
    
    print(f"Target Pose: {target_pose}")
    print("Moving gripper in a perfect horizontal line...")
    
    # Parameters for moveL: (pose, speed, acceleration, asynchronous)
    # Keeping speeds safe (0.05 m/s = 5 cm per second)
    speed = 0.05
    acceleration = 0.2
    
    # Execute linear movement
    rtde_c.moveL(target_pose, speed, acceleration)
    print("Horizontal movement complete!")
    
    time.sleep(1)

    # Move back from paper
    print("Moving back from paper...")
    rtde_c.forceModeStop()
    target_pose[0] += 0.03
    rtde_c.moveL(target_pose, speed, acceleration)

finally:
    # Safely disconnect
    rtde_c.stopL(2.0)
    rtde_c.disconnect()
    rtde_r.disconnect()
    print("Disconnected safely.")