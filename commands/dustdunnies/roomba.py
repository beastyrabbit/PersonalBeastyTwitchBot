import json
import signal
import sys
from datetime import timedelta, datetime
import random

import redis

##########################
# Initialize
##########################
timeoutList = {}
timeout_in_seconds = 30
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client.set("roomba_max_hit_value", 1000)
max_value_to_roomba = int(redis_client.get("roomba_max_hit_value").decode('utf-8'))
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.roomba')
pubsub.subscribe('twitch.command.clean')
pubsub.subscribe('twitch.command.vacuum')

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
# Default Message Methods
##########################
def send_admin_message_to_redis(message):
    # Create unified message object
    admin_message_obj = {
        "type": "admin",
        "source": "system",
        "content": message,
    }
    redis_client.publish('admin.brb.send', json.dumps(admin_message_obj))


def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)


##########################
# Helper Functions
##########################
def do_the_cleaning_command(user_obj,username) -> int:
    global timeoutList
    global timeout_in_seconds
    global max_value_to_roomba
    global redis_client
    # Check if is allowed to clean
    #if user_obj["moderator"] or user_obj["broadcaster"]:
    #    return random.randint(1, max_value_to_roomba)
    if username not in timeoutList:
        timeoutList[username] = datetime.now(tz=None)
    else:
        last_timeout = timeoutList[username]
        print(f"Username: {username} and Last Timeout in seconds: {datetime.now(tz=None) - last_timeout}")
        if datetime.now(tz=None) - last_timeout > timedelta(seconds=timeout_in_seconds):
            timeoutList[username] = datetime.now(tz=None)
        else:
            send_admin_message_to_redis(f"Username: {username} still has {timeout_in_seconds - int((datetime.now(tz=None) - last_timeout).total_seconds())} in Timeout")
            return 0
    #print(f"Timeout List: {timeoutList}")
    rnd_number_for_user = get_random = random.randint(1, max_value_to_roomba)
    return rnd_number_for_user

def handle_user_data(user_obj, rnd_number_for_user):
    username_lower = user_obj["name"].lower()
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user = json.loads(user_json)
    else:
        user = {
            "name": user_obj["name"],
            "display_name": user_obj["display_name"],
            "chat": {"count": 0},
            "command": {"count": 0},
            "admin": {"count": 0},
            "dustbunnies": {},
            "banking": {}
        }
    if "dustbunnies" not in user:
        user["dustbunnies"] = {}
    # Only update dustbunnies-specific fields
    user["dustbunnies"]["collected_dustbunnies"] = user["dustbunnies"].get("collected_dustbunnies", 0) + rnd_number_for_user
    user["dustbunnies"]["message_count"] = user["dustbunnies"].get("message_count", 0) + 1
    redis_client.set(user_key, json.dumps(user))


##########################
# Main
##########################
send_admin_message_to_redis("Roomba command is running")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        username = message_obj["author"]["display_name"]
        # Roomba command to clean up the channel...
        # We can store the amount of messages cleaned up in a database...
        random_value = do_the_cleaning_command(message_obj["author"],username)
        handle_user_data(message_obj["author"],random_value)
        username = message_obj["author"]["mention"]

        if max_value_to_roomba == random_value:
            # Congratulate the user for hitting the max value
            redis_client.set("roomba_max_hit_value", max_value_to_roomba * 10)
            max_value_to_roomba = int(redis_client.get("roomba_max_hit_value").decode('utf-8'))
            send_message_to_redis(f'{username} hit the max value! 🐰🐻')
            send_message_to_redis(f'@Beastyrabbit Max Clean Value just was increased by {username} and is now {max_value_to_roomba}.! 🐰🐻')

        elif random_value == 69:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Nice! 😎')

        elif random_value == 420:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Blazing! 😎')

        elif random_value == 666:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Hail 😈!')

        elif random_value == 1337:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Elite! 🤖')

        elif random_value == 80085:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Boobs! 🍑')

        elif random_value == 8008:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Boob! 🍑')

        elif random_value == 8008135:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Boobies! 🍑🍑')

        elif random_value == 619:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! San Diego! 🌴')

        elif random_value == 42:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! The Answer! 🤖')

        elif random_value == 404:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Not Found! 🤖')

        elif random_value == 9001:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Over 9000! 🤖')

        # 007
        elif random_value == 7:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Bond! 🤵')

        elif random_value == 911:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Emergency! 🚨')

        # cash now
        elif random_value == 1800:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰🐻! Cash Now! 💰')

        elif random_value > 0:
            # Username cleaned up random_value messages...
            send_message_to_redis(f'{username} cleaned up {random_value} Dustbunnies 🐰!')
