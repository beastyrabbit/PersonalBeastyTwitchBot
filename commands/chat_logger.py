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
CHAT_MESSAGES_KEY = 'twitch:messages:all'  # Sorted set for time-based storage
MAX_STORED_MESSAGES = 10000  # Limit to prevent unbounded growth

##########################
# Initialize Redis
##########################
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.chat.received')

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    """Handle graceful exit by unsubscribing from Redis channels."""
    try:
        log_info("Chat logger shutting down", "chat_logger")
        print("Unsubscribing from all channels before exiting")
        pubsub.unsubscribe()
    except Exception as e:
        error_msg = f"Error during shutdown: {e}"
        print(error_msg)
        log_error(error_msg, "chat_logger")
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Main
##########################
# Send startup message
log_startup("Chat logger is now active and listening for messages", "chat_logger")
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            # Parse the message
            try:
                message_obj = json.loads(message['data'].decode('utf-8'))
                log_debug("Received chat message", "chat_logger")
            except json.JSONDecodeError as je:
                error_msg = f"JSON decode error: {je}"
                log_error(error_msg, "chat_logger", {"data": str(message.get('data', 'N/A'))})
                continue

            # Use existing timestamp if available, otherwise add one
            if 'timestamp' not in message_obj:
                message_obj['timestamp'] = datetime.now().isoformat()
                log_debug("Added timestamp to message", "chat_logger")

            # Add a numeric timestamp for Redis sorting
            current_time = time.time()
            message_obj['_score'] = current_time  # Hidden field just for sorting

            # Store in sorted set with timestamp as score (legacy, for history)
            message_json = json.dumps(message_obj)
            try:
                redis_client.zadd(CHAT_MESSAGES_KEY, {message_json: current_time})
                log_debug("Stored message in main collection", "chat_logger")
            except redis.RedisError as re:
                error_msg = f"Redis error storing message: {re}"
                log_error(error_msg, "chat_logger", {"error": str(re)})
                continue

            # --- Unified user JSON logic ---
            try:
                author = message_obj.get('author', {})
                username = author.get('name') or author.get('display_name')
                if username:
                    username_lower = username.lower()
                    user_key = f"user:{username_lower}"

                    log_debug(f"Processing user data for {username}", "chat_logger")

                    user_data = redis_client.get(user_key)
                    if user_data:
                        user_json = json.loads(user_data)
                        log_debug(f"Found existing user {username}", "chat_logger")
                    else:
                        log_info(f"Creating new user record for {username}", "chat_logger")
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

                    # Update chat count and last message
                    previous_count = user_json["log"].get("chat", 0)
                    user_json["log"]["chat"] = previous_count + 1
                    user_json["log"]["last_message"] = message_obj.get("content", "")
                    user_json["log"]["last_timestamp"] = message_obj["timestamp"]

                    redis_client.set(user_key, json.dumps(user_json))

                    log_debug(f"Updated user {username} chat count to {user_json['log']['chat']}", "chat_logger")
            except Exception as ue:
                error_msg = f"Error updating user data: {ue}"
                log_error(error_msg, "chat_logger", {
                    "error": str(ue),
                    "username": username if 'username' in locals() else "Unknown"
                })
                # Continue processing even if user update fails

            # Store in type-specific set if needed
            try:
                if 'type' in message_obj:
                    type_key = f"twitch:messages:{message_obj['type']}"
                    redis_client.zadd(type_key, {message_json: current_time})
                    log_debug(f"Stored message in type collection: {message_obj['type']}", "chat_logger")
            except redis.RedisError as re:
                error_msg = f"Redis error storing message in type collection: {re}"
                log_error(error_msg, "chat_logger", {"error": str(re)})
                # Continue processing even if type-specific storage fails

            # Prune if exceeding max count (for main collection)
            try:
                current_count = redis_client.zcard(CHAT_MESSAGES_KEY)
                if current_count > MAX_STORED_MESSAGES:
                    # Remove oldest messages (lowest scores)
                    redis_client.zremrangebyrank(CHAT_MESSAGES_KEY,
                                                0,
                                                current_count - MAX_STORED_MESSAGES - 1)
                    log_info(f"Pruned chat history to {MAX_STORED_MESSAGES} messages", "chat_logger", {
                        "removed": current_count - MAX_STORED_MESSAGES
                    })
            except redis.RedisError as re:
                error_msg = f"Redis error pruning messages: {re}"
                log_error(error_msg, "chat_logger", {"error": str(re)})
                # Continue processing even if pruning fails

            # Log the stored message
            message_type = message_obj.get('type', 'unknown')
            content = message_obj.get('content', '')
            display_name = message_obj.get('author', {}).get('display_name', 'Unknown')

            log_info(f"Stored chat message from {display_name}", "chat_logger", {
                "type": message_type,
                "content_length": len(content)
            })
            print(f"Stored {message_type} message: {content}")

        except Exception as e:
            error_msg = f"Error processing message: {e}"
            print(error_msg)
            log_error(error_msg, "chat_logger", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
