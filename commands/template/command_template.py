#!/usr/bin/env python3
"""
Command Template

This template provides a standardized structure for creating new command files
in the TwitchBotV2 project. Replace this docstring with a description of your command.

Usage:
- Copy this file to the appropriate command subdirectory
- Rename it to your command name (e.g. mycommand.py)
- Modify the command subscription, permissions, and logic as needed
- Add your command function implementation
"""
import json

from module.message_utils import send_admin_message_to_redis, register_exit_handler
from module.shared_obs import get_obs_client
from module.shared_redis import pubsub

##########################
# Initialize
##########################
# Replace with your command name(s)
pubsub.subscribe('twitch.command.example')
pubsub.subscribe('twitch.command.alias')  # Optional additional command aliases

# Initialize any command-specific variables here
COOLDOWN_SECONDS = 30
cooldown_users = {}

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################


def handle_command(message_obj):
    # Example of using OBS client with the new pattern
    obs_client = get_obs_client()
    if obs_client is not None:
        try:
            # Use OBS client here
            pass
        except Exception as e:
            print(f"Error using OBS client: {e}")
    return
    
##########################
# Main
##########################
send_admin_message_to_redis("Example command is ready to be used", command="example")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            handle_command(message_obj)
        except Exception as e:
            print(f"Error processing command: {e}")
            # Optionally send error to admin channel
            send_admin_message_to_redis(f"Error in example command: {str(e)}", command="example")