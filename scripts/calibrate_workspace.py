#!/usr/bin/env python3
import os
import sys
import yaml
import time
import numpy as np

# Add root folder to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import rtde_control
    import rtde_receive
except ImportError:
    print("Error: The 'ur_rtde' library is not installed in the active environment.")
    sys.exit(1)

# Default Robot IP - match physical UR5e controller IP
ROBOT_IP = "192.168.57.101"
OUTPUT_PATH = "config/calibration.yaml"

def rotation_vector_to_matrix(rv: np.ndarray) -> np.ndarray:
    """
    Converts a 3D rotation vector (axis-angle) to a 3x3 rotation matrix
    using Rodrigues' rotation formula.
    """
    angle = np.linalg.norm(rv)
    if angle < 1e-6:
        return np.eye(3)
    k = rv / angle
    K = np.array([
        [0.0, -k[2], k[1]],
        [k[2], 0.0, -k[0]],
        [-k[1], k[0], 0.0]
    ])
    R = np.eye(3) + np.sin(angle) * K + (1.0 - np.cos(angle)) * np.dot(K, K)
    return R

def probe_surface_point(rtde_c, rtde_r, p_start_pose: list, target_force: float = 2.0, speed: float = 0.002, accel: float = 0.02) -> list:
    """
    Moves the tool tip slowly along the tool's local Z-axis (pointing forward)
    until contact force along that axis exceeds target_force.
    Returns the exact contact pose [X, Y, Z, Rx, Ry, Rz].
    
    Fixes:
      - 1: Reduced target_force (2.0N) and speed (2mm/s) to prevent rigid collision stops.
      - 2: Probes along tool Z-axis (pen direction) instead of hardcoded base axes.
    """
    # 1. Zero the force sensor
    print("Zeroing force/torque sensor...")
    rtde_c.zeroFtSensor()
    time.sleep(0.5)
    
    # 2. Compute tool Z-axis vector in base coordinates
    # p_start_pose[3:] contains the axis-angle rotation vector [Rx, Ry, Rz]
    rv = np.array(p_start_pose[3:])
    R = rotation_vector_to_matrix(rv)
    
    # The third column of R is the tool's Z unit vector (pointing out of the tool/pen tip)
    uz_tool = R[:, 2]
    
    # Construct base coordinate velocity vector (moving forward along tool Z)
    velocity = list(uz_tool * speed) + [0.0, 0.0, 0.0]
    
    # 3. Begin probing motion
    print(f"Probing along tool Z-axis (velocity unit vector: {[round(c, 4) for c in uz_tool]} at {speed * 1000:.1f} mm/s)...")
    rtde_c.speedL(velocity, accel)
    
    contact_pose = None
    start_time = time.time()
    
    try:
        while True:
            # Safety timeout
            if time.time() - start_time > 15.0:
                print("❌ Probing timeout reached (15s) without detecting contact.")
                break
                
            # Read actual force vector in base coordinates
            forces_base = np.array(rtde_r.getActualTCPForce()[:3])
            
            # Project base forces onto the tool Z axis to get force along the pen barrel
            current_force = abs(np.dot(forces_base, uz_tool))
            
            # Contact confirmation
            if current_force >= target_force:
                rtde_c.speedStop()
                time.sleep(0.2) # Settle time
                contact_pose = rtde_r.getActualTCPPose()
                print(f"✅ Contact confirmed! Force along tool Z: {current_force:.2f} N. Pose: {[round(c, 4) for c in contact_pose[:3]]}")
                break
                
            time.sleep(0.005) # 200 Hz monitoring loop
    except Exception as e:
        print(f"❌ Error during probing search: {e}")
    finally:
        rtde_c.speedStop()
        
    return contact_pose

