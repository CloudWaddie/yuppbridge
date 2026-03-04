#!/usr/bin/env python3
"""
YuppBridge Setup Script

Run this script to configure YuppBridge with an interactive wizard.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src import config


def main():
    """Run the configuration wizard."""
    print()
    config.ensure_config_exists()
    print()


if __name__ == "__main__":
    main()
