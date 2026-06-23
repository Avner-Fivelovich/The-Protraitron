#!/usr/bin/env python3
"""
scripts/go_to_base_test_location.py
Loads a recorded base test location from a YAML file, connects to the UR5e robot,
and moves the robot joints back to that recorded position.
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
logger = get_logger("GoToBaseLocation")

try:
    import rtde_control
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    logger.info("Please install it by running: pip install ur_rtde")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Send robot to the recorded base test location")
    parser.add_argument("--config", type=str, default="config/base_test_location.yaml", help="YAML file with target location")
    parser.add_argument("--robot-ip", type=str, default=None, help="Robot IP (overrides IP in config)")
    parser.add_argument("--speed", type=float, default=0.2, help="Joint speed in rad/s (default: 0.2)")
    parser.add_argument("--accel", type=float, default=0.1, help="Joint acceleration in rad/s^2 (default: 0.1)")
    parser.add_argument("--yes", action="store_true", help="Skip operator confirmation prompt")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        logger.info("Please run scripts/record_base_test_location.py first to create it.")
        sys.exit(1)

    try:
        with open(args.config, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to read/parse {args.config}: {e}")
        sys.exit(1)

    joints = data.get("joints")
    pose = data.get("pose")
    ip = args.robot_ip if args.robot_ip is not None else data.get("robot_ip", "192.168.57.101")

    if not joints:
        logger.error(f"No joint coordinates ('joints') found in {args.config}.")
        sys.exit(1)

    logger.info(f"Target location loaded from {args.config}")
    logger.info(f"Target joints: {[round(q, 4) for q in joints]}")
    if pose:
        logger.info(f"Target pose (meters): {[round(x, 4) for x in pose[:3]]} (XYZ)")

    if not args.yes:
        confirm = input(f"Confirm moving the physical robot at {ip} to target joints? [y/N]: ")
        if confirm.lower() != 'y':
            logger.info("Movement canceled by user.")
            sys.exit(0)

    logger.info(f"Connecting to robot control interface at IP: {ip}...")
    rtde_c = None
    try:
        rtde_c = rtde_control.RTDEControlInterface(ip)
        logger.success("Control interface connected successfully!")

        logger.info(f"Moving to base test location using moveJ (speed={args.speed}, accel={args.accel})...")
        # Joint move is safe and doesn't get stuck on singularities
        rtde_c.moveJ(joints, args.speed, args.accel)
        logger.success("Robot successfully arrived at the base test location.")

    except Exception as e:
        logger.error(f"Failed to communicate or move: {e}")
        sys.exit(1)
    finally:
        if rtde_c:
            try:
                rtde_c.disconnect()
                logger.info("Disconnected control interface.")
            except Exception:
                pass

if __name__ == "__main__":
    main()
