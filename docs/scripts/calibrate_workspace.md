<style>
h1, h2, h3, h4, h5, h6 {
    font-family: 'Space Grotesk', sans-serif;
    text-transform: uppercase;
}
h1 {
    border-bottom: 2px solid #4a148c;
}
h2, h3 {
    border-bottom: 2px solid #26a69a;
}
body, p, li, table {
    font-family: 'Inter', sans-serif;
}
pre, code {
    font-family: 'JetBrains Mono', monospace;
    background-color: #0f0f10;
    color: #f8f8f2;
    padding: 2px 4px;
    border-radius: 4px;
}
pre code {
    padding: 0;
}
</style>

# WORKSPACE CALIBRATION SCRIPT

This document explains the purpose, usage, and inner workings of the `calibrate_workspace.py` script for the Portraitron 3000 robotic drawing workspace.

## PURPOSE

The `calibrate_workspace.py` script identifies the exact physical starting point (P1) and the hover position (P0) for the UR5e robot's end effector. It uses a manual teaching approach followed by an automated force-feedback probing routine to precisely detect the drawing surface.

## HOW TO USE

1. **Power and Connect**: Ensure the UR5e robot is powered on and connected. The script attempts to connect to the default robot IP: `192.168.57.101`.
2. **Execute the Script**: Run the script from the command line. You can optionally pass a tool configuration profile.
   ```bash
   python scripts/calibrate_workspace.py [config_name]
   ```
   *(If `config_name` is omitted, it defaults to `marker`)*
3. **Follow the Prompts**:
   * **Jog the Robot**: Use the UR teach pendant to maneuver the pen tip so it hovers approximately 1.5 cm normal to the **Bottom-Left** corner of the paper (with 1cm margins).
   * **Orient the Tool**: Ensure the pen is perpendicular to the paper surface.
   * **Capture P0**: Press Enter in the terminal to record this initial hover pose as `P0`.
4. **Automated Probing**: The robot will automatically probe downward to find the actual paper surface (`P1`) using force feedback.
5. **Retract**: After contact is made, it will retract 3 mm away from `P1` along the X-axis (`p0_pose_new[0] += 0.003`) to establish a safe, final `P0` hover position.

## CONFIGURATION FILES

The script interacts with the following configuration files:

### INPUT CONFIGURATIONS
* **`config/[config_name].yaml`**: The tool configuration file (e.g., `config/marker.yaml`) loaded via `load_config_from_yaml`. This configures probing parameters used by the `probe_surface_point()` utility.

### OUTPUT CONFIGURATION
* **`config/calibration.yaml`**: The output file where the calibration results are saved. It contains:
  * `p0_joints`: The final joint angles for the hover position.
  * `p0_pose`: The final cartesian pose (TCP) for the hover position.
  * `p1`: The confirmed cartesian surface point at the bottom-left corner.
  * `width`: Hardcoded to `0.19` (meters).
  * `height`: Hardcoded to `0.27` (meters).

## INNER WORKINGS

1. **Initialization**: The script connects to the UR5e robot via the `ur_rtde` library (`RTDEControlInterface` and `RTDEReceiveInterface`).
2. **Manual P0 Capture**: It waits for user confirmation, then uses `rtde_r.getActualQ()` and `rtde_r.getActualTCPPose()` to fetch the starting joints and pose. It temporarily saves this as `config/calibration.yaml`.
3. **Surface Probing (P1)**: It calls `probe_surface_point(...)` from `src.common.robot_utils`, which moves the tool towards the surface until a force threshold (configured in the tool YAML) is triggered. This establishes the exact point `P1`.
4. **Final P0 Adjustment**: Calculates a new `P0` by offsetting the newly found `P1` by +3mm along the X-axis. Note: the X-axis offset implies the frame of reference expects the surface normal to be along the X-axis.
5. **Persistence**: Finally, it dumps the updated state (`P0`, `P1`, `width`, and `height`) back into `config/calibration.yaml`.
