# Codebase Cleanup & Refactoring To-Do

This document tracks unused code, dead imports, style violations, and architectural refactoring targets identified across the repository.

> [!WARNING]
> **Status: Pending Cleanup**  
> Hold off on applying automated refactoring passes until all active feature branches are merged.

---

## 1. Unused Imports & Dead Code

The following unused imports and variables have been identified for safe removal or refactoring:

### Common Modules
- [ ] **`src/common/logger.py`**
  - Unused import: `os` (line 2)
  - Unused import: `time` (line 3)
- [ ] **`src/common/robot_utils.py`**
  - Unused local variable: `speed_slowdown_factor` (line 143)

### Robot Control & Drawing Modules
- [ ] **`src/robot/controller.py`**
  - Unused import: `math` (line 4)
  - Unused import: `wait_for_motion_complete` (line 19)
- [ ] **`src/robot/mask_filtering.py`**
  - Unused local variable: `mfy_range` (line 298)
  - Unused local variable: `sy_range` (line 300)
- [ ] **`src/robot/path_optimization.py`**
  - Unused local variable: `merged_total_dist` (line 146)
- [ ] **`src/robot/poc_drawing.py`**
  - Unused import: `sys` (line 1)
  - Unused import: `os` (line 2)
  - Unused local variable: `rx` (line 77)
  - Unused local variable: `ry` (line 78)
- [ ] **`src/robot/swiftsketch_integration.py`**
  - Empty `f-string` without expressions/placeholders (line 101)
  - Unused local variable: `result` (capturing `subprocess.run` return value at line 128)
- [ ] **`src/robot/text_drawing.py`**
  - Unused import: `os` (line 1)
  - Unused import: `sys` (line 2)

---

## 2. Formatting & PEP-8 Compliance

Linter analysis (`flake8`) reported **535 formatting violations** across the repository. The primary categories are:

| Error Code | Description | Affected Areas | Recommendation |
| :--- | :--- | :--- | :--- |
| **`E501`** | Line too long (> 79/88 characters) | `src/server/main.py`, `src/vision/camera_capture.py` | Break long expressions; adopt `black` / `ruff` formatting with an 88 or 100 char limit. |
| **`W291` / `W293`** | Trailing whitespace / blank lines with whitespace | Repository-wide | Configure pre-commit hook or editor to strip trailing whitespace on save. |
| **`E302` / `E305`** | Expected 2 blank lines before/after top-level definitions | Repository-wide | Standardize spacing around functions and class definitions. |
| **`F401` / `F841`** | Unused imports and unused variables | Identified modules above | Run `autoflake` or `ruff check --select F401,F841 --fix`. |

---

## 3. Architectural Notes & Observations

> [!NOTE]
> **Environment & Dependencies**
> - **SwiftSketch Integration:** `swiftsketch` dependencies must be loaded externally from `../swiftsketch` or the submodule `SwiftSketch-Protraitron` utilizing the designated `swiftsketch_env` Conda environment.
> - **Async Server Performance:** FastAPI endpoints (such as `/api/upload`) offload heavy SVG generation to threadpools (`starlette.concurrency.run_in_threadpool` or `asyncio.to_thread`) to avoid blocking the main event loop.

---

## 4. Recommended Execution Plan

1. **Pre-cleanup Verification:** Ensure current automated unit tests (`pytest`) pass cleanly.
2. **Automated Dead Code Removal:** Run `ruff` or `autoflake` targeting specific files in `src/`.
3. **Automated Code Formatting:** Format the repository using `ruff format` or `black` + `isort`.
4. **Manual Spot-check:** Verify robot communication modules and SwiftSketch invocation scripts.
5. **CI/CD Lint Step:** Add a `flake8` or `ruff check` step to prevent future style drift.
