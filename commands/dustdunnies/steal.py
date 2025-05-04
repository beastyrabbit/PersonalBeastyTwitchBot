import json
import signal
import sys

import redis
import numpy as np
from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import redis_client, pubsub

##########################
# Initialize
##########################
max_value_to_roomba = int(redis_client.get("roomba_max_hit_value").decode('utf-8'))
pubsub.subscribe('twitch.command.steal')
pubsub.subscribe('twitch.command.rob')

##########################
# Exit Function
##########################

# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################

def steal_dustbunnies(user_that_gets_robbed, receiving_user, amount_stolen):
    user_that_gets_robbed_lower = user_that_gets_robbed.lower().replace("@", "")
    robbed_key = f"user:{user_that_gets_robbed_lower}"
    if redis_client.exists(robbed_key):
        robbed_json = redis_client.get(robbed_key)
        robbed_data = json.loads(robbed_json)
        if "dustbunnies" not in robbed_data:
            robbed_data["dustbunnies"] = {}
        if robbed_data["dustbunnies"].get("collected_dustbunnies", 0) <= amount_stolen:
            amount_stolen = robbed_data["dustbunnies"].get("collected_dustbunnies", 0)
        robbed_data["dustbunnies"]["collected_dustbunnies"] = robbed_data["dustbunnies"].get("collected_dustbunnies", 0) - amount_stolen
        redis_client.set(robbed_key, json.dumps(robbed_data))
    else:
        send_message_to_redis(f"{user_that_gets_robbed} does not have pockets yet")
        return 0
    receiver_lower = receiving_user["name"].lower()
    receiver_key = f"user:{receiver_lower}"
    if redis_client.exists(receiver_key):
        receiver_json = redis_client.get(receiver_key)
        receiver_data = json.loads(receiver_json)
    else:
        receiver_data = {
            "name": receiving_user["name"],
            "display_name": receiving_user["display_name"],
            "chat": {"count": 0},
            "command": {"count": 0},
            "admin": {"count": 0},
            "dustbunnies": {},
            "banking": {}
        }
    if "dustbunnies" not in receiver_data:
        receiver_data["dustbunnies"] = {}
    # Only update dustbunnies-specific fields
    receiver_data["dustbunnies"]["collected_dustbunnies"] = receiver_data["dustbunnies"].get("collected_dustbunnies", 0) + amount_stolen
    redis_client.set(receiver_key, json.dumps(receiver_data))
    return amount_stolen

def generate_rnd_amount_to_steal() -> int:
    # Pre-configured parameters
    global max_value_to_roomba

    luck_factor = 20.0  # Higher values make high numbers less likely

    # Create a range of possible values
    values = np.linspace(0, max_value_to_roomba, 1000)

    # Define weights: Exponentially decrease probability for higher values
    weights = np.exp(-luck_factor * (values / max_value_to_roomba))
    weights /= weights.sum()  # Normalize to sum to 1

    # Generate a single result
    result = np.random.choice(values, size=1, p=weights)
    return int(result[0])

##########################
# Main
##########################
send_admin_message_to_redis('Steal command is ready to use')
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        username = message_obj["author"]["display_name"]
        # Frist get user that will be given to
        msg_content = message_obj["content"]
        # remove !give from the message
        user_that_gets_robbed = msg_content.split()[1] if len(msg_content.split()) > 1 else None
        steal_amount = generate_rnd_amount_to_steal()
        if not user_that_gets_robbed:
            send_message_to_redis(f"{message_obj["auther"]["mention"]} you need to use the @username to steal dustbunnies")
            continue

        if not user_that_gets_robbed.startswith("@"):
            send_message_to_redis(f"{message_obj["auther"]["mention"]} you need to use the @username to steal dustbunnies")
            continue
        # check if user start with @ because we need the username
        steal_amount = steal_dustbunnies(user_that_gets_robbed,message_obj["author"],steal_amount)
        send_message_to_redis(f"{message_obj["author"]["mention"]} stole {steal_amount} dustbunnies from {user_that_gets_robbed}")










