import json
import signal
import sys
import time
from datetime import datetime

import redis

from module.message_utils import log_startup, log_info, log_error, log_debug

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

REDIS_HOST = '192.168.50.115'
REDIS_PORT = 6379
REDIS_DB = 0
COMMANDS_KEY = 'twitch:messages:commands'  # Sorted set for all commands
MAX_STORED_COMMANDS = 5000  # Limit to prevent unbounded growth

##########################
# Initialize Redis
##########################
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
pubsub = redis_client.pubsub()
pubsub.psubscribe('twitch.command.*')

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    """Handle graceful exit by unsubscribing from Redis channels."""
    try:
        log_info("Command logger shutting down", "command_logger")
        print("Unsubscribing from all channels before exiting")
        pubsub.punsubscribe()
    except Exception as e:
        error_msg = f"Error during shutdown: {e}"
        print(error_msg)
        log_error(error_msg, "command_logger")
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Main
##########################
# Send startup message
log_startup("Command logger is now active and listening for commands", "command_logger")
for message in pubsub.listen():
    if message["type"] == "pmessage":
        try:
            # Parse the message
            try:
                message_obj = json.loads(message['data'].decode('utf-8'))
                channel = message['channel'].decode('utf-8')
                log_debug(f"Received command on channel: {channel}", "command_logger")
            except json.JSONDecodeError as je:
                error_msg = f"JSON decode error: {je}"
                log_error(error_msg, "command_logger", {"data": str(message.get('data', 'N/A'))})
                continue
            except UnicodeDecodeError as ue:
                error_msg = f"Unicode decode error: {ue}"
                log_error(error_msg, "command_logger", {"data": str(message.get('data', 'N/A'))})
                continue

            # Extract command name from channel (twitch.command.commandname)
            try:
                command_name = channel.split('.')[-1]
                log_debug(f"Processing command: {command_name}", "command_logger")
            except Exception as e:
                error_msg = f"Error extracting command name: {e}"
                log_error(error_msg, "command_logger", {"channel": channel})
                command_name = "unknown"

            # Ensure message follows our unified structure
            if 'type' not in message_obj:
                message_obj['type'] = 'command'
                log_debug("Added default type: command", "command_logger")

            if 'source' not in message_obj:
                message_obj['source'] = 'twitch'
                log_debug("Added default source: twitch", "command_logger")

            if 'timestamp' not in message_obj:
                message_obj['timestamp'] = datetime.now().isoformat()
                log_debug("Added timestamp to message", "command_logger")

            if 'metadata' not in message_obj:
                message_obj['metadata'] = {}

            if 'event_data' not in message_obj:
                message_obj['event_data'] = {}

            # Make sure command is in event_data
            if 'command' in message_obj:
                message_obj['event_data']['command'] = message_obj.pop('command')
                log_debug("Moved command to event_data", "command_logger")
            else:
                message_obj['event_data']['command'] = command_name

            # Add a numeric timestamp for Redis sorting
            current_time = time.time()
            message_obj['_score'] = current_time

            # Convert to JSON for storage
            message_json = json.dumps(message_obj)

            # Store in Redis with error handling
            try:
                # Store in commands sorted set
                redis_client.zadd(COMMANDS_KEY, {message_json: current_time})
                log_debug("Stored command in main collection", "command_logger")

                # Store in all messages set too
                redis_client.zadd('twitch:messages:all', {message_json: current_time})

                # Store in command-specific set for easy retrieval
                command_key = f"twitch:commands:{command_name}"
                redis_client.zadd(command_key, {message_json: current_time})
                log_debug(f"Stored command in command-specific collection: {command_name}", "command_logger")
            except redis.RedisError as re:
                error_msg = f"Redis error storing command: {re}"
                log_error(error_msg, "command_logger", {"error": str(re), "command": command_name})
                # Continue processing even if Redis storage fails

            # Prune if exceeding max count
            try:
                current_count = redis_client.zcard(COMMANDS_KEY)
                if current_count > MAX_STORED_COMMANDS:
                    # Remove oldest commands (lowest scores)
                    redis_client.zremrangebyrank(COMMANDS_KEY,
                                                0,
                                                current_count - MAX_STORED_COMMANDS - 1)
                    log_info(f"Pruned command history to {MAX_STORED_COMMANDS} commands", "command_logger", {
                        "removed": current_count - MAX_STORED_COMMANDS
                    })
            except redis.RedisError as re:
                error_msg = f"Redis error pruning commands: {re}"
                log_error(error_msg, "command_logger", {"error": str(re)})
                # Continue processing even if pruning fails

            # Unified user JSON logging for commands
            try:
                author = message_obj.get('author', {})
                username = author.get('name') or author.get('display_name')
                if username:
                    username_lower = username.lower()
                    user_key = f"user:{username_lower}"

                    log_debug(f"Processing user data for {username}", "command_logger")

                    user_data = redis_client.get(user_key)
                    if user_data:
                        user_json = json.loads(user_data)
                        log_debug(f"Found existing user {username}", "command_logger")
                    else:
                        log_info(f"Creating new user record for {username}", "command_logger")
                        user_json = {
                            "name": username,
                            "display_name": author.get('display_name', username),
                            "log": {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0},
                            "dustbunnies": {},
                            "banking": {}
                        }

                    # Use log sub-object for counters
                    if "log" not in user_json:
                        user_json["log"] = {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0}

                    # Update command count and last command
                    previous_count = user_json["log"].get("command", 0)
                    user_json["log"]["command"] = previous_count + 1
                    user_json["log"]["last_command"] = command_name
                    user_json["log"]["last_timestamp"] = message_obj["timestamp"]

                    redis_client.set(user_key, json.dumps(user_json))

                    log_debug(f"Updated user {username} command count to {user_json['log']['command']}", "command_logger")
            except Exception as ue:
                error_msg = f"Error updating user data: {ue}"
                log_error(error_msg, "command_logger", {
                    "error": str(ue),
                    "username": username if 'username' in locals() else "Unknown"
                })
                # Continue processing even if user update fails

            # Log the stored command
            author_name = message_obj.get('author', {}).get('display_name', 'Unknown')
            content = message_obj.get('content', '')

            log_info(f"Stored command from {author_name}: !{command_name}", "command_logger", {
                "command": command_name,
                "content_length": len(content)
            })
            print(f"Stored command: !{command_name} from {author_name} - {content}")

        except Exception as e:
            error_msg = f"Error processing command: {e}"
            print(error_msg)
            log_error(error_msg, "command_logger", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