def main():
    print("=" * 60)
    # Tri-State Robotics Division
    print("PORTRAITRON 3000 - SEMI-AUTOMATED 3-POINT PLANE CALIBRATION")
    print("=" * 60)
    
    # Ensure config directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    print(f"Connecting to UR5e at IP: {ROBOT_IP}...")
    try:
        rtde_c = rtde_control.RTDEControlInterface(ROBOT_IP)
        rtde_r = rtde_receive.RTDEReceiveInterface(ROBOT_IP)
        print("✅ Sockets connected successfully.")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
        
    try:
        print("\nINSTRUCTIONS:")
        print("1. Use the teach pendant to jog the robot arm.")
        print("2. Place the pen tip hovering approximately 1.5 cm normal to the")
        print("   Bottom-Left corner of your A4 drawing sheet (this is hover pose P0).")
        print("3. Ensure the tool is oriented perpendicular to the paper surface.")
        
        input("\nPress [ENTER] when ready to capture P0...")
        p0_joints = rtde_r.getActualQ()
        p0_pose = rtde_r.getActualTCPPose()
        print(f"Recorded P0 Pose: {[round(c, 4) for c in p0_pose[:3]]}")
        print(f"Recorded P0 Joints: {[round(c, 4) for c in p0_joints]}")
        
        # 1. Probing P1 (Bottom-Left Surface)
        print("\n[STEP 1/3] Probing Bottom-Left Surface (P1)...")
        # Probing forward from current P0 hover along tool Z axis
        p1_surface = probe_surface_point(rtde_c, rtde_r, p_start_pose=p0_pose)
        if not p1_surface:
            print("❌ Probing P1 failed. Aborting calibration.")
            return
            
        # Retract back to hover pose P0 using moveJ to resolve joint configurations safely
        print("Retracting to P0 hover...")
        rtde_c.moveJ(p0_pose, 0.2, 0.1)
        time.sleep(0.5)
        
        # 2. Probing P2 (Bottom-Right Surface)
        print("\n[STEP 2/3] Moving to Bottom-Right and probing (P2)...")
        # Shift 19 cm to the right (+Y direction in base frame)
        p2_hover = list(p0_pose)
        p2_hover[1] += 0.19
        
        # Move to P2 hover using joint-space moveJ to prevent linear singularity errors
        print("Moving to P2 hover...")
        rtde_c.moveJ(p2_hover, 0.2, 0.1)
        time.sleep(0.5)
        
        p2_surface = probe_surface_point(rtde_c, rtde_r, p_start_pose=p2_hover)
        if not p2_surface:
            print("❌ Probing P2 failed. Aborting calibration.")
            return
            
        print("Retracting to P2 hover...")
        rtde_c.moveJ(p2_hover, 0.2, 0.1)
        time.sleep(0.5)
        
        # 3. Probing P3 (Top-Left Surface)
        print("\n[STEP 3/3] Moving to Top-Left and probing (P3)...")
        # Return to P0, then shift 27 cm up (+Z direction in base frame)
        print("Returning to P0 hover...")
        rtde_c.moveJ(p0_pose, 0.2, 0.1)
        time.sleep(0.5)
        
        p3_hover = list(p0_pose)
        p3_hover[2] += 0.27
        
        print("Moving to P3 hover...")
        rtde_c.moveJ(p3_hover, 0.2, 0.1)
        time.sleep(0.5)
        
        p3_surface = probe_surface_point(rtde_c, rtde_r, p_start_pose=p3_hover)
        if not p3_surface:
            print("❌ Probing P3 failed. Aborting calibration.")
            return
            
        print("Retracting to P3 hover...")
        rtde_c.moveJ(p3_hover, 0.2, 0.1)
        time.sleep(0.5)
        
        # Return to safety start pose
        print("\nCalibration probing completed. Returning to starting hover P0...")
        rtde_c.moveJ(p0_pose, 0.2, 0.1)
        
        # Write calibration configuration to yaml
        cal_data = {
            "p0_joints": [float(q) for q in p0_joints],
            "p0_pose": [float(p) for p in p0_pose],
            "p1": [float(p) for p in p1_surface],
            "p2": [float(p) for p in p2_surface],
            "p3": [float(p) for p in p3_surface],
            "width": 0.19,
            "height": 0.27,
            "# spring_compression_depth": 0.000 # Disabled: no spring available
        }
        
        with open(OUTPUT_PATH, "w") as f:
            yaml.safe_dump(cal_data, f, default_flow_style=False)
            
        print(f"\n🎉 SUCCESS: Workspace calibration saved to {OUTPUT_PATH}!")
        
    finally:
        # Safe disconnect
        rtde_c.disconnect()
        rtde_r.disconnect()
        print("Calibration script finished.")

if __name__ == "__main__":
    main()
