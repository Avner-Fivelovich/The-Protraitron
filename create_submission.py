#!/usr/bin/env python3
"""
Create a submission zip file for The Portraitron 3000 project.
Includes all essential code, configs, documentation, and tests.
Excludes: .venv, __pycache__, plots, large media files, archive folders, etc.
"""

import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT_ROOT = Path(__file__).parent.resolve()
ZIP_NAME = f"Portraitron_Submission_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
ZIP_PATH = PROJECT_ROOT / ZIP_NAME

# Files and directories to include
INCLUDE_FILES = [
    "main.py",
    "requirements.txt",
    "README.md",
    "LICENSE",
]

INCLUDE_DIRS = [
    "src",
    "config",
    "tests",
    "scripts",
    "docs",
]

# Patterns to exclude
EXCLUDE_PATTERNS = {
    "__pycache__",
    ".venv",
    ".git",
    "*.pyc",
    ".pytest_cache",
    ".DS_Store",
    ".calibrate_gui_state.yaml",
}

EXCLUDE_DIRS = {
    "plots",
    "pictures",
    "Presentation",
    "hardware",
    "archive",
    "SwiftSketch-Protraitron",
    "web_server",  # Large pre-trained model directory
}

# Files to exclude from src/
EXCLUDE_FROM_SRC = {
    "hila.py",  # Unused standalone test script
}

# Scripts to exclude
EXCLUDE_SCRIPTS = {
    "test_ur5e_connection_yulia.py",  # Duplicate of test_ur5e_connection.py
    "send_notification.py",           # Email utility, not part of core workflow
    "new_robot_test.py",              # Minimal test, redundant with test_ur5e_connection.py
    "test_ur5e_nudge.py",             # Unused test script
}

# Config files to exclude
EXCLUDE_CONFIG_FILES = {
    "paper_manipulation.yaml.example",  # Keep only the main file
    "server.yaml.example",              # Keep only the main file
}


def should_exclude(path_obj, parent_dir=""):
    """Check if path should be excluded."""
    name = path_obj.name
    
    # Check exact filename exclusions in src/
    if parent_dir and "src" in parent_dir and name in EXCLUDE_FROM_SRC:
        return True
    
    # Check script exclusions
    if parent_dir and "scripts" in parent_dir and name in EXCLUDE_SCRIPTS:
        return True
    
    # Check config file exclusions
    if parent_dir and "config" in parent_dir and name in EXCLUDE_CONFIG_FILES:
        return True
    
    # Check common exclusions
    if name in EXCLUDE_PATTERNS:
        return True
    
    # Check directory exclusions at root level
    if path_obj.is_dir() and name in EXCLUDE_DIRS:
        return True
    
    # Exclude hidden files/dirs (except certain cases)
    if name.startswith("."):
        return True
    
    return False


def add_files_to_zip(zf, source_path, arcname=""):
    """Recursively add files to zip, respecting exclusion rules."""
    source_path = Path(source_path)
    
    if not source_path.exists():
        print(f"  ⚠️  Skipping missing: {source_path}")
        return
    
    if source_path.is_file():
        if not should_exclude(source_path):
            zf.write(source_path, arcname=arcname)
            print(f"  ✓ {arcname}")
    
    elif source_path.is_dir():
        if should_exclude(source_path, parent_dir=str(source_path)):
            print(f"  ⊘ Excluding directory: {source_path.name}/")
            return
        
        for item in source_path.iterdir():
            item_arcname = f"{arcname}/{item.name}" if arcname else item.name
            
            if should_exclude(item, parent_dir=str(source_path)):
                if item.is_dir():
                    print(f"  ⊘ Excluding: {item_arcname}/")
                else:
                    print(f"  ⊘ Excluding: {item_arcname}")
                continue
            
            add_files_to_zip(zf, item, item_arcname)


def create_submission_zip():
    """Create the submission zip file."""
    print(f"\n{'=' * 60}")
    print(f"Creating Portraitron Submission Zip")
    print(f"{'=' * 60}\n")
    
    if ZIP_PATH.exists():
        print(f"⚠️  {ZIP_NAME} already exists. Overwriting...\n")
        ZIP_PATH.unlink()
    
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add root-level files
        print("📄 Root Files:")
        for file in INCLUDE_FILES:
            file_path = PROJECT_ROOT / file
            if file_path.exists():
                zf.write(file_path, arcname=file)
                print(f"  ✓ {file}")
            else:
                print(f"  ⚠️  Missing: {file}")
        
        # Add directories
        print("\n📁 Directories:")
        for dir_name in INCLUDE_DIRS:
            dir_path = PROJECT_ROOT / dir_name
            if dir_path.exists():
                print(f"\n  {dir_name}/")
                add_files_to_zip(zf, dir_path, arcname=dir_name)
            else:
                print(f"  ⚠️  Missing directory: {dir_name}/")
    
    # Print summary
    zip_size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"\n{'=' * 60}")
    print(f"✅ Submission zip created successfully!")
    print(f"{'=' * 60}")
    print(f"\n📦 File: {ZIP_PATH}")
    print(f"📊 Size: {zip_size_mb:.2f} MB")
    print(f"\n📋 Contents Summary:")
    print(f"   • main.py (entry point)")
    print(f"   • src/ (core modules, excluding hila.py)")
    print(f"   • config/ (YAML configuration files)")
    print(f"   • tests/ (unit tests)")
    print(f"   • scripts/ (calibration and utilities)")
    print(f"   • docs/ (documentation)")
    print(f"   • README.md (project overview & full documentation)")
    print(f"   • requirements.txt (dependencies)")
    print(f"\n🚫 Excluded:")
    print(f"   • archive/ (legacy code)")
    print(f"   • plots/ (generated outputs)")
    print(f"   • web_server/ (large pre-trained models)")
    print(f"   • .venv/ (virtual environment)")
    print(f"   • __pycache__/ (Python cache)")
    print(f"   • src/robot/hila.py (unused test script)")
    print(f"   • scripts/test_ur5e_connection_yulia.py (duplicate)")
    print(f"   • scripts/send_notification.py (email utility, not core)")
    print(f"   • scripts/new_robot_test.py (redundant test)")
    print(f"   • scripts/test_ur5e_nudge.py (unused)")
    print(f"   • config/paper_manipulation.yaml.example (kept only main file)")
    print(f"   • config/server.yaml.example (kept only main file)")
    print(f"\n✨ Ready for submission!\n")
    
    return ZIP_PATH


if __name__ == "__main__":
    try:
        zip_file = create_submission_zip()
    except Exception as e:
        print(f"\n❌ Error creating zip: {e}")
        exit(1)
