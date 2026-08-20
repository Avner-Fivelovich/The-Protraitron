#!/usr/bin/env python3
import os
import sys
import yaml
import argparse
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

OUTPUT_PATH = "config/paper_manipulation.yaml"
STEP_SIZE = 0.005 # 5mm

class CalibrationGUI:
    def __init__(self, master, robot_ip):
        self.master = master
        self.robot_ip = robot_ip
        self.master.title("Paper Manipulation Calibration")
        self.master.geometry("500x600")
        
        self.rtde_c = None
        self.rtde_r = None
        self.gripper = RobotiqGripper()
        
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
        
        # Delay the connection thread by 500ms so the Tkinter mainloop has time to draw the window first
        # (The C++ ur_rtde library sometimes holds the Python GIL while connecting, which blocks rendering)
        import threading
        self.master.after(500, lambda: threading.Thread(target=self.connect_robot, daemon=True).start())
        
    def load_config(self):
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        if os.path.exists(OUTPUT_PATH):
            with open(OUTPUT_PATH, 'r') as f:
                return yaml.safe_load(f) or {}
        return {
            "speeds": {"default_move": 0.1, "cut_pull": 0.3, "fetch_pull": 0.05},
            "force_thresholds": {"handover_pull": 5.0},
            "locations": {}
        }
        
    def save_config(self):
        self.config["locations"] = self.locations
        with open(OUTPUT_PATH, 'w') as f:
            yaml.safe_dump(self.config, f, default_flow_style=False)
        logger.info(f"Saved config to {OUTPUT_PATH}")

    def connect_robot(self):
        try:
            self.rtde_c = rtde_control.RTDEControlInterface(self.robot_ip)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.robot_ip)
            self.gripper.connect(self.robot_ip, 63352)
            self.gripper.activate()
            self.status_var.set("Connected to UR5e & Gripper")
        except Exception as e:
            self.status_var.set(f"Connection Failed: {e}")
            
    def create_widgets(self):
        self.status_var = tk.StringVar(value="Connecting...")
        tk.Label(self.master, textvariable=self.status_var, fg="blue").pack(pady=5)
        
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
        
        self.speed_var = tk.DoubleVar(value=0.25)
        self.step_var = tk.DoubleVar(value=0.005)

        settings_frame = tk.LabelFrame(self.master, text="Movement Settings")
        settings_frame.pack(pady=5, padx=10, fill="x")
        
        tk.Label(settings_frame, text="Speed (m/s):").grid(row=0, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.speed_var, from_=0.01, to=0.5, resolution=0.01, orient="horizontal").grid(row=0, column=1, padx=5, sticky="ew")
        
        tk.Label(settings_frame, text="Step Size (m):").grid(row=1, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.step_var, from_=0.001, to=0.05, resolution=0.001, orient="horizontal").grid(row=1, column=1, padx=5, sticky="ew")
        settings_frame.grid_columnconfigure(1, weight=1)

        jog_frame = tk.LabelFrame(self.master, text="Jogging Keyboard (W/S=X, A/D=Y, Q/E=Z)")
        jog_frame.pack(pady=10, padx=10, fill="x")
        
        axes = [(0, "X", 1), (1, "Y", 2), (2, "Z", 3)]
        for axis_idx, axis_name, col_offset in axes:
            tk.Button(jog_frame, text=f"+{axis_name}", command=lambda idx=axis_idx: self.jog(idx, 1)).grid(row=0, column=col_offset, padx=5, pady=5)
            tk.Button(jog_frame, text=f"-{axis_name}", command=lambda idx=axis_idx: self.jog(idx, -1)).grid(row=1, column=col_offset, padx=5, pady=5)
        
        grip_frame = tk.LabelFrame(self.master, text="Gripper")
        grip_frame.pack(pady=10, padx=10, fill="x")
        tk.Button(grip_frame, text="Open", command=lambda: self.gripper.move_and_wait_for_pos(0, 255, 255)).pack(side="left", padx=10, pady=5)
        tk.Button(grip_frame, text="Close", command=lambda: self.gripper.move_and_wait_for_pos(255, 255, 255)).pack(side="left", padx=10, pady=5)
        
        # Keyboard bindings (multiplier 1 for positive, -1 for negative)
        self.master.bind('<w>', lambda e: self.jog(0, 1))
        self.master.bind('<s>', lambda e: self.jog(0, -1))
        self.master.bind('<a>', lambda e: self.jog(1, 1))
        self.master.bind('<d>', lambda e: self.jog(1, -1))
        self.master.bind('<q>', lambda e: self.jog(2, 1))
        self.master.bind('<e>', lambda e: self.jog(2, -1))
        self.master.bind('<space>', lambda e: self.save_point())
        
    def jog(self, axis, direction):
        if not self.rtde_c or not self.rtde_r:
            logger.warning("Jog attempted, but robot is not connected.")
            return
            
        try:
            pose = self.rtde_r.getActualTCPPose()
            step = self.step_var.get()
            speed = self.speed_var.get()
            
            move_dist = direction * step
            axis_name = ["X", "Y", "Z"][axis]
            logger.info(f"Jogging {axis_name}-axis by {move_dist}m at speed {speed}m/s")
            
            pose[axis] += move_dist
            success = self.rtde_c.moveL(pose, speed, 0.5)
            
            if not success:
                logger.error(f"moveL command returned False! Robot may be in a fault state or target is out of reach. Target: {pose}")
        except Exception as e:
            logger.error(f"Exception during jog: {e}", exc_info=True)
        
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
        if self.rtde_c: self.rtde_c.disconnect()
        if self.rtde_r: self.rtde_r.disconnect()
        self.gripper.disconnect()
        self.master.destroy()

if __name__ == "__main__":
    logger.info("Parsing arguments...")
    parser = argparse.ArgumentParser(description="Paper Manipulation Calibration GUI")
    parser.add_argument("--ip", type=str, default="192.168.57.101", help="Robot IP Address")
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
