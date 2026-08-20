#!/usr/bin/env python3
"""
Standalone UR5e smoke test: verify RTDE connectivity and apply one small TCP nudge.

Design goals:
- No calibration dependency.
- One controlled move only (default: +Z by 0.03 m).
- Conservative speed/acceleration defaults.
- Explicit operator confirmation unless --yes is passed.
"""

import argparse
import copy
import os
import sys
import time
from typing import Optional

import yaml

# Make sure local project imports work when running this script directly.
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.common.logger import get_logger

try:
    import rtde_control
    import rtde_receive
except ImportError:
    print("[ERROR] Missing dependency 'ur_rtde'. Install with: pip install ur_rtde")
    sys.exit(1)

logger = get_logger("UR5eNudgeTest")

DEFAULT_ROBOT_IP = "192.168.57.100"
DEFAULT_AXIS = "-y"
DEFAULT_DISTANCE_M = 0.03
DEFAULT_SPEED_MPS = 0.02
DEFAULT_ACCEL_MPS2 = 0.10

AXIS_TO_INDEX_SIGN = {
    "+x": (0, 1.0),
    "-x": (0, -1.0),
    "+y": (1, 1.0),
    "-y": (1, -1.0),
    "+z": (2, 1.0),
    "-z": (2, -1.0),
}


def read_config_robot_ip() -> Optional[str]:
    """Reads robot IP from config via files_pathes indirection if available."""
    files_paths_cfg = os.path.join(PROJECT_ROOT, "config", "files_pathes.yaml")
    if not os.path.exists(files_paths_cfg):
        return None

    try:
        with open(files_paths_cfg, "r", encoding="utf-8") as f:
            paths_cfg = yaml.safe_load(f) or {}
        server_cfg_path = paths_cfg.get("paths", {}).get("server_config", "config/server.yaml")
        if not os.path.isabs(server_cfg_path):
            server_cfg_path = os.path.join(PROJECT_ROOT, server_cfg_path)
        if not os.path.exists(server_cfg_path):
            return None

        with open(server_cfg_path, "r", encoding="utf-8") as f:
            server_cfg = yaml.safe_load(f) or {}
        return server_cfg.get("hardware", {}).get("robot_ip")
    except Exception as exc:
        logger.warning(f"Could not read configured robot IP: {exc}")
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="UR5e connection and one-step TCP nudge test (no calibration)."
    )
    parser.add_argument(
        "--robot-ip",
        type=str,
        default=DEFAULT_ROBOT_IP,
        help=f"Robot controller IP address (default: {DEFAULT_ROBOT_IP})",
    )
    parser.add_argument(
        "--axis",
        type=str.lower,
        choices=sorted(AXIS_TO_INDEX_SIGN.keys()),
        default=DEFAULT_AXIS,
        help=f"Cartesian base-frame axis for nudge (default: {DEFAULT_AXIS})",
    )
    parser.add_argument(
        "--distance",
        type=float,
        default=DEFAULT_DISTANCE_M,
        help=f"Nudge distance in meters (default: {DEFAULT_DISTANCE_M})",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_SPEED_MPS,
        help=f"Linear move speed in m/s (default: {DEFAULT_SPEED_MPS})",
    )
    parser.add_argument(
        "--accel",
        type=float,
        default=DEFAULT_ACCEL_MPS2,
        help=f"Linear move acceleration in m/s^2 (default: {DEFAULT_ACCEL_MPS2})",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only connect and print telemetry, do not move.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt.",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=0.20,
        help="Wait time after move before reading final TCP pose (default: 0.20)",
    )
    return parser.parse_args()


def format_pose_xyz_mm(pose):
    return [round(v * 1000.0, 1) for v in pose[:3]]


def confirm_or_abort(args: argparse.Namespace, target_pose) -> bool:
    logger.info("Motion confirmation required.")
    logger.info(f"Axis: {args.axis}, distance: {args.distance:.4f} m")
    logger.info(f"Target TCP XYZ (mm): {format_pose_xyz_mm(target_pose)}")

    if args.yes:
        return True

    if not sys.stdin.isatty():
        logger.error("Non-interactive terminal and --yes not set. Aborting for safety.")
        return False

    user_input = input("Proceed with moveL? [y/N]: ").strip().lower()
    return user_input in {"y", "yes"}


