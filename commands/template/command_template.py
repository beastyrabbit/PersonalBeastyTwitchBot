#!/usr/bin/env python3
"""Template for creating new command files in the TwitchBotV2 project.

Usage: Copy, rename, modify subscriptions and implement command logic.
"""
import json

from module.message_utils import (
    register_exit_handler, 
    log_startup, log_debug, log_info, log_warning, log_error, log_critical
)
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
    # Example of using different log levels with custom styling
    command = message_obj.get('command')
    content = message_obj.get('content')
    username = message_obj.get('author', {}).get('name', 'Unknown')

    # Debug log example - detailed information for debugging
    log_debug(f"Processing command '{command}' with content: '{content}'", "example", {
        "user": username,
        "timestamp": message_obj.get('timestamp')
    })

    # Example of using OBS client with the new pattern
    obs_client = get_obs_client()
    if obs_client is not None:
        try:
            # Use OBS client here
            log_info("Using OBS client for command processing", "example", {
                "command": command,
                "user": username
            })

            # Example of a warning log
            if command == "example" and not content:
                log_warning("Command used without parameters", "example", {
                    "user": username,
                    "suggestion": "Try using '!example parameter' instead"
                })

            # Simulate different scenarios for demonstration
            if content and content.lower() == "error":
                # Demonstrate error logging
                log_error("User requested error demonstration", "example", {
                    "user": username,
                    "content": content
                })

            elif content and content.lower() == "critical":
                # Demonstrate critical error logging
                log_critical("User requested critical error demonstration", "example", {
                    "user": username,
                    "content": content,
                    "actions": [
                        {
                            "label": "Reset System",
                            "actionType": "message",
                            "message": "!reset",
                            "theme": "danger"
                        }
                    ]
                })

            else:
                # Normal info logging with custom styling
                log_info(f"Command '{command}' processed successfully", "example", {
                    "user": username,
                    "content": content,
                    # Custom styling overrides for this specific message
                    "icon": "check-circle",
                    "style": "highlight",
                    "highlightColor": "#E6F7FF"
                })

        except Exception as e:
            error_msg = f"Error using OBS client: {e}"
            print(error_msg)
            log_error(error_msg, "example", {
                "error": str(e),
                "user": username,
                "command": command
            })
    return

##########################
# Main
##########################
# Send startup message with custom styling
log_startup("Example command is ready to be used", "example", {
    "version": "1.0.0",
    "config": {
        "log_level": LOG_LEVEL,
        "cooldown": COOLDOWN_SECONDS
    },
    # Custom styling for this specific startup message
    "icon": "rocket",
    "actions": [
        {
            "label": "View Documentation",
            "actionType": "url",
            "url": "https://example.com/docs",
            "urlTarget": "_blank",
            "theme": "info"
        }
    ]
})

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            # Parse the message data
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            username = message_obj.get('author', {}).get('name', 'Unknown')

            # Log the received command with basic info
            log_info(f"Received command: {command}", "example", {
                "user": username,
                "content": content,
                "timestamp": message_obj.get('timestamp')
            })

            # Print to console for debugging
            print(f"Chat Command: {command} from {username}: {content}")

            # Process the command
            handle_command(message_obj)

        except json.JSONDecodeError as e:
            # Specific handling for JSON parsing errors
            error_msg = f"Invalid JSON format in message: {e}"
            print(error_msg)
            log_error(error_msg, "example", {
                "error": str(e),
                "error_type": "JSONDecodeError",
                "message_data": str(message.get('data', 'N/A')),
                "icon": "file-code"  # Custom icon for JSON errors
            })

        except Exception as e:
            # General error handling
            error_msg = f"Error processing command: {e}"
            print(error_msg)

            # Get detailed traceback information
            import traceback
            tb_str = traceback.format_exc()

            # Log the error with detailed information and custom styling
            log_error(error_msg, "example", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
