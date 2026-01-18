#!/usr/bin/env python3
"""
Quick launcher for LLMUD Terminal App.

Run from project root: python play.py
Or: ./play.py (after chmod +x play.py)
"""

import sys
import os

# Add mud_client to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mud_client'))

from llmud.terminal_app import main

if __name__ == "__main__":
    main()

