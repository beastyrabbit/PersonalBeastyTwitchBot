import json

import redis

from module.message_utils import send_message_to_redis, register_exit_handler
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
pubsub.subscribe('twitch.command.unlurk')
pubsub.subscribe('twitch.command.back')
pubsub.subscribe('twitch.command.online')
pubsub.subscribe('twitch.command.show')

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def write_unlurk_to_redis(author_obj):
    """
    Record a user's unlurk status in Redis and send a confirmation message.

    Args:
        author_obj (dict): The author object containing user information
    """
    try:
        username = author_obj.get('display_name', author_obj['name'])
        username_lower = author_obj['name'].lower()
        user_key = f"user:{username_lower}"

        log_info(f"Processing unlurk command for {username}", "unlurk", {
            "user": username
        })

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user_obj = json.loads(user_json)
            log_debug(f"Found existing user {username}", "unlurk")
        else:
            log_info(f"Creating new user account for {username}", "unlurk")
            user_obj = {
                "name": author_obj["name"],
                "display_name": author_obj.get("display_name", author_obj["name"]),
                "log": {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0},
                "dustbunnies": {},
                "banking": {}
            }

        if "log" not in user_obj:
            log_debug(f"Creating log object for {username}", "unlurk")
            user_obj["log"] = {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0}

        previous_unlurk_count = user_obj["log"].get("unlurk", 0)
        user_obj["log"]["unlurk"] = previous_unlurk_count + 1

        redis_client.set(user_key, json.dumps(user_obj))

        log_info(f"User {username} has unlurked", "unlurk", {
            "previous_unlurk_count": previous_unlurk_count,
            "new_unlurk_count": user_obj["log"]["unlurk"]
        })

        send_message_to_redis(f"Lord! {author_obj['mention']} has returned to the realm")

    except Exception as e:
        error_msg = f"Error processing unlurk command: {e}"
        log_error(error_msg, "unlurk", {
            "error": str(e),
            "user": author_obj.get('display_name', author_obj.get('name', 'Unknown'))
        })
        print(error_msg)

##########################
# Main
##########################
# Send startup message
log_startup("Unlurk command is ready to be used", "unlurk")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content', '')
            print(f"Chat Command: {command} and Message: {content}")

            log_info(f"Received {command} command", "unlurk", {"content": content})
            write_unlurk_to_redis(message_obj["author"])

        except Exception as e:
            error_msg = f"Error processing unlurk command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "unlurk", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
