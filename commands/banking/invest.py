import json
import time
from datetime import datetime

from module.shared_redis import redis_client, pubsub

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler

##########################
# Initialize
##########################

pubsub.subscribe('twitch.command.invest')
pubsub.subscribe('twitch.command.investment')
pubsub.subscribe('twitch.command.investing')
pubsub.subscribe('twitch.command.bank')
pubsub.subscribe('twitch.command.banking')
pubsub.subscribe('twitch.command.investments')
pubsub.subscribe('twitch.command.deposit')

##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################
def invest_money_as_mod(user_that_invests, receiving_user, invest_amount):
    user_that_receiving_lower = receiving_user.lower().replace("@", "")
    user_key = f"user:{user_that_receiving_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_obj = json.loads(user_json)
    else:
        # create new user if not exists
        user_obj = {
            "name": user_that_receiving_lower,
            "display_name": receiving_user.replace("@", ""),
            "chat": {"count": 0},
            "command": {"count": 0},
            "admin": {"count": 0},
            "dustbunnies": {},
            "banking": {}
        }
    if "banking" not in user_obj:
        user_obj["banking"] = {}
    if "dustbunnies" not in user_obj:
        user_obj["dustbunnies"] = {}

    # Check if user has enough dustbunnies
    if user_obj["dustbunnies"].get("collected_dustbunnies", 0) < invest_amount:
        send_message_to_redis(f"@{user_that_receiving_lower} does not have enough dustbunnies to invest {invest_amount}")
        return False

    # Subtract the invested amount from dustbunnies
    user_obj["dustbunnies"]["collected_dustbunnies"] = user_obj["dustbunnies"].get("collected_dustbunnies", 0) - invest_amount

    # Only update banking-specific fields
    user_obj["banking"]["total_bunnies_collected"] = user_obj["banking"].get("total_bunnies_collected", 0)
    user_obj["banking"]["bunnies_invested"] = user_obj["banking"].get("bunnies_invested", 0) + invest_amount
    user_obj["banking"]["timestamp_investment"] = datetime.now(tz=None).isoformat()
    user_obj["banking"]["last_interest_collected"] = user_obj["banking"].get("last_interest_collected", 0)
    redis_client.set(user_key, json.dumps(user_obj))
    return True

def invest_money(user, invest_amount):
    username_lower = user["name"].lower()
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_obj = json.loads(user_json)
    else:
        user_obj = {
            "name": user["name"],
            "display_name": user["display_name"],
            "chat": {"count": 0},
            "command": {"count": 0},
            "admin": {"count": 0},
            "dustbunnies": {},
            "banking": {}
        }
    if "banking" not in user_obj:
        user_obj["banking"] = {}
    if "dustbunnies" not in user_obj:
        user_obj["dustbunnies"] = {}

    # Check if user has enough dustbunnies
    if user_obj["dustbunnies"].get("collected_dustbunnies", 0) < invest_amount:
        send_message_to_redis(f"{user['mention']} you do not have enough dustbunnies to invest {invest_amount}")
        return False

    # Subtract the invested amount from dustbunnies
    user_obj["dustbunnies"]["collected_dustbunnies"] = user_obj["dustbunnies"].get("collected_dustbunnies", 0) - invest_amount

    # Only update banking-specific fields
    user_obj["banking"]["total_bunnies_collected"] = user_obj["banking"].get("total_bunnies_collected", 0)
    user_obj["banking"]["bunnies_invested"] = user_obj["banking"].get("bunnies_invested", 0) + invest_amount
    user_obj["banking"]["timestamp_investment"] = datetime.now(tz=None).isoformat()
    user_obj["banking"]["last_interest_collected"] = user_obj["banking"].get("last_interest_collected", 0)
    redis_client.set(user_key, json.dumps(user_obj))
    return True

##########################
# Main
##########################
send_admin_message_to_redis("Invest command is running", "invest")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        msg_content = message_obj["content"]
        msg_parts = msg_content.split()

        # Check if this is a mod/broadcaster investing for someone else
        if len(msg_parts) > 2 and (message_obj["author"]["moderator"] or message_obj["author"]["broadcaster"]):
            invest_for_user = msg_parts[1]
            try:
                invest_amount = int(msg_parts[2])
            except ValueError:
                send_message_to_redis(f"{message_obj['author']['mention']} the amount must be a number")
                continue

            # Check if user starts with @ because we need the username
            if not invest_for_user.startswith("@"):
                send_message_to_redis(f"{message_obj['author']['mention']} you need to use the @username to invest for someone")
                continue

            # Invest for the user as mod/broadcaster
            if invest_money_as_mod(message_obj["author"], invest_for_user, invest_amount):
                send_message_to_redis(f"{message_obj['author']['mention']} invested {invest_amount} points for {invest_for_user}")
        else:
            # Regular invest for self
            try:
                invest_amount = int(msg_parts[1]) if len(msg_parts) > 1 else None
            except ValueError:
                send_message_to_redis(f"{message_obj['author']['mention']} the amount must be a number")
                continue

            if not invest_amount:
                send_message_to_redis(f"{message_obj['author']['mention']} you need to specify an amount to invest")
                continue

            redis_client.publish(f'twitch.command.collect', json.dumps(message_obj))
            time.sleep(1)
            if invest_money(message_obj["author"], invest_amount):
                send_message_to_redis(f"{message_obj['author']['mention']} you have invested {invest_amount} points")
