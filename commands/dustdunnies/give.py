import json
import signal
import sys
from datetime import timedelta, datetime
import random

import redis

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.give')
pubsub.subscribe('twitch.command.donate')
pubsub.subscribe('twitch.command.gift')
pubsub.subscribe('twitch.command.share')

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

def give_dustbunnies_as_mod(user_that_gives, receiving_user, amount_gives):
    user_that_receiving_lower = receiving_user.lower().replace("@", "")
    user_key = f"user:{user_that_receiving_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_data = json.loads(user_json)
    else:
        # create new user if not exists
        user_data = {
            "name": user_that_receiving_lower,
            "display_name": receiving_user.replace("@", ""),
            "chat": {"count": 0},
            "command": {"count": 0},
            "admin": {"count": 0},
            "dustbunnies": {},
            "banking": {}
        }
    if "dustbunnies" not in user_data:
        user_data["dustbunnies"] = {}
    # only update dustbunnies fields
    user_data["dustbunnies"]["collected_dustbunnies"] = user_data["dustbunnies"].get("collected_dustbunnies", 0) + amount_gives
    redis_client.set(user_key, json.dumps(user_data))


def give_dustbunnies(user_that_gives, receiving_user, amount_gives):
    giver_lower = user_that_gives["name"].lower()
    giver_key = f"user:{giver_lower}"
    if redis_client.exists(giver_key):
        giver_json = redis_client.get(giver_key)
        giver_data = json.loads(giver_json)
        if "dustbunnies" not in giver_data:
            giver_data["dustbunnies"] = {}
        # check if enough dustbunnies
        if giver_data["dustbunnies"].get("collected_dustbunnies", 0) < amount_gives:
            send_message_to_redis(f"{user_that_gives['mention']} does not have enough dustbunnies nice try")
            return
        giver_data["dustbunnies"]["collected_dustbunnies"] -= amount_gives
        redis_client.set(giver_key, json.dumps(giver_data))
    else:
        send_message_to_redis(f"{user_that_gives['mention']} does not exist and cant give dustbunnies")
        return
    user_that_receiving_lower = receiving_user.lower().replace("@", "")
    receiver_key = f"user:{user_that_receiving_lower}"
    if redis_client.exists(receiver_key):
        receiver_json = redis_client.get(receiver_key)
        receiver_data = json.loads(receiver_json)
    else:
        # create new user if not exists
        receiver_data = {
            "name": user_that_receiving_lower,
            "display_name": receiving_user.replace("@", ""),
            "chat": {"count": 0},
            "command": {"count": 0},
            "admin": {"count": 0},
            "dustbunnies": {},
            "banking": {}
        }
    if "dustbunnies" not in receiver_data:
        receiver_data["dustbunnies"] = {}
    # only update dustbunnies fields
    receiver_data["dustbunnies"]["collected_dustbunnies"] = receiver_data["dustbunnies"].get("collected_dustbunnies", 0) + amount_gives
    redis_client.set(receiver_key, json.dumps(receiver_data))


def give_all_dustbunnies(amount):
    all_users = redis_client.keys("user:*")
    for user in all_users:
        user_json = redis_client.get(user)
        user_obj = json.loads(user_json)
        if "dustbunnies" not in user_obj:
            user_obj["dustbunnies"] = {}
        # only update dustbunnies fields
        user_obj["dustbunnies"]["collected_dustbunnies"] = user_obj["dustbunnies"].get("collected_dustbunnies", 0) + amount
        redis_client.set(user, json.dumps(user_obj))
    send_message_to_redis(f"All Users got {amount} dustbunnies")

##########################
# Main
##########################
send_admin_message_to_redis("Give Command is ready to be used")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        username = message_obj["author"]["display_name"]
        # Frist get user that will be given to
        msg_content = message_obj["content"]
        # remove !give from the message
        give_to_user = msg_content.split()[1] if len(msg_content.split()) > 1 else None
        amount = int(msg_content.split()[2]) if len(msg_content.split()) > 2 else None
        if not give_to_user or not amount:
            send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the !give <@username> <amount> to give dustbunnies")
            continue

        # check for give all
        if give_to_user == "all":
            # check if broadcaster
            if message_obj["author"]["broadcaster"]:
                # get all users
                give_all_dustbunnies(amount)
            else:
                send_message_to_redis(f"{message_obj["author"]["display_name"]} are not allowed to use this command")
        else:
            # check if user start with @ because we need the username
            if not give_to_user.startswith("@"):
                send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the @username to give dustbunnies")
                continue
            if message_obj["author"]["moderator"] or message_obj["author"]["broadcaster"]:
                give_dustbunnies_as_mod(message_obj["author"],give_to_user,amount)
                send_message_to_redis(f"{message_obj["author"]["mention"]} gave {amount} dustbunnies to {give_to_user}")
            else:
                give_dustbunnies(message_obj["author"], give_to_user, amount)
                send_message_to_redis(f"{message_obj["author"]["mention"]} gave {amount} dustbunnies to {give_to_user}")








