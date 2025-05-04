import json
import signal
import sys

from module.message_utils import send_admin_message_to_redis
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

def send_message_to_redis(send_message, command="points"):
    redis_client.publish('twitch.chat.send', send_message)

def print_statistics(username):
    username_lower = username.lower()
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_obj = json.loads(user_json)
        # Dustbunnies
        dustbunnies = user_obj.get("dustbunnies", {})
        collected = dustbunnies.get("collected_dustbunnies", 0)
        message_count = dustbunnies.get("message_count", 0)
        send_message_to_redis(f"{username} has collected {collected} dustbunnies and has sent {message_count} messages", command="points")
        # Banking
        banking = user_obj.get("banking", {})
        invested = banking.get("bunnies_invested", 0)
        total_collected = banking.get("total_bunnies_collected", 0)
        send_message_to_redis(f"{username} has invested {invested} dustbunnies and has collected {total_collected} dustbunnies", command="points")
    else:
        send_message_to_redis(f"{username} has not collected any dustbunnies yet", command="points")
        send_message_to_redis(f"{username} has not invested any dustbunnies yet", command="points")


##########################
# Main
##########################
send_admin_message_to_redis("Points command is ready to be used", "points")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        username_to_check = message_obj["author"]["mention"]
        if message_obj["author"]["moderator"]:
            username_to_check_in_content = message_obj["content"].split()[1] if len(message_obj["content"].split()) > 1 else None
            if username_to_check_in_content:
                username_to_check = username_to_check_in_content
        print_statistics(username_to_check)
