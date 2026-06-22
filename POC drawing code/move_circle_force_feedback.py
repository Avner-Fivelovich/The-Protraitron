'''
This code is an attempt to draw a circle or part of a circle using
forceMode
servol
feedback control on target force
'''

import math
import time
from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface

ROBOT_IP = "192.168.57.101"

# Initialize interfaces
rtde_c = RTDEControlInterface(ROBOT_IP)
rtde_r = RTDEReceiveInterface(ROBOT_IP)

try:
    print("Reading center position...")
    center_pose = rtde_r.getActualTCPPose()
    
    # --- Circle Parameters ---
    RADIUS = 0.03        # 3 centimeters radius (0.03 meters)
    ANGLE = 180          # Angle of the circle to execute in degrees
    SPEED = 0.1         
    ACCELERATION = 0.2  
    
    # Real-time streaming parameters (500Hz loop for e-Series)
    DT = 0.002           
    TOTAL_TIME = 5.0     # Take 5 seconds to draw the half-circle
    NUM_STEPS = int(TOTAL_TIME / DT)

    # --- Force Mode Configurations (Base Relative, Pushing on X) ---
    TARGET_FORCE = 0.5   # Target force in Newtons (0.5 N)
    FORCE_TYPE_BASE = 2
    base_selection_vector = [1, 0, 0, 0, 0, 0]    # Compliance ONLY on global Base X axis
    base_wrench = [TARGET_FORCE, 0.0, 0.0, 0.0, 0.0, 0.0] # Target force profile
    limits = [0.005, 0.05, 0.05, 0.2, 0.2, 0.2]   # Controlled slow approach

    # --- Pre-calculate positions ---
    print("Generating real-time trajectory...")
    raw_waypoints = []
    for i in range(NUM_STEPS + 1):
        theta = (math.radians(ANGLE) * i) / NUM_STEPS
        wp = list(center_pose)
        wp[1] = center_pose[1] + RADIUS * math.cos(theta)
        wp[2] = center_pose[2] + RADIUS * math.sin(theta)
        raw_waypoints.append(wp)

    # --- Move to the starting point smoothly while still in rigid control ---
    print("Moving to starting waypoint (Hover position)...")
    first_point_pose = raw_waypoints[0]
    rtde_c.moveL(first_point_pose, SPEED, ACCELERATION)
    time.sleep(1)

    # --- Pre-engagement Sensor Calibration ---
    print("Zeroing FT sensor right above the paper...")
    rtde_c.zeroFtSensor()
    time.sleep(0.5)

    # Set gain scaling and damping once before entering the loop
    #rtde_c.forceModeSetGainScaling(0.2)
    #rtde_c.forceModeSetDamping(1.0)

    # =========================================================================
    # --- Loop until contact force is felt ---
    # =========================================================================
    CONTACT_FORCE_THRESHOLD = 0.07  # Stop approach when threshold force is felt
    MAX_APPROACH_TIME = 60.0        # Safety timeout in seconds
    
    print(f"Activating Force Mode. Approaching paper along Base X...")
    
    start_time = time.time()
    measured_force_x = 0.0
    consecutive_hits = 0  # Debounce counter to avoid instant noise triggers

    while True:
        # 1. Calculate elapsed time accurately
        elapsed_time = time.time() - start_time
        
        # 2. Check safety timeout
        if elapsed_time > MAX_APPROACH_TIME:
            raise TimeoutError(f"Robot failed to detect paper within timeout. Ran for {elapsed_time:.2f}s")

        # 3. Apply Force Mode and Servo commands
        base_task_frame = [first_point_pose[0], first_point_pose[1], first_point_pose[2], 0.0, 0.0, 0.0]
        rtde_c.forceMode(base_task_frame, base_selection_vector, base_wrench, FORCE_TYPE_BASE, limits)
        rtde_c.servoL(first_point_pose, 0.0, 0.0, DT, 0.03, 2000)
        
        # 4. READ THE SENSOR
        actual_forces = rtde_r.getActualTCPForce()
        measured_force_x = actual_forces[0]
        
        # DEBUG PRINT: Watch what the robot is actually seeing in real-time
        # (Printed every ~20 steps so it doesn't flood your terminal)
        if int(elapsed_time * 500) % 20 == 0:
            print(f"Time: {elapsed_time:.2f}s | Live Base X Force: {abs(measured_force_x):.2f} N")

        # 5. DEBOUNCE CHECK: Must read above threshold for 5 consecutive frames (10ms)
        if abs(measured_force_x) <= CONTACT_FORCE_THRESHOLD:
            consecutive_hits += 1
            if consecutive_hits >= 5:
                print(f"Stable contact confirmed at {abs(measured_force_x):.2f}N!")
                break
        else:
            consecutive_hits = 0 # Reset if it was just a temporary spike/noise

        # 6. Crucial pacing step at the very bottom of the loop execution block
        time.sleep(DT)

    print(f"Paper surface contacted safely! Proceeding to drawing sequence...")

    # =========================================================================
    # --- EXECUTION PHASE (Drawing the circle under constant force) ---
    # =========================================================================
    print("Executing smooth circle while maintaining force compliance...")
    for wp in raw_waypoints:
        actual_forces = rtde_r.getActualTCPForce()
        measured_force_x = actual_forces[0]
        if measured_force_x > 0.7:
            base_wrench[0] -= 0.1
            print(f"Force exceeded target! Adjusting wrench to {base_wrench[0]:.2f} N")
        elif measured_force_x < 0.3:
            base_wrench[0] += 0.1
            print(f"Force below target! Adjusting wrench to {base_wrench[0]:.2f} N")
        base_task_frame = [wp[0], wp[1], wp[2], 0.0, 0.0, 0.0]
        
        rtde_c.forceMode(base_task_frame, base_selection_vector, base_wrench, FORCE_TYPE_BASE, limits)
        rtde_c.servoL(wp, 0.0, 0.0, DT, 0.03, 2000)
        time.sleep(DT)

    print("Circle complete!")

    # =========================================================================
    # --- CLEANUP AND RETRACTION ---
    # =========================================================================
    print("Stopping real-time stream and force mode...")
    rtde_c.servoStop() 
    rtde_c.forceModeStop()
    time.sleep(0.2) 

    print("Retracting pen away from paper...")
    current_actual_pose = rtde_r.getActualTCPPose()
    
    retract_pose = list(current_actual_pose)
    retract_pose[0] += 0.04  # Pull back 4 cm clear of the paper
    
    rtde_c.moveL(retract_pose, 0.05, 0.1)
    print("Pen successfully lifted.")

    print("Moving back to original center position...")
    rtde_c.moveL(center_pose, SPEED, ACCELERATION)
    print("Returned to center position successfully.")

finally:
    # Safely disconnect
    rtde_c.forceModeStop()
    rtde_c.stopL(2.0)
    rtde_c.disconnect()
    rtde_r.disconnect()
    print("Disconnected safely.")