def main() -> int:
    args = parse_args()

    if args.distance <= 0.0:
        logger.error("Distance must be positive.")
        return 2
    if args.speed <= 0.0 or args.accel <= 0.0:
        logger.error("Speed and acceleration must be positive.")
        return 2

    config_ip = read_config_robot_ip()
    if config_ip and config_ip != args.robot_ip:
        logger.warning(
            "Configured robot IP differs from this test target: "
            f"config={config_ip}, test_target={args.robot_ip}"
        )

    logger.info("UR5e RTDE CONNECTION + NUDGE TEST")
    logger.info(f"Target Robot IP: {args.robot_ip}")
    logger.info("No calibration is used by this script.")

    rtde_c = None
    rtde_r = None
    movement_started = False

    try:
        logger.info("Connecting rtde_receive...")
        rtde_r = rtde_receive.RTDEReceiveInterface(args.robot_ip)
        logger.success("rtde_receive connected.")

        logger.info("Connecting rtde_control...")
        rtde_c = rtde_control.RTDEControlInterface(args.robot_ip)
        logger.success("rtde_control connected.")

        is_connected = rtde_c.isConnected()
        is_emergency_stopped = rtde_r.isEmergencyStopped()
        is_protective_stopped = rtde_r.isProtectiveStopped()

        logger.info(f"RTDE control connected : {is_connected}")
        logger.info(f"Emergency stop active  : {is_emergency_stopped}")
        logger.info(f"Protective stop active : {is_protective_stopped}")

        if not is_connected:
            logger.error("RTDE control reports disconnected state. Aborting.")
            return 3

        if is_emergency_stopped or is_protective_stopped:
            logger.error("Robot is in a stopped safety state. Clear it on Polyscope and retry.")
            return 4

        joints = rtde_r.getActualQ()
        tcp_pose_start = rtde_r.getActualTCPPose()

        logger.info(f"Start joint angles (rad): {[round(x, 4) for x in joints]}")
        logger.info(f"Start TCP XYZ (mm): {format_pose_xyz_mm(tcp_pose_start)}")
        logger.info(f"Start TCP RxRyRz: {[round(x, 4) for x in tcp_pose_start[3:]]}")

        if args.check_only:
            logger.success("Check-only mode complete. No motion executed.")
            return 0

        axis_idx, sign = AXIS_TO_INDEX_SIGN[args.axis]
        target_pose = copy.deepcopy(tcp_pose_start)
        target_pose[axis_idx] += sign * args.distance

        if not confirm_or_abort(args, target_pose):
            logger.warning("Motion cancelled by operator.")
            return 5

        logger.info(
            f"Executing moveL to target with speed={args.speed} m/s, accel={args.accel} m/s^2..."
        )
        movement_started = True
        move_ok = rtde_c.moveL(target_pose, args.speed, args.accel)
        if not move_ok:
            logger.error("moveL returned failure.")
            return 6

        if args.settle_seconds > 0:
            time.sleep(args.settle_seconds)

        tcp_pose_end = rtde_r.getActualTCPPose()
        delta = [tcp_pose_end[i] - tcp_pose_start[i] for i in range(3)]

        logger.success("Motion complete.")
        logger.info(f"End TCP XYZ (mm): {format_pose_xyz_mm(tcp_pose_end)}")
        logger.info(f"Delta XYZ (mm): {[round(v * 1000.0, 2) for v in delta]}")
        logger.info("No return-to-start move was performed (by design).")

        return 0

    except Exception as exc:
        logger.error(f"Test failed: {exc}")
        return 1

    finally:
        if rtde_c and movement_started:
            try:
                rtde_c.stopL(0.5)
            except Exception:
                pass

        if rtde_c:
            try:
                rtde_c.disconnect()
                logger.info("Disconnected rtde_control.")
            except Exception:
                pass

        if rtde_r:
            try:
                rtde_r.disconnect()
                logger.info("Disconnected rtde_receive.")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
