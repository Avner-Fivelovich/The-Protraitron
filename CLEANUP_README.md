# Codebase Cleanup & Refactoring Todo

This document outlines the unused code, unused imports, and formatting issues identified in the repository during our architectural review.

**⚠️ Status: Pending Cleanup**  
*Do not clean these up yet, as requested.*

## 1. Unused Imports & Variables (Functional Cleanup)
These items are definitively unused and can be safely removed or refactored:

*   **`src/common/logger.py`**
    *   Line 2: Unused import `os`
    *   Line 3: Unused import `time`
*   **`src/common/robot_utils.py`**
    *   Line 143: Local variable `speed_slowdown_factor` is assigned but never used.
*   **`src/robot/controller.py`**
    *   Line 4: Unused import `math`
    *   Line 19: Unused import `wait_for_motion_complete`
*   **`src/robot/mask_filtering.py`**
    *   Line 298: Local variable `mfy_range` assigned but never used.
    *   Line 300: Local variable `sy_range` assigned but never used.
*   **`src/robot/path_optimization.py`**
    *   Line 146: Local variable `merged_total_dist` assigned but never used.
*   **`src/robot/poc_drawing.py`**
    *   Line 1: Unused import `sys`
    *   Line 2: Unused import `os`
    *   Line 77: Local variable `rx` assigned but never used.
    *   Line 78: Local variable `ry` assigned but never used.
*   **`src/robot/swiftsketch_integration.py`**
    *   Line 101: `f-string` used without any placeholders.
    *   Line 128: Local variable `result` assigned but never used (capturing `subprocess.run` return).
*   **`src/robot/text_drawing.py`**
    *   Line 1: Unused import `os`
    *   Line 2: Unused import `sys`

## 2. Formatting & PEP-8 Issues (Style Cleanup)
The `flake8` linter found **535 formatting violations** across the repository. The most common issues are:
*   **`E501` (Line too long):** Many lines in `src/server/main.py`, `src/vision/camera_capture.py`, and other files exceed the 79-character limit (some exceeding 120 characters).
*   **`W293` & `W291` (Whitespace):** Extensive use of trailing whitespace and lines containing only whitespace.
*   **`E302` & `E305` (Blank lines):** Incorrect spacing around class and function definitions (PEP-8 expects 2 blank lines, but only 1 was found in many places).

## 3. General Architecture Review
*   **Missing Dependencies:** Confirmed that `swiftsketch` must be loaded externally from `../swiftsketch` or the local `SwiftSketch-Protraitron` tree using the `swiftsketch_env` Conda environment.
*   **Security/Blocking:** FastAPI endpoints like `/api/upload` have been verified and patched to properly yield to the async event loop using threadpools instead of blocking the main server process during heavy SVGs generations.
