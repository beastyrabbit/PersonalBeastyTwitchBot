import json
import signal
import sys
import time
from datetime import datetime

from module.shared_redis import redis_client, pubsub
from module.shared_obs import send_custom_message

##########################
# Configuration
##########################

# Log level configuration
DEFAULT_LOG_LEVEL = "INFO"
LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
    'IMPORTANT': 55,  # New level for important notifications
    'STARTUP': 60
}

# Custom log styles configuration
# This allows customizing the appearance and behavior of each log level
LOG_STYLES = {
    'DEBUG': {
        'enabled': True,  # Whether this log level is enabled
        'style': 'message',  # Style: message, error, highlight
        'color': '#808080',  # Color for the message
        'user': {
            'name': 'Debug',
            'color': '#808080'
        },
        'icon': 'help',  # Icon to display with the message
        'format': '[DEBUG] {filename}:{lineno} - {content}',  # Message format
        'quote': 'Debug Information'  # Optional quote displayed in a dedicated holder
    },
    'INFO': {
        'enabled': True,
        'style': 'message',
        'color': '#1E90FF',
        'user': {
            'name': 'Info',
            'color': '#1E90FF'
        },
        'icon': 'info',
        'format': '[INFO] {filename}:{lineno} - {content}',
        'canClose': False,
    },
    'WARNING': {
        'enabled': True,
        'style': 'message',
        'color': '#FFA500',
        'highlightColor': '#FFF3E0',  # Lighter orange background
        'user': {
            'name': 'warning',
            'color': '#FFA500'
        },
        'icon': 'magnet',
        'format': '[WARNING] {filename}:{lineno} - {content}',
        'canClose': False
    },
    'ERROR': {
        'enabled': True,
        'style': 'error',
        'color': '#FF4500',
        'user': {
            'name': 'Error',
            'color': '#FF4500'
        },
        'icon': 'read',
        'format': '[ERROR] {filename}:{lineno} - {content}',
        'canClose': False
    },
    'CRITICAL': {
        'enabled': True,
        'style': 'error',
        'color': '#FF0000',
        'user': {
            'name': 'Critical',
            'color': '#FF0000'
        },
        'icon': 'emergency',
        'format': '[CRITICAL] {filename}:{lineno} - {content}',
        'canClose': False
    },
    'IMPORTANT': {
        'enabled': True,
        'style': 'highlight',
        'color': '#9932CC',  # Purple color for important notifications
        'highlightColor': '#F3E5F5',  # Light purple background
        'user': {
            'name': 'Important',
            'color': '#9932CC'
        },
        'icon': 'api',  # Notification icon
        'format': '[IMPORTANT] {filename}:{lineno} - {content}',
        'canClose': False,
        'todayFirst': True  # Show in "greet them" section
    },
    'STARTUP': {
        'enabled': True,
        'style': 'message',
        'color': '#32CD32',
        'highlightColor': '#E8F5E9',  # Light green background
        'user': {
            'name': 'Startup',
            'color': "#32CD32"
        },
        'icon': 'stars',
        'format': '[STARTUP] {filename}:{lineno} - {content}',
        'canClose': False,
    }
}

# Get log level from environment or use default
import os
SYSTEM_LOG_LEVEL_NAME = os.environ.get('SYSTEM_LOG_LEVEL', DEFAULT_LOG_LEVEL)

# Convert string level to numeric
if SYSTEM_LOG_LEVEL_NAME.isdigit():
    SYSTEM_LOG_LEVEL = int(SYSTEM_LOG_LEVEL_NAME)
else:
    SYSTEM_LOG_LEVEL_NAME = SYSTEM_LOG_LEVEL_NAME.upper()
    SYSTEM_LOG_LEVEL = LOG_LEVELS.get(SYSTEM_LOG_LEVEL_NAME, LOG_LEVELS['INFO'])

print(f"System logger running with log level: {SYSTEM_LOG_LEVEL_NAME} ({SYSTEM_LOG_LEVEL})")

##########################
# Initialize Redis
##########################
# Subscribe to system command pattern (and admin for backward compatibility)
pubsub.psubscribe('system.*', 'admin.*')

