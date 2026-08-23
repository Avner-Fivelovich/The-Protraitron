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
        self.gripper_open_pos = self.gripper_cfg.get("open_pos", 0)
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
                self.gripper.activate()
                self.gripper_connected = True
                logger.success("Gripper connected and activated.")
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
        
    def get_partial_sequences(self):
        return {
            "Store Marker & Grab Magnet 1": [
                ("move", "safe_paper"),
                ("move", "safe_tools"),
                ("move", "above_dock"),
                ("move", "marker_dock"),
                ("gripper", "open"),
                ("move", "above_dock"),
                ("move", "safe_tools"),
                ("move", "safe_paper"),
                ("move", "magnet_1_start"),
                ("gripper", "close"),
                ("move", "safe_paper"),
                ("move", "magnet_1_temp"),
                ("gripper", "open"),
                ("move", "safe_paper")
            ],
            "Grab Knife & Cut Paper": [
                ("move", "safe_paper"),
                ("move", "safe_tools"),
                ("move", "above_knife"),
                ("move", "knife_dock"),
                ("gripper", "close"),
                ("move", "above_knife"),
                ("move", "safe_tools"),
                ("move", "safe_paper"),
                ("move", "start_cut_location"),
                ("force_cut", ("end_cut_location", self.cut_movement_speed)),
                ("move", "safe_paper"),
                ("move", "safe_tools"),
                ("move", "above_knife"),
                ("move", "knife_dock"),
                ("gripper", "open"),
                ("move", "safe_tools"),
                ("move", "safe_paper")
            ],
            "Handover Drawing": [
                ("move", "safe_paper"),
                ("move", "paper_location"),
                ("gripper", "close"),
                ("move_speed", ("pull_paper_location", self.pull_paper_speed)),
                ("move", "safe_paper"),
                ("move_speed", ("safe_midpoint_to_user", self.handover_speed)),
                ("move_speed", ("user_handing_location", self.handover_speed)),
                ("wait_pull", self.pull_timeout),
                ("gripper", "open"),
                ("move_speed", ("safe_midpoint_to_user", self.handover_speed)),
                ("move", "safe_paper")
            ],
            "Load New Paper": [
                ("move", "safe_paper"),
                ("move", "magnet_2_start"),
                ("gripper", "close"),
                ("move", "safe_paper"),
                ("move", "magnet_2_temp"),
                ("gripper", "open"),
                ("move", "safe_paper"),
                ("move", "new_paper_location"),
                ("gripper", "close"),
                ("move_speed", ("paper_pull_end", self.fetch_paper_speed)),
                ("gripper", "open"),
                ("move", "safe_paper")
            ],
            "Replace Magnets & Grab Marker": [
                ("move", "safe_paper"),
                ("move", "magnet_2_temp"),
                ("gripper", "close"),
                ("move", "safe_paper"),
                ("move", "magnet_2_start"),
                ("gripper", "open"),
                ("move", "safe_paper"),
                ("move", "magnet_1_temp"),
                ("gripper", "close"),
                ("move", "safe_paper"),
                ("move", "below_magnet_2_start"),
                ("force_straighten", "magnet_1_start"),
                ("gripper", "open"),
                ("move", "safe_paper"),
                ("move", "safe_tools"),
                ("move", "above_dock"),
                ("move", "marker_dock"),
                ("gripper", "close"),
                ("move", "above_dock"),
                ("move", "safe_tools"),
                ("move", "safe_paper"),
                ("move", "P0")
            ]
        }

    def execute_paper_swap(self):
        """Executes the full paper manipulation sequence."""
        if not self.locs:
            logger.error("No locations found in config. Please run calibration first.")
            return False
            
        logger.info("Starting full paper swap sequence...")
        
        self.connect_gripper()
        
        # Stitch all partial sequences together for the full swap
        sequence = []
        for seq_name, seq_actions in self.get_partial_sequences().items():
            sequence.extend(seq_actions)
            
        return self.execute_sequence(sequence)

    def execute_sequence(self, sequence):
        try:
            for action in sequence:
                act_type = action[0]
                if act_type == "move":
                    self._move_to(action[1])
                elif act_type == "move_speed":
                    self._move_to(action[1][0], speed=action[1][1])
                elif act_type == "gripper":
                    if action[1] == "open":
                        self._open_gripper()
                    else:
                        self._close_gripper()
                elif act_type == "wait_pull":
                    success = self._wait_for_human_pull(timeout=action[1])
                    if not success:
                        logger.warning("Human pull timeout. Aborting sequence.")
                        self._open_gripper()
                        return False
                elif act_type == "force_cut":
                    self._force_move(action[1][0], speed=action[1][1])
                elif act_type == "force_straighten":
                    self._force_move(action[1], speed=self.default_speed)
                    
            logger.info("Sequence completed successfully.")
            return True
            
        except Exception as e:
            logger.error(f"Sequence execution failed: {e}")
            return False

    def _move_to(self, location_name, speed=None):
        if speed is None:
            speed = self.default_speed
        
        target = self.locs.get(location_name)
        if not target or len(target) < 6:
            raise ValueError(f"Invalid or missing location: {location_name}")
            
        logger.info(f"Moving to {location_name}...")
        self.rtde_c.moveL(target, speed, speed * 2)
        
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
        if not target or len(target) < 6:
            raise ValueError(f"Invalid or missing location: {location_name}")
            
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
            self.rtde_c.moveL(target, speed, speed * 2)
        finally:
            self.rtde_c.forceModeStop()
            time.sleep(0.1)
