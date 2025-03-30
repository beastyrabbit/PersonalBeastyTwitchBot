import json
import signal
import sys

import redis
import numpy as np

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
max_value_to_roomba = int(redis_client.get("roomba_max_hit_value").decode('utf-8'))
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.steal')
pubsub.subscribe('twitch.command.rob')

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

def steal_dustbunnies(user_that_gets_robbed,receiving_user,amount_stolen):
    global redis_client
    # check if user that gets stolen from has enough dustbunnies
    user_that_gets_robbed_lower = user_that_gets_robbed.lower().replace("@","")

    if redis_client.exists(f"dustbunnies:{user_that_gets_robbed_lower}"):
        user_json = redis_client.get(f"dustbunnies:{user_that_gets_robbed_lower}")
        user = json.loads(user_json)
        if user["collected_dustbunnies"] <= amount_stolen:
            amount_stolen = user["collected_dustbunnies"]
        user["collected_dustbunnies"] -= amount_stolen
        redis_client.set(f"dustbunnies:{user_that_gets_robbed_lower}", json.dumps(user))
    else:
        send_message_to_redis(f"{user_that_gets_robbed} does not have pockets yet")
        return 0

    # User that stole the dustbunnies
    if redis_client.exists(f"dustbunnies:{receiving_user["name"]}"):
        user_json = redis_client.get(f"dustbunnies:{receiving_user["name"]}")
        user = json.loads(user_json)
        user["collected_dustbunnies"] += amount_stolen
        redis_client.set(f"dustbunnies:{receiving_user["name"]}", json.dumps(user))
    else:
        user = {
            "name": receiving_user["name"],
            "display_name": receiving_user["display_name"],
            "collected_dustbunnies": str(amount_stolen),
            "message_count": 0
        }
        redis_client.set(f"dustbunnies:{receiving_user["name"]}", json.dumps(user))

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










