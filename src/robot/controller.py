import os
import yaml
import time
import numpy as np
from src.common.geometry import PlaneCalibrator

try:
    import rtde_control
    import rtde_receive
except ImportError:
    # Fallback for offline testing or compilation phase
    rtde_control = None
    rtde_receive = None

class UR5eController:
    """
    Manages connections and command executions for the physical UR5e arm,
    using 3-point plane projection for slanted/tilted drawing beds.
    """
    def __init__(self, ip_address: str, config_path: str = "config/calibration.yaml"):
        self.ip = ip_address
        self.config_path = config_path
        self.rtde_c = None
        self.rtde_r = None
        
        # Calibration placeholders
        self.p0_joints = None
        self.p0_pose = None
        self.p1 = None
        self.p2 = None
        self.p3 = None
        self.width = 0.19
        self.height = 0.27
        self.calibrator = None
        self.z_travel_offset = 0.015  # 1.5 cm lift above paper plane
        
        self.load_calibration()
        
    def load_calibration(self):
        """Loads plane parameters and starting poses from config/calibration.yaml."""
        if not os.path.exists(self.config_path):
            print(f"Calibration file {self.config_path} not found. Running in uncalibrated mode.")
            return
            
        try:
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f)
            
            self.p0_joints = data.get("p0_joints")
            self.p0_pose = data.get("p0_pose")
            self.p1 = data.get("p1")
            self.p2 = data.get("p2")
            self.p3 = data.get("p3")
            self.width = data.get("width", 0.19)
            self.height = data.get("height", 0.27)
            
            if self.p1 and self.p2 and self.p3:
                self.calibrator = PlaneCalibrator(self.p1, self.p2, self.p3)
                print("✅ 3D Plane Calibrator initialized successfully from config.")
            else:
                print("⚠️ Incomplete plane points in calibration config.")
        except Exception as e:
            print(f"❌ Failed to load calibration: {e}")
            
    def connect(self) -> bool:
        """Initializes socket connections to the UR5e controller."""
        if not rtde_control or not rtde_receive:
            print("❌ Cannot connect: ur_rtde library is not installed.")
            return False
            
        try:
            print(f"Connecting to UR5e at {self.ip}...")
            self.rtde_c = rtde_control.RTDEControlInterface(self.ip)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip)
            print("✅ UR5e Control & Receive interfaces connected.")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.rtde_c = None
            self.rtde_r = None
            return False
            
    def disconnect(self):
        """Safely terminates socket connections."""
        print("Shutting down robot sockets...")
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
        print("Robot sockets disconnected.")
        
    def home(self):
        """Moves joint space directly to the starting hover configuration p0."""
        if not self.rtde_c:
            print("❌ Robot not connected.")
            return
            
        if self.p0_joints is None:
            print("❌ Homing failed: No p0_joints stored in calibration.")
            return
            
        print("Homing to Bottom-Left starting hover pose (P0)...")
        # Joint-space moveJ is safe against singularities and joint flips
        self.rtde_c.moveJ(self.p0_joints, 0.4, 0.2)
        print("Robot arrived at P0.")
        
    def execute_drawing_path(self, strokes_2d: list, speed: float = 0.05, accel: float = 0.1, blend_radius: float = 0.002, draw_depth_offset: float = 0.0):
        """
        Executes a continuous path of 2D strokes on the plane.
        Projects normalized coordinates [0, 1] to base 3D coordinates, keeping tool perpendicular.
        """
        if not self.rtde_c:
            print("❌ Robot not connected.")
            return
            
        if not self.calibrator or not self.p0_pose:
            print("❌ Calibration parameters not loaded. Execute calibration first.")
            return
            
        # Tool orientation is aligned normal to the paper (stored at P0 manual alignment)
        rx, ry, rz = self.p0_pose[3:]
        
        for idx, stroke in enumerate(strokes_2d):
            if len(stroke) == 0:
                continue
                
            print(f"Drawing stroke {idx + 1}/{len(strokes_2d)} containing {len(stroke)} waypoints...")
            
            # 1. Project the first coordinate and move to safe hover pose
            x0, y0 = stroke[0]
            # Hover point has +z_travel_offset (1.5 cm) relative to drawing depth offset
            p_hover = self.calibrator.project_canvas_to_base(x0, y0, depth_offset=draw_depth_offset - self.z_travel_offset)
            hover_pose = list(p_hover) + [rx, ry, rz]
            
            print(f"Moving to hover pose: {[round(c, 4) for c in hover_pose[:3]]}")
            self.rtde_c.moveL(hover_pose, 0.1, 0.2)
            
            # 2. Lower pen slowly to touch the surface
            p_start = self.calibrator.project_canvas_to_base(x0, y0, depth_offset=draw_depth_offset)
            start_pose = list(p_start) + [rx, ry, rz]
            
            print("Lowering pen to surface...")
            self.rtde_c.moveL(start_pose, 0.02, 0.05)
            
            # 3. Assemble coordinates into continuous blended path
            path = []
            for i in range(1, len(stroke)):
                xi, yi = stroke[i]
                p_i = self.calibrator.project_canvas_to_base(xi, yi, depth_offset=draw_depth_offset)
                
                # Blend radius must be 0.0 for the last point to stop execution cleanly
                current_blend = blend_radius if i < (len(stroke) - 1) else 0.0
                waypoint = list(p_i) + [rx, ry, rz, speed, accel, current_blend]
                path.append(waypoint)
                
            if path:
                # Execute linear movePath
                self.rtde_c.moveL(path)
                
            # 4. Retract back to hover plane at the end of the stroke
            x_last, y_last = stroke[-1]
            p_retract = self.calibrator.project_canvas_to_base(x_last, y_last, depth_offset=draw_depth_offset - self.z_travel_offset)
            retract_pose = list(p_retract) + [rx, ry, rz]
            
            print("Retracting pen...")
            self.rtde_c.moveL(retract_pose, 0.08, 0.15)
            
        # Return to safe home
        self.home()
