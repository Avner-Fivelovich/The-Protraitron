import os
import sys
import time
import math
import numpy as np

from src.common.logger import get_logger

# Import logger
logger = get_logger("PaperRoller")

# Try to import Robotiq preamble from archive if available
try:
    from archive.Robotiq_gripper.robotiq_preamble import ROBOTIQ_PREAMBLE
except ImportError:
    ROBOTIQ_PREAMBLE = ""


def rotvec_to_rotmat(rotvec: np.ndarray) -> np.ndarray:
    """
    Converts a 3D rotation vector (axis-angle in radians, [Rx, Ry, Rz])
    into a 3x3 rotation matrix using Rodrigues' rotation formula.
    """
    theta = np.linalg.norm(rotvec)
    if theta < 1e-9:
        return np.eye(3)
    k = rotvec / theta
    K = np.array([
        [0.0, -k[2], k[1]],
        [k[2], 0.0, -k[0]],
        [-k[1], k[0], 0.0]
    ])
    R = np.eye(3) + np.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)
    return R


def rotmat_to_rotvec(R: np.ndarray) -> np.ndarray:
    """
    Converts a 3x3 rotation matrix into a 3D rotation vector [Rx, Ry, Rz].
    """
    trace = np.trace(R)
    cos_theta = np.clip((trace - 1.0) / 2.0, -1.0, 1.0)
    theta = math.acos(cos_theta)
    
    if theta < 1e-9:
        return np.zeros(3)
    
    if math.isclose(theta, math.pi, rel_tol=1e-4):
        # 180 degree singularity
        diag = np.diag(R)
        axis_idx = np.argmax(diag)
        col = R[:, axis_idx] + np.eye(3)[:, axis_idx]
        norm = np.linalg.norm(col)
        if norm > 1e-9:
            k = col / norm
            return k * math.pi
            
    sin_theta = math.sin(theta)
    rx = (R[2, 1] - R[1, 2]) / (2.0 * sin_theta)
    ry = (R[0, 2] - R[2, 0]) / (2.0 * sin_theta)
    rz = (R[1, 0] - R[0, 1]) / (2.0 * sin_theta)
    
    return np.array([rx, ry, rz]) * theta


def rotate_tool_orientation(rx: float, ry: float, rz: float, angle_deg: float, axis: str = 'z') -> tuple[float, float, float]:
    """
    Rotates a UR5e orientation vector [Rx, Ry, Rz] around the tool's local axis ('x', 'y', or 'z')
    by angle_deg degrees.
    """
    rotvec = np.array([rx, ry, rz], dtype=float)
    R_base_to_tool = rotvec_to_rotmat(rotvec)
    
    angle_rad = math.radians(angle_deg)
    ca = math.cos(angle_rad)
    sa = math.sin(angle_rad)
    
    if axis.lower() == 'x':
        R_delta = np.array([
            [1.0, 0.0, 0.0],
            [0.0, ca, -sa],
            [0.0, sa, ca]
        ])
    elif axis.lower() == 'y':
        R_delta = np.array([
            [ca, 0.0, sa],
            [0.0, 1.0, 0.0],
            [-sa, 0.0, ca]
        ])
    else:  # 'z' (Tool approach/wrist 3 axis)
        R_delta = np.array([
            [ca, -sa, 0.0],
            [sa, ca, 0.0],
            [0.0, 0.0, 1.0]
        ])
        
    # Tool-local rotation: R_new = R_base_to_tool * R_delta
    R_new = R_base_to_tool @ R_delta
    rotvec_new = rotmat_to_rotvec(R_new)
    return float(rotvec_new[0]), float(rotvec_new[1]), float(rotvec_new[2])


