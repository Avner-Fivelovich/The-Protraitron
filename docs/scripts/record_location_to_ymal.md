<style>
  body {
    font-family: 'Inter', sans-serif;
  }
  h1, h2, h3, h4 {
    font-family: 'Space Grotesk', sans-serif;
    text-transform: uppercase;
  }
  h1 {
    border-bottom: 3px solid #4a148c;
    padding-bottom: 5px;
  }
  h2 {
    border-bottom: 2px solid #26a69a;
    padding-bottom: 4px;
    margin-top: 1.5em;
  }
  h3 {
    color: #4a148c;
  }
  pre, code {
    font-family: 'JetBrains Mono', monospace;
  }
  pre {
    background-color: #0f0f10;
    color: #e0e0e0;
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
  }
  code {
    background-color: #f4f4f4;
    color: #d32f2f;
    padding: 2px 4px;
    border-radius: 3px;
  }
  pre code {
    background-color: transparent;
    color: inherit;
    padding: 0;
  }
</style>

# Record Location to YAML Script

**File:** `scripts/record_location_to_ymal.py` (Note: Name reflects the typo in the source directory)

## Overview

The `record_location_to_ymal.py` script is a utility for capturing the physical state of the UR5e robot and persisting it into a configuration file. It connects to the robot's real-time data exchange (RTDE) interface, reads the current joint angles and Tool Center Point (TCP) pose, and exports them to a structured YAML file. 

## Purpose

The primary purpose of this script is to easily record reference positions and calibration points for the robot (e.g., home position, paper pickup location, drawing canvas origin). By manually moving the robot into a desired physical configuration and executing this script, developers can seamlessly log precise spatial coordinates into the system's `config/locations` database for subsequent automated routines.

## How to Use

Ensure that the robot is powered on, accessible over the network, and the `ur_rtde` Python library is installed.

### Basic Execution

Run the script without arguments to record the location as the default `base_test` configuration:

```bash
./venv/bin/python scripts/record_location_to_ymal.py
```

### CLI Arguments

You can customize the recording process using the following command-line flags:

* `--name`: Specifies the name of the location. The output will be saved as `config/locations/{name}.yaml`. (Default: `base_test`)
* `--robot-ip`: Specifies the IP address of the UR5e robot. (Default: `192.168.57.101`)
* `--output`: Provides a direct absolute or relative path to an output YAML file. This overrides the standard `--name` parameter and standard output folder.

### Example

To record a drawing canvas origin on a robot with a custom IP:

```bash
./venv/bin/python scripts/record_location_to_ymal.py --name canvas_origin --robot-ip 192.168.1.50
```

## Config Files and Outputs

The script naturally interacts with the `config/locations/` directory in the repository.

* **Target Output:** Unless an explicit `--output` flag is given, the output YAML is written to `config/locations/<name>.yaml`.
* **Output Structure:** The generated YAML file is structured as follows:

```yaml
robot_ip: 192.168.57.101
joints: [0.0, -1.57, 0.0, -1.57, 0.0, 0.0]
pose: [0.1, 0.2, 0.3, 3.14, 0.0, 0.0]
timestamp: "2026-08-20 10:15:30"
```

## Inner Workings

1. **Path Injection:** Temporarily appends the project root (`..`) to `sys.path` to allow imports of internal modules, notably `src.common.logger` for standardized logging.
2. **Library Validation:** Attempts to import `rtde_receive` from the `ur_rtde` package, providing a graceful fallback error message and termination if it's missing.
3. **Argument Parsing:** Uses the `argparse` module to build the command-line interface.
4. **Robot Telemetry Setup:** Establishes an `RTDEReceiveInterface` connection targeting the specified `--robot-ip`.
5. **Data Extraction:** 
   * Invokes `rtde_r.getActualQ()` to fetch the 6 joint angles (in radians).
   * Invokes `rtde_r.getActualTCPPose()` to fetch the 6-degree-of-freedom pose (X, Y, Z in meters, followed by Rx, Ry, Rz rotation vectors).
6. **Persistence:** Dumps the parsed data structures into a dictionary alongside the current timestamp, and leverages `yaml.safe_dump` to write this payload accurately into the destination file.
7. **Cleanup:** Safely disconnects the RTDE telemetry interface inside a `finally` block to prevent lingering sockets.
