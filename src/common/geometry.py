import numpy as np

class PlaneCalibrator:
    """
    Handles 3D coordinate transformation for an arbitrary plane in space
    using three calibrated contact points (Bottom-Left, Bottom-Right, Top-Left).
    """
    def __init__(self, p1: list, p2: list, p3: list):
        # Extract 3D position vectors (X, Y, Z) in meters
        self.p1 = np.array(p1[:3])
        self.p2 = np.array(p2[:3])
        self.p3 = np.array(p3[:3])
        
        # Calculate local axes vectors
        v_x = self.p2 - self.p1
        v_y_temp = self.p3 - self.p1
        
        # Compute orthonormal unit vectors
        self.ux = v_x / np.linalg.norm(v_x)
        
        # Normal vector pointing outward from surface
        n = np.cross(v_x, v_y_temp)
        self.uz = n / np.linalg.norm(n)
        
        # Orthogonal Y axis lying in the plane
        self.uy = np.cross(self.uz, self.ux)
        
        # Save physical dimensions in meters
        self.width = np.linalg.norm(v_x)
        self.height = np.dot(v_y_temp, self.uy)
        
    def project_canvas_to_base(self, x_norm: float, y_norm: float, depth_offset: float = 0.0) -> np.ndarray:
        """
        Projects normalized canvas coordinate [0, 1] onto the 3D plane.
        Applies depth_offset in the direction normal to the plane (into the surface).
        """
        x_phys = x_norm * self.width
        y_phys = y_norm * self.height
        
        # Calculate 3D position on the plane surface
        p_surface = self.p1 + (x_phys * self.ux) + (y_phys * self.uy)
        
        # Apply offset normal to the surface (uz points outward, so we subtract to push inward)
        p_draw = p_surface - (depth_offset * self.uz)
        return p_draw

def generate_semicircle_canvas(radius: float, width: float, height: float, theta_deg: float, num_steps: int = 100) -> np.ndarray:
    """
    Generates normalized 2D canvas coordinates [0, 1] representing a semicircle.
    Starts at the center minus radius to the left, sweeping counter-clockwise.
    """
    rx = radius / width
    ry = radius / height
    
    theta_rad = np.radians(theta_deg)
    # Semicircle starts at the left (pi radians) and sweeps clockwise (subtracting theta)
    # to draw the upper side of the circle (y values increase).
    angles = np.linspace(np.pi, np.pi - theta_rad, num_steps)
    
    x = 0.5 + rx * np.cos(angles)
    y = 0.5 + ry * np.sin(angles)
    
    return np.column_stack((x, y))
