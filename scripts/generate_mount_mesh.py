"""
scripts/generate_mount_mesh.py
Generates two 3D-printable STL files for the Robotiq 2F-85 grasped pen mount:
1. Robust & Stable Model: 100mm tall, 70mm pen insertion depth, straight cuboid walls.
2. Fast-to-Print Model: 42mm tall, 12mm insertion depth, straight cuboid walls.
"""
import math
import os
import struct

def calculate_normal(v1, v2, v3):
    # Vector cross product to calculate facet normal: (v2 - v1) x (v3 - v1)
    ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
    vx, vy, vz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx*nx + ny*ny + nz*nz)
    if length > 0.0:
        return [nx / length, ny / length, nz / length]
    return [0.0, 0.0, 0.0]

def add_box(triangles, x_min, x_max, y_min, y_max, z_min, z_max):
    # 8 Vertices of a box
    v = [
        [x_min, y_min, z_min],  # 0
        [x_max, y_min, z_min],  # 1
        [x_max, y_max, z_min],  # 2
        [x_min, y_max, z_min],  # 3
        [x_min, y_min, z_max],  # 4
        [x_max, y_min, z_max],  # 5
        [x_max, y_max, z_max],  # 6
        [x_min, y_max, z_max],  # 7
    ]
    
    # Define the 12 triangles (faces) of the box
    faces = [
        # Bottom Face
        (v[0], v[2], v[1]), (v[0], v[3], v[2]),
        # Top Face
        (v[4], v[5], v[6]), (v[4], v[6], v[7]),
        # Front Face
        (v[0], v[1], v[5]), (v[0], v[5], v[4]),
        # Back Face
        (v[2], v[3], v[7]), (v[2], v[7], v[6]),
        # Left Face
        (v[0], v[4], v[7]), (v[0], v[7], v[3]),
        # Right Face
        (v[1], v[2], v[6]), (v[1], v[6], v[5]),
    ]
    
    for tri in faces:
        normal = calculate_normal(tri[0], tri[1], tri[2])
        triangles.append((normal, tri[0], tri[1], tri[2]))

def add_hollow_cylinder(triangles, r_out, r_in, z_bot, z_top, segments=32):
    for i in range(segments):
        theta1 = 2.0 * math.pi * i / segments
        theta2 = 2.0 * math.pi * (i + 1) / segments
        
        c1, s1 = math.cos(theta1), math.sin(theta1)
        c2, s2 = math.cos(theta2), math.sin(theta2)
        
        # Outer Vertices
        vo1_top = [r_out * c1, r_out * s1, z_top]
        vo2_top = [r_out * c2, r_out * s2, z_top]
        vo1_bot = [r_out * c1, r_out * s1, z_bot]
        vo2_bot = [r_out * c2, r_out * s2, z_bot]
        
        # Inner Vertices
        vi1_top = [r_in * c1, r_in * s1, z_top]
        vi2_top = [r_in * c2, r_in * s2, z_top]
        vi1_bot = [r_in * c1, r_in * s1, z_bot]
        vi2_bot = [r_in * c2, r_in * s2, z_bot]
        
        # 1. Outer Wall
        t1 = (vo1_bot, vo2_top, vo2_bot)
        t2 = (vo1_bot, vo1_top, vo2_top)
        triangles.append((calculate_normal(*t1), t1[0], t1[1], t1[2]))
        triangles.append((calculate_normal(*t2), t2[0], t2[1], t2[2]))
        
        # 2. Inner Wall
        t3 = (vi1_bot, vi2_bot, vi2_top)
        t4 = (vi1_bot, vi2_top, vi1_top)
        triangles.append((calculate_normal(*t3), t3[0], t3[1], t3[2]))
        triangles.append((calculate_normal(*t4), t4[0], t4[1], t4[2]))
        
        # 3. Bottom Rim
        t5 = (vo1_bot, vo2_bot, vi2_bot)
        t6 = (vo1_bot, vi2_bot, vi1_bot)
        triangles.append((calculate_normal(*t5), t5[0], t5[1], t5[2]))
        triangles.append((calculate_normal(*t6), t6[0], t6[1], t6[2]))
        
        # 4. Top Rim
        t7 = (vo1_top, vi2_top, vo2_top)
        t8 = (vo1_top, vi1_top, vi2_top)
        triangles.append((calculate_normal(*t7), t7[0], t7[1], t7[2]))
        triangles.append((calculate_normal(*t8), t8[0], t8[1], t8[2]))

def write_binary_stl(filepath, triangles):
    with open(filepath, 'wb') as f:
        # Header (80 bytes)
        f.write(b'\x00' * 80)
        # Number of triangles (4 bytes)
        f.write(struct.pack('<I', len(triangles)))
        
        # Write each triangle
        for normal, v1, v2, v3 in triangles:
            # 3 floats for normal, 3 floats for each vertex
            data = struct.pack('<12fH', 
                               normal[0], normal[1], normal[2],
                               v1[0], v1[1], v1[2],
                               v2[0], v2[1], v2[2],
                               v3[0], v3[1], v3[2],
                               0) # Attribute byte count
            f.write(data)

