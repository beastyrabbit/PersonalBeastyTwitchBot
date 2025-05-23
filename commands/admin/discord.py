import json

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error
from module.shared_redis import pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################

pubsub.subscribe('twitch.command.discord')


##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################


##########################
# Main
##########################
log_startup("Discord command is running", "discord")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            user = message_obj["author"].get("display_name", "Unknown")

            print(f"Chat Command: {command} and Message: {content}")
            log_info(f"Received discord command from {user}", "discord")

            if not message_obj["author"]["moderator"]:
                log_info(f"Non-moderator {user} attempted to use discord command", "discord")
                send_message_to_redis('🚨 Only moderators can use this command 🚨')
                continue

            log_info(f"Sending discord link to chat", "discord")
            send_message_to_redis('Join the discord server at https://discord.gg/dPdWbv8xrj')
        except Exception as e:
            error_msg = f"Error processing discord command: {e}"
            print(error_msg)
            log_error(error_msg, "discord", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
