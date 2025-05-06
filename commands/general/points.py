import json
import signal
import sys

from module.message_utils import send_admin_message_to_redis, send_message_to_redis
from module.shared_redis import redis_client, pubsub

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
def handle_exit(signum, frame):
    print("Unsubscribing from all channels bofore exiting")
    pubsub.unsubscribe()
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Helper Functions
##########################


def print_statistics(username):
    username_lower = username.lower()
    # remove the "@" from the username if it exists
    if username_lower.startswith("@"):
        username_lower = username_lower[1:]
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_obj = json.loads(user_json)
        
        # User log information
        log = user_obj.get("log", {})
        chat_count = log.get("chat", 0)
        command_count = log.get("command", 0)
        last_command = log.get("last_command", "none")
        last_message = log.get("last_message", "")
        
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
        send_message_to_redis(f"{username} has no records in the system yet", command="points")


##########################
# Main
##########################
send_admin_message_to_redis("Points command is ready to be used", "points")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        command = message_obj.get('command', '')
        print(f"Chat Command: {command} and Message: {message_obj.get('content')}")
        
        # Get username to check
        username_to_check = message_obj["author"]["mention"]
        # If moderator can check stats for other users
        if message_obj["author"]["moderator"] or message_obj["author"]["broadcaster"]:
            username_to_check_in_content = message_obj["content"].split()[1] if len(message_obj["content"].split()) > 1 else None
            if username_to_check_in_content:
                username_to_check = username_to_check_in_content
        print_statistics(username_to_check)
