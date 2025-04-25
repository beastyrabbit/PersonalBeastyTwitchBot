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

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)

def write_lurk_to_redis(auther_obj):
    global redis_client
    if redis_client.exists(f"global:{auther_obj['name']}"):
        user_json = redis_client.get(f"global:{auther_obj['name']}")
        user_obj = json.loads(user_json)
        if "lurk" in user_obj:
            user_obj["lurk"] += 1
        else:
            user_obj["lurk"] = 1
        redis_client.set(f"global:{auther_obj['name']}", json.dumps(user_obj))
    else:
        redis_client.set(f"global:{auther_obj['name']}", json.dumps({"lurk": 1}))
    send_message_to_redis(f"{auther_obj['mention']} will be cheering from the shadows!")
    


##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('Command')} and Message: {message_obj.get('content')}")
        write_lurk_to_redis(message_obj["author"])















