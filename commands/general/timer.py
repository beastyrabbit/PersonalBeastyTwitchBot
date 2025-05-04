import json
import signal
import sys
import threading
import time
from datetime import datetime
import redis
from module.message_utils import send_admin_message_to_redis

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)

pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.timer')
pubsub.subscribe('twitch.command.countdown')
pubsub.subscribe('twitch.command.clock')

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

##########################
# Main
##########################
send_admin_message_to_redis("Timer command is ready to be used")

for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        time_name = message_obj["content"].split()[1] if len(message_obj["content"].split()) > 1 else None
        time_in_minutes = int(message_obj["content"].split()[2]) if len(message_obj["content"].split()) > 1 else None
        if not time_name or not time_in_minutes:
            send_message_to_redis(f"Invalid time value. Please specify the time in minutes (e.g., !timer focus 5).")
        time_in_seconds = time_in_minutes * 60
        # Inform the chat about the timer being set
        send_message_to_redis(f'{time_name.capitalize()} Timer set for {time} minute(s) 🤖 !')

        # Half point if time is longer then 25 minutes
        if time_in_seconds > 1500:
            threading.Timer(time_in_seconds / 2, send_message_to_redis, [f'@{message_obj["auther"]["mention"]} your {time_name.capitalize()} Timer has halfway done! 🚨']).start()


        # 2 min left on timer
        threading.Timer(time_in_seconds - 120, send_message_to_redis, [f'@{message_obj["auther"]["mention"]} your {time_name.capitalize()} Timer has 2 minutes left! 🚨']).start()

        # Notify the chat that the timer is up
        threading.Timer(time_in_seconds, send_message_to_redis, [f'@{message_obj["auther"]["mention"]} your {time_name.capitalize()} Timer is up! 🚨']).start()
