##########################
# Helper Functions
##########################
def format_log_message(level_name, content, caller=None, **kwargs):
    """
    Format a log message according to the configured style for the given level.

    Args:
        level_name (str): The name of the log level (DEBUG, INFO, etc.)
        content (str): The content of the log message
        caller (dict, optional): Information about the caller (filename, lineno)
        **kwargs: Additional formatting parameters

    Returns:
        dict: A formatted message object ready to be sent
    """
    original_level = level_name.upper()
    if original_level not in LOG_STYLES:
        # Throw an error for unknown log types
        error_msg = f"Unsupported log level: {original_level}"
        print(error_msg)
        # Set it to ERROR type and include the original level in the message
        level_name = 'ERROR'
        content = f"Unsupported log type '{original_level}' was tried to send: {content}"
    else:
        level_name = original_level

    style = LOG_STYLES[level_name]

    # Create caller info if not provided
    if caller is None:
        try:
            import inspect
            frame = inspect.currentframe().f_back.f_back  # Go back two frames to get the caller
            if frame is not None and hasattr(frame, 'f_code'):
                filename = frame.f_code.co_filename
                lineno = frame.f_lineno
                caller = {
                    'filename': filename.split('/')[-1],  # Just the filename, not the full path
                    'lineno': lineno
                }
            else:
                # If frame is None or doesn't have f_code, use default values
                caller = {
                    'filename': 'unknown',
                    'lineno': 0
                }
        except Exception as e:
            print(f"Error getting caller info: {e}")
            # Use default values if an error occurs
            caller = {
                'filename': 'unknown',
                'lineno': 0
            }

    # Format the message content
    format_str = style.get('format', '[{level_name}] {filename}:{lineno} - {content}')
    formatted_content = format_str.format(
        level_name=level_name,
        filename=caller.get('filename', 'unknown'),
        lineno=caller.get('lineno', '?'),
        content=content,
        **kwargs
    )

    # Create the message object
    message_obj = {
        'content': formatted_content,
        'raw_content': content,  # Store the original content
        'level': LOG_LEVELS.get(level_name, 0),
        'level_name': level_name,
        'timestamp': datetime.now().isoformat(),
        'caller': caller,
        'type': 'system',
        'source': 'system_logger',
        'metadata': {},
        'event_data': {}
    }

    # Add styling information
    message_obj['style'] = style.get('style', 'message')
    message_obj['color'] = style.get('color', '#FFFFFF')

    if 'highlightColor' in style:
        message_obj['highlightColor'] = style['highlightColor']

    if 'icon' in style:
        message_obj['icon'] = style['icon']

    if 'canClose' in style:
        message_obj['canClose'] = style['canClose']

    # Add user information
    if 'user' in style:
        message_obj['user'] = style['user']

    # Add any additional kwargs
    for key, value in kwargs.items():
        if key not in message_obj:
            message_obj[key] = value

    return message_obj

def send_log_message(level_name, content, caller=None, **kwargs):
    """
    Send a log message with the given level.

    Args:
        level_name (str): The name of the log level (DEBUG, INFO, etc.)
        content (str): The content of the log message
        caller (dict, optional): Information about the caller (filename, lineno)
        **kwargs: Additional formatting parameters

    Returns:
        bool: True if the message was sent, False otherwise
    """
    level_name = level_name.upper()

    # Check if this log level is enabled
    if level_name in LOG_STYLES and not LOG_STYLES[level_name].get('enabled', True):
        return False

    # Check if the log level exists
    if level_name not in LOG_LEVELS:
        # This should not happen as format_log_message should have caught it,
        # but just in case, handle it here too
        error_msg = f"Unsupported log level: {level_name}"
        print(error_msg)
        # Set it to ERROR type and include the original level in the message
        content = f"Unsupported log type '{level_name}' was tried to send: {content}"
        level_name = 'ERROR'
        level = LOG_LEVELS['ERROR']
    else:
        level = LOG_LEVELS[level_name]

    # Check if the log level is high enough
    if level < SYSTEM_LOG_LEVEL and level_name != 'STARTUP':
        return False

    # Format the message
    message_obj = format_log_message(level_name, content, caller, **kwargs)

    # Send the message to Redis
    channel = f"system.log.{level_name.lower()}"
    redis_client.publish(channel, json.dumps(message_obj))

    return True


