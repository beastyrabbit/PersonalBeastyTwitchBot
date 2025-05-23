import json

import redis

from module.message_utils import send_system_message_to_redis, send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)

pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.lurk')
pubsub.subscribe('twitch.command.hide')
pubsub.subscribe('twitch.command.away')
pubsub.subscribe('twitch.command.offline')

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def write_lurk_to_redis(author_obj):
    """
    Record a user's lurk status in Redis and send a confirmation message.

    Args:
        author_obj (dict): The author object containing user information
    """
    try:
        username = author_obj.get('display_name', author_obj['name'])
        username_lower = author_obj['name'].lower()
        user_key = f"user:{username_lower}"

        log_info(f"Processing lurk command for {username}", "lurk", {
            "user": username
        })

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user_obj = json.loads(user_json)
            log_debug(f"Found existing user {username}", "lurk")
        else:
            log_info(f"Creating new user account for {username}", "lurk")
            user_obj = {
                "name": author_obj["name"],
                "display_name": author_obj.get("display_name", author_obj["name"]),
                "log": {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0},
                "dustbunnies": {},
                "banking": {}
            }

        if "log" not in user_obj:
            log_debug(f"Creating log object for {username}", "lurk")
            user_obj["log"] = {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0}

        previous_lurk_count = user_obj["log"].get("lurk", 0)
        user_obj["log"]["lurk"] = previous_lurk_count + 1

        redis_client.set(user_key, json.dumps(user_obj))

        log_info(f"User {username} is now lurking", "lurk", {
            "previous_lurk_count": previous_lurk_count,
            "new_lurk_count": user_obj["log"]["lurk"]
        })

        send_message_to_redis(f"{author_obj['mention']} will be cheering from the shadows!")

    except Exception as e:
        error_msg = f"Error processing lurk command: {e}"
        log_error(error_msg, "lurk", {
            "error": str(e),
            "user": author_obj.get('display_name', author_obj.get('name', 'Unknown'))
        })
        print(error_msg)

##########################
# Main
##########################
# Send startup message
log_startup("Lurk command is ready to be used", "lurk")
send_system_message_to_redis("Lurk command is running", "lurk")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            print(f"Chat Command: {command} and Message: {content}")

            log_info(f"Received {command} command", "lurk", {"content": content})
            write_lurk_to_redis(message_obj["author"])

        except Exception as e:
            error_msg = f"Error processing lurk command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "lurk", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_system_message_to_redis(f"Error in lurk command: {str(e)}", "lurk")
