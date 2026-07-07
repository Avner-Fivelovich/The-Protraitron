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
        self.dryrun = False
        
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
        if self.dryrun:
            logger.success("[DRY RUN] Bypassing connection to physical robot.")
            # Set default p1 and p0_pose if not loaded from calibration file
            if self.p1 is None:
                self.p1 = [-0.8706, 0.1412, 0.2553]
            if self.p0_pose is None:
                self.p0_pose = [-0.8676, 0.1412, 0.2553, 0.0, 0.0, 0.0]
            return True

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
        if self.dryrun:
            logger.info("[DRY RUN] Bypassing socket shutdown.")
            return

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
        if self.dryrun:
            logger.info("[DRY RUN] Homing bypassed.")
            return

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
        if self.dryrun:
            logger.info("Dry run active. Plotting the expected drawing...")
            self.plot_expected_drawing(strokes_2d)
            return

        if not self.rtde_c:
            logger.error("Robot not connected.")
            return
            
        if not self.p0_pose or not self.p1:
            logger.error("Calibration parameters not loaded. Execute calibration first.")
            return
            
        # Tool orientation is aligned normal to the paper (stored at P0 manual alignment)
        rx, ry, rz = self.p0_pose[3:]
        
        # X hover plane is 5 mm above P1 X coordinate (positive direction points away from board)
        X_hover = self.p1[0] + 0.005
        
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
        # Negative X points towards the drawing board, so command a negative force to push into the surface
        tool_wrench = [-self.cfg['forward_force'], 0.0, 0.0, 0.0, 0.0, 0.0]
        
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
        Streams and executes a stroke trajectory under compliance force control,
        logging live forces and coordinates at 10Hz during motion.
        Uses a real-time servoL loop to keep forceMode active and compliant.
        """
        # Convert stroke normalized points to physical Y-Z coordinates
        points = []
        for pt in stroke:
            Y = self.p1[1] + pt[0] * self.width
            Z = self.p1[2] + pt[1] * self.height
            points.append(np.array([Y, Z]))
            
        # Compute cumulative distance along the path
        dists = [np.linalg.norm(points[i] - points[i-1]) for i in range(1, len(points))]
        cum_dists = [0.0] + list(np.cumsum(dists))
        total_dist = cum_dists[-1]
        
        if total_dist <= 0.0:
            logger.warning("Stroke trajectory has zero length. Skipping execution.")
            return
            
        # Calculate execution duration based on configured slide speed
        total_time = total_dist / speed
        DT = 0.002  # 500Hz loop rate
        num_steps = int(total_time / DT)
        
        logger.info(f"Executing compliant slide: distance={total_dist*100:.2f} cm, speed={speed*100:.2f} cm/s, time={total_time:.2f}s...")
        
        tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        tool_selection_vector = [1, 0, 0, 0, 0, 0] # Compliance only on Base X
        # Negative X points towards the drawing board, so command a negative force to push into the surface
        tool_wrench = [-self.cfg['forward_force'], 0.0, 0.0, 0.0, 0.0, 0.0]
        
        # Pre-generate target trajectory points at 500Hz
        raw_wp_list = []
        for step in range(num_steps + 1):
            t = step * DT
            d = min(t * speed, total_dist)
            
            # Interpolate Y and Z along the path
            Y_target = np.interp(d, cum_dists, [pt[0] for pt in points])
            Z_target = np.interp(d, cum_dists, [pt[1] for pt in points])
            raw_wp_list.append((Y_target, Z_target))
            
        # Apply moving average smoothing (boxcar filter) based on blend_radius
        if blend_radius > 0.0:
            window_size = int(blend_radius / speed / DT)
            # Ensure window_size is at least 3 for a valid smoothing filter
            if window_size >= 3 and len(raw_wp_list) > window_size:
                pad_size = window_size // 2
                kernel = np.ones(window_size) / window_size
                
                y_arr = np.array([wp[0] for wp in raw_wp_list])
                z_arr = np.array([wp[1] for wp in raw_wp_list])
                
                # Pad edges to prevent boundary shrink artifacts
                y_padded = np.pad(y_arr, pad_size, mode='edge')
                z_padded = np.pad(z_arr, pad_size, mode='edge')
                
                y_smooth = np.convolve(y_padded, kernel, mode='valid')[:len(raw_wp_list)]
                z_smooth = np.convolve(z_padded, kernel, mode='valid')[:len(raw_wp_list)]
                
                raw_wp_list = list(zip(y_smooth, z_smooth))
                logger.info(f"Trajectory smoothed using blend_radius={blend_radius*1000:.1f}mm (moving average window={window_size} steps).")

        try:
            for step, (Y_target, Z_target) in enumerate(raw_wp_list):
                # Target pose in base frame
                wp = [x_draw, Y_target, Z_target, rx, ry, rz]
                
                # Keep compliance mode active and stream position
                self.rtde_c.forceMode(
                    tool_task_frame, 
                    tool_selection_vector, 
                    tool_wrench, 
                    self.cfg['force_type_tool'], 
                    self.cfg['force_limits']
                )
                self.rtde_c.servoL(wp, 0.0, 0.0, DT, 0.03, 2000)
                
                # Log telemetry at 10Hz (every 50 steps at 500Hz)
                if step % 50 == 0 or step == len(raw_wp_list) - 1:
                    actual_pose = self.rtde_r.getActualTCPPose()
                    actual_forces = self.rtde_r.getActualTCPForce()
                    x_canvas = (actual_pose[1] - self.p1[1]) / self.width if self.width != 0 else 0.0
                    y_canvas = (actual_pose[2] - self.p1[2]) / self.height if self.height != 0 else 0.0
                    
                    logger.info(
                        f"Drawing... TCP: [{actual_pose[0]:.4f}, {actual_pose[1]:.4f}, {actual_pose[2]:.4f}] | "
                        f"Canvas: ({x_canvas:.3f}, {y_canvas:.3f}) | "
                        f"Forces: Fx={actual_forces[0]:.2f}N, Fy={actual_forces[1]:.2f}N, Fz={actual_forces[2]:.2f}N"
                    )
                time.sleep(DT)
        finally:
            # Stop servo motion cleanly
            self.rtde_c.servoStop()

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

    def plot_expected_drawing(self, strokes_2d: list):
        """
        Plots the expected drawing strokes using matplotlib.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib is required for dryrun plotting. Please install it using: pip install matplotlib")
            return
            
        fig, ax = plt.subplots(figsize=(5, 5 * (self.height / self.width) if self.width != 0 else 7))
        for stroke in strokes_2d:
            if not stroke:
                continue
            stroke_np = np.array(stroke)
            ax.plot(stroke_np[:, 0], stroke_np[:, 1], 'b-', linewidth=2)
            
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        ax.set_title("Expected Drawing Preview (Dry Run)")
        ax.set_xlabel("Canvas X (Normalized)")
        ax.set_ylabel("Canvas Y (Normalized)")
        ax.grid(True)
        plt.show()
