#!/usr/bin/env python3
"""
scripts/test_ur5e_connection.py
A basic standalone python script to verify Ethernet socket connectivity, 
read real-time joint positions, TCP poses, and F/T sensor telemetry from a UR5e.
"""
import sys
import time

try:
    import rtde_control
    import rtde_receive
except ImportError:
    print("Error: The 'ur_rtde' library is not installed in the active environment.")
    print("Please install it by running: pip install ur_rtde")
    sys.exit(1)

# Default Robot IP - Edit this to match your physical UR5e controller IP
# (Standard default factory IP is often 192.168.1.100, but in lab setups it is customized)
ROBOT_IP = "192.168.56.101"

def print_troubleshooting_guide(ip):
    """Prints troubleshooting advice in case of connection failure."""
    print("\n" + "="*50)
    print("CONNECTION TROUBLESHOOTING GUIDE")
    print("="*50)
    print(f"1. Ping Test: Open a terminal and run 'ping {ip}' to check physical link.")
    print("2. IP Configuration: Ensure your host PC is on the same subnet.")
    print("   - Host IP example: 192.168.56.10 (Subnet mask: 255.255.255.0)")
    print("3. Ethernet Cable: Verify that the cable is plugged firmly into the")
    print("   robot controller cabinet block and your computer/switch.")
    print("4. Polyscope Settings: On the Teach Pendant:")
    print("   - Check that 'Remote Control' mode is active in the top-right header.")
    print("   - Verify Ethernet settings under Settings > System > Network.")
    print("="*50)

def main():
    print("="*60)
    print("PORTRAITRON 3000 - UR5e RTDE CONNECTION DIAGNOSTIC")
    print("="*60)
    print(f"Targeting Robot IP: {ROBOT_IP}")
    print("Attempting to connect to Port 30003 (Control) & Port 30004 (Receive)...")

    rtde_c = None
    rtde_r = None

    try:
        # Step 1: Establish Receive telemetry connection (Port 30004)
        print("\nConnecting to rtde_receive telemetry interface...")
        rtde_r = rtde_receive.RTDEReceiveInterface(ROBOT_IP)
        print("✅ Receive interface connected successfully!")

        # Step 2: Establish Control write connection (Port 30003)
        print("Connecting to rtde_control write interface...")
        rtde_c = rtde_control.RTDEControlInterface(ROBOT_IP)
        print("✅ Control interface connected successfully!")

        print("\n" + "-"*40)
        print("REAL-TIME ROBOT TELEMETRY READINGS")
        print("-"*40)

        # Step 3: Read and print Safety Status
        is_emergency_stopped = rtde_r.isEmergencyStopped()
        is_protective_stopped = rtde_r.isProtectiveStopped()
        is_connected = rtde_c.isConnected()

        print(f"RTDE Control Connected : {is_connected}")
        print(f"Emergency Stop Active  : {is_emergency_stopped}")
        print(f"Protective Stop Active : {is_protective_stopped}")

        if is_emergency_stopped or is_protective_stopped:
            print("\n⚠️ WARNING: The robot safety system is in a stopped state.")
            print("Please release E-stops or unlock Protective Stops via Polyscope.")

        # Step 4: Read actual joint coordinates (in radians and convert to degrees)
        q_rad = rtde_r.getActualQ()
        q_deg = [round(np_rad * 180.0 / 3.14159265, 2) for np_rad in q_rad]
        print(f"Actual Joint Angles (rad): {[round(x, 4) for x in q_rad]}")
        print(f"Actual Joint Angles (deg): {q_deg}")

        # Step 5: Read actual Tool Center Point (TCP) Pose
        # Pose is: [X, Y, Z, Rx, Ry, Rz] where positions are in meters
        tcp_pose = rtde_r.getActualTCPPose()
        print(f"Actual TCP Pose (meters) : {[round(x, 4) for x in tcp_pose[:3]]} (XYZ)")
        print(f"Actual TCP Pose (mm)     : {[round(x * 1000.0, 1) for x in tcp_pose[:3]]} (XYZ)")
        print(f"Actual TCP Orientation   : {[round(x, 4) for x in tcp_pose[3:]]} (Rx, Ry, Rz rotation vector)")

        # Step 6: Read raw TCP force/torque sensor readings (Base coordinate frame)
        tcp_forces = rtde_r.getActualTCPForce()
        print(f"Raw F/T Sensor forces (N): {[round(x, 2) for x in tcp_forces[:3]]} (Fx, Fy, Fz)")
        print(f"Raw F/T Sensor torque(Nm): {[round(x, 3) for x in tcp_forces[3:]]} (Mx, My, Mz)")

        print("\n🎉 DIAGNOSTIC TEST COMPLETED SUCCESSFULLY!")
        print("Both control and telemetry channels are fully operational.")

    except Exception as e:
        print(f"\n❌ ERROR: Failed to establish RTDE communication channel.")
        print(f"Error Details: {e}")
        print_troubleshooting_guide(ROBOT_IP)
    
    finally:
        # Step 7: Clean shutdown of sockets
        print("\nShutting down sockets...")
        if rtde_c:
            try:
                rtde_c.disconnect()
                print("Disconnected rtde_control successfully.")
            except Exception:
                pass
        if rtde_r:
            try:
                rtde_r.disconnect()
                print("Disconnected rtde_receive successfully.")
            except Exception:
                pass
        print("Connection diagnostic closed.")

if __name__ == '__main__':
    main()
