#!/usr/bin/env python3
"""
scripts/write_text.py
Connects to the UR5e robot, prompts for a string (or uses a command line argument / default),
and draws the text on paper using compliant force control.
"""
import os
import sys
import argparse
import time

# Add root folder to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.robot.controller import UR5eController
from src.robot.text_drawing import run_text_drawing
from src.common.logger import get_logger

logger = get_logger("TextDrawingScript")

def main():
    parser = argparse.ArgumentParser(description="Command the UR5e robot to write text on paper.")
    parser.add_argument("text", type=str, nargs="?", default="doofenshmirtz evil inc.",
                        help="Text to write on paper (default: 'doofenshmirtz evil inc.')")
    parser.add_argument("--robot-ip", type=str, default="192.168.57.101",
                        help="Robot IP address (default: 192.168.57.101)")
    parser.add_argument("--width", type=float, default=0.8,
                        help="Text bounding box width fraction of canvas (default: 0.8)")
    parser.add_argument("--height", type=float, default=0.2,
                        help="Text bounding box height fraction of canvas (default: 0.2)")
    args = parser.parse_args()

    CALIBRATION_PATH = "config/calibration.yaml"
    MARKER_CONFIG_PATH = "config/marker.yaml"

    if not os.path.exists(CALIBRATION_PATH):
        logger.critical("Calibration file is missing. Please run calibrate_workspace.py first.")
        sys.exit(1)

    logger.info("Initializing UR5e Controller...")
    controller = UR5eController(args.robot_ip, calibration_path=CALIBRATION_PATH, marker_config_path=MARKER_CONFIG_PATH)

    if not controller.connect():
        logger.error("Connection failed. Aborting text drawing.")
        sys.exit(1)

    try:
        run_text_drawing(controller, args.text, target_width=args.width, target_height=args.height)
    finally:
        controller.disconnect()

if __name__ == "__main__":
    main()
