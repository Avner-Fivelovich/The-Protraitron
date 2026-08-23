<style>
  h1, h2, h3, h4, h5, h6 {
    font-family: 'Space Grotesk', sans-serif;
    text-transform: uppercase;
    border-bottom: 2px solid #4a148c;
    color: #26a69a;
  }
  body, p, li, table {
    font-family: 'Inter', sans-serif;
  }
  pre, code {
    font-family: 'JetBrains Mono', monospace;
    background-color: #0f0f10;
    color: #e0e0e0;
    padding: 0.2em 0.4em;
    border-radius: 3px;
  }
  pre {
    padding: 1em;
    overflow: auto;
  }
</style>

# CALIBRATE PAPER GUI (`scripts/calibrate_paper_gui.py`)

## PURPOSE
The `calibrate_paper_gui.py` script provides a full-featured, Tkinter-based graphical user interface for calibrating, jogging, testing, and verifying the physical waypoints required for the UR5e robot's autonomous paper manipulation, tool changing, and stamping sequences.

It enables step-by-step recording of 6D Cartesian poses and joint configurations across 26 distinct stages (including pen/knife docking, magnet handling, paper cutting, roll pulling, and rubber stamping), while offering live TCP monitoring, freedrive hand-guiding, gripper actuation, and test sequence execution.

---

## HOW TO USE IT

### 1. Launching the GUI
Run the script from the root repository directory:
```bash
python scripts/calibrate_paper_gui.py
```
To specify a custom robot IP address on the command line:
```bash
python scripts/calibrate_paper_gui.py --ip 192.168.57.100
```
*(If `--ip` is omitted, the IP defaults to `hardware.robot_ip` configured in `config/server.yaml`)*

### 2. Connection Workflow
* Click the **Reconnect** button in the GUI header to establish low-latency RTDE communication with the UR5e robot (`RTDEControlInterface` / `RTDEReceiveInterface`) and connect to the Robotiq Gripper socket.
* The status label in the header displays connection status, active modes, or safety state warnings (e.g., Protective Stop or Singularity alerts).

### 3. Robot Jogging and Positioning
* **Keyboard & UI Jogging**: Move the robot's TCP along the X, Y, and Z axes using the on-screen buttons or keyboard shortcuts (`W`/`S`, `A`/`D`, `Q`/`E`).
* **Hand-Guided Freedrive**: Click **🖐 Freedrive (Hand-Guide)** or press `F` to enable zero-gravity hand-guiding. Move the arm manually to the desired pose, then press `F` again to lock the position.
* **Movement Settings**:
  * **Speed (m/s)**: Adjust jogging velocity (0.005 to 0.15 m/s).
  * **Accel (m/s²)**: Adjust acceleration (0.01 to 0.5 m/s²).
  * **Step Size (m)**: Set distance per jog click/keypress (0.001 to 0.05 m).
  * **Mode**: Choose between **Joint IK (Safe / No Stops)** (`moveJ_IK`) to avoid Cartesian singularities, or **Linear (`moveL`)**.
* **Live Coordinates & Copy**: View real-time TCP coordinates (`X`, `Y`, `Z`, `Rx`, `Ry`, `Rz`). Click **📋 Copy** to copy the current 6D pose array directly to the clipboard.

### 4. Gripper Control and Rotation
* **Actuation**: Click **Open** or **Close** to actuate the Robotiq gripper to configured percentage limits (**Open Pos %** and **Close Pos %**).
* **Tool Rotation**: Click **Turn +** or **Turn -** to rotate the gripper around the tool Z-axis by the configured angle (**Turn (degrees)**).
* **Tuning Parameters**: Adjust gripper speed, force, and rotational increments using the dedicated sliders.

### 5. Step-by-Step Waypoint Calibration
The top panel displays the current step number and stage description:
1. Jog or hand-guide the robot to the specified physical location.
2. Click **Save Point & Next** (or press `Spacebar`) to capture both the Cartesian pose `[X, Y, Z, Rx, Ry, Rz]` and joint angles `[q0, q1, q2, q3, q4, q5]`.
3. Use **Back** to re-calibrate a previous waypoint or **Skip** to advance without modifying an existing recorded waypoint.
4. Changes are saved automatically to `config/paper_manipulation.yaml`.

### 6. Go To Saved Location (Validation)
* The **Go To Saved Location** panel dynamically renders buttons for all recorded waypoints.
* **Color Code**: Green buttons indicate verified hybrid waypoints (containing both joint angles and TCP pose for deterministic `moveJ` motion); grey buttons indicate pose-only waypoints.
* Check **Use moveL (Linear) [l]** (or press `l`) to test linear Cartesian trajectories instead of joint-space motion.

### 7. Action Sequences Execution
The GUI allows executing high-level automated sequences directly via `PaperHandler` to verify end-to-end reliability:
* **Full Paper Swap**: Executes the complete paper handling cycle.
* **Pick up Marker / Drop Marker**: Tests marker tool changer docking.
* **Pick up Knife / Drop Knife**: Tests cutter tool changer docking.
* **Execute Cut**: Tests the linear paper cutting slice across the roll.
* **Hand to User**: Delivers the cut paper portrait to the human participant with force-assisted handover.
* **Put New Paper**: Deploys fresh paper from the roll and anchors it with the magnets.
* **Execute Stamping**: Tests picking up the stamp, pressing it into the ink pad, and stamping the paper.

---

## KEYBOARD SHORTCUTS REFERENCE

