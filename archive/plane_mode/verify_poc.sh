#!/bin/bash
# scripts/verify_poc.sh
# Automated verification script for the Portraitron 3000 POC

set -e

# Base directory setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

# ANSI escape codes for colored terminal output
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
BLUE='\033[94m'
NC='\033[0m' # No Color

echo "=========================================================="
echo " PORTRAITRON 3000 - POC INTERACTIVE VERIFICATION SCRIPT"
echo "=========================================================="

# 1. Virtual Environment Activation
if [ ! -d "venv" ]; then
    echo -e "${RED}[ERROR]${NC} Local virtual environment 'venv' not found."
    echo "Please create it using Python 3.9 before running this script."
    exit 1
fi

echo "Activating virtual environment..."
source venv/bin/activate

# 2. Dependency Check
echo -e "\n${BLUE}[STEP 1/5]${NC} Checking python dependencies..."
python3 -c "
import sys
import yaml
import numpy
import matplotlib
import rtde_control
import rtde_receive
from src.common.logger import get_logger
get_logger('DependencyCheck').success('Success: all imports (ur_rtde, pyyaml, numpy, matplotlib) are working!')
"

# 3. Offline Plotting Simulation
echo -e "\n${BLUE}[STEP 2/5]${NC} Running offline trajectory plotting..."
echo "Verify that the generated semicircle looks correct and starts at center-minus-radius to the left."
python3 scripts/poc_circle.py --plot-only --radius 0.04 --theta 180

# 4. Calibration Wizard
echo -e "\n${BLUE}[STEP 3/5]${NC} Ready for Calibration?"
echo "This will connect to the physical robot at 192.168.57.101."
echo "You will be prompted to jog the robot to hover Bottom-Left (P0), then the robot will automatically probe P1, P2, P3."
read -p "Do you want to run workspace calibration now? [y/N]: " run_cal
if [[ "$run_cal" =~ ^[Yy]$ ]]; then
    python3 scripts/calibrate_workspace.py
else
    echo "Skipping calibration. (Will use existing config/calibration.yaml if available)"
fi

# 5. Air Run
echo -e "\n${BLUE}[STEP 4/5]${NC} Ready for Air Run?"
echo "This runs the semicircle drawing trajectory +50mm normal offset above the surface."
read -p "Do you want to execute the Air Run on the UR5e? [y/N]: " run_air
if [[ "$run_air" =~ ^[Yy]$ ]]; then
    python3 scripts/poc_circle.py --air-run --radius 0.04 --theta 180
else
    echo "Skipping Air Run."
fi

# 6. Real Drawing Run
echo -e "\n${BLUE}[STEP 5/5]${NC} Ready for Real Ink Drawing?"
echo "This will draw directly on the paper surface (0.0mm depth offset)."
read -p "Do you want to execute the Real Ink Run on the UR5e? [y/N]: " run_real
if [[ "$run_real" =~ ^[Yy]$ ]]; then
    python3 scripts/poc_circle.py --radius 0.04 --theta 180
else
    echo "Skipping Real Ink Run."
fi

echo "=========================================================="
echo -e "${GREEN}[SUCCESS]${NC} Verification Script Completed."
echo "=========================================================="
