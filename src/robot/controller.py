import os
import yaml
import time
import math
import numpy as np
import datetime

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

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
    def __init__(self, ip_address: str, calibration_path: str = "config/paper_manipulation.yaml", marker_config_path: str = "config/marker.yaml"):
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
        
        # Load configs
        self.cfg = load_config_from_yaml(self.marker_config_path)
        self.load_calibration()
        
    def load_calibration(self):
        """
        Reads starting hover joint angles, tool poses, and reference corner P1 from paper_manipulation.yaml.
        """
        if not os.path.exists(self.calibration_path):
            logger.warning(f"Calibration file {self.calibration_path} not found. Running in uncalibrated mode.")
            return
        try:
            with open(self.calibration_path, "r") as f:
                data = yaml.safe_load(f) or {}
            
            self.p0_pose = data.get("locations", {}).get("draw_home")
            if isinstance(self.p0_pose, dict):
                self.p0_joints = self.p0_pose.get("joints", data.get("p0_joints"))
                self.p0_pose = self.p0_pose.get("pose")
            else:
                self.p0_joints = data.get("p0_joints")
            
            self.p1 = data.get("p1")
            self.p2 = data.get("p2")
            
            # Prioritize marker.yaml canvas dimensions if paper_manipulation.yaml doesn't explicitly override
            self.width = data.get("width", self.cfg.get("canvas_width", 0.19))
            self.height = data.get("height", self.cfg.get("canvas_height", 0.27))
            
            if self.p1:
                logger.success("Calibration loaded successfully from config.")
            else:
                logger.warning("Calibration point P1 is missing in config.")
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            self.p1 = None
            self.p2 = None

        if self.p1 is None:
            # Set default p1 and p0_pose if not loaded from calibration file
            self.p1 = [-0.8706, 0.1412, 0.2553]
            self.p0_pose = [-0.8676, 0.1412, 0.2553, 0.0, 3.1415, 0.0]
            logger.warning("Using default hardcoded calibration point (P1).")
            
    def get_x_surface(self, y_target: float) -> float:
        """
        Calculates the expected surface X depth (plane tilt) at a given Y coordinate
        using linear interpolation between P1 (left edge) and P2 (right edge).
        """
        if not self.p1:
            return 0.0
            
        x1 = self.p1[0]
        y1 = self.p1[1]
        
        # If P2 is not calibrated, assume the board is perfectly flat along X
        if not self.p2 or self.width <= 0:
            return x1
            
        x2 = self.p2[0]
        y2 = self.p2[1]
        
        # Linear interpolation for X based on Y target
        x_surface = x1 + ((y_target - y1) / self.width) * (x2 - x1)
        return x_surface

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
            flags = (
                rtde_control.RTDEControlInterface.FLAG_DISABLE_REMOTE_CONTROL_CHECK
                | rtde_control.RTDEControlInterface.FLAG_USE_EXT_UR_CAP
            )
            try:
                self.rtde_c = rtde_control.RTDEControlInterface(self.ip, flags=flags, ur_cap_port=50002)
            except Exception as ext_err:
                logger.warning(f"External URCap port unavailable ({ext_err}), falling back to standard RTDE...")
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
        Moves configuration back to the starting hover pose P0.
        Uses moveJ if joint angles are available, otherwise moveL.
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
            
        try:
            logger.info("Homing to Bottom-Left starting hover pose (P0) using moveL...")
            self.rtde_c.moveL(self.p0_pose, self.cfg.get('home_speed', 0.1), self.cfg.get('home_accel', 0.2))
            logger.success("Robot arrived at P0.")
        except Exception as e:
            logger.error(f"Homing failed (possibly disconnected): {e}")
        
    def log_event(self, event_name: str):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        logger.info(f"[TIMESTAMP] {now_str} - Event: {event_name}")

    def execute_drawing_path(self, strokes_2d: list, speed: float = 0.05, accel: float = 0.1, blend_radius: float = 0.002, draw_depth_offset: float = 0.0, progress_callback = None, plot_path_prefix: str = None, connections: list = None, original_strokes: list = None):
        """
        Iterates over strokes, positioning to 1cm hover plane, probing, and executing 
        trajectory under X-axis compliance mode. Passes original_strokes to preview plotting if in dryrun mode.
        """
        self.log_event("Drawing execution loop started")
        if self.dryrun:
            logger.info("Dry run active. Simulating/plotting expected drawing...")
            self.log_event("Dry run simulation started")
            if progress_callback:
                for idx in range(len(strokes_2d)):
                    if progress_callback(idx + 1, len(strokes_2d)) == False:
                        logger.warning("Simulated drawing cancelled via progress callback.")
                        break
                    time.sleep(0.05) # short sleep to show animation progress
            
            # Format the output display paths
            display_png = f"{plot_path_prefix}.png" if plot_path_prefix else "plots/expected_drawing_preview.png"
            display_pdf = f"{plot_path_prefix}.pdf" if plot_path_prefix else "plots/expected_drawing_preview.pdf"
            self.log_event(f"Saving expected drawing preview to {display_png} and {display_pdf}")
            
            self.plot_expected_drawing(strokes_2d, plot_path_prefix=plot_path_prefix, connections=connections, original_strokes=original_strokes)
            self.log_event("Dry run simulation completed")
            self.log_event("Drawing execution loop completed successfully")
            return

        if not self.rtde_c:
            logger.error("Robot not connected.")
            self.log_event("Drawing execution loop failed: Robot not connected")
            return
            
        if not self.p0_pose or not self.p1:
            logger.error("Calibration parameters not loaded. Execute calibration first.")
            self.log_event("Drawing execution loop failed: Calibration parameters missing")
            return
            
        # Tool orientation is aligned normal to the paper (stored at P0 manual alignment)
        rx, ry, rz = self.p0_pose[3:]
        
        # X hover plane above P1 X coordinate (positive direction points away from board)
        X_hover = self.p1[0] + self.cfg.get('hover_distance', 0.005)
        
        total_strokes = len(strokes_2d)
        for idx, stroke in enumerate(strokes_2d):
            if len(stroke) == 0:
                continue
                
            if progress_callback:
                if progress_callback(idx + 1, len(strokes_2d)) == False:
                    logger.warning("Drawing execution cancelled via progress callback.")
                    break
                
            # Calculate physical length of the current stroke (in meters)
            pts = np.array(stroke)
            pts_phys = pts * np.array([self.width, self.height])
            stroke_length_m = float(np.sum(np.linalg.norm(pts_phys[1:] - pts_phys[:-1], axis=1))) if len(stroke) > 1 else 0.0
            
            # Calculate transition air distance from the end of the previous stroke to start of this stroke
            air_dist_m = 0.0
            if idx > 0 and len(strokes_2d[idx-1]) > 0:
                p_prev_last = np.array(strokes_2d[idx-1][-1]) * np.array([self.width, self.height])
                p_curr_first = np.array(stroke[0]) * np.array([self.width, self.height])
                air_dist_m = float(np.linalg.norm(p_curr_first - p_prev_last))

            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Started (Length: {stroke_length_m:.4f} m / {stroke_length_m*100:.2f} cm, Air transition: {air_dist_m:.4f} m / {air_dist_m*100:.2f} cm)")
            
            # 1. Move to the safe hover pose above the start of the stroke in the Y-Z plane
            x0, y0 = stroke[0]
            Y_start = self.p1[1] + x0 * self.width
            X_hover_dynamic = self.get_x_surface(Y_start) + self.cfg.get('hover_distance', 0.005)
            
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Safe hover move started")
            hover_pose = self._move_to_hover(x0, y0, X_hover_dynamic, rx, ry, rz)
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Safe hover move completed")
            
            # 2. Probe surface point along X-axis at this Y-Z coordinate
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Probing surface started")
            p_contact = probe_surface_point(self.rtde_c, self.rtde_r, hover_pose, self.cfg)
            if not p_contact:
                logger.error(f"Probing failed or robot disconnected at stroke {idx + 1}. Aborting drawing sequence.")
                self.log_event(f"Stroke {idx + 1}/{total_strokes} - Probing failed. Aborting.")
                break
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Surface contact established")
                
            # Apply drawing depth offset to contact X pose (decreasing X pushes closer to board)
            x_draw = p_contact[0] - draw_depth_offset
            
            # 3. Settle and activate force compliance
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Force compliance enabled")
            self._enable_force_compliance()
            
            # 4. Stream and execute stroke waypoints
            start_draw_time = time.time()
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Drawing trajectory started")
            self._draw_stroke_trajectory(stroke, x_draw, rx, ry, rz, speed, accel, blend_radius)
            elapsed_draw_time = time.time() - start_draw_time
            avg_speed = (stroke_length_m / elapsed_draw_time) if elapsed_draw_time > 0 else 0.0
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Drawing trajectory completed (Duration: {elapsed_draw_time:.2f}s, Avg speed: {avg_speed*100:.2f} cm/s)")
            
            # 5. Disable force compliance and retract to hover plane
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Compliance disabled and retract started")
            x_last, y_last = stroke[-1]
            Y_end = self.p1[1] + x_last * self.width
            X_hover_dynamic_end = self.get_x_surface(Y_end) + self.cfg.get('hover_distance', 0.005)
            self._stop_compliance_and_retract(x_last, y_last, X_hover_dynamic_end, rx, ry, rz)
            self.log_event(f"Stroke {idx + 1}/{total_strokes} - Compliance disabled and retract completed")
            
        # Return to safe starting joint configuration
        self.log_event("Robot returning to home configuration")
        self.home()
        self.log_event("Drawing execution loop completed successfully")

    def _move_to_hover(self, x_canvas: float, y_canvas: float, x_hover: float, rx: float, ry: float, rz: float) -> list:
        """
        Moves the robot linearly in Y-Z to a safe hover position above the stroke start point.
        """
        Y_start = self.p1[1] + x_canvas * self.width
        Z_start = self.p1[2] + y_canvas * self.height
        hover_pose = [x_hover, Y_start, Z_start, rx, ry, rz]
        
        logger.info(f"Moving to hover pose: {[round(c, 4) for c in hover_pose[:3]]}")
        self.rtde_c.moveL(hover_pose, self.cfg.get('hover_speed', 0.05), self.cfg.get('hover_accel', 0.1))
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
        DT = self.cfg.get('dt', 0.002)  # 500Hz loop rate
        num_steps = int(total_time / DT)
        
        logger.info(f"Executing compliant slide: distance={total_dist*100:.2f} cm, speed={speed*100:.2f} cm/s, time={total_time:.2f}s...")
        
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
                # Initialize period starting time for real-time control (500Hz)
                t_start = self.rtde_c.initPeriod()
                
                # Target pose in base frame
                wp = [x_draw, Y_target, Z_target, rx, ry, rz]
                
                # Stream position using servoL
                self.rtde_c.servoL(wp, 0.0, 0.0, DT, self.cfg.get('servo_lookahead', 0.03), self.cfg.get('servo_gain', 2000))
                
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
                
                # Wait to maintain real-time period
                self.rtde_c.waitPeriod(t_start)
        finally:
            # Stop servo motion cleanly
            self.rtde_c.servoStop()

    def _stop_compliance_and_retract(self, x_canvas: float, y_canvas: float, x_hover: float, rx: float, ry: float, rz: float):
        """
        Disables compliance mode and retracts the pen linearly back to the hover plane.
        """
        logger.info("Stopping force compliance and retracting...")
        self.rtde_c.forceModeStop()
        time.sleep(self.cfg.get('stop_sleep', 0.1))
        
        Y_last = self.p1[1] + x_canvas * self.width
        Z_last = self.p1[2] + y_canvas * self.height
        retract_pose = [x_hover, Y_last, Z_last, rx, ry, rz]
        
        self.rtde_c.moveL(retract_pose, self.cfg.get('retract_speed', 0.05), self.cfg.get('retract_accel', 0.1))

    def plot_expected_drawing(self, strokes_2d: list, plot_path_prefix: str = None, connections: list = None, original_strokes: list = None):
        """
        Plots the expected drawing strokes using matplotlib and saves the plots
        to the specified path/directory. Highlights merged connection lines in red
        and overlays a stats card showing stroke optimizations.
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("matplotlib is required for dryrun plotting. Please install it using: pip install matplotlib")
            return
            
        fig, ax = plt.subplots(figsize=(5.5, 5.5 * (self.height / self.width) if self.width != 0 else 7))
        
        # Plot each stroke
        for idx, stroke in enumerate(strokes_2d):
            if not stroke:
                continue
            stroke_np = np.array(stroke)
            # Plot stroke path in blue
            ax.plot(stroke_np[:, 0], stroke_np[:, 1], 'b-', linewidth=2.5, label='Drawing stroke' if idx == 0 else "")
            
        # Highlight connection lines in red dashed style
        if connections:
            for c_idx, (p1, p2) in enumerate(connections):
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r--', linewidth=2.5, label='Merged Connection' if c_idx == 0 else "")
        
        # Compute path metrics
        def _get_path_metrics(strokes):
            draw_d = 0.0
            for s in strokes:
                if len(s) > 1:
                    pts = np.array(s) * np.array([self.width, self.height])
                    draw_d += np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1))
            
            air_d = 0.0
            cleaned = [s for s in strokes if len(s) > 0]
            if len(cleaned) > 1:
                for i in range(len(cleaned) - 1):
                    p_end = np.array(cleaned[i][-1]) * np.array([self.width, self.height])
                    p_start = np.array(cleaned[i+1][0]) * np.array([self.width, self.height])
                    air_d += np.linalg.norm(p_end - p_start)
            return draw_d, air_d

        opt_draw_d, opt_air_d = _get_path_metrics(strokes_2d)
        opt_total_d = opt_draw_d + opt_air_d
        opt_lifts = len(strokes_2d)

        # ── Rich Stats Card Overlay ───────────────────────────────────────────
        info_lines = []
        info_lines.append(r"$\bf{DRAWING\ STATS}$")
        info_lines.append(f"Pen Lifts (Strokes): {opt_lifts}")

        if original_strokes:
            orig_draw_d, orig_air_d = _get_path_metrics(original_strokes)
            orig_lifts = len([s for s in original_strokes if len(s) > 0])
            saved_lifts = orig_lifts - opt_lifts
            if saved_lifts > 0:
                info_lines.append(f"  (Saved {saved_lifts} lifts via merging)")
            
            info_lines.append(f"Drawing Dist: {opt_draw_d:.2f}m ({opt_draw_d*100:.0f}cm)")
            info_lines.append(f"Air Distance: {opt_air_d:.2f}m ({opt_air_d*100:.0f}cm)")
            
            air_saved = orig_air_d - opt_air_d
            if orig_air_d > 0 and air_saved > 0:
                pct = air_saved / orig_air_d * 100
                info_lines.append(f"  (Saved {air_saved:.2f}m | {pct:.1f}% air via TSP)")
            info_lines.append(f"Total Distance: {opt_total_d:.2f}m ({opt_total_d*100:.0f}cm)")
        else:
            info_lines.append(f"Drawing Dist: {opt_draw_d:.2f}m ({opt_draw_d*100:.0f}cm)")
            info_lines.append(f"Air Distance: {opt_air_d:.2f}m ({opt_air_d*100:.0f}cm)")
            info_lines.append(f"Total Distance: {opt_total_d:.2f}m ({opt_total_d*100:.0f}cm)")

        textstr = "\n".join(info_lines)
        props = dict(boxstyle='round,pad=0.5', facecolor='#f8f9fa', alpha=0.9, edgecolor='#cccccc', linewidth=1)
        ax.text(1.05, 0.98, textstr, transform=ax.transAxes, fontsize=8.5,
                verticalalignment='top', bbox=props, fontfamily='sans-serif')

        # Show legend if we had labels
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(handles, labels, loc='lower left', bbox_to_anchor=(1.05, 0.0), framealpha=0.9)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        ax.set_title("Expected Drawing Preview (Dry Run)")
        ax.set_xlabel("Canvas X (Normalized)")
        ax.set_ylabel("Canvas Y (Normalized)")
        ax.grid(True, linestyle=':', alpha=0.5)
        
        # Determine saving paths
        if plot_path_prefix:
            png_path = f"{plot_path_prefix}.png"
            pdf_path = f"{plot_path_prefix}.pdf"
            # Ensure the directory exists
            os.makedirs(os.path.dirname(plot_path_prefix), exist_ok=True)
        else:
            os.makedirs("plots", exist_ok=True)
            png_path = "plots/expected_drawing_preview.png"
            pdf_path = "plots/expected_drawing_preview.pdf"
        
        try:
            plt.savefig(png_path, dpi=300, bbox_inches='tight')
            plt.savefig(pdf_path, bbox_inches='tight')
            logger.info(f"Saved expected drawing preview plots to '{png_path}' and '{pdf_path}'")
        except Exception as e:
            logger.error(f"Failed to save preview plots: {e}")
            
        # Display the plot
        plt.show()
