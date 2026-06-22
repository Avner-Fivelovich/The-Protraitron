'''
This was also straight line testing, but I've since used this script just to print position
'''

from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface
import time

ROBOT_IP = "192.168.57.101"  # Adjust if using your other IP

# Initialize both Control and Receive interfaces
rtde_c = RTDEControlInterface(ROBOT_IP)
rtde_r = RTDEReceiveInterface(ROBOT_IP)

try:
    print("Reading current robot position...")
    # getActualTCPPose() returns [X, Y, Z, Rx, Ry, Rz]
    # X, Y, Z are in meters. Rx, Ry, Rz are rotation vectors in radians.
    start_pose = rtde_r.getActualTCPPose()
    print(f"Start Pose: {start_pose}")
    # Start Pose: [-0.8527237664755836, 0.1571307208270486, 0.4876231179134238, 2.15051266415504, -0.02765766917600443, -2.2237520239915205]

    # Create the target pose for a horizontal line
    # We copy the exact current position, height (Z), and tilt (Rx, Ry, Rz)
    # target_pose = list(start_pose)
    
    # # Modify ONLY the Y-coordinate to slide horizontally to the side
    # # Moving +10 centimeters (0.10 meters) to the robot's left
    # target_pose[1] += 0.05
    
    # print(f"Target Pose: {target_pose}")
    # print("Moving gripper in a perfect horizontal line...")
    
    # # Parameters for moveL: (pose, speed, acceleration, asynchronous)
    # # Keeping speeds safe (0.05 m/s = 5 cm per second)
    # speed = 0.05
    # acceleration = 0.2
    
    # # Execute linear movement
    # rtde_c.moveL(target_pose, speed, acceleration)
    # print("Horizontal movement complete!")
    
    # time.sleep(1)
    
    # # Optional: Move backward along the exact same horizontal line
    # print("Returning to start position along the same line...")
    # rtde_c.moveL(start_pose, speed, acceleration)
    # print("Return complete.")

finally:
    # Always cleanly close communication ports
    rtde_c.stopL(2.0)
    rtde_c.disconnect()
    rtde_r.disconnect()
    print("Disconnected safely.")

# import time
# from rtde_control import RTDEControlInterface
# from rtde_receive import RTDEReceiveInterface

# # Configuration
# ROBOT_IP = "192.168.57.101"

# print(f"Connecting to robot at {ROBOT_IP}...")
# try:
#     rtde_c = RTDEControlInterface(ROBOT_IP)
#     rtde_r = RTDEReceiveInterface(ROBOT_IP)
#     print("Connected successfully!")

#     # 1. Get the current TCP Pose
#     current_pose = rtde_r.getActualTCPPose()
#     print(f"Starting Position: {current_pose}")

    
# # ==========================================
#     # FORCE MODE CONFIGURATION (Z-AXIS INTO WALL)
#     # ==========================================
#     task_frame = [0, 0, 0, 0, 0, 0] 
    
#     # Selection Vector: [X, Y, Z, Rx, Ry, Rz]
#     # Make Z compliant (1), and X, Y rigid (0)
#     selection_vector = [0, 0, 1, 0, 0, 0] 
    
#     # Wrench: [Fx, Fy, Fz, Tx, Ty, Tz]
#     # Apply 2 Newtons of force in the Z direction
#     wrench = [0.0, 0.0, 2.0, 0.0, 0.0, 0.0] 
    
#     force_type = 2 
    
#     # Limits: Restrict the compliant Z-axis speed to 0.05 m/s to prevent punching
#     limits = [0.1, 0.1, 0.05, 0.5, 0.5, 0.5]

#     print("Activating Force Mode... Watch for contact!")
#     # Turn on Force Mode. The robot will now start pushing forward in X.
# # To this:
#     rtde_c.forceMode(task_frame, selection_vector, wrench, force_type, limits)    
#     # Give the arm 1 second to press against the wall and stabilize the 10N pressure
#     time.sleep(1) 

#     # ==========================================
#     # LINEAR MOVEMENT (DRAWING)
#     # ==========================================
#     target_pose = list(current_pose)
#     # Move 15cm along the Y-axis (sideways) to draw the line
#     target_pose[1] += 0.15 
    
#     linear_speed = 0.05       # 5 cm/s
#     linear_acceleration = 0.02

#     print(f"Drawing line across the wall...")
#     # The robot executes this movement while STILL applying the 10N force in X
#     rtde_c.moveL(target_pose, linear_speed, linear_acceleration, False)
    
#     print("Stroke completed!")

# except Exception as e:
#     print(f"An error occurred: {e}")

# finally:
#     # ==========================================
#     # CLEANUP (CRITICAL SAFETY STEP)
#     # ==========================================
#     if 'rtde_c' in locals():
#         print("Stopping Force Mode...")
#         # You MUST turn off force mode, otherwise the robot keeps pushing forever
#         rtde_c.forceModeStop()
        
#         # Optional: Pull the pen straight back from the wall (negative X) by 2cm
#         print("Retracting from wall...")
#         retract_pose = rtde_r.getActualTCPPose()
#         retract_pose[0] -= 0.02
#         rtde_c.moveL(retract_pose, 0.05, 0.05, False)
        
#         rtde_c.disconnect()
#     print("Disconnected safely.")