def main():
    os.makedirs("hardware", exist_ok=True)
    
    # -------------------------------------------------------------------------
    # 1. GENERATE THE "ROBUST & STABLE" MODEL (100mm Tall, Ultra-Deep Insertion)
    # -------------------------------------------------------------------------
    triangles_robust = []
    
    # Lower core (Z in [0, 70]) - hollowed for deep Z insertion (aligned to 12.0mm cylinder outer radius)
    add_box(triangles_robust, -12.0, 12.0, -17.5, -12.0, 0.0, 70.0)  # Front
    add_box(triangles_robust, -12.0, 12.0, 12.0, 17.5, 0.0, 70.0)    # Back
    add_box(triangles_robust, -13.0, -12.0, -17.5, 17.5, 0.0, 70.0)   # Left
    add_box(triangles_robust, 12.0, 13.0, -17.5, 17.5, 0.0, 70.0)    # Right
    
    # Upper core (Z in [70, 100]) - 30mm solid ceiling stop at the top
    add_box(triangles_robust, -13.0, 13.0, -17.5, 17.5, 70.0, 100.0)
    
    # Left Flange walls (X in [-17, -13]) - Open top for smooth Z entry
    add_box(triangles_robust, -17.0, -13.0, -17.5, -11.25, 0.0, 100.0)
    add_box(triangles_robust, -17.0, -13.0, 11.25, 17.5, 0.0, 100.0)
    add_box(triangles_robust, -17.0, -13.0, -11.25, 11.25, 0.0, 1.75) # Bottom Rim
    
    # Right Flange walls (X in [13, 17]) - Open top for smooth Z entry
    add_box(triangles_robust, 13.0, 17.0, -17.5, -11.25, 0.0, 100.0)
    add_box(triangles_robust, 13.0, 17.0, 11.25, 17.5, 0.0, 100.0)
    add_box(triangles_robust, 13.0, 17.0, -11.25, 11.25, 0.0, 1.75) # Bottom Rim
    
    # Hollow cylinder cage (Z in [-40, 70])
    add_hollow_cylinder(triangles_robust, r_out=12.0, r_in=8.25, z_bot=-40.0, z_top=70.0)
    
    robust_file = "hardware/robotiq_pen_mount_robust.stl"
    write_binary_stl(robust_file, triangles_robust)
    print(f"Mesh generation successful: {robust_file} ({len(triangles_robust)} facets)")
    
    # -------------------------------------------------------------------------
    # 2. GENERATE THE "FAST-TO-PRINT" MODEL (42mm Tall, Compact & Light)
    # -------------------------------------------------------------------------
    triangles_fast = []
    
    # Lower core (Z in [0, 12]) - hollowed for Z insertion (aligned to 10.0mm cylinder outer radius)
    add_box(triangles_fast, -10.0, 10.0, -12.5, -10.0, 0.0, 12.0)  # Front
    add_box(triangles_fast, -10.0, 10.0, 10.0, 12.5, 0.0, 12.0)    # Back
    add_box(triangles_fast, -11.0, -10.0, -12.5, 12.5, 0.0, 12.0)   # Left
    add_box(triangles_fast, 10.0, 11.0, -12.5, 12.5, 0.0, 12.0)    # Right
    
    # Upper core (Z in [12, 42]) - 30mm solid ceiling stop at the top
    add_box(triangles_fast, -11.0, 11.0, -12.5, 12.5, 12.0, 42.0)
    
    # Left Flange walls (X in [-14.5, -11]) - Open top
    add_box(triangles_fast, -14.5, -11.0, -12.5, -11.25, 0.0, 42.0)
    add_box(triangles_fast, -14.5, -11.0, 11.25, 12.5, 0.0, 42.0)
    add_box(triangles_fast, -14.5, -11.0, -11.25, 11.25, 0.0, 1.75) # Bottom Rim
    
    # Right Flange walls (X in [11, 14.5]) - Open top
    add_box(triangles_fast, 11.0, 14.5, -12.5, -11.25, 0.0, 42.0)
    add_box(triangles_fast, 11.0, 14.5, 11.25, 12.5, 0.0, 42.0)
    add_box(triangles_fast, 11.0, 14.5, -11.25, 11.25, 0.0, 1.75) # Bottom Rim
    
    # Hollow cylinder cage (Z in [-30, 12]) - Outer diameter 20.0mm (radius 10.0)
    add_hollow_cylinder(triangles_fast, r_out=10.0, r_in=8.25, z_bot=-30.0, z_top=12.0)
    
    fast_file = "hardware/robotiq_pen_mount_fast.stl"
    write_binary_stl(fast_file, triangles_fast)
    print(f"Mesh generation successful: {fast_file} ({len(triangles_fast)} facets)")

if __name__ == "__main__":
    main()
