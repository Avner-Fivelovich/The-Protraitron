# Reference Repositories Guide

This guide compiles details and code utilities from external repositories to assist in developing and optimizing **The Portraitron**.

---

## 1. Advantages of Using Two Robotic Arms for Tight Assemblies
*   **Path**: `/Users/avnerf/Documents/GitHub/Advantages-of-using-two-robotic-arms-for-tight-assemblies`

### Key Modules & Structure:
- `dual_arm_trajectory_generation.py`: Search optimization for initial base setups and joint trajectories.
- `trajectory_ik.py`: Resolves Inverse Kinematics (IK) for Cartesian paths and builds smooth joint transitions.
- `collision_detection.py`: Coordinates collision check routines using PyBullet.
- `utils/ik.py` & `utils/trajectory.py`: Helpers for kinematics and trajectory generation.

### Direct Porting & Reference Value:
- **Joint Flip Prevention**: To draw continuous paths smoothly, we can reuse the graph-based path solver in `trajectory_ik.py`. It builds a waypoint-joint state transition graph $G = (V, E)$ using `networkx` and runs Dijkstra's algorithm to choose the path minimizing maximum joint change:
  $$\text{weight} = \max(\Delta\theta)$$
  This prevents abrupt wrist/shoulder flips during long drawing strokes.
- **Headless Collision Testing**: Uses PyBullet in direct mode to verify joint coordinates:
  - `check_self_collision(joint_angles, robot_id)`: Prevents the drawing arm from colliding with itself.

---

## 2. Dual Arm Calibration
*   **Path**: `/Users/avnerf/Documents/GitHub/dual_arm_calibration`

### Key Modules & Structure:
- `uri_calibration/src/calibration.py`: Automation script for synchronized calibration grid movements.
- `uri_calibration/src/solve.py`: Outlier filtering and transformation solver.
- `uri_calibration/src/utils.py`: Kinematics, conversion routines, and optimization solvers.

### Direct Porting & Reference Value:
- **Pose & Transformation Helpers (`utils.py:L229-273`)**:
  - Convert Axis-Angle/Rotation Vectors to $3\times3$ Rotation Matrices: `rotvec_to_R(rv)` and `R_to_rotvec(R)`.
  - Convert 6-DOF pose arrays $[x, y, z, r_x, r_y, r_z]$ to $4\times4$ Transformation Matrices: `pose_to_T(p)` and `T_to_pose(T)`:
    $$T = \begin{bmatrix} R & t \\ 0 & 1 \end{bmatrix}$$
- **Base-to-Base Coordinate Calibration**:
  $$\text{ayla\_in\_uri} = T_{U\_TCP} \cdot F \cdot T_{A\_TCP}^{-1}$$
- **Sensor Wrench Transformation**:
  When drawing under compliance force control, the wrist sensor measures forces/torques at the joint flange, which must be projected to the pen tip (TCP). We can port the torque transform formula in `utils.py`:
  $$F_{tcp} = F_{flange}$$
  $$M_{tcp} = M_{flange} - (p \times F_{flange})$$
  This enables precision force control at the marker tip during drawing.

---

## 3. SwiftSketch
*   **Path**: `/Users/avnerf/Documents/GitHub/swiftsketch`

### Key Modules & Structure:
- `ControlSketch/painter_params.py`: Saliency-based stroke initialization and differentiable vector representation using `pydiffvg`.
- `SwiftSketch/generate.py`: Main model inference script executing raster-to-vector sketch conversions.
- `SwiftSketch/model/SwiftSketch_model.py`: Transformer-decoder model defining output stroke structures.
- `SwiftSketch/utils/sketch_utils.py`: Stroke parsing, sorting, and analytical geometry helpers.

### Direct Porting & Reference Value:
- **Bézier Path Extraction**: `sketch_utils.py:extract_control_points_from_svg` translates SVGs into Bézier control coordinate tensors:
  $$\text{shape: } [\text{batch\_size}, \text{num\_strokes}, 4, 2]$$
- **Curve Length Estimation**:
  $$\text{Length} \approx \sum_{j=1}^{M-1} \| B(t_{j+1}) - B(t_j) \|$$
  Implemented via `calculate_length(strokes)` to estimate physical drawing times.
- **Top-to-Bottom Drawing Sort**:
  `calculate_highest_points(strokes)` analytical solver computes the root of the derivative of the cubic Bézier polynomial $B'(t) = 0$ for $t \in [0,1]$. This can be used to sort strokes by height to draw from the top down and avoid smudging previous lines.
- **Stroke Sorting Modes**:
  `sort_strokes` provides `highest_point`, `length`, and `contour_and_attn` modes to structure the sequence of pen paths.
