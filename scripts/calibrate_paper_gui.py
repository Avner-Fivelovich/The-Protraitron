#!/usr/bin/env python3
import os
import sys
import time
import yaml
import argparse
import threading
import tkinter as tk
from tkinter import ttk

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.logger import get_logger

logger = get_logger("PaperCalibrationGUI")

try:
    import rtde_control
    import rtde_receive
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    sys.exit(1)

from src.robot.robotiq_gripper import RobotiqGripper

CENTRAL_CONFIG_PATH = "config/server.yaml"

def load_central_config():
    if os.path.exists(CENTRAL_CONFIG_PATH):
        with open(CENTRAL_CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

CENTRAL_CONFIG = load_central_config()
GUI_CONFIG = CENTRAL_CONFIG.get("calibration_gui", {})
OUTPUT_PATH = GUI_CONFIG.get("output_path", "config/paper_manipulation.yaml")

class CalibrationGUI:
    def __init__(self, master, robot_ip):
        self.master = master
        self.robot_ip = robot_ip
        self.master.title("Paper Manipulation Calibration")
        self.master.geometry(GUI_CONFIG.get("window_geometry", "500x600"))
        
        self.rtde_c = None
        self.rtde_r = None
        self.gripper = RobotiqGripper()
        self.motion_lock = threading.Lock()
        self.is_moving = False
        self.freedrive_active = False
        self.closing = False
        self.keepalive_started = False
        
        self.config = self.load_config()
        self.locations = self.config.get("locations", {})
        
        self.stages = [
            ("pen_dock", "Location of the pen dock (to store pen)"),
            ("magnet_1_start", "Current/original location of Magnet 1"),
            ("magnet_1_temp", "Temporary parking location for Magnet 1"),
            ("magnet_2_start", "Current/original location of Magnet 2"),
            ("magnet_2_temp", "Temporary parking location for Magnet 2"),
            ("paper_grab", "Location to grab the completed drawing edge"),
            ("cut_trajectory", "End location after pulling downward to cut paper"),
            ("handover_target", "Target location to wait for human to pull the paper"),
            ("new_paper_roll", "Location to grab the edge of the fresh paper roll"),
            ("paper_pull_end", "End location after pulling the fresh paper across the board")
        ]
        self.current_stage_idx = 0
        
        self.create_widgets()
        
        # We no longer auto-connect on startup to guarantee the window renders instantly
        # without being blocked by the C++ ur_rtde GIL lock on network timeouts.
        self.status_var.set("Not Connected (Click Reconnect)")
        self.reconnect_btn.config(state="normal")
        
    def load_config(self):
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        if os.path.exists(OUTPUT_PATH):
            with open(OUTPUT_PATH, 'r') as f:
                return yaml.safe_load(f) or {}
        
        manip_defaults = CENTRAL_CONFIG.get("paper_manipulation_defaults", {})
        return {
            "speeds": manip_defaults.get("speeds", {"default_move": 0.1, "cut_pull": 0.3, "fetch_pull": 0.05}),
            "force_thresholds": manip_defaults.get("force_thresholds", {"handover_pull": 5.0}),
            "locations": {}
        }
        
    def save_config(self):
        self.config["locations"] = self.locations
        with open(OUTPUT_PATH, 'w') as f:
            yaml.safe_dump(self.config, f, default_flow_style=False)
        logger.info(f"Saved config to {OUTPUT_PATH}")

    def _keepalive_loop(self):
        while not self.closing:
            time.sleep(1.0)
            if self.rtde_c and self.rtde_r:
                try:
                    if not self.freedrive_active and not self.is_moving:
                        if not self.rtde_r.isProtectiveStopped() and not self.rtde_r.isEmergencyStopped():
                            if not self.rtde_c.isProgramRunning():
                                logger.info("Keepalive: Restoring RTDE script on controller...")
                                self.rtde_c.reuploadScript()
                except Exception:
                    pass

    def connect_robot(self):
        try:
            logger.info(f"Connecting to UR5e RTDE at {self.robot_ip}...")
            self.rtde_c = rtde_control.RTDEControlInterface(self.robot_ip)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.robot_ip)
            gripper_port = CENTRAL_CONFIG.get("hardware", {}).get("gripper_port", 63352)
            logger.info(f"Connecting to Gripper at {self.robot_ip}:{gripper_port}...")
            self.gripper.connect(self.robot_ip, gripper_port)
            self.gripper.activate()
            self.status_var.set("Connected to UR5e & Gripper")
            self.freedrive_btn.config(state="normal")
            if not self.keepalive_started:
                self.keepalive_started = True
                threading.Thread(target=self._keepalive_loop, daemon=True).start()
            logger.info("Successfully connected to UR5e & Gripper.")
        except Exception as e:
            logger.error(f"Robot connection failed: {e}")
            self.status_var.set(f"Connection Failed: {e}")
        finally:
            self.reconnect_btn.config(state="normal")
                
    def trigger_reconnect(self):
        self.status_var.set("Connecting...")
        self.reconnect_btn.config(state="disabled")
        threading.Thread(target=self.connect_robot, daemon=True).start()

    def toggle_freedrive(self):
        if not self.rtde_c:
            return
        try:
            if not self.freedrive_active:
                if not self.rtde_c.isProgramRunning():
                    self.rtde_c.reuploadScript()
                    time.sleep(0.3)
                self.rtde_c.freedriveMode()
                self.freedrive_active = True
                self.freedrive_btn.config(text="🛑 Stop Freedrive", bg="#ffcccc")
                self.status_var.set("Freedrive ON: Move arm by hand!")
                logger.info("Freedrive mode enabled (move robot arm by hand).")
            else:
                self.rtde_c.endFreedriveMode()
                self.freedrive_active = False
                self.freedrive_btn.config(text="🖐 Freedrive (Hand-Guide)", bg="#e0e0e0")
                self.status_var.set("Connected to UR5e & Gripper")
                logger.info("Freedrive mode disabled.")
        except Exception as e:
            logger.error(f"Error toggling freedrive: {e}")
            self.status_var.set(f"Freedrive Error: {e}")
            
    def create_widgets(self):
        status_frame = tk.Frame(self.master)
        status_frame.pack(pady=5)
        
        self.status_var = tk.StringVar(value="Connecting...")
        tk.Label(status_frame, textvariable=self.status_var, fg="blue").pack(side="left", padx=5)
        
        self.reconnect_btn = tk.Button(status_frame, text="Reconnect", command=self.trigger_reconnect, state="disabled")
        self.reconnect_btn.pack(side="left", padx=5)

        self.freedrive_btn = tk.Button(status_frame, text="🖐 Freedrive (Hand-Guide)", command=self.toggle_freedrive, bg="#e0e0e0", state="disabled")
        self.freedrive_btn.pack(side="left", padx=5)
        
        self.stage_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        tk.Label(self.master, textvariable=self.stage_var, font=("Helvetica", 16, "bold")).pack(pady=5)
        tk.Label(self.master, textvariable=self.desc_var).pack(pady=5)
        
        self.update_stage_display()
        
        btn_frame = tk.Frame(self.master)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Back", command=self.prev_stage).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Save Point & Next", command=self.save_point, bg="green").grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="Skip", command=self.next_stage).grid(row=0, column=2, padx=5)
        
        move_settings = GUI_CONFIG.get("movement_settings", {})
        self.speed_var = tk.DoubleVar(value=move_settings.get("default_speed", 0.03))
        self.step_var = tk.DoubleVar(value=move_settings.get("default_step", 0.005))
        self.accel_var = tk.DoubleVar(value=move_settings.get("default_accel", 0.10))

        settings_frame = tk.LabelFrame(self.master, text="Movement Settings")
        settings_frame.pack(pady=5, padx=10, fill="x")
        
        tk.Label(settings_frame, text="Speed (m/s):").grid(row=0, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.speed_var, from_=0.005, to=0.15, resolution=0.005, orient="horizontal").grid(row=0, column=1, padx=5, sticky="ew")
        
        tk.Label(settings_frame, text="Accel (m/s²):").grid(row=1, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.accel_var, from_=0.01, to=0.5, resolution=0.01, orient="horizontal").grid(row=1, column=1, padx=5, sticky="ew")
        
        tk.Label(settings_frame, text="Step Size (m):").grid(row=2, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.step_var, from_=0.001, to=0.05, resolution=0.001, orient="horizontal").grid(row=2, column=1, padx=5, sticky="ew")

        # Interpolation mode selector
        self.move_mode_var = tk.StringVar(value="joint_ik")
        mode_frame = tk.Frame(settings_frame)
        mode_frame.grid(row=3, column=0, columnspan=2, pady=4, sticky="w")
        tk.Label(mode_frame, text="Mode:").pack(side="left", padx=5)
        tk.Radiobutton(mode_frame, text="Joint IK (Safe / No Stops)", variable=self.move_mode_var, value="joint_ik").pack(side="left", padx=5)
        tk.Radiobutton(mode_frame, text="Linear (moveL)", variable=self.move_mode_var, value="linear").pack(side="left", padx=5)
        
        settings_frame.grid_columnconfigure(1, weight=1)

        jog_frame = tk.LabelFrame(self.master, text="Jogging Keyboard (W/S=X, A/D=Y, Q/E=Z, F=Freedrive)")
        jog_frame.pack(pady=10, padx=10, fill="x")
        
        axes = [(0, "X", 1), (1, "Y", 2), (2, "Z", 3)]
        for axis_idx, axis_name, col_offset in axes:
            tk.Button(jog_frame, text=f"+{axis_name}", command=lambda idx=axis_idx: self.jog(idx, 1)).grid(row=0, column=col_offset, padx=5, pady=5)
            tk.Button(jog_frame, text=f"-{axis_name}", command=lambda idx=axis_idx: self.jog(idx, -1)).grid(row=1, column=col_offset, padx=5, pady=5)
        
        grip_frame = tk.LabelFrame(self.master, text="Gripper Controls (O=Open, C=Close, G=Toggle)")
        grip_frame.pack(pady=10, padx=10, fill="x")
        
        grip_settings_conf = GUI_CONFIG.get("gripper_settings", {})
        self.grip_speed_var = tk.IntVar(value=grip_settings_conf.get("default_speed", 100))
        self.grip_force_var = tk.IntVar(value=grip_settings_conf.get("default_force", 100))
        self.grip_step_var = tk.IntVar(value=grip_settings_conf.get("default_step", 5))
        
        # Gripper Settings
        grip_settings = tk.Frame(grip_frame)
        grip_settings.pack(fill="x", padx=5, pady=5)
        tk.Label(grip_settings, text="Speed (%):").grid(row=0, column=0, sticky="e")
        tk.Scale(grip_settings, variable=self.grip_speed_var, from_=1, to=100, orient="horizontal").grid(row=0, column=1, sticky="ew")
        tk.Label(grip_settings, text="Force (%):").grid(row=1, column=0, sticky="e")
        tk.Scale(grip_settings, variable=self.grip_force_var, from_=1, to=100, orient="horizontal").grid(row=1, column=1, sticky="ew")
        tk.Label(grip_settings, text="Step (%):").grid(row=2, column=0, sticky="e")
        tk.Scale(grip_settings, variable=self.grip_step_var, from_=1, to=50, orient="horizontal").grid(row=2, column=1, sticky="ew")
        grip_settings.grid_columnconfigure(1, weight=1)

        # Gripper Actions
        grip_actions = tk.Frame(grip_frame)
        grip_actions.pack(pady=8)
        
        tk.Button(grip_actions, text="🟢 Open Gripper (O)", command=lambda: self.async_grip(0), bg="#d4edda", font=("Helvetica", 10, "bold"), padx=8, pady=4).pack(side="left", padx=5)
        tk.Button(grip_actions, text="🔴 Close Gripper (C)", command=lambda: self.async_grip(100), bg="#f8d7da", font=("Helvetica", 10, "bold"), padx=8, pady=4).pack(side="left", padx=5)
        tk.Button(grip_actions, text="Jog Open (-)", command=lambda: self.jog_gripper(-1)).pack(side="left", padx=5)
        tk.Button(grip_actions, text="Jog Close (+)", command=lambda: self.jog_gripper(1)).pack(side="left", padx=5)
        
        # Keyboard bindings (multiplier 1 for positive, -1 for negative)
        for key, axis, direction in [('w', 0, 1), ('s', 0, -1), ('a', 1, 1), ('d', 1, -1), ('q', 2, 1), ('e', 2, -1)]:
            self.master.bind(f'<{key}>', lambda e, a=axis, d=direction: self.jog(a, d))
        self.master.bind('<space>', lambda e: self.save_point())
        self.master.bind('<f>', lambda e: self.toggle_freedrive())
        self.master.bind('<o>', lambda e: self.async_grip(0))
        self.master.bind('<c>', lambda e: self.async_grip(100))
        self.master.bind('<g>', lambda e: self.toggle_gripper())
        
    def toggle_gripper(self):
        if not self.gripper or not self.gripper.is_connected():
            logger.warning("Gripper attempted toggle, but is not connected.")
            return
        cur_pos = self.gripper.get_current_position()
        # If currently open (<=50), close it; otherwise open it
        target = 100 if cur_pos <= 128 else 0
        self.async_grip(target)

    def async_grip(self, target_percent):
        if not self.gripper or not self.gripper.is_connected():
            logger.warning("Gripper attempted move, but is not connected.")
            return
        speed = int((self.grip_speed_var.get() / 100.0) * 255)
        force = int((self.grip_force_var.get() / 100.0) * 255)
        target = int((target_percent / 100.0) * 255)
        logger.info(f"Commanding Gripper to {target_percent}% (pos {target}, speed {speed}, force {force})")
        threading.Thread(target=self.gripper.move_and_wait_for_pos, args=(target, speed, force), daemon=True).start()
        
    def jog_gripper(self, direction):
        if not self.gripper or not self.gripper.is_connected():
            logger.warning("Gripper attempted jog, but is not connected.")
            return
        try:
            current_pos = self.gripper.get_current_position()
            current_percent = (current_pos / 255.0) * 100.0
            step = self.grip_step_var.get()
            target_percent = max(0, min(100, current_percent + (direction * step)))
            self.async_grip(target_percent)
        except Exception as e:
            logger.error(f"Failed to read/jog gripper: {e}")

    def jog(self, axis, direction):
        if not self.rtde_c or not self.rtde_r:
            logger.warning("Jog attempted, but robot is not connected.")
            return

        if self.is_moving:
            return

        threading.Thread(target=self._execute_jog, args=(axis, direction), daemon=True).start()

    def _execute_jog(self, axis, direction):
        with self.motion_lock:
            if self.is_moving:
                return
            self.is_moving = True
            try:
                if self.freedrive_active:
                    self.toggle_freedrive()

                if self.rtde_r.isProtectiveStopped():
                    logger.warning("Robot in Protective Stop! Clear/unlock it on PolyScope teach pendant.")
                    self.status_var.set("Protective Stop! Unlock on Pendant")
                    return

                if self.rtde_r.isEmergencyStopped():
                    logger.warning("Robot in Emergency Stop! Release E-stop.")
                    self.status_var.set("Emergency Stop active!")
                    return

                # If the RTDE script terminated on the robot, re-upload it
                if not self.rtde_c.isProgramRunning():
                    logger.info("RTDE control script is not running on controller. Re-uploading script...")
                    self.status_var.set("Re-uploading script to robot...")
                    try:
                        self.rtde_c.reuploadScript()
                        time.sleep(0.3)
                        self.status_var.set("Connected to UR5e & Gripper")
                    except Exception as err:
                        logger.error(f"Failed to reupload script: {err}")
                        self.status_var.set("Script error - Check Pendant")
                        return

                pose = self.rtde_r.getActualTCPPose()
                step = self.step_var.get()
                speed = self.speed_var.get()
                accel = self.accel_var.get()

                move_dist = direction * step
                axis_name = ["X", "Y", "Z"][axis]

                pose[axis] += move_dist
                logger.info(f"Jogging {axis_name}-axis by {move_dist:+.4f}m at speed {speed}m/s, accel {accel}m/s²")

                try:
                    if not self.rtde_c.isPoseWithinSafetyLimits(pose):
                        logger.warning(f"Target pose {pose} violates safety limits. Move aborted.")
                        self.status_var.set("Move rejected: Safety limits")
                        return
                except Exception:
                    pass

                mode = self.move_mode_var.get()
                if mode == "joint_ik":
                    # moveJ_IK operates smoothly in joint space avoiding Cartesian straight-line singularities
                    success = self.rtde_c.moveJ_IK(pose, speed=0.3, acceleration=0.4)
                else:
                    success = self.rtde_c.moveL(pose, speed, accel)

                if not success and not self.rtde_r.isProtectiveStopped() and not self.rtde_r.isEmergencyStopped():
                    # If failed because script stopped during idle, re-upload and retry once immediately
                    logger.info("Retrying motion with fresh script upload...")
                    try:
                        self.rtde_c.reuploadScript()
                        time.sleep(0.5)
                        pose = self.rtde_r.getActualTCPPose()
                        pose[axis] += move_dist
                        if mode == "joint_ik":
                            success = self.rtde_c.moveJ_IK(pose, speed=0.3, acceleration=0.4)
                        else:
                            success = self.rtde_c.moveL(pose, speed, accel)
                    except Exception as retry_err:
                        logger.error(f"Retry failed: {retry_err}")

                if not success:
                    if self.rtde_r.isProtectiveStopped():
                        logger.error("Robot entered Protective Stop during move!")
                        self.status_var.set("Protective Stop! Unlock on Pendant")
                    else:
                        logger.error(f"Motion command returned False! Target pose: {pose}")
                        self.status_var.set("Move failed (near singularity or unreachable)")
                else:
                    self.status_var.set("Connected to UR5e & Gripper")
            except Exception as e:
                logger.error(f"Exception during jog: {e}", exc_info=True)
                self.status_var.set(f"Jog Error: {e}")
            finally:
                self.is_moving = False
        
    def update_stage_display(self):
        if self.current_stage_idx < len(self.stages):
            key, desc = self.stages[self.current_stage_idx]
            self.stage_var.set(f"Step {self.current_stage_idx+1}/{len(self.stages)}: {key}")
            self.desc_var.set(desc)
        else:
            self.stage_var.set("Calibration Complete!")
            self.desc_var.set("You can close this window.")
            
    def save_point(self):
        if self.current_stage_idx >= len(self.stages):
            return
        if self.rtde_r:
            key = self.stages[self.current_stage_idx][0]
            pose = self.rtde_r.getActualTCPPose()
            self.locations[key] = pose
            self.save_config()
            logger.info(f"Saved {key}: {pose}")
        self.next_stage()
        
    def next_stage(self):
        self.current_stage_idx += 1
        self.update_stage_display()

    def prev_stage(self):
        if self.current_stage_idx > 0:
            self.current_stage_idx -= 1
            self.update_stage_display()
        
    def on_closing(self):
        self.closing = True
        if self.freedrive_active and self.rtde_c:
            try:
                self.rtde_c.endFreedriveMode()
            except Exception:
                pass
        for obj in (self.rtde_c, self.rtde_r, self.gripper if self.gripper and self.gripper.socket else None):
            if obj: obj.disconnect()
        self.master.destroy()

if __name__ == "__main__":
    logger.info("Parsing arguments...")
    parser = argparse.ArgumentParser(description="Paper Manipulation Calibration GUI")
    default_ip = CENTRAL_CONFIG.get("hardware", {}).get("robot_ip", "192.168.57.100")
    parser.add_argument("--ip", type=str, default=default_ip, help="Robot IP Address")
    args = parser.parse_args()

    logger.info("Initializing Tkinter root window...")
    try:
        root = tk.Tk()
    except Exception as e:
        logger.critical(f"Failed to initialize Tkinter: {e}")
        sys.exit(1)
        
    logger.info("Building GUI components...")
    app = CalibrationGUI(root, args.ip)
    
    logger.info("Registering window protocols...")
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    logger.info("Starting Tkinter main loop (Window should appear now)...")
    root.mainloop()
