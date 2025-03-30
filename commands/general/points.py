import json
import signal
import sys
import time
from datetime import datetime
import redis

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)

pubsub = redis_client.pubsub()
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

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)

def print_statistics(username):
    global redis_client
    username_db = username.lower()[:1]
    if redis_client.exists(f"dustbunnies:{username_db}"):
        user_json = redis_client.get(f"dustbunnies:{username_db}")
        user_obj = json.loads(user_json)
        send_message_to_redis(f"{username} has collected {user_obj['collected_dustbunnies']} dustbunnies and has sent {user_obj['message_count']} messages")
    else:
        send_message_to_redis(f"{username} has not collected any dustbunnies yet")
    if redis_client.exists(f"banking:{username_db}"):
        user_json = redis_client.get(f"banking:{username_db}")
        user_obj = json.loads(user_json)
        send_message_to_redis(f"{username} has invested {user_obj['bunnies_invested']} dustbunnies and has collected {user_obj['total_bunnies_collected']} dustbunnies")
    else:
        send_message_to_redis(f"{username} has not invested any dustbunnies yet")


##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        username_to_check = message_obj["author"]["mention"]
        if message_obj["Auther"]["moderator"]:
            username_to_check_in_content = message_obj["content"].split()[1] if len(message_obj["content"].split()) > 1 else None
            if username_to_check_in_content:
                username_to_check = username_to_check_in_content
        print_statistics(username_to_check)















