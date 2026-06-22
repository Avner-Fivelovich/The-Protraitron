#!/usr/bin/env python3
import os
import sys
import yaml
import time

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

def probe_surface_point(rtde_c, rtde_r, axis_idx: int, direction: int, target_force: float = 4.5, speed: float = 0.005, accel: float = 0.02) -> list:
    """
    Moves the tool tip slowly along specified axis until the TCP force exceeds target_force.
    Returns the exact contact pose [X, Y, Z, Rx, Ry, Rz].
    """
    # 1. Tare force sensor
    print("Zeroing force/torque sensor...")
    rtde_c.zeroFtSensor()
    time.sleep(0.5)
    
    # 2. Build velocity vector
    velocity = [0.0] * 6
    velocity[axis_idx] = direction * speed
    
    # 3. Begin probing motion
    print(f"Probing along axis {axis_idx} (velocity: {direction * speed:.4f} m/s)...")
    rtde_c.speedL(velocity, accel)
    
    contact_pose = None
    start_time = time.time()
    
    try:
        while True:
            # Safety timeout
            if time.time() - start_time > 15.0:
                print("❌ Probing timeout reached (15s) without detecting contact.")
                break
                
            # Read actual force vector
            forces = rtde_r.getActualTCPForce()
            current_force = abs(forces[axis_idx])
            
            # Contact confirmation
            if current_force >= target_force:
                rtde_c.speedStop()
                time.sleep(0.2) # Settle time
                contact_pose = rtde_r.getActualTCPPose()
                print(f"✅ Contact confirmed! Force: {current_force:.2f} N. Pose: {[round(c, 4) for c in contact_pose[:3]]}")
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
        # Probing in negative X direction (axis 0, direction -1)
        p1_surface = probe_surface_point(rtde_c, rtde_r, axis_idx=0, direction=-1)
        if not p1_surface:
            print("❌ Probing P1 failed. Aborting calibration.")
            return
            
        # Retract back to hover pose P0
        print("Retracting to P0 hover...")
        rtde_c.moveL(p0_pose, 0.05, 0.1)
        time.sleep(0.5)
        
        # 2. Probing P2 (Bottom-Right Surface)
        print("\n[STEP 2/3] Moving to Bottom-Right and probing (P2)...")
        # Shift 19 cm to the right (+Y direction in base frame)
        p2_hover = list(p0_pose)
        p2_hover[1] += 0.19
        
        print("Moving to P2 hover...")
        rtde_c.moveL(p2_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        p2_surface = probe_surface_point(rtde_c, rtde_r, axis_idx=0, direction=-1)
        if not p2_surface:
            print("❌ Probing P2 failed. Aborting calibration.")
            return
            
        print("Retracting to P2 hover...")
        rtde_c.moveL(p2_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        # 3. Probing P3 (Top-Left Surface)
        print("\n[STEP 3/3] Moving to Top-Left and probing (P3)...")
        # Return to P0, then shift 27 cm up (+Z direction in base frame)
        print("Returning to P0 hover...")
        rtde_c.moveL(p0_pose, 0.05, 0.1)
        time.sleep(0.5)
        
        p3_hover = list(p0_pose)
        p3_hover[2] += 0.27
        
        print("Moving to P3 hover...")
        rtde_c.moveL(p3_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        p3_surface = probe_surface_point(rtde_c, rtde_r, axis_idx=0, direction=-1)
        if not p3_surface:
            print("❌ Probing P3 failed. Aborting calibration.")
            return
            
        print("Retracting to P3 hover...")
        rtde_c.moveL(p3_hover, 0.05, 0.1)
        time.sleep(0.5)
        
        # Return to safety start pose
        print("\nCalibration probing completed. Returning to starting hover P0...")
        rtde_c.moveL(p0_pose, 0.05, 0.1)
        
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
