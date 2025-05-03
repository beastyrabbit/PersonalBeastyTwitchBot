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

def give_dustbunnies_as_mod(user_that_gives,receiving_user,amount_gives):
    global redis_client
    # give the User the dustbunnies and remove the @
    user_that_receiving_lower = receiving_user.lower().replace("@","")
    if redis_client.exists(f"dustbunnies:{user_that_receiving_lower}"):
        user_json = redis_client.get(f"dustbunnies:{user_that_receiving_lower}")
        user = json.loads(user_json)
        user["collected_dustbunnies"] += amount_gives
        redis_client.set(f"dustbunnies:{user_that_receiving_lower}", json.dumps(user))
    else:
        user = {
            "name": user_that_receiving_lower,
            "display_name": receiving_user.replace("@",""),
            "collected_dustbunnies": amount_gives,
            "message_count": 0
        }
        redis_client.set(f"dustbunnies:{user_that_receiving_lower}", json.dumps(user))


def give_dustbunnies(user_that_gives,receiving_user,amount_gives):
    global redis_client
    # check if user that gives has enough dustbunnies
    if redis_client.exists(f"dustbunnies:{user_that_gives["name"]}"):
        user_json = redis_client.get(f"dustbunnies:{user_that_gives["name"]}")
        user = json.loads(user_json)
        if user["collected_dustbunnies"] <= amount_gives:
            send_message_to_redis(f"{user_that_gives["mention"]} does not have enough dustbunnies nice try")
            return
        user["collected_dustbunnies"] -= amount_gives
        redis_client.set(f"dustbunnies:{user_that_gives["name"]}", json.dumps(user))
    else:
        send_message_to_redis(f"{user_that_gives["mention"]} does not exist and cant give dustbunnies")

    # give the User  the dustbunnies and remove the @
    user_that_receiving_lower = receiving_user.lower().replace("@","")
    if redis_client.exists(f"dustbunnies:{user_that_receiving_lower}"):
        user_json = redis_client.get(f"dustbunnies:{user_that_receiving_lower}")
        user = json.loads(user_json)
        user["collected_dustbunnies"] += amount_gives
        redis_client.set(f"dustbunnies:{user_that_receiving_lower}", json.dumps(user))
    else:
        user = {
            "name": user_that_receiving_lower,
            "display_name": receiving_user.replace("@",""),
            "collected_dustbunnies": amount_gives,
            "message_count": 0
        }
        redis_client.set(f"dustbunnies:{user_that_receiving_lower}", json.dumps(user))

def give_all_dustbunnies(amount):
    global redis_client
    all_users = redis_client.keys("dustbunnies:*")
    for user in all_users:
        user_json = redis_client.get(user)
        user_obj = json.loads(user_json)
        user_obj["collected_dustbunnies"] += amount
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








