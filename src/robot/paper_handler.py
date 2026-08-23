import time
import math
import os
from src.common.logger import get_logger
from src.common.config_utils import load_config_from_yaml
from src.robot.robotiq_gripper import RobotiqGripper

logger = get_logger("PaperHandler")

class PaperHandler:
    def __init__(self, rtde_c, rtde_r, config_path="config/paper_manipulation.yaml"):
        self.rtde_c = rtde_c
        self.rtde_r = rtde_r
        self.config_path = config_path
        self.config = load_config_from_yaml(self.config_path)
        self.gripper = RobotiqGripper()
        self.gripper_connected = False
        
        # Load parameters
        self.speeds = self.config.get("speeds", {})
        self.default_speed = self.speeds.get("default_move", 0.1)
        self.cut_movement_speed = self.speeds.get("cut_movement_speed", 0.05)
        self.pull_paper_speed = self.speeds.get("pull_paper_speed", 0.1)
        self.fetch_paper_speed = self.speeds.get("fetch_paper_speed", 0.05)
        self.handover_speed = self.speeds.get("handover_speed", 0.15)
        
        self.force_thresholds = self.config.get("force_thresholds", {})
        self.handover_pull = self.force_thresholds.get("handover_pull", 5.0)
        
        self.straightening_offset_y = self.config.get("straightening_offset_y", 0.02)
        
        self.gripper_cfg = self.config.get("gripper", {})
        self.gripper_port = self.gripper_cfg.get("port", 63352)
        self.gripper_open_pos = self.gripper_cfg.get("open_pos", 127)
        self.gripper_close_pos = self.gripper_cfg.get("close_pos", 255)
        self.gripper_speed = self.gripper_cfg.get("speed", 127)
        self.gripper_force = self.gripper_cfg.get("force", 127)
        self.gripper_sleep = self.gripper_cfg.get("sleep_time", 0.5)
        
        self.timing_cfg = self.config.get("timing", {})
        self.pull_timeout = self.timing_cfg.get("wait_pull_timeout", 30.0)
        self.force_check_interval = self.timing_cfg.get("force_check_interval", 0.1)
        
        self.locs = self.config.get("locations", {})
        
    def connect_gripper(self, ip=None):
        if ip is None:
            # Fallback to server.yaml or default
            server_config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "server.yaml")
            try:
                import yaml
                with open(server_config_path, "r") as f:
                    cfg = yaml.safe_load(f)
                    ip = cfg.get("hardware", {}).get("robot_ip", "192.168.57.101")
            except Exception:
                ip = "192.168.57.101"
                
        if not self.gripper_connected:
            try:
                logger.info(f"Connecting to Robotiq gripper at {ip}:{self.gripper_port}...")
                self.gripper.connect(ip, self.gripper_port)
                if not self.gripper.is_active():
                    self.gripper.activate()
                self.gripper_connected = True
                logger.success("Gripper connected and ready.")
            except Exception as e:
                logger.error(f"Failed to connect to gripper: {e}")

    def disconnect(self):
        if self.gripper_connected:
            try:
                logger.info("Disconnecting Robotiq gripper...")
                self.gripper.disconnect()
                self.gripper_connected = False
                logger.success("Gripper disconnected.")
            except Exception as e:
                logger.error(f"Failed to disconnect gripper: {e}")

    def execute_paper_swap(self):
        """Executes the full paper manipulation sequence."""
        if not self.locs:
            logger.error("No locations found in config. Please run calibration first.")
            return False
            
        logger.info("Starting paper swap sequence...")
        
        self.connect_gripper()
        
    def pick_up(self, object_name):
        self._move_to("safe_tools", allow_joint=True)
        self._move_to(f"above_{object_name}", allow_joint=True)
        self._move_to(object_name, allow_joint=True)
        self._close_gripper()
        self._move_to(f"above_{object_name}", allow_joint=True)
        self._move_to("safe_tools", allow_joint=True)
        if object_name == "marker_dock":
            self._move_to("safe_paper", allow_joint=False)

    def drop(self, object_name):
        self._move_to("safe_tools", allow_joint=False)
        self._move_to(f"above_{object_name}", allow_joint=True)
        self._move_to(object_name, allow_joint=True)
        self._open_gripper()
        self._move_to(f"above_{object_name}", allow_joint=True)
        self._move_to("safe_tools", allow_joint=False)

    def execute_stamping(self):
        self._move_to("safe_tools", allow_joint=True)
        self._move_to("above_stamp", allow_joint=True)
        self._move_to("stamp", allow_joint=True)
        self._close_gripper()
        self._move_to("above_stamp", allow_joint=True)
        self._move_to("above_ink", allow_joint=True)
        self._move_to("ink", allow_joint=True)
        self._move_to("above_ink", allow_joint=True)
        self._move_to("safe_tools", allow_joint=True)
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("stamping_pos", allow_joint=True)
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("safe_tools", allow_joint=True)
        self._move_to("above_stamp", allow_joint=True)
        self._move_to("stamp", allow_joint=True)
        self._open_gripper()
        self._move_to("above_stamp", allow_joint=True)
        self._move_to("safe_tools", allow_joint=True)

    def execute_cut(self):
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("cut_start_pos", allow_joint=True)
        
        start_target = self.locs.get("cut_start_pos")
        end_target = self.locs.get("cut_end_pos")
        p_start = start_target.get("pose") if isinstance(start_target, dict) else start_target
        p_end = end_target.get("pose") if isinstance(end_target, dict) else end_target
        
        if self.rtde_c:
            from src.common.robot_utils import probe_surface_point
            from src.common.config_utils import load_config_from_yaml
            probe_cfg = load_config_from_yaml("config/marker.yaml")
            
            logger.info("Probing surface for cutting...")
            p_contact = probe_surface_point(self.rtde_c, self.rtde_r, p_start, probe_cfg)
            if not p_contact:
                logger.error("Failed to probe surface for cutting. Aborting cut.")
                self._move_to("safe_paper", allow_joint=True)
                return
                
            p_start = list(p_contact)
            p_end = list(p_end)
            p_end[0] = p_contact[0]
            
            # Activate force compliance to push the knife into the paper
            cut_force = self.config.get("cut_force", 15.0)
            cut_damping = self.config.get("cut_damping", 0.005)
            tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            tool_selection_vector = [1, 0, 0, 0, 0, 0] # Compliance only on Base X
            tool_wrench = [-cut_force, 0.0, 0.0, 0.0, 0.0, 0.0]
            limits = [0.15, 0.15, 0.15, 0.2, 0.2, 0.2]
            
            logger.info(f"Activating force mode for cutting (Force: {cut_force}N, Damping: {cut_damping})...")
            self.rtde_c.forceModeSetDamping(cut_damping)
            self.rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, 2, limits)
            time.sleep(0.5)
            
            if p_start and p_end and len(p_start) == 6 and len(p_end) == 6:
                dist = math.sqrt(sum((b - a)**2 for a, b in zip(p_start[:3], p_end[:3])))
                speed = self.cut_movement_speed
                total_time = dist / speed if speed > 0 else 0
                DT = 0.002
                num_steps = int(total_time / DT)
                
                try:
                    for step in range(num_steps + 1):
                        t_start = self.rtde_c.initPeriod()
                        frac = min(1.0, (step * DT) / total_time) if total_time > 0 else 1.0
                        wp = [a + (b - a) * frac for a, b in zip(p_start, p_end)]
                        self.rtde_c.servoL(wp, 0.0, 0.0, DT, 0.03, 2000)
                        self.rtde_c.waitPeriod(t_start)
                finally:
                    self.rtde_c.servoStop()
            else:
                self._move_to("cut_end_pos", speed=self.cut_movement_speed, allow_joint=False)
                
            logger.info("Stopping force mode...")
            self.rtde_c.forceModeStop()
            time.sleep(0.1)
            
        else:
            self._move_to("cut_end_pos", speed=self.cut_movement_speed, allow_joint=False)
            
        self._move_to("safe_paper", allow_joint=True)

    def hand_to_user(self):
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("lower_magnet_start", allow_joint=True)
        self._close_gripper()
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("lower_magnet_park", allow_joint=True)
        self._open_gripper()
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("safe_tools", allow_joint=True)
        self._move_to("cut_paper_grab", allow_joint=True)
        self._move_to("cut_paper_pull_dest", speed=self.pull_paper_speed, allow_joint=False)
        self._move_to("safe_midpoint_to_user", allow_joint=True)
        self._move_to("user_handover_location", allow_joint=True)
        self._wait_for_human_pull()
        self._open_gripper()
        self._move_to("user_handover_location", allow_joint=True)
        self._move_to("safe_tools", allow_joint=True)
        self._move_to("safe_paper", allow_joint=True)
        
        # Park the upper magnet so it is out of the way for pulling new paper
        self._move_to("upper_magnet_end", allow_joint=True)
        self._close_gripper()
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("upper_magnet_park", allow_joint=True)
        self._open_gripper()
        self._move_to("safe_paper", allow_joint=True)

    def put_new_paper(self):
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("fresh_paper_grab", allow_joint=False)
        self._close_gripper()
        self._move_to("fresh_paper_pull_dest", speed=self.fetch_paper_speed, allow_joint=False)
        self._open_gripper()
        self._move_to("upper_magnet_park", allow_joint=True)
        self._close_gripper()
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("upper_magnet_start", allow_joint=True)
        self._open_gripper()
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("lower_magnet_park", allow_joint=True)
        self._close_gripper()
        self._move_to("safe_paper", allow_joint=True)
        self._move_to("paper_straighten_start", allow_joint=True)
        self._move_to("lower_magnet_start", allow_joint=False)
        self._open_gripper()
        self._move_to("safe_paper", allow_joint=True)

    def _move_to(self, location_name, speed=None, allow_joint=False):
        if speed is None:
            speed = self.default_speed
        
        target = self.locs.get(location_name)
        if not target:
            raise ValueError(f"Invalid or missing location: {location_name}")
            
        logger.info(f"Moving to {location_name}...")
        if isinstance(target, dict):
            pose = target.get("pose")
            joints = target.get("joints")
            if not pose or len(pose) < 6:
                raise ValueError(f"Invalid hybrid pose for: {location_name}")
            target_pose = pose
            
            if allow_joint and joints and len(joints) >= 6:
                logger.info(f"Using moveJ (arc motion) for {location_name} to avoid singularities...")
                self.rtde_c.moveJ(joints, speed*2, speed*4)
            else:
                self.rtde_c.moveL(pose, speed, speed * 2)
        else:
            if len(target) < 6:
                raise ValueError(f"Invalid or missing location: {location_name}")
            target_pose = target
            self.rtde_c.moveL(target_pose, speed, speed * 2)
        
        # Live validation
        timeout = 10.0
        start = time.time()
        while time.time() - start < timeout:
            if self.rtde_r is None:
                break
            curr = self.rtde_r.getActualTCPPose()
            dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr[:3], target_pose[:3])))
            if dist < 0.005:  # 5mm tolerance for validation
                break
            time.sleep(0.01)
        else:
            if self.rtde_r is not None:
                logger.warning(f"Warning: Move to {location_name} timed out or did not reach target accurately. (Off by {dist*1000:.1f}mm)")
        
    def _open_gripper(self):
        if self.gripper_connected:
            self.gripper.move_and_wait_for_pos(self.gripper_open_pos, self.gripper_speed, self.gripper_force) # Fully open (adjust based on actual gripper max open)
            time.sleep(self.gripper_sleep)
            
    def _close_gripper(self):
        if self.gripper_connected:
            self.gripper.move_and_wait_for_pos(self.gripper_close_pos, self.gripper_speed, self.gripper_force) # Fully closed
            time.sleep(self.gripper_sleep)
            
    def _wait_for_human_pull(self, timeout=None):
        if timeout is None:
            timeout = self.pull_timeout
        logger.info(f"Waiting for human pull (timeout: {timeout}s)...")
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                logger.error("Timeout reached while waiting for human pull.")
                return False
                
            actual_forces = self.rtde_r.getActualTCPForce()
            # Check Z axis force (assuming pulling down/away triggers Z or vector magnitude)
            force_mag = math.sqrt(actual_forces[0]**2 + actual_forces[1]**2 + actual_forces[2]**2)
            if force_mag > self.handover_pull:
                logger.info(f"Pull detected: {force_mag:.2f}N")
                return True
            time.sleep(self.force_check_interval)

    def _force_move(self, location_name, speed=None):
        if speed is None:
            speed = self.default_speed
        
        target = self.locs.get(location_name)
        if not target:
            raise ValueError(f"Invalid or missing location: {location_name}")
            
        if isinstance(target, dict):
            target_pose = target.get("pose")
        else:
            target_pose = target
            
        if not target_pose or len(target_pose) < 6:
            raise ValueError(f"Invalid location pose for: {location_name}")
            
        logger.info(f"Force moving to {location_name}...")
        
        tool_task_frame = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        tool_selection_vector = [1, 0, 0, 0, 0, 0] # Compliance only on Base X
        # Negative X points towards the drawing board (standard Portraitron setup)
        tool_wrench = [-15.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        force_type = 2
        force_limits = [2.0, 2.0, 1.5, 1.0, 1.0, 1.0]
        
        try:
            self.rtde_c.forceModeSetDamping(0.005)
            self.rtde_c.forceMode(tool_task_frame, tool_selection_vector, tool_wrench, force_type, force_limits)
            time.sleep(0.5) # Wait for force stabilization
            self.rtde_c.moveL(target_pose, speed, speed * 2)
            
            # Live validation
            timeout = 10.0
            start = time.time()
            while time.time() - start < timeout:
                if self.rtde_r is None:
                    break
                curr = self.rtde_r.getActualTCPPose()
                dist = math.sqrt(sum((a - b)**2 for a, b in zip(curr[:3], target_pose[:3])))
                if dist < 0.005:
                    break
                time.sleep(0.01)
            else:
                if self.rtde_r is not None:
                    logger.warning(f"Warning: Force move to {location_name} timed out or did not reach target accurately. (Off by {dist*1000:.1f}mm)")
        finally:
            self.rtde_c.forceModeStop()
            time.sleep(0.1)

    def execute_paper_swap(self):
        """Executes the full paper manipulation sequence by chaining atomic functions."""
        if not self.locs:
            logger.error("No locations found in config. Please run calibration first.")
            return False
            
        logger.info("Starting full paper swap sequence using atomic functions...")
        self.connect_gripper()
        
        try:
            # 1. Store Marker (drop it)
            self.drop("marker_dock")
            
            # 2. Grab Knife & Cut
            self.pick_up("knife_dock")
            self.execute_cut()
            self.drop("knife_dock")
            
            # 3. Handover Drawing
            self.hand_to_user()
            
            # 4. Load New Paper
            self.put_new_paper()
            
            # 5. Grab Marker
            self.pick_up("marker_dock")
            
            # 6. Go Home
            self._move_to("draw_home", allow_joint=True)
            
            logger.info("Sequence completed successfully.")
            return True
            
        except Exception as e:
            logger.error(f"Sequence execution failed: {e}")
            return False
