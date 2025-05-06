#!/usr/bin/env python3
"""
Game of Life Command

This command implements Conway's Game of Life as a web visualization.
It can be triggered with 'gameoflife', 'gol', or 'gl' commands.

Features:
- Full HD web visualization
- Configurable pixel size
- Seed parameter for reproducible results
- Automatic running with dustbunnies rewards
- Speed-up after configurable time intervals
- Detection for stable states (infinite loops or dead cells)
- Configurable maximum duration
"""

# Import the main module from the GOL package
from commands.games.GOL.command_handler import start_command_handler

if __name__ == "__main__":
    # Start the command handler
    start_command_handler()
