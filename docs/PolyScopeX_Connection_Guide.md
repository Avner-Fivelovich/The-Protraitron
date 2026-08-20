# PolyScope X Connection Guide for The Protraitron

This document outlines the necessary steps to successfully connect and run `The Protraitron` remote application with a UR5e robot running **PolyScope X**.

Because PolyScope X introduces a ground-up rearchitecture compared to the legacy PolyScope 5, some traditional connection methods (like the old Dashboard Server on port 29999 or automatic script uploads) are no longer supported natively without the correct configuration.

## 1. Robot Motion Control (ur_rtde)

The `ur_rtde` library is used to control the robot's motion. The good news is that standard motion commands via RTDE (Port 30004 for telemetry, Port 30003 for control) **work out of the box** without any Python code changes in our repository.

However, you must configure the robot correctly to accept these commands:

### On the Teach Pendant:
1. **Enable Remote Control Mode:** 
   * Navigate to the **Safety Overview** (or top-right header).
   * Ensure the operational mode is set to **Automatic**.
   * Toggle the control mode to **Remote**. 
   * *(Note: When in Remote mode, local control from the Teach Pendant is disabled).*
2. **Network Setup:**
   * Verify the robot's IP address (e.g., `192.168.57.100`) matches the `robot_ip` specified in `config/server.yaml`.

*Note: In previous versions of `ur_rtde` on MacOS, the `FLAG_USE_EXT_UR_CAP` flag was unsupported. Thus, `ur_rtde` relies on its default connection method, which successfully bridges to the PolyScope X RTDE interfaces for motion control.*

## 2. Robotiq Gripper Control

This is the primary breaking change. In PolyScope 5, `The Protraitron` communicates with the Robotiq Gripper via a raw socket connection on **Port 63352**. 

**PolyScope X does not expose Port 63352 by default.** The legacy Robotiq URCap that opened this port is not compatible with PolyScope X. Furthermore, sending arbitrary URScript commands to Port 30002 is blocked by default on PolyScope X unless explicitly configured in Interpreter Mode.

### How to Fix Gripper Connectivity (Recommended Method)

To allow the existing python socket code (in `src/robot/robotiq_gripper.py` and `paper_handler.py`) to function without a complete rewrite, you must forward the robot's RS-485 Tool Communication port to the network.

1. **Download the Forwarder:** Obtain the [Universal_Robots_ToolComm_Forwarder_URCapX](https://github.com/UniversalRobots/Universal_Robots_ToolComm_Forwarder_URCapX) package provided by Universal Robots.
2. **Install URCapX:** Install this URCapX onto your PolyScope X controller.
3. **Configure the Forwarder:** 
   * Set up the forwarder to expose the Tool I/O (RS-485) interface over the network.
   * Ensure it forwards to the same port expected by our configuration (Port `63352`).
4. **Remove Conflicts:** Ensure no other legacy gripper URCaps are attempting to claim the RS-485 interface simultaneously.

Once the ToolComm Forwarder is active, the gripper socket commands (`test_ur5e_connection.py`, etc.) will succeed.

## 3. PolyScope X Robot API (Optional)

If you ever need to debug the robot's state, PolyScope X now features a modern RESTful API (replacing the old Dashboard Server).
* You can access the live documentation directly from the robot by navigating a web browser to:
  `http://[ROBOT_IP]/universal-robots/robot-api/docs`
* This API runs on standard HTTP ports (80/443) and can be used to query system state, clear protective stops, or load/play `.urpx` programs.
