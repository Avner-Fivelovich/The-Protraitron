#!/usr/bin/env python3
"""
Root entry point wrapper for the Portraitron 3000 Command Generator Dashboard.
Delegates to src/command_generator/server.py.
"""
import sys
import os

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.command_generator.server import main

if __name__ == "__main__":
    main()
