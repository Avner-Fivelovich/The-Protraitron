#!/usr/bin/env python3
"""
scripts/roll_paper.py
Standalone script to execute the Paper Rolling Routine using UR5e and Robotiq Gripper.
Opens gripper, rotates tool 90 degrees, closes onto paper, pulls downward ~10cm to roll, and releases.
"""
import os
import sys
import argparse
import time

# Add root folder to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.logger import get_logger
from src.robot.controller import UR5eController
from src.robot.paper_roller import PaperRoller

logger = get_logger("RollPaperScript")


def main():
    parser = argparse.ArgumentParser(description="Run UR5e Robotiq Gripper Paper Rolling Routine")
    parser.add_argument("--ip", type=str, default="192.168.57.101", help="UR5e Robot IP address (default: 192.168.57.101)")
    parser.add_argument("--calibration", type=str, default="config/paper_manipulation.yaml", help="Path to paper_manipulation.yaml")
    parser.add_argument("--marker-config", type=str, default="config/marker.yaml", help="Path to marker.yaml")
    parser.add_argument("--distance", type=float, default=0.10, help="Distance in meters to pull downward (default: 0.10 m = 10 cm)")
    parser.add_argument("--rotate-deg", type=float, default=90.0, help="Tool rotation angle in degrees (default: 90.0)")
    parser.add_argument("--axis", type=str, default="z", choices=["x", "y", "z"], help="Tool rotation axis (default: z)")
    parser.add_argument("--speed", type=float, default=0.04, help="Pull speed in m/s (default: 0.04 m/s)")
    parser.add_argument("--accel", type=float, default=0.08, help="Pull acceleration in m/s^2 (default: 0.08 m/s^2)")
    parser.add_argument("--x-pos", type=float, default=0.5, help="Normalized X grab coordinate [0.0 - 1.0] (default: 0.5)")
    parser.add_argument("--y-pos", type=float, default=0.95, help="Normalized Y grab coordinate [0.0 - 1.0] (default: 0.95)")
    parser.add_argument("--dryrun", action="store_true", help="Simulate without connecting to physical hardware")
    parser.add_argument("--activate-gripper", action="store_true", help="Send activation command to Robotiq gripper before rolling")

    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("       PORTRAITRON 3000 - PAPER ROLLING ROUTINE")
    print("=" * 55)
    print(f"  Robot IP:        {args.ip}")
    print(f"  Pull Distance:   {args.distance * 100:.1f} cm ({args.distance} m)")
    print(f"  Tool Rotation:   {args.rotate_deg}° along {args.axis.upper()}-axis")
    print(f"  Speed / Accel:   {args.speed * 100:.1f} cm/s / {args.accel * 100:.1f} cm/s²")
    print(f"  Grab Position:   Canvas ({args.x_pos:.2f}, {args.y_pos:.2f})")
    print(f"  Dry Run Mode:    {args.dryrun}")
    print("=" * 55 + "\n")

    controller = UR5eController(
        ip_address=args.ip,
        calibration_path=args.calibration,
        marker_config_path=args.marker_config
    )

    if args.dryrun:
        controller.dryrun = True

    logger.info("Connecting to robot...")
    if not controller.connect():
        logger.critical("Could not connect to robot. Exiting.")
        sys.exit(1)

    roller = PaperRoller(controller)

    if args.activate_gripper and not controller.dryrun:
        roller.gripper.activate()

    # Execute paper rolling routine
    success = roller.roll_paper(
        pull_distance_m=args.distance,
        rotate_deg=args.rotate_deg,
        rotation_axis=args.axis,
        speed=args.speed,
        accel=args.accel,
        x_canvas=args.x_pos,
        y_canvas=args.y_pos
    )

    controller.disconnect()

    if success:
        logger.success("Paper rolling task completed successfully!")
        sys.exit(0)
    else:
        logger.error("Paper rolling task failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
