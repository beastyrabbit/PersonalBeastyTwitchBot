import json
import signal
import sys

import redis

from module.message_utils import send_admin_message_to_redis

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

def send_message_to_redis(send_message, command="lurk"):
    redis_client.publish('twitch.chat.send', send_message)

def write_lurk_to_redis(auther_obj):
    username_lower = auther_obj['name'].lower()
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_obj = json.loads(user_json)
    else:
        user_obj = {
            "name": auther_obj["name"],
            "display_name": auther_obj.get("display_name", auther_obj["name"]),
            "log": {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0},
            "dustbunnies": {},
            "banking": {}
        }
    if "log" not in user_obj:
        user_obj["log"] = {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0}
    user_obj["log"]["lurk"] = user_obj["log"].get("lurk", 0) + 1
    redis_client.set(user_key, json.dumps(user_obj))
    send_message_to_redis(f"{auther_obj['mention']} will be cheering from the shadows!", command="lurk")


##########################
# Main
##########################
send_admin_message_to_redis("Lurk command is ready to be used", "lurk")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('Command')} and Message: {message_obj.get('content')}")
        write_lurk_to_redis(message_obj["author"])
