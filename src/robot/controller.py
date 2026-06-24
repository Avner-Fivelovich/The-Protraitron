import os
import yaml
import time
import math
import numpy as np

# -------------------------------------------------------------
# Import loggers and shared robot control utilities
# -------------------------------------------------------------
from src.common.logger import get_logger
from src.common.config_utils import load_config_from_yaml
from src.common.robot_utils import wait_for_motion_complete, probe_surface_point

try:
    import rtde_control
    import rtde_receive
except ImportError:
    # Fallback for offline testing or compilation phase
    rtde_control = None
    rtde_receive = None

# Initialize controller logger
logger = get_logger("UR5eController")

class UR5eController:
    """
    Manages connections and command executions for the physical UR5e arm,
    using real-time force compliance along the approach axis.
    """
    def __init__(self, ip_address: str, calibration_path: str = "config/calibration.yaml", marker_config_path: str = "config/marker.yaml"):
        # -------------------------------------------------------------
        # Initialization and configuration loading
        # -------------------------------------------------------------
        self.ip = ip_address
        self.calibration_path = calibration_path
        self.marker_config_path = marker_config_path
        self.rtde_c = None
        self.rtde_r = None
        
        # Calibration placeholders
        self.p0_joints = None
        self.p0_pose = None
        self.p1 = None
        self.width = 0.19
        self.height = 0.27
        
        # Load calibration parameters and default compliance configs
        self.load_calibration()
        self.cfg = load_config_from_yaml(self.marker_config_path)
        
    def load_calibration(self):
        """
        Reads starting hover joint angles, tool poses, and reference corner P1 from calibration.yaml.
        """
        if not os.path.exists(self.calibration_path):
            logger.warning(f"Calibration file {self.calibration_path} not found. Running in uncalibrated mode.")
            return
            
        try:
            with open(self.calibration_path, "r") as f:
                data = yaml.safe_load(f)
            
            self.p0_joints = data.get("p0_joints")
            self.p0_pose = data.get("p0_pose")
            self.p1 = data.get("p1")
            self.width = data.get("width", 0.19)
            self.height = data.get("height", 0.27)
            
            if self.p1:
                logger.success("Calibration loaded successfully from config.")
            else:
                logger.warning("Calibration point P1 is missing in config.")
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            
    def connect(self) -> bool:
        """
        Initializes socket interfaces to communicate with the UR5e controller.
        """
        if not rtde_control or not rtde_receive:
            logger.error("Cannot connect: ur_rtde library is not installed.")
            return False
            
        try:
            logger.info(f"Connecting to UR5e at {self.ip}...")
            self.rtde_c = rtde_control.RTDEControlInterface(self.ip)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip)
            logger.success("UR5e Control & Receive interfaces connected.")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.rtde_c = None
            self.rtde_r = None
            return False
            
    def disconnect(self):
        """
        Safely shuts down RTDE communication interfaces.
        """
        logger.info("Shutting down robot sockets...")
        if self.rtde_c:
            try:
                self.rtde_c.disconnect()
            except:
                pass
            self.rtde_c = None
        if self.rtde_r:
            try:
                self.rtde_r.disconnect()
            except:
                pass
            self.rtde_r = None
        logger.info("Robot sockets disconnected.")
        
    def home(self):
        """
        Moves configuration linearly back to the starting hover pose P0 using moveL.
        """
        if not self.rtde_c:
            logger.error("Robot not connected.")
            return
            
        if self.p0_pose is None:
            logger.error("Homing failed: No p0_pose stored in calibration.")
            return
            
        logger.info("Homing to Bottom-Left starting hover pose (P0) using moveL...")
        self.rtde_c.moveL(self.p0_pose, 0.1, 0.2)
        logger.success("Robot arrived at P0.")
        
    def execute_drawing_path(self, strokes_2d: list, speed: float = 0.05, accel: float = 0.1, blend_radius: float = 0.002, draw_depth_offset: float = 0.0):
        """
        Iterates over strokes, positioning to 1cm hover plane, probing, and executing 
        trajectory under X-axis compliance mode.
        """
        if not self.rtde_c:
            logger.error("Robot not connected.")
            return
            
        if not self.p0_pose or not self.p1:
            logger.error("Calibration parameters not loaded. Execute calibration first.")
            return
            
        # Tool orientation is aligned normal to the paper (stored at P0 manual alignment)
        rx, ry, rz = self.p0_pose[3:]
        
        # X hover plane is 1 cm above P1 X coordinate (positive direction points away from board)
        X_hover = self.p1[0] + 0.01
        
        for idx, stroke in enumerate(strokes_2d):
            if len(stroke) == 0:
                continue
                
            logger.info(f"Drawing stroke {idx + 1}/{len(strokes_2d)} containing {len(stroke)} waypoints...")
            
            # 1. Move to the safe hover pose above the start of the stroke in the Y-Z plane
            x0, y0 = stroke[0]
            hover_pose = self._move_to_hover(x0, y0, X_hover, rx, ry, rz)
            
            # 2. Probe surface point along X-axis at this Y-Z coordinate
            logger.info("Probing surface point for stroke start...")
            p_contact = probe_surface_point(self.rtde_c, self.rtde_r, hover_pose, self.cfg)
            if not p_contact:
                logger.error(f"Probing failed for stroke {idx + 1}. Skipping this stroke.")
                continue
                
            # Apply drawing depth offset to contact X pose (decreasing X pushes closer to board)
            x_draw = p_contact[0] - draw_depth_offset
            
            # 3. Settle and activate force compliance
            self._enable_force_compliance()
            
            # 4. Stream and execute stroke waypoints
            self._draw_stroke_trajectory(stroke, x_draw, rx, ry, rz, speed, accel, blend_radius)
            
            # 5. Disable force compliance and retract to hover plane
            x_last, y_last = stroke[-1]
            self._stop_compliance_and_retract(x_last, y_last, X_hover, rx, ry, rz)
            
        # Return to safe starting joint configuration
        self.home()

    def _move_to_hover(self, x_canvas: float, y_canvas: float, x_hover: float, rx: float, ry: float, rz: float) -> list:
        """
        Moves the robot linearly in Y-Z to a safe hover position above the stroke start point.
        """
        Y_start = self.p1[1] + x_canvas * self.width
        Z_start = self.p1[2] + y_canvas * self.height
        hover_pose = [x_hover, Y_start, Z_start, rx, ry, rz]
        
        logger.info(f"Moving to hover pose: {[round(c, 4) for c in hover_pose[:3]]}")
        self.rtde_c.moveL(hover_pose, 0.05, 0.1)
        return hover_pose

    def _enable_force_compliance(self):
        """
        Activates force compliance mode along the Base X-axis and waits to stabilize.
        """
        logger.info("Waiting for robot to settle...")
        time.sleep(self.cfg['settle_sleep'])
        
        tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        tool_selection_vector = [1, 0, 0, 0, 0, 0] # Compliance only on Base X
        tool_wrench = [self.cfg['forward_force'], 0.0, 0.0, 0.0, 0.0, 0.0]
        
        self.rtde_c.forceModeSetDamping(self.cfg['force_damping'])
        self.rtde_c.forceMode(
            tool_task_frame, 
            tool_selection_vector, 
            tool_wrench, 
            self.cfg['force_type_tool'], 
            self.cfg['force_limits']
        )
        logger.info("Force mode activated. Stabilizing...")
        
        stabilize_start = time.time()
        while time.time() - stabilize_start < self.cfg['stabilize_timeout']:
            actual_forces = self.rtde_r.getActualTCPForce()
            logger.info(f"Stabilizing... Live Force: Fx={actual_forces[0]:.2f}N")
            time.sleep(self.cfg['stabilize_poll_interval'])

    def _draw_stroke_trajectory(self, stroke: list, x_draw: float, rx: float, ry: float, rz: float, speed: float, accel: float, blend_radius: float):
        """
        Streams and executes a stroke trajectory under compliance force control.
        """
        path = []
        for i in range(1, len(stroke)):
            xi, yi = stroke[i]
            Y_i = self.p1[1] + xi * self.width
            Z_i = self.p1[2] + yi * self.height
            
            # Blend radius must be 0.0 for the last point to stop execution cleanly
            current_blend = blend_radius if i < (len(stroke) - 1) else 0.0
            waypoint = [x_draw, Y_i, Z_i, rx, ry, rz, speed, accel, current_blend]
            path.append(waypoint)
            
        if path:
            logger.info(f"Streaming stroke path with {len(path)} waypoints...")
            self.rtde_c.moveL(path)

    def _stop_compliance_and_retract(self, x_canvas: float, y_canvas: float, x_hover: float, rx: float, ry: float, rz: float):
        """
        Disables compliance mode and retracts the pen linearly back to the hover plane.
        """
        logger.info("Stopping force compliance and retracting...")
        self.rtde_c.forceModeStop()
        time.sleep(0.1)
        
        Y_last = self.p1[1] + x_canvas * self.width
        Z_last = self.p1[2] + y_canvas * self.height
        retract_pose = [x_hover, Y_last, Z_last, rx, ry, rz]
        
        self.rtde_c.moveL(retract_pose, 0.05, 0.1)
