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
from src.robot.paper_roller import rotate_tool_orientation
from src.robot.robotiq_gripper import RobotiqGripper
from src.robot.paper_handler import PaperHandler

logger = get_logger("PaperCalibrationGUI")

try:
    import rtde_control
    import rtde_receive
except ImportError:
    logger.critical("The 'ur_rtde' library is not installed in the active environment.")
    sys.exit(1)

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
        self.gripper = None
        self.gripper_connected = False
        self.motion_lock = threading.Lock()
        self.is_moving = False
        self.freedrive_active = False
        self.closing = False
        self.keepalive_started = False
        
        self.config = self.load_config()
        self.locations = self.config.get("locations", {})
        
        self.stages = [
            ("draw_home", "Starting draw location"),
            ("safe_paper", "Safe location away from paper"),
            ("safe_tools", "Safe location above the tool docks"),
            ("above_marker_dock", "Hover location above the marker dock"),
            ("marker_dock", "Location to store the marker"),
            ("magnet_1_start", "Current location of Magnet 1"),
            ("magnet_1_park", "Temporary parking location for Magnet 1"),
            ("above_knife", "Hover location above the knife dock"),
            ("knife_dock", "Location to store the knife"),
            ("cut_start_pos", "Start location of the paper cut"),
            ("cut_end_pos", "End location of the paper cut"),
            ("cut_paper_grab", "Location to grab the cut paper"),
            ("cut_paper_pull_dest", "Location to pull the cut paper to"),
            ("safe_midpoint_to_user", "Safe midpoint to user handover"),
            ("user_handover_location", "Target location to handover the paper to the user"),
            ("magnet_2_start", "Current location of Magnet 2"),
            ("magnet_2_park", "Temporary parking location for Magnet 2"),
            ("fresh_paper_grab", "Location to grab the edge of the fresh paper roll"),
            ("fresh_paper_pull_dest", "End location after pulling the fresh paper down"),
            ("paper_straighten_start", "Location below magnet 2 to start straightening paper")
        ]
        self.current_stage_idx = 0
        
        self.create_widgets()
        
        # We no longer auto-connect on startup to guarantee the window renders instantly
        # without being blocked by the C++ ur_rtde GIL lock on network timeouts.
        self.status_var.set("Not Connected (Click Reconnect)")
        self.reconnect_btn.config(state="normal")
        
        self._update_live_coords()
        
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

    def get_state_path(self):
        return os.path.join(os.path.dirname(OUTPUT_PATH), ".calibrate_gui_state.yaml")

    def load_gui_state(self):
        state_path = self.get_state_path()
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Error loading GUI state: {e}")
        return {}

    def save_gui_state(self):
        try:
            state = {
                "speed_var": self.speed_var.get(),
                "accel_var": self.accel_var.get(),
                "step_var": self.step_var.get(),
                "move_mode_var": self.move_mode_var.get(),
                "grip_speed_var": self.grip_speed_var.get(),
                "grip_force_var": self.grip_force_var.get(),
                "grip_step_var": self.grip_step_var.get(),
                "grip_turn_var": self.grip_turn_var.get(),
                "grip_open_pos_var": self.grip_open_pos_var.get(),
                "grip_close_pos_var": self.grip_close_pos_var.get()
            }
            with open(self.get_state_path(), 'w') as f:
                yaml.safe_dump(state, f, default_flow_style=False)
            logger.info("Saved GUI parameters state.")
        except Exception as e:
            logger.error(f"Error saving GUI state: {e}")

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

    def _update_live_coords(self):
        if not self.closing:
            try:
                if self.rtde_r:
                    pose = self.rtde_r.getActualTCPPose()
                    self.coords_var.set(f"TCP: X:{pose[0]:.3f} Y:{pose[1]:.3f} Z:{pose[2]:.3f} | Rx:{pose[3]:.2f} Ry:{pose[4]:.2f} Rz:{pose[5]:.2f}")
                else:
                    self.coords_var.set("TCP: X: -- Y: -- Z: -- | Rx: -- Ry: -- Rz: --")
            except Exception:
                pass
            self.master.after(200, self._update_live_coords)

    def copy_location(self):
        try:
            if self.rtde_r:
                pose = self.rtde_r.getActualTCPPose()
                pose_str = f"[{pose[0]:.4f}, {pose[1]:.4f}, {pose[2]:.4f}, {pose[3]:.4f}, {pose[4]:.4f}, {pose[5]:.4f}]"
                self.master.clipboard_clear()
                self.master.clipboard_append(pose_str)
                logger.info(f"Copied current pose to clipboard: {pose_str}")
            else:
                logger.warning("Cannot copy location: Robot not connected.")
        except Exception as e:
            logger.error(f"Failed to copy location: {e}")


    def connect_robot(self):
        try:
            logger.info(f"Connecting to UR5e RTDE at {self.robot_ip}...")
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.robot_ip)
            flags = (
                rtde_control.RTDEControlInterface.FLAG_DISABLE_REMOTE_CONTROL_CHECK
                | rtde_control.RTDEControlInterface.FLAG_USE_EXT_UR_CAP
            )
            try:
                self.rtde_c = rtde_control.RTDEControlInterface(self.robot_ip, flags=flags, ur_cap_port=50002)
            except Exception as external_control_error:
                logger.warning(
                    f"External URCap port 50002 unavailable ({external_control_error}); "
                    "falling back to standard RTDE control."
                )
                self.rtde_c = rtde_control.RTDEControlInterface(self.robot_ip)
            self.status_var.set("Connected to UR5e")
            self.freedrive_btn.config(state="normal")
            if hasattr(self, 'goto_btn'):
                self.goto_btn.config(state="normal")
            if hasattr(self, 'test_buttons'):
                for btn in self.test_buttons:
                    btn.config(state="normal")

            gripper_port = CENTRAL_CONFIG.get("hardware", {}).get("gripper_port", 63352)
            try:
                logger.info(f"Connecting to Robotiq gripper at {self.robot_ip}:{gripper_port}...")
                self.gripper = RobotiqGripper()
                self.gripper.connect(self.robot_ip, gripper_port)
                if self.gripper.mock_mode:
                    logger.warning("Robotiq gripper is in mock mode; gripper controls are disabled.")
                    self.gripper = None
                else:
                    self.gripper.activate(auto_calibrate=False)
                    self.gripper_connected = True
                    self.gripper_btn_state("normal")
                    logger.info("Robotiq gripper connected and activated.")
            except Exception as gripper_error:
                self.gripper = None
                self.gripper_connected = False
                logger.error(f"Gripper connection failed: {gripper_error}")

            if not self.keepalive_started:
                self.keepalive_started = True
                threading.Thread(target=self._keepalive_loop, daemon=True).start()
            logger.info("Successfully connected to UR5e.")
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
                self.status_var.set("Connected to UR5e")
                logger.info("Freedrive mode disabled.")
        except Exception as e:
            logger.error(f"Error toggling freedrive: {e}")
            self.status_var.set(f"Freedrive Error: {e}")
            
    def create_widgets(self):
        # Main Canvas for scrolling
        self.canvas = tk.Canvas(self.master)
        self.scrollbar = tk.Scrollbar(self.master, orient="vertical", command=self.canvas.yview)
        self.main_frame = tk.Frame(self.canvas)

        self.main_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw", tags="main_frame_window")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig("main_frame_window", width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel for scrolling (cross-platform)
        def _on_mousewheel(event):
            if event.num == 4 or event.delta > 0:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                self.canvas.yview_scroll(1, "units")
        
        self.master.bind_all("<MouseWheel>", _on_mousewheel)
        self.master.bind_all("<Button-4>", _on_mousewheel)
        self.master.bind_all("<Button-5>", _on_mousewheel)

        status_frame = tk.Frame(self.main_frame)
        status_frame.pack(pady=5)
        
        self.status_var = tk.StringVar(value="Connecting...")
        tk.Label(status_frame, textvariable=self.status_var, fg="blue").pack(side="left", padx=5)
        
        self.reconnect_btn = tk.Button(status_frame, text="Reconnect", command=self.trigger_reconnect, state="disabled")
        self.reconnect_btn.pack(side="left", padx=5)

        self.freedrive_btn = tk.Button(status_frame, text="🖐 Freedrive (Hand-Guide)", command=self.toggle_freedrive, bg="#e0e0e0", state="disabled")
        self.freedrive_btn.pack(side="left", padx=5)

        coords_frame = tk.Frame(self.main_frame)
        coords_frame.pack(pady=2)
        self.coords_var = tk.StringVar(value="TCP: X: -- Y: -- Z: -- | Rx: -- Ry: -- Rz: --")
        tk.Label(coords_frame, textvariable=self.coords_var, font=("Courier", 11)).pack(side="left")
        tk.Button(coords_frame, text="📋 Copy", command=self.copy_location).pack(side="left", padx=10)
        
        self.stage_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        tk.Label(self.main_frame, textvariable=self.stage_var, font=("Helvetica", 16, "bold")).pack(pady=5)
        tk.Label(self.main_frame, textvariable=self.desc_var).pack(pady=5)
        
        self.update_stage_display()
        
        btn_frame = tk.Frame(self.main_frame)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Back", command=self.prev_stage).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Save Point & Next", command=self.save_point, bg="green").grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="Skip", command=self.next_stage).grid(row=0, column=2, padx=5)
        
        saved_state = self.load_gui_state()
        move_settings = GUI_CONFIG.get("movement_settings", {})
        self.speed_var = tk.DoubleVar(value=saved_state.get("speed_var", move_settings.get("default_speed", 0.03)))
        self.step_var = tk.DoubleVar(value=saved_state.get("step_var", move_settings.get("default_step", 0.005)))
        self.accel_var = tk.DoubleVar(value=saved_state.get("accel_var", move_settings.get("default_accel", 0.10)))

        settings_frame = tk.LabelFrame(self.main_frame, text="Movement Settings")
        settings_frame.pack(pady=5, padx=10, fill="x")
        
        tk.Label(settings_frame, text="Speed (m/s):").grid(row=0, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.speed_var, from_=0.005, to=0.15, resolution=0.005, orient="horizontal").grid(row=0, column=1, padx=5, sticky="ew")
        
        tk.Label(settings_frame, text="Accel (m/s²):").grid(row=1, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.accel_var, from_=0.01, to=0.5, resolution=0.01, orient="horizontal").grid(row=1, column=1, padx=5, sticky="ew")
        
        tk.Label(settings_frame, text="Step Size (m):").grid(row=2, column=0, padx=5)
        tk.Scale(settings_frame, variable=self.step_var, from_=0.001, to=0.05, resolution=0.001, orient="horizontal").grid(row=2, column=1, padx=5, sticky="ew")

        # Interpolation mode selector
        self.move_mode_var = tk.StringVar(value=saved_state.get("move_mode_var", "joint_ik"))
        mode_frame = tk.Frame(settings_frame)
        mode_frame.grid(row=3, column=0, columnspan=2, pady=4, sticky="w")
        tk.Label(mode_frame, text="Mode:").pack(side="left", padx=5)
        tk.Radiobutton(mode_frame, text="Joint IK (Safe / No Stops)", variable=self.move_mode_var, value="joint_ik").pack(side="left", padx=5)
        tk.Radiobutton(mode_frame, text="Linear (moveL)", variable=self.move_mode_var, value="linear").pack(side="left", padx=5)

        gripper_settings = GUI_CONFIG.get("gripper_settings", {})
        self.grip_speed_var = tk.IntVar(value=saved_state.get("grip_speed_var", gripper_settings.get("default_speed", 50)))
        self.grip_force_var = tk.IntVar(value=saved_state.get("grip_force_var", gripper_settings.get("default_force", 50)))
        self.grip_step_var = tk.IntVar(value=saved_state.get("grip_step_var", gripper_settings.get("default_step", 5)))
        self.grip_turn_var = tk.DoubleVar(value=saved_state.get("grip_turn_var", gripper_settings.get("default_turn_degrees", 10.0)))

        self.grip_open_pos_var = tk.IntVar(value=saved_state.get("grip_open_pos_var", 50))
        self.grip_close_pos_var = tk.IntVar(value=saved_state.get("grip_close_pos_var", 100))

        gripper_frame = tk.LabelFrame(self.main_frame, text="Gripper")
        gripper_frame.pack(pady=5, padx=10, fill="x")
        self.gripper_buttons = []
        for column, label, command in (
            (0, "Open", lambda: self.async_grip(self.grip_open_pos_var.get())),
            (1, "Turn +", lambda: self.rotate_gripper(1)),
            (2, "Turn -", lambda: self.rotate_gripper(-1)),
            (3, "Close", lambda: self.async_grip(self.grip_close_pos_var.get())),
        ):
            button = tk.Button(gripper_frame, text=label, command=command, state="disabled", width=10)
            button.grid(row=0, column=column, padx=5, pady=5)
            self.gripper_buttons.append(button)

        tk.Label(gripper_frame, text="Open Pos (%)").grid(row=1, column=0)
        tk.Scale(gripper_frame, variable=self.grip_open_pos_var, from_=0, to=100, orient="horizontal").grid(row=1, column=1, sticky="ew")
        
        tk.Label(gripper_frame, text="Close Pos (%)").grid(row=2, column=0)
        tk.Scale(gripper_frame, variable=self.grip_close_pos_var, from_=0, to=100, orient="horizontal").grid(row=2, column=1, sticky="ew")

        tk.Label(gripper_frame, text="Speed").grid(row=3, column=0)
        tk.Scale(gripper_frame, variable=self.grip_speed_var, from_=1, to=100, orient="horizontal").grid(row=3, column=1, sticky="ew")
        tk.Label(gripper_frame, text="Force").grid(row=4, column=0)
        tk.Scale(gripper_frame, variable=self.grip_force_var, from_=1, to=100, orient="horizontal").grid(row=4, column=1, sticky="ew")
        tk.Label(gripper_frame, text="Turn (degrees)").grid(row=5, column=0)
        tk.Scale(gripper_frame, variable=self.grip_turn_var, from_=1, to=90, resolution=1, orient="horizontal").grid(row=5, column=1, sticky="ew")
        gripper_frame.grid_columnconfigure(1, weight=1)
        
        settings_frame.grid_columnconfigure(1, weight=1)

        jog_frame = tk.LabelFrame(self.main_frame, text="Jogging Keyboard (W/S=X, A/D=Y, Q/E=Z, F=Freedrive)")
        jog_frame.pack(pady=10, padx=10, fill="x")
        
        axes = [(0, "X", 1), (1, "Y", 2), (2, "Z", 3)]
        for axis_idx, axis_name, col_offset in axes:
            tk.Button(jog_frame, text=f"+{axis_name}", command=lambda idx=axis_idx: self.jog(idx, 1)).grid(row=0, column=col_offset, padx=5, pady=5)
            tk.Button(jog_frame, text=f"-{axis_name}", command=lambda idx=axis_idx: self.jog(idx, -1)).grid(row=1, column=col_offset, padx=5, pady=5)
        
        # Keyboard bindings (multiplier 1 for positive, -1 for negative)
        for key, axis, direction in [('w', 0, 1), ('s', 0, -1), ('a', 1, 1), ('d', 1, -1), ('q', 2, 1), ('e', 2, -1)]:
            self.master.bind(f'<{key}>', lambda e, a=axis, d=direction: self.jog(a, d))
        self.master.bind('<space>', lambda e: self.save_point())
        self.master.bind('<f>', lambda e: self.toggle_freedrive())

        # Test Sequences Frame
        test_frame = tk.LabelFrame(self.main_frame, text="Test Action Sequences")
        test_frame.pack(pady=10, padx=10, fill="x")
        
        self.test_buttons = []
        dummy_ph = PaperHandler(None, None)
        seqs = dummy_ph.get_partial_sequences()
        
        row = 0
        for seq_name, seq_actions in seqs.items():
            desc_parts = []
            for act in seq_actions:
                if act[0] == "move":
                    desc_parts.append(act[1])
                elif act[0] == "move_speed":
                    desc_parts.append(act[1][0])
                elif act[0] == "gripper":
                    desc_parts.append(f"[{act[1].upper()}]")
                elif act[0] == "force_cut":
                    desc_parts.append(f"CUT_TO({act[1][0]})")
                elif act[0] == "force_straighten":
                    desc_parts.append(f"STRAIGHTEN({act[1]})")
                elif act[0] == "wait_pull":
                    desc_parts.append("WAIT_PULL")
            
            desc_str = " ➔ ".join(desc_parts)
            tk.Label(test_frame, text=desc_str, font=("Courier", 10), wraplength=450, justify="left", fg="gray").grid(row=row, column=0, padx=5, sticky="w")
            row += 1
            
            btn = tk.Button(test_frame, text=seq_name, command=lambda name=seq_name: self.run_test_sequence(name), state="disabled")
            btn.grid(row=row, column=0, padx=5, pady=2, sticky="ew")
            self.test_buttons.append(btn)
            row += 1
                
        btn_all = tk.Button(test_frame, text="Run Full Paper Swap", bg="#ffcccc", command=lambda: self.run_test_sequence("all"), state="disabled")
        btn_all.grid(row=row, column=0, padx=5, pady=10, sticky="ew")
        self.test_buttons.append(btn_all)
        test_frame.grid_columnconfigure(0, weight=1)

        # Go To Location Frame
        goto_frame = tk.LabelFrame(self.main_frame, text="Go To Saved Location")
        goto_frame.pack(pady=5, padx=10, fill="x")
        
        self.goto_var = tk.StringVar()
        self.goto_combo = ttk.Combobox(goto_frame, textvariable=self.goto_var, state="readonly")
        self.goto_combo.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.goto_btn = tk.Button(goto_frame, text="Go", command=self.go_to_location, state="disabled", bg="#ccffcc")
        self.goto_btn.grid(row=0, column=1, padx=5, pady=5)
        goto_frame.grid_columnconfigure(0, weight=1)
        
        self.update_goto_combo()

    def update_goto_combo(self):
        loc_keys = list(self.locations.keys())
        self.goto_combo['values'] = loc_keys
        if loc_keys:
            self.goto_combo.set(loc_keys[0])
            
    def go_to_location(self):
        loc_name = self.goto_var.get()
        if not loc_name or loc_name not in self.locations:
            logger.warning(f"Invalid location selected: {loc_name}")
            return
            
        target = self.locations[loc_name]
        if not self.rtde_c or not self.rtde_r:
            logger.warning("Robot is not connected.")
            return
            
        if self.is_moving:
            return
            
        threading.Thread(target=self._execute_go_to, args=(loc_name, target), daemon=True).start()
        
    def _execute_go_to(self, loc_name, target):
        with self.motion_lock:
            if self.is_moving: return
            self.is_moving = True
            try:
                if self.freedrive_active:
                    self.toggle_freedrive()
                
                self.status_var.set(f"Moving to {loc_name}...")
                speed = self.speed_var.get()
                accel = self.accel_var.get()
                mode = self.move_mode_var.get()
                
                if mode == "joint_ik":
                    success = self.rtde_c.moveJ_IK(target, speed=0.3, acceleration=0.4)
                else:
                    success = self.rtde_c.moveL(target, speed, accel)
                    
                if success:
                    self.status_var.set(f"Arrived at {loc_name}")
                else:
                    self.status_var.set(f"Failed to move to {loc_name}")
            except Exception as e:
                logger.error(f"Error moving to {loc_name}: {e}")
                self.status_var.set("Move Error!")
            finally:
                self.is_moving = False

    def gripper_btn_state(self, state):
        for button in self.gripper_buttons:
            button.config(state=state)
        
    def toggle_gripper(self):
        if not self.gripper_connected or not self.gripper:
            logger.warning("Gripper attempted toggle, but is not connected.")
            return
        cur_pos = self.gripper.get_current_position()
        # If currently open (<=128), close it; otherwise open it
        target = self.grip_close_pos_var.get() if cur_pos <= 128 else self.grip_open_pos_var.get()
        self.async_grip(target)

    def run_test_sequence(self, seq_name):
        if not self.rtde_c or not self.rtde_r:
            logger.warning("Cannot run test sequence: robot is not connected.")
            return
        if self.is_moving:
            return
            
        threading.Thread(target=self._execute_test_sequence, args=(seq_name,), daemon=True).start()
        
    def _execute_test_sequence(self, seq_name):
        with self.motion_lock:
            if self.is_moving: return
            self.is_moving = True
            try:
                if self.freedrive_active:
                    self.toggle_freedrive()
                    
                self.status_var.set(f"Testing {seq_name}...")
                
                # We instantiate a fresh PaperHandler using current config locations
                # We need to save the current locations to the yaml first so PaperHandler loads them
                self.save_config()
                
                ph = PaperHandler(self.rtde_c, self.rtde_r, config_path=self.output_path)
                ph.gripper = self.gripper
                ph.gripper_connected = self.gripper_connected
                
                if seq_name == "all":
                    success = ph.execute_paper_swap()
                else:
                    seqs = ph.get_partial_sequences()
                    if seq_name in seqs:
                        success = ph.execute_sequence(seqs[seq_name])
                    else:
                        success = False
                        
                if success:
                    self.status_var.set("Test Sequence complete!")
                else:
                    self.status_var.set("Test Sequence failed!")
                    
            except Exception as e:
                logger.error(f"Error during sequence test: {e}")
                self.status_var.set("Test Error!")
            finally:
                self.is_moving = False

    def rotate_gripper(self, direction):
        if not self.rtde_c or not self.rtde_r:
            logger.warning("Gripper rotation attempted, but the robot is not connected.")
            return
        if self.is_moving:
            return
        angle = direction * self.grip_turn_var.get()
        threading.Thread(target=self._execute_rotation, args=(angle,), daemon=True).start()

    def _execute_rotation(self, angle):
        with self.motion_lock:
            if self.is_moving:
                return
            self.is_moving = True
            try:
                if self.freedrive_active:
                    self.toggle_freedrive()

                if self.rtde_r.isProtectiveStopped():
                    self.status_var.set("Protective Stop! Unlock on Pendant")
                    return
                if self.rtde_r.isEmergencyStopped():
                    self.status_var.set("Emergency Stop active!")
                    return
                if not self.rtde_c.isProgramRunning():
                    self.rtde_c.reuploadScript()
                    time.sleep(0.3)

                pose = list(self.rtde_r.getActualTCPPose())
                pose[3:] = rotate_tool_orientation(*pose[3:], angle, axis="z")
                logger.info(f"Rotating gripper around tool Z by {angle:+.1f} degrees")

                try:
                    if not self.rtde_c.isPoseWithinSafetyLimits(pose):
                        self.status_var.set("Rotation rejected: Safety limits")
                        return
                except Exception:
                    pass

                if self.move_mode_var.get() == "joint_ik":
                    success = self.rtde_c.moveJ_IK(pose, speed=0.3, acceleration=0.4)
                else:
                    success = self.rtde_c.moveL(pose, self.speed_var.get(), self.accel_var.get())

                if success:
                    self.status_var.set("Connected to UR5e")
                else:
                    self.status_var.set("Rotation failed")
            except Exception as e:
                logger.error(f"Exception during gripper rotation: {e}", exc_info=True)
                self.status_var.set(f"Rotation Error: {e}")
            finally:
                self.is_moving = False

    def async_grip(self, target_percent):
        if not self.gripper_connected or not self.gripper:
            logger.warning("Gripper attempted move, but is not connected.")
            return
        speed = int((self.grip_speed_var.get() / 100.0) * 255)
        force = int((self.grip_force_var.get() / 100.0) * 255)
        target = int((target_percent / 100.0) * 255)
        logger.info(f"Commanding Gripper to {target_percent}% (pos {target}, speed {speed}, force {force})")
        threading.Thread(target=self.gripper.move_and_wait_for_pos, args=(target, speed, force), daemon=True).start()
        
    def jog_gripper(self, direction):
        if not self.gripper_connected or not self.gripper:
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
                        self.status_var.set("Connected to UR5e")
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
                    self.status_var.set("Connected to UR5e")
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
        self.save_gui_state()
        self.closing = True
        if self.freedrive_active and self.rtde_c:
            try:
                self.rtde_c.endFreedriveMode()
            except Exception:
                pass
        for obj in (self.rtde_c, self.rtde_r):
            if obj:
                try:
                    obj.disconnect()
                except Exception:
                    pass
        if self.gripper:
            try:
                self.gripper.disconnect()
            except Exception:
                pass
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
