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
        self.cut_speed = self.speeds.get("cut_pull", 0.3)
        self.fetch_speed = self.speeds.get("fetch_pull", 0.05)
        
        self.force_thresholds = self.config.get("force_thresholds", {})
        self.handover_pull = self.force_thresholds.get("handover_pull", 5.0)
        
        self.straightening_offset_y = self.config.get("straightening_offset_y", 0.02)
        
        self.gripper_cfg = self.config.get("gripper", {})
        self.gripper_port = self.gripper_cfg.get("port", 63352)
        self.gripper_open_pos = self.gripper_cfg.get("open_pos", 0)
        self.gripper_close_pos = self.gripper_cfg.get("close_pos", 255)
        self.gripper_speed = self.gripper_cfg.get("speed", 255)
        self.gripper_force = self.gripper_cfg.get("force", 255)
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
        
        sequence = [
            ("move", "pen_dock"),
            ("gripper", "open"),
            ("move", "magnet_1_start"),
            ("gripper", "close"),
            ("move", "magnet_1_temp"),
            ("gripper", "open"),
            ("move", "magnet_2_start"),
            ("gripper", "close"),
            ("move", "magnet_2_temp"),
            ("gripper", "open"),
            ("move", "paper_grab"),
            ("gripper", "close"),
            ("move_speed", ("cut_trajectory", self.cut_speed)),
            ("move", "handover_target"),
            ("wait_pull", self.pull_timeout),
            ("gripper", "open"),
            ("move", "new_paper_roll"),
            ("gripper", "close"),
            ("move_speed", ("paper_pull_end", self.fetch_speed)),
            ("gripper", "open"),
            ("move", "magnet_2_temp"),
            ("gripper", "close"),
            ("move", "magnet_2_start"),
            ("gripper", "open"),
            ("move", "magnet_1_temp"),
            ("gripper", "close"),
            ("straighten", "magnet_1"),
            ("move", "pen_dock"),
            ("gripper", "close"),
        ]
        
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
                elif act_type == "straighten":
                    self._return_and_straighten_magnet_1()
                    
            logger.info("Paper swap sequence complete. Ready for next drawing.")
            return True
            
        except Exception as e:
            logger.error(f"Paper swap sequence failed: {e}")
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

    def _return_and_straighten_magnet_1(self):
        logger.info("Returning and straightening Magnet 1...")
        target = self.locs.get("magnet_1_start")
        if not target:
            raise ValueError("magnet_1_start not set")
            
        # Move just below target (assume Y is the direction of straightening)
        # We will move according to config offset in Y (or relative to the board)
        straighten_start = list(target)
        straighten_start[1] -= self.straightening_offset_y 
        
        self.rtde_c.moveL(straighten_start, self.default_speed, self.default_speed * 2)
        
        # Slide to target
        self.rtde_c.moveL(target, self.fetch_speed, self.fetch_speed * 2)
        self._open_gripper()
