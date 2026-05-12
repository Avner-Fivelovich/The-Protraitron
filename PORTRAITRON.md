# Portraitron: Robotic Portrait Artist

## Project Overview
**Portraitron** is an automated robotic system designed to capture a person's likeness and translate it into a physical drawing using a robotic arm (UR5e).

## Team
* **Hila**
* **Shira**
* **Avner**

## Application & Functionality
**Scope:** Full end-to-end automated portraiture.
1. **Subject Capture:** High-definition picture of the subject.
2. **Stroke Generation:** Convert camera input to drawing strokes (SwiftSketch algorithm).
3. **Robotic Execution:** Pick up pen, draw strokes, return pen.
4. **Finalization:** Pick up stamp, apply commemorative mark, return stamp.
5. **Delivery:** Hand the page to a designated location.

**Environment:** Robotics lab with UR5e, 2D cameras, and custom end-effectors.

## Technologies
* **Robot:** UR5e (Precision & Safety).
* **Vision:** Dual 2D cameras (Subject/Workspace).
* **Software:** ROS, Python, SwiftSketch.
* **Hardware:** Custom 3D-printed/machined pen and stamp holders.

## Timeline & Milestones
* **Phase 1 (Weeks 1-4):** Research, setup, and basic trajectory control.
* **Phase 2 (Weeks 5-8):** Vision integration and stroke generation.
* **Phase 3 (Week 9):** **Proof of Concept (POC)** - Drawing a circular line.
* **Phase 4 (Weeks 10-12):** End-to-end integration and final refinement.

## Team Responsibility Matrix (Proposed)
* **Vision & Image Processing:** Image capture, background removal, and stroke conversion.
* **Robot Control & Path Planning:** Kinematics, trajectory generation, and ROS communication.
* **Hardware & Systems Integration:** Mechanical design of end-effectors, overall workflow logic, and testing.

## Proof of Concept (POC) - Week 9
* **Goal:** Execute a precise circular line drawing.
* **Purpose:** Proving the feasibility of the coordinate mapping and the stability of the drawing tool.
