#!/usr/bin/env python3
"""
scripts/record_base_test_location.py
Connects to the UR5e robot, reads its current position (joints and TCP pose),
and writes it to a YAML configuration file under config/locations/.
"""
import os
import sys
import argparse
import yaml
import time

# Add root folder to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.logger import get_logger

# Initialize logger
logger = get_logger("RecordLocation")

try:
    import rtde_receive
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    logger.info("Please install it by running: pip install ur_rtde")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Record robot's current pose/joints to a locations YAML file")
    parser.add_argument("--config", type=str, default="config/server.yaml", 
                        help="Path to YAML configuration file (default: config/server.yaml)")
    parser.add_argument("--name", type=str, nargs="?", default=None, 
                        help="Name of the location (saves as locations_dir/{name}.yaml)")
    parser.add_argument("--robot-ip", type=str, default=None, help="Robot IP (overrides config)")
    parser.add_argument("--output", type=str, default=None, 
                        help="Direct path to output YAML file (overrides standard path)")
    args = parser.parse_args()

    # Load config file
    config = {}
    if os.path.exists(args.config):
        with open(args.config, "r") as f:
            config = yaml.safe_load(f) or {}
            
    record_cfg = config.get("record_location", {})
    hardware_cfg = config.get("hardware", {})
    dirs_cfg = config.get("directories", {})

    # Apply configuration with fallbacks
    name = args.name or record_cfg.get("default_name", "base_test")
    robot_ip = args.robot_ip or hardware_cfg.get("robot_ip", "192.168.57.101")
    locations_dir = dirs_cfg.get("locations_dir", "config/locations")

    # Determine destination file path
    if args.output:
        dest_path = args.output
    else:
        dest_path = os.path.join(locations_dir, f"{name}.yaml")

    logger.info(f"Connecting to robot telemetry interface at IP: {robot_ip}...")
    rtde_r = None
    try:
        rtde_r = rtde_receive.RTDEReceiveInterface(robot_ip)
        logger.success("Telemetry interface connected successfully!")

        logger.info("Reading current joints and TCP pose...")
        joints = rtde_r.getActualQ()
        pose = rtde_r.getActualTCPPose()

        # Display retrieved values
        logger.info(f"Actual Joint Angles (rad): {[round(x, 5) for x in joints]}")
        logger.info(f"Actual TCP Pose (meters) : {[round(x, 5) for x in pose[:3]]} (XYZ)")
        logger.info(f"Actual TCP Orientation   : {[round(x, 5) for x in pose[3:]]} (Rx, Ry, Rz)")

        # Prepare YAML structure
        output_data = {
            "robot_ip": robot_ip,
            "joints": [float(q) for q in joints],
            "pose": [float(p) for p in pose],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Make sure output directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        with open(dest_path, "w") as f:
            yaml.safe_dump(output_data, f, default_flow_style=False)
        
        logger.success(f"Location '{name}' successfully written to {dest_path}!")

    except Exception as e:
        logger.error(f"Failed to communicate with robot: {e}")
        sys.exit(1)
    finally:
        if rtde_r:
            try:
                rtde_r.disconnect()
                logger.info("Disconnected telemetry interface.")
            except Exception:
                pass

if __name__ == "__main__":
    main()
