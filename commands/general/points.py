import json

from module.message_utils import send_system_message_to_redis, send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning
from module.shared_redis import redis_client, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.points')
pubsub.subscribe('twitch.command.stats')
pubsub.subscribe('twitch.command.dustbunnies')
pubsub.subscribe('twitch.command.balance')

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def print_statistics(username, command_name="points"):
    """
    Retrieve and display user statistics including dustbunnies and banking information.

    Args:
        username (str): The username to check statistics for
        command_name (str, optional): The command that triggered this function. Defaults to "points".
    """
    try:
        log_info(f"Retrieving statistics for {username}", command_name, {
            "user": username
        })

        username_lower = username.lower()
        # remove the "@" from the username if it exists
        if username_lower.startswith("@"):
            username_lower = username_lower[1:]

        user_key = f"user:{username_lower}"

        if redis_client.exists(user_key):
            log_debug(f"Found user data for {username}", command_name)
            user_json = redis_client.get(user_key)
            user_obj = json.loads(user_json)

            # User log information
            log = user_obj.get("log", {})
            chat_count = log.get("chat", 0)
            command_count = log.get("command", 0)
            last_command = log.get("last_command", "none")

            # Dustbunnies information
            dustbunnies = user_obj.get("dustbunnies", {})
            collected = dustbunnies.get("collected_dustbunnies", 0)
            message_count = dustbunnies.get("message_count", 0)

            # Banking information
            banking = user_obj.get("banking", {})
            invested = banking.get("bunnies_invested", 0)
            total_collected = banking.get("total_bunnies_collected", 0)
            interest_collected = banking.get("last_interest_collected", 0)

            # Send formatted messages with statistics
            display_name = user_obj.get("display_name", username)

            log_info(f"Retrieved statistics for {display_name}", command_name, {
                "chat_count": chat_count,
                "command_count": command_count,
                "dustbunnies": collected,
                "invested": invested,
                "interest": interest_collected
            })

            # Stats summary
            # send_message_to_redis(f"{display_name} has sent {chat_count} chat messages and used {command_count} commands. Last command: {last_command}", command="stats")

            # Dustbunnies summary
            send_message_to_redis(f"{display_name} has collected {collected} dustbunnies total", command="dustbunnies")

            # Banking summary
            if invested > 0:
                send_message_to_redis(f"{display_name} has invested {invested} dustbunnies and earned {interest_collected} in interest", command="balance")
            else:
                send_message_to_redis(f"{display_name} has not invested any dustbunnies yet", command="balance")
        else:
            log_warning(f"No user data found for {username}", command_name)
            send_message_to_redis(f"{username} has no records in the system yet", command="points")

    except Exception as e:
        error_msg = f"Error retrieving statistics: {e}"
        log_error(error_msg, command_name, {
            "error": str(e),
            "username": username
        })
        print(error_msg)
        send_message_to_redis(f"Error retrieving statistics for {username}", command="points")

##########################
# Main
##########################
# Send startup message
log_startup("Points command is ready to be used", "points")
send_system_message_to_redis("Points command is running", "points")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '')
            content = message_obj.get('content', '')
            print(f"Chat Command: {command} and Message: {content}")

            log_info(f"Received {command} command", command, {"content": content})

            # Get username to check
            username_to_check = message_obj["author"]["mention"]
            requester = message_obj["author"]["display_name"]

            # If moderator can check stats for other users
            if message_obj["author"]["moderator"] or message_obj["author"]["broadcaster"]:
                username_to_check_in_content = message_obj["content"].split()[1] if len(message_obj["content"].split()) > 1 else None
                if username_to_check_in_content:
                    username_to_check = username_to_check_in_content
                    log_info(f"Moderator {requester} checking stats for {username_to_check}", command)

            print_statistics(username_to_check, command)

        except Exception as e:
            error_msg = f"Error processing {command} command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "points", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_system_message_to_redis(f"Error in points command: {str(e)}", "points")
