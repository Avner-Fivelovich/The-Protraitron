#!/usr/bin/env python3
"""
scripts/record_base_test_location.py
Connects to the UR5e robot, reads its current position (joints and TCP pose),
and writes it to a YAML configuration file.
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
logger = get_logger("RecordBaseLocation")

try:
    import rtde_receive
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    logger.info("Please install it by running: pip install ur_rtde")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Record robot's current pose/joints as base test location")
    parser.add_argument("--robot-ip", type=str, default="192.168.57.101", help="Robot IP (default: 192.168.57.101)")
    parser.add_argument("--output", type=str, default="config/base_test_location.yaml", help="Output YAML path")
    args = parser.parse_args()

    logger.info(f"Connecting to robot telemetry interface at IP: {args.robot_ip}...")
    rtde_r = None
    try:
        rtde_r = rtde_receive.RTDEReceiveInterface(args.robot_ip)
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
            "robot_ip": args.robot_ip,
            "joints": [float(q) for q in joints],
            "pose": [float(p) for p in pose],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Make sure output directory exists
        os.makedirs(os.path.dirname(args.output), exist_ok=True)

        with open(args.output, "w") as f:
            yaml.safe_dump(output_data, f, default_flow_style=False)
        
        logger.success(f"Base test location successfully written to {args.output}!")

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
