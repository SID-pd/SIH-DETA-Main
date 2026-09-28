#!/usr/bin/env python3
"""Convenience launcher for SIH-DETA SSH server hardware & capability inspector."""
import sys
from pathlib import Path

# Add Historical-Delay-Records to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "Historical-Delay-Records"))

from system_check import print_system_diagnostic

if __name__ == "__main__":
    print_system_diagnostic()
