#!/usr/bin/env python3
"""
scripts/go_to_base_test_location.py
Loads a recorded location from a named YAML file in config/locations/,
connects to the UR5e robot, and moves the robot joints back to that recorded position.
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
logger = get_logger("GoToLocation")

try:
    import rtde_control
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    logger.info("Please install it by running: pip install ur_rtde")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Send robot to a recorded location from config/locations/")
    parser.add_argument("--name", type=str, nargs="?", default="base_test", 
                        help="Name of the location to load from config/locations/{name}.yaml")
    parser.add_argument("--config", type=str, default=None, 
                        help="Direct path to config YAML file (overrides name)")
    parser.add_argument("--robot-ip", type=str, default=None, help="Robot IP (overrides IP in config)")
    parser.add_argument("--speed", type=float, default=0.2, help="Movement speed (rad/s for moveJ, m/s for moveL) (default: 0.2)")
    parser.add_argument("--accel", type=float, default=0.1, help="Movement acceleration (rad/s^2 for moveJ, m/s^2 for moveL) (default: 0.1)")
    parser.add_argument("--movel", action="store_true", help="Use Cartesian linear moveL instead of joint space moveJ")
    parser.add_argument("--yes", action="store_true", help="Skip operator confirmation prompt")
    args = parser.parse_args()

    # Determine source file path
    if args.config:
        src_path = args.config
    else:
        src_path = os.path.join("config", "locations", f"{args.name}.yaml")

    if not os.path.exists(src_path):
        logger.error(f"Location file not found: {src_path}")
        logger.info(f"Please run scripts/record_base_test_location.py {args.name} first to create it.")
        sys.exit(1)

    try:
        with open(src_path, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to read/parse {src_path}: {e}")
        sys.exit(1)

    joints = data.get("joints")
    pose = data.get("pose")
    ip = args.robot_ip if args.robot_ip is not None else data.get("robot_ip", "192.168.57.101")

    if args.movel:
        if not pose:
            logger.error(f"Cannot use --movel: No pose coordinates ('pose') found in {src_path}.")
            sys.exit(1)
    else:
        if not joints:
            logger.error(f"No joint coordinates ('joints') found in {src_path}.")
            sys.exit(1)

    logger.info(f"Target location '{args.name}' loaded from {src_path}")
    if joints:
        logger.info(f"Target joints: {[round(q, 4) for q in joints]}")
    if pose:
        logger.info(f"Target pose (meters): {[round(x, 4) for x in pose[:3]]} (XYZ)")

    if not args.yes:
        confirm_target = "pose" if args.movel else "joints"
        confirm = input(f"Confirm moving the physical robot at {ip} to target {confirm_target}? [y/N]: ")
        if confirm.lower() != 'y':
            logger.info("Movement canceled by user.")
            sys.exit(0)

    logger.info(f"Connecting to robot control interface at IP: {ip}...")
    rtde_c = None
    try:
        rtde_c = rtde_control.RTDEControlInterface(ip)
        logger.success("Control interface connected successfully!")

        if args.movel:
            logger.info(f"Moving to location '{args.name}' using moveL (speed={args.speed}, accel={args.accel})...")
            rtde_c.moveL(pose, args.speed, args.accel)
        else:
            logger.info(f"Moving to location '{args.name}' using moveJ (speed={args.speed}, accel={args.accel})...")
            # Joint move is safe and doesn't get stuck on singularities
            rtde_c.moveJ(joints, args.speed, args.accel)
        logger.success(f"Robot successfully arrived at '{args.name}'.")

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
