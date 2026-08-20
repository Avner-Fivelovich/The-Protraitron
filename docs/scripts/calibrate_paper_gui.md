<style>
  h1, h2, h3, h4, h5, h6 {
    font-family: 'Space Grotesk', sans-serif;
    text-transform: uppercase;
  }
  h1, h2 {
    border-bottom: 2px solid #4a148c;
  }
  h3 {
    border-left: 4px solid #26a69a;
    padding-left: 8px;
  }
  body, p, li, td {
    font-family: 'Inter', sans-serif;
  }
  pre, .pre-style {
    background-color: #0f0f10;
    color: #f8f8f2;
    font-family: 'JetBrains Mono', monospace;
    padding: 12px;
    border-radius: 4px;
    display: block;
    overflow-x: auto;
  }
  code {
    font-family: 'JetBrains Mono', monospace;
  }
</style>

# Calibrate Paper GUI (`calibrate_paper_gui.py`)

## Purpose
The `calibrate_paper_gui.py` script provides a user-friendly, Tkinter-based graphical interface for calibrating the physical locations required for the UR5e robot's paper manipulation sequence. It enables precise, step-by-step recording of waypoints (e.g., pen dock, magnet positions, paper grab and cut trajectories) necessary for the Portraitron's autonomous paper handling.

## How to Use It
1. **Launch the Application**: Run the script from the terminal, optionally providing the robot's IP address.
   <div class="pre-style"><code>python scripts/calibrate_paper_gui.py --ip 192.168.57.101</code></div>
2. **Connect to Robot**: Click the **Reconnect** button in the GUI to establish a connection with the UR5e and the Robotiq Gripper.
3. **Jog and Calibrate**:
   - Use the **Jogging Keyboard** (on-screen buttons or W/S/A/D/Q/E keys) to move the robot's TCP in X, Y, and Z dimensions.
   - Adjust **Movement Settings** (speed and step size) for fine or coarse control.
   - Use **Gripper Controls** to open, close, or jog the gripper.
4. **Save Waypoints**: The UI guides you through a 10-step sequence. Once the robot is positioned correctly for a step, press **Save Point & Next** (or the spacebar) to record the position.
5. **Completion**: Upon finishing all steps, the calibration is complete and the configurations are saved.

## Configuration Files
The application interacts exclusively with the following configuration file:
* **Output Path**: `config/paper_manipulation.yaml`
* **Data Stored**: 
  - `locations`: Dictionary mapping each sequence stage (e.g., `pen_dock`, `magnet_1_start`) to its corresponding 6D TCP pose `[X, Y, Z, Rx, Ry, Rz]`.
  - Default configurations for `speeds` (`default_move`, `cut_pull`, `fetch_pull`) and `force_thresholds` (`handover_pull`) are initialized if the file does not already exist.

## Inner Workings
* **Robot Interface**: Utilizes `ur_rtde` (`rtde_control` and `rtde_receive`) for low-latency communication with the UR5e controller.
* **Gripper Integration**: Connects to the Robotiq gripper via a custom socket interface (`src.robot.robotiq_gripper.RobotiqGripper`). Gripper actions (full/jog) run asynchronously.
* **State Machine**: The sequence is defined as a list of 10 stages. The GUI tracks the active stage to update the instructions and map the saved pose to the correct key.
* **Threading**: Network connections and blocking robot movements (like gripper actuation) are dispatched to background threads (e.g., `threading.Thread`) to prevent the Tkinter main loop from freezing.
* **Safety & Resilience**: The script employs try-except blocks for connection attempts and movement commands. If the robot enters a fault state or reaches a singularity, error logs are written instead of crashing the GUI.