class RobotiqGripper:
    """
    Controls a Robotiq 2-finger gripper using URScript commands over UR RTDE socket.
    """
    def __init__(self, rtde_c, dryrun: bool = False):
        self.rtde_c = rtde_c
        self.dryrun = dryrun

    def call(self, script_name: str, script_function: str) -> bool:
        if self.dryrun or not self.rtde_c:
            logger.info(f"[DRY RUN] Gripper command executed: {script_name} -> {script_function}")
            return True
        try:
            return self.rtde_c.sendCustomScriptFunction(
                "ROBOTIQ_" + script_name,
                ROBOTIQ_PREAMBLE + "\n" + script_function
            )
        except Exception as e:
            logger.error(f"Failed to send gripper script {script_name}: {e}")
            return False

    def activate(self) -> bool:
        """Activates the gripper motor."""
        logger.info("Activating Robotiq gripper...")
        ret = self.call("ACTIVATE", "rq_activate()")
        if not self.dryrun:
            time.sleep(2.0)
        logger.success("Robotiq gripper activated.")
        return ret

    def set_speed(self, speed_percent: int = 100) -> bool:
        """Sets gripper speed [0-100]."""
        return self.call("SET_SPEED", f"rq_set_speed_norm({speed_percent})")

    def set_force(self, force_percent: int = 100) -> bool:
        """Sets gripper pinch force [0-100]."""
        return self.call("SET_FORCE", f"rq_set_force_norm({force_percent})")

    def open(self) -> bool:
        """Opens the gripper jaws completely."""
        logger.info("Opening gripper jaws...")
        ret = self.call("OPEN", "rq_open_and_wait()")
        if self.dryrun:
            time.sleep(0.5)
        logger.success("Gripper jaws opened.")
        return ret

    def close(self) -> bool:
        """Closes the gripper jaws completely to clamp paper."""
        logger.info("Closing gripper jaws (clamping)...")
        ret = self.call("CLOSE", "rq_close_and_wait()")
        if self.dryrun:
            time.sleep(0.5)
        logger.success("Gripper jaws closed.")
        return ret