##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels before exiting")
    pubsub.punsubscribe()
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "pmessage":  # Pattern message
        try:
            # Parse the message
            message_obj = json.loads(message['data'].decode('utf-8'))
            channel = message['channel'].decode('utf-8')

            # Extract command from channel name (system.commandname or admin.commandname)
            channel_parts = channel.split('.')
            command_type = channel_parts[0]  # 'system' or 'admin'
            command_name = channel_parts[-1]

            # Special handling for log messages
            is_log_message = False
            if command_type == 'system' and len(channel_parts) > 2 and channel_parts[1] == 'log':
                is_log_message = True
                # Get the log level name
                level_name = channel_parts[2].upper() if len(channel_parts) > 2 else 'UNKNOWN'

                # Extract the actual log level from the message object
                message_level_name = message_obj.get('level_name', 'UNKNOWN')

                # Check if this is a known log level in the message
                if message_level_name not in LOG_STYLES:
                    # Handle unknown log type
                    error_msg = f"Unsupported log level in message: {message_level_name}"
                    print(error_msg)
                    # Create an error message
                    error_content = f"Unsupported log type '{message_level_name}' was received"
                    # Create a new error message and publish it
                    error_obj = format_log_message('ERROR', error_content)
                    redis_client.publish('system.log.error', json.dumps(error_obj))
                    # Skip processing this message
                    continue

                # Use the level from the message object instead of the channel
                level_name = message_level_name

                # Check if this log level is enabled in the configuration
                if not LOG_STYLES[level_name].get('enabled', True):
                    # Skip messages for disabled log levels
                    continue

                # Check if the log level is high enough to process
                log_level = message_obj.get('level', 0)
                if log_level < SYSTEM_LOG_LEVEL and log_level != LOG_LEVELS.get('STARTUP', 60):
                    # Skip messages below the configured log level, but always process STARTUP messages
                    continue

                # For log messages, use the command as the command_name
                if len(channel_parts) > 2:
                    command_name = channel_parts[2]  # system.log.commandname


            # Create a standard message object if one doesn't exist
            if isinstance(message_obj, str) or not isinstance(message_obj, dict):
                # If message_obj is just a string or not a dict, create a new structure
                content = str(message_obj)
                message_obj = {
                    "content": content
                }

            # Ensure message follows our unified structure
            if 'type' not in message_obj:
                message_obj['type'] = command_type  # 'system' or 'admin'

            if 'source' not in message_obj:
                message_obj['source'] = 'system'

            if 'timestamp' not in message_obj:
                message_obj['timestamp'] = datetime.now().isoformat()

            if 'metadata' not in message_obj:
                message_obj['metadata'] = {}

            if 'event_data' not in message_obj:
                message_obj['event_data'] = {}

            # Add command details
            message_obj['event_data']['command_name'] = command_name
            # Keep admin_command for backward compatibility
            message_obj['event_data']['admin_command'] = command_name


            # Print appropriate message based on message type
            if is_log_message:
                level_name = message_obj.get('level_name', 'UNKNOWN')
                caller = message_obj.get('caller', {})
                filename = caller.get('filename', 'unknown')
                lineno = caller.get('lineno', '?')

                # Apply styling from LOG_STYLES
                style = LOG_STYLES.get(level_name, LOG_STYLES['INFO'])

                # Apply styling to message_obj if not already present
                if 'style' not in message_obj:
                    message_obj['style'] = style.get('style', 'message')

                if 'color' not in message_obj:
                    message_obj['color'] = style.get('color', '#FFFFFF')

                if 'highlightColor' not in message_obj and 'highlightColor' in style:
                    message_obj['highlightColor'] = style['highlightColor']

                if 'icon' not in message_obj and 'icon' in style:
                    message_obj['icon'] = style['icon']

                if 'canClose' not in message_obj and 'canClose' in style:
                    message_obj['canClose'] = style['canClose']

                if 'user' not in message_obj and 'user' in style:
                    message_obj['user'] = style['user']

                if 'quote' not in message_obj and 'quote' in style:
                    message_obj['quote'] = style['quote']

                if 'todayFirst' not in message_obj and 'todayFirst' in style:
                    message_obj['todayFirst'] = style['todayFirst']

                # Extract styling from extra_data if present
                if 'extra_data' in message_obj:
                    extra_data = message_obj.pop('extra_data')
                    for key, value in extra_data.items():
                        if key not in message_obj:
                            message_obj[key] = value

                # Build style_info string for console output
                style_info = f"style={message_obj.get('style', 'message')}"

                if 'color' in message_obj:
                    style_info += f", color={message_obj['color']}"

                if 'icon' in message_obj:
                    style_info += f", icon={message_obj['icon']}"

                print(f"[{level_name}] {filename}:{lineno} - {message_obj.get('content', 'No content')} ({style_info})")

                # Send log message to OBS
                try:
                    # Create a copy of the message object for OBS
                    obs_message = message_obj.copy()

                    # Format the message for OBS if needed
                    if 'message' not in obs_message:
                        obs_message['message'] = obs_message.get('content', 'No content')

                    # Ensure all required fields for Twitchat are present
                    if 'style' not in obs_message:
                        obs_message['style'] = 'message'

                    # Add col parameter for positioning if not present
                    if 'col' not in obs_message:
                        obs_message['col'] = 0  # Default to first column

                    # Send to OBS
                    send_custom_message(obs_message)
                except Exception as e:
                    print(f"Error sending log message to OBS: {e}")
            else:
                print(f"Stored {command_type} command: {command_name} - {message_obj.get('content', 'No content')}")

        except Exception as e:
            print(f"Error processing {command_type if 'command_type' in locals() else 'admin/system'} command: {e}")
            print(f"Message data: {message.get('data', 'N/A')}")
