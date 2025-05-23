#!/usr/bin/env python3
"""Template for creating new command files in the TwitchBotV2 project.

Usage: Copy, rename, modify subscriptions and implement command logic.
"""
import json

from module.message_utils import register_exit_handler, log_startup, log_info, log_error
from module.shared_obs import get_obs_client
from module.shared_redis import pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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
    """Processes the received command message.

    @param message_obj: The parsed message object from Twitch
    """
    # Example of using OBS client with the new pattern
    obs_client = get_obs_client()
    if obs_client is not None:
        try:
            # Use OBS client here
            log_info("Using OBS client", "example")
            pass
        except Exception as e:
            error_msg = f"Error using OBS client: {e}"
            print(error_msg)
            log_error(error_msg, "example", {"error": str(e)})
    return

##########################
# Main
##########################
# Send startup message
log_startup("Example command is ready to be used", "example")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            print(f"Chat Command: {command} and Message: {content}")
            log_info(f"Received command: {command}", "example", {"content": content})
            handle_command(message_obj)
        except Exception as e:
            error_msg = f"Error processing command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "example", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