class PaperRoller:
    """
    Coordinates paper grabbing, 90-degree tool orientation rotation,
    and downward pulling motion (~10 cm) to roll the paper.
    """
    def __init__(self, controller):
        self.controller = controller
        self.gripper = RobotiqGripper(controller.rtde_c, dryrun=controller.dryrun)

    def roll_paper(
        self,
        pull_distance_m: float = 0.10,
        rotate_deg: float = 90.0,
        rotation_axis: str = 'z',
        speed: float = 0.04,
        accel: float = 0.08,
        x_canvas: float = 0.5,
        y_canvas: float = 0.95,
        grab_depth_offset: float = 0.005
    ) -> bool:
        """
        Executes the full paper roll workflow:
        1. Move to safe hover above the top edge of paper.
        2. Rotate tool orientation by rotate_deg (90 degrees).
        3. Open gripper jaws.
        4. Advance forward to paper grabbing depth.
        5. Close gripper jaws onto paper.
        6. Move linearly downward along Base Z by pull_distance_m to roll the paper.
        7. Open gripper jaws to release paper.
        8. Retract back to safe hover and return home.

        :param pull_distance_m: Distance in meters to pull downwards (default 0.10 m = 10 cm).
        :param rotate_deg: Angle in degrees to rotate the tool (default 90.0 deg).
        :param rotation_axis: Axis of tool rotation ('z' for tool wrist 3 rotation).
        :param speed: Linear speed in m/s (default 0.04 m/s).
        :param accel: Acceleration in m/s^2 (default 0.08 m/s^2).
        :param x_canvas: Normalized X coordinate on page (0.5 = center).
        :param y_canvas: Normalized Y coordinate on page (0.95 = near top edge).
        :param grab_depth_offset: Distance in meters from hover plane to grab depth.
        :return: True if successful, False otherwise.
        """
        logger.info(f"=== Starting Paper Rolling Routine ===")
        logger.info(f"Parameters: Pull distance = {pull_distance_m * 100:.1f} cm, Rotation = {rotate_deg} deg on {rotation_axis.upper()}-axis, Speed = {speed * 100:.1f} cm/s")

        if not self.controller.p0_pose or not self.controller.p1:
            logger.error("Calibration parameters not loaded. Please run calibration first.")
            return False

        # ---------------------------------------------------------
        # Step 1: Compute Target Positions
        # ---------------------------------------------------------
        # Default orientation from calibration
        rx_default, ry_default, rz_default = self.controller.p0_pose[3:]
        
        # Calculate 90-degree rotated orientation
        rx_rot, ry_rot, rz_rot = rotate_tool_orientation(rx_default, ry_default, rz_default, rotate_deg, axis=rotation_axis)
        logger.info(f"Rotated tool orientation: Rx={rx_rot:.4f}, Ry={ry_rot:.4f}, Rz={rz_rot:.4f}")

        # Hover plane X coordinate (10mm in front of board)
        x_hover = self.controller.p1[0] + 0.010  # 10 mm safe hover for gripper
        x_grab = self.controller.p1[0] - grab_depth_offset # Paper contact plane

        # Physical Y and Z start coordinates near top edge of paper
        y_start = self.controller.p1[1] + x_canvas * self.controller.width
        z_start = self.controller.p1[2] + y_canvas * self.controller.height

        hover_pose = [x_hover, y_start, z_start, rx_rot, ry_rot, rz_rot]
        grab_pose = [x_grab, y_start, z_start, rx_rot, ry_rot, rz_rot]
        
        # Downward target pose (Z coordinate decreased by pull_distance_m)
        z_pulled = z_start - pull_distance_m
        pulled_pose = [x_grab, y_start, z_pulled, rx_rot, ry_rot, rz_rot]
        hover_pulled_pose = [x_hover, y_start, z_pulled, rx_default, ry_default, rz_default]

        try:
            # ---------------------------------------------------------
            # Step 2: Move to Hover Pose with 90° Rotated Orientation
            # ---------------------------------------------------------
            logger.info(f"1. Moving to hover position above paper (Z = {z_start:.4f}m) with 90° orientation...")
            if not self.controller.dryrun and self.controller.rtde_c:
                self.controller.rtde_c.moveL(hover_pose, speed, accel)
            else:
                logger.info(f"[DRY RUN] moveL -> Hover Pose: {[round(c, 4) for c in hover_pose]}")
                time.sleep(0.5)

            # ---------------------------------------------------------
            # Step 3: Open Gripper Jaws
            # ---------------------------------------------------------
            logger.info("2. Opening gripper jaws in preparation for grabbing...")
            self.gripper.open()

            # ---------------------------------------------------------
            # Step 4: Advance Forward to Paper Grab Pose
            # ---------------------------------------------------------
            logger.info(f"3. Advancing forward to paper edge (X = {x_grab:.4f}m)...")
            if not self.controller.dryrun and self.controller.rtde_c:
                self.controller.rtde_c.moveL(grab_pose, speed=0.02, acceleration=0.05)
            else:
                logger.info(f"[DRY RUN] moveL -> Grab Pose: {[round(c, 4) for c in grab_pose]}")
                time.sleep(0.5)

            # ---------------------------------------------------------
            # Step 5: Close Gripper onto Paper
            # ---------------------------------------------------------
            logger.info("4. Clamping gripper onto paper...")
            self.gripper.close()
            time.sleep(0.5)

            # ---------------------------------------------------------
            # Step 6: Pull Downward to Roll Paper
            # ---------------------------------------------------------
            logger.info(f"5. Pulling paper downward by {pull_distance_m * 100:.1f} cm (from Z={z_start:.4f}m to Z={z_pulled:.4f}m)...")
            if not self.controller.dryrun and self.controller.rtde_c:
                self.controller.rtde_c.moveL(pulled_pose, speed, accel)
            else:
                logger.info(f"[DRY RUN] moveL -> Pulled Target Pose: {[round(c, 4) for c in pulled_pose]}")
                time.sleep(1.0)
            logger.success("Paper successfully pulled downward.")

            # ---------------------------------------------------------
            # Step 7: Release Paper and Retract
            # ---------------------------------------------------------
            logger.info("6. Opening gripper to release paper...")
            self.gripper.open()

            logger.info("7. Retracting tool away from paper...")
            if not self.controller.dryrun and self.controller.rtde_c:
                self.controller.rtde_c.moveL(hover_pulled_pose, speed, accel)
            else:
                logger.info(f"[DRY RUN] moveL -> Retract Hover Pose: {[round(c, 4) for c in hover_pulled_pose]}")
                time.sleep(0.5)

            # ---------------------------------------------------------
            # Step 8: Return Home (P0)
            # ---------------------------------------------------------
            logger.info("8. Returning arm to home pose (P0)...")
            self.controller.home()
            logger.success("=== Paper Rolling Routine Completed Successfully ===")
            return True

        except Exception as e:
            logger.error(f"Error during paper rolling execution: {e}")
            try:
                self.gripper.open()
                self.controller.home()
            except:
                pass
            return False
