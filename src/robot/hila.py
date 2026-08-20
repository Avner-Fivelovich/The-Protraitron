from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface
import time

ROBOT_IP = "192.168.57.100"  # Replace with your UR5e IP

try:
    print(f"Connecting to RTDE interfaces at {ROBOT_IP}...")
    rtde_r = RTDEReceiveInterface(ROBOT_IP)
    rtde_c = RTDEControlInterface(ROBOT_IP)

    # Read current joint angles in radians
    actual_q = rtde_r.getActualQ()
    print(f"Current Joint Angles (rad): {actual_q}")

    # Read TCP pose [X, Y, Z, Rx, Ry, Rz] in meters/radians
    actual_tcp = rtde_r.getActualTCPPose()
    print(f"Current TCP Pose (m, rad): {actual_tcp}")

    # Small, slow movement on Joint 6 (Wrist 3)
    target_q = list(actual_q)
    target_q[5] += 0.1  # Rotate ~5.7 degrees

    print("Executing safe joint motion...")
    rtde_c.moveJ(target_q, speed=0.2, acceleration=0.5)
    print("Motion complete.")

    # Stop script on controller
    rtde_c.stopScript()

except Exception as e:
    print(f"Failed to communicate via RTDE: {e}")