import json
import signal
import sys
import time
from datetime import datetime

import redis

##########################
# Configuration
##########################
REDIS_HOST = '192.168.50.115'
REDIS_PORT = 6379
REDIS_DB = 0
SYSTEM_COMMANDS_KEY = 'twitch:messages:system'  # Sorted set for all system commands
ADMIN_COMMANDS_KEY = 'twitch:messages:admin'  # Legacy key for backward compatibility
HELPER_COMMANDS_KEY = 'twitch:messages:helper'  # Sorted set for all helper commands
LOG_MESSAGES_KEY = 'twitch:messages:log'  # Sorted set for all log messages
MAX_STORED_COMMANDS = 5000  # Limit to prevent unbounded growth

# Log level configuration
DEFAULT_LOG_LEVEL = "INFO"
LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
    'STARTUP': 60
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
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
pubsub = redis_client.pubsub()

# Subscribe to system command pattern (and admin for backward compatibility)
pubsub.psubscribe('system.*', 'admin.*')

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

            # Unified user JSON logging for system commands
            author = message_obj.get('author', {})
            username = author.get('name') or author.get('display_name')
            if username:
                username_lower = username.lower()
                user_key = f"user:{username_lower}"
                user_data = redis_client.get(user_key)
                if user_data:
                    user_json = json.loads(user_data)
                else:
                    user_json = {
                        "name": username,
                        "display_name": author.get('display_name', username),
                        "log": {"chat": 0, "command": 0, "admin": 0, "system": 0, "lurk": 0, "unlurk": 0},
                        "dustbunnies": {},
                        "banking": {}
                    }
                if "log" not in user_json:
                    user_json["log"] = {"chat": 0, "command": 0, "admin": 0, "system": 0, "lurk": 0, "unlurk": 0}

                # Increment the appropriate counter based on message type
                if command_type == 'system':
                    user_json["log"]["system"] = user_json["log"].get("system", 0) + 1
                    user_json["log"]["last_system_command"] = command_name
                else:  # 'admin' for backward compatibility
                    user_json["log"]["admin"] = user_json["log"].get("admin", 0) + 1
                    user_json["log"]["last_admin_command"] = command_name

                user_json["log"]["last_timestamp"] = message_obj["timestamp"]
                redis_client.set(user_key, json.dumps(user_json))

            # Add a numeric timestamp for Redis sorting
            current_time = time.time()
            message_obj['_score'] = current_time

            # Convert to JSON for storage
            message_json = json.dumps(message_obj)

            # Store in appropriate commands sorted set
            if is_log_message:
                # Store log messages in the log messages set
                redis_client.zadd(LOG_MESSAGES_KEY, {message_json: current_time})
                # Also store in level-specific set
                level_name = message_obj.get('level_name', 'UNKNOWN')
                level_key = f"twitch:log:{level_name.lower()}"
                redis_client.zadd(level_key, {message_json: current_time})
            elif message_obj['type'] == 'helper':
                redis_client.zadd(HELPER_COMMANDS_KEY, {message_json: current_time})
            elif message_obj['type'] == 'system':
                redis_client.zadd(SYSTEM_COMMANDS_KEY, {message_json: current_time})
            else:  # 'admin' for backward compatibility
                redis_client.zadd(ADMIN_COMMANDS_KEY, {message_json: current_time})

            # Store in all messages set too
            redis_client.zadd('twitch:messages:all', {message_json: current_time})

            # Store in command-specific set for easy retrieval
            if is_log_message:
                # For log messages, use a different key pattern
                command_key = f"twitch:log:{command_name}"
            elif command_type == 'system':
                command_key = f"twitch:system:{command_name}"
            else:  # 'admin' for backward compatibility
                command_key = f"twitch:admin:{command_name}"

            redis_client.zadd(command_key, {message_json: current_time})

            # Prune if exceeding max count
            if is_log_message:
                current_count = redis_client.zcard(LOG_MESSAGES_KEY)
                if current_count > MAX_STORED_COMMANDS:
                    # Remove oldest log messages (lowest scores)
                    redis_client.zremrangebyrank(LOG_MESSAGES_KEY,
                                                0,
                                                current_count - MAX_STORED_COMMANDS - 1)
            elif command_type == 'system':
                current_count = redis_client.zcard(SYSTEM_COMMANDS_KEY)
                if current_count > MAX_STORED_COMMANDS:
                    # Remove oldest commands (lowest scores)
                    redis_client.zremrangebyrank(SYSTEM_COMMANDS_KEY,
                                                0,
                                                current_count - MAX_STORED_COMMANDS - 1)
            else:  # 'admin' for backward compatibility
                current_count = redis_client.zcard(ADMIN_COMMANDS_KEY)
                if current_count > MAX_STORED_COMMANDS:
                    # Remove oldest commands (lowest scores)
                    redis_client.zremrangebyrank(ADMIN_COMMANDS_KEY,
                                                0,
                                                current_count - MAX_STORED_COMMANDS - 1)

            # Print appropriate message based on message type
            if is_log_message:
                level_name = message_obj.get('level_name', 'UNKNOWN')
                caller = message_obj.get('caller', {})
                filename = caller.get('filename', 'unknown')
                lineno = caller.get('lineno', '?')
                print(f"[{level_name}] {filename}:{lineno} - {message_obj.get('content', 'No content')}")
            else:
                print(f"Stored {command_type} command: {command_name} - {message_obj.get('content', 'No content')}")

        except Exception as e:
            print(f"Error processing {command_type if 'command_type' in locals() else 'admin/system'} command: {e}")
            print(f"Message data: {message.get('data', 'N/A')}")
