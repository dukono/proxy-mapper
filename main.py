#!/usr/bin/env python3
"""
Proxy Monitor - A modern Python proxy with UI for monitoring and mocking HTTP traffic.

Usage:
    python main.py

Then configure your browser/system to use proxy at localhost:8080
and open the UI at http://localhost:8081
"""

import sys
import os

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import main

if __name__ == "__main__":
    main()