| Key / Shortcut | Action | Description |
| :--- | :--- | :--- |
| `W` / `S` | Jog X-axis (+ / -) | Moves TCP along the Cartesian X-axis |
| `A` / `D` | Jog Y-axis (+ / -) | Moves TCP along the Cartesian Y-axis |
| `Q` / `E` | Jog Z-axis (+ / -) | Moves TCP along the Cartesian Z-axis |
| `F` | Toggle Freedrive | Toggles UR5e hand-guided zero-gravity mode |
| `Space` | Save Point & Next | Records current waypoint pose & joints and advances stage |
| `L` | Toggle Linear Mode | Toggles `moveL` mode in the "Go To Saved Location" panel |
| `Mouse Wheel` | Scroll UI | Scrolls the control canvas smoothly |

---

## 26-STAGE CALIBRATION SEQUENCE

| Stage # | Key Identifier | Description |
| :---: | :--- | :--- |
| **1** | `draw_home` | Starting draw location |
| **2** | `safe_paper` | Safe hover location away from paper surface |
| **3** | `safe_tools` | Safe transit location above the tool docks |
| **4** | `above_marker_dock` | Hover location above the marker dock |
| **5** | `marker_dock` | Final docked location to store/retrieve the marker |
| **6** | `lower_magnet_start` | Location to pick up the lower paper magnet |
| **7** | `lower_magnet_park` | Temporary parking location for the lower magnet |
| **8** | `above_knife_dock` | Hover location above the knife dock |
| **9** | `knife_dock` | Final docked location to store/retrieve the knife |
| **10** | `cut_start_pos` | Starting point for the horizontal paper cut |
| **11** | `cut_end_pos` | Ending point for the horizontal paper cut |
| **12** | `cut_paper_grab` | Position to pinch and grab the cut paper sheet |
| **13** | `cut_paper_pull_dest` | Destination to pull the cut paper away from the easel |
| **14** | `safe_midpoint_to_user` | Intermediate waypoint on trajectory toward user handover |
| **15** | `user_handover_location` | Target location to present the portrait to the user |
| **16** | `upper_magnet_start` | Location to pick up the upper paper magnet |
| **17** | `upper_magnet_park` | Temporary parking location for the upper magnet |
| **18** | `upper_magnet_end` | Final destination for the upper magnet after rolling paper |
| **19** | `fresh_paper_grab` | Position to pinch the leading edge of the fresh paper roll |
| **20** | `fresh_paper_pull_dest` | End location after pulling fresh paper down the board |
| **21** | `paper_straighten_start` | Location below upper magnet to start smoothing paper |
| **22** | `above_stamp` | Hover location above the stamp dock |
| **23** | `stamp` | Docked location to grasp the rubber stamp |
| **24** | `above_ink` | Hover location above the ink pad |
| **25** | `ink` | Contact location to press the stamp into the ink pad |
| **26** | `stamping_pos` | Contact location to press the inked stamp onto the paper |

---

## CONFIGURATION FILES

### Input & Central Configurations
* **`config/server.yaml`**: Configures default parameters:
  * `hardware.robot_ip`: Default IP address for the robot.
  * `hardware.gripper_port`: Socket port for Robotiq gripper communication (default `63352`).
  * `calibration_gui`: Default window geometry (`500x600`), movement slider defaults, and gripper limits.
  * `paper_manipulation_defaults`: Baseline speeds (`default_move`, `cut_pull`, `fetch_pull`) and force thresholds (`handover_pull`).

### Output Configuration
* **`config/paper_manipulation.yaml`**: Primary configuration file generated and updated by the GUI.
  * `locations`: Dictionary mapping each waypoint key to its hybrid definition:
    ```yaml
    locations:
      marker_dock:
        joints: [3.680, -2.170, -1.788, -2.278, -1.101, -3.160]
        pose: [-0.608, -0.156, 0.131, -1.150, -1.227, 1.280]
    ```
  * `speeds`: Trajectory speed profiles for regular moves, cuts, and pulls.
  * `force_thresholds`: Sensitivity threshold for user handover release.

### UI State Persistence
* **`config/.calibrate_gui_state.yaml`**: Automatically saves and restores slider positions (speed, acceleration, step size, gripper settings, motion mode) between application restarts.

---

## INNER WORKINGS & ARCHITECTURE

1. **UR5e RTDE Communication**:
   * Utilizes `ur_rtde` (`RTDEControlInterface` and `RTDEReceiveInterface`) for deterministic control and real-time telemetry at up to 500 Hz.
   * Employs fallback logic for external URCap port `50002`, gracefully reverting to standard RTDE control if URCap extensions are unavailable.
2. **Robotiq Gripper Socket Protocol**:
   * Integrates `src.robot.robotiq_gripper.RobotiqGripper` to drive the Robotiq 2F gripper over TCP port `63352` (or falls back to mock mode if disconnected).
3. **Kinematics & Tool Space Rotation**:
   * Uses `rotate_tool_orientation()` to compute relative rotations around the tool Z-axis while preserving Cartesian translation coordinates.
   * Supports `moveJ` (joint space), `moveJ_IK` (inverse kinematics in joint space), and `moveL` (linear Cartesian space), checking `isPoseWithinSafetyLimits()` prior to execution.
4. **Multithreaded Non-Blocking Execution**:
   * All network connections, jogging steps, gripper commands, and sequence runs are dispatched to background threads with a `motion_lock` mutex. This guarantees the Tkinter main event loop remains responsive with 0% interface lag.
5. **Keepalive Daemon & Error Resilience**:
   * An active background keepalive loop monitors `isProgramRunning()`. If the PolyScope robot script stops due to controller idle timeouts, it automatically re-uploads the RTDE control script.
   * Explicit checks for `isProtectiveStopped()` and `isEmergencyStopped()` provide actionable feedback on the GUI status bar without crashing the application.
