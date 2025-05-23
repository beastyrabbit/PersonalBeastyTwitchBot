import json

import numpy as np

from module.message_utils import send_system_message_to_redis, send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning
from module.shared_redis import redis_client, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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
    """
    Transfer dustbunnies from one user to another.

    Args:
        user_that_gets_robbed (str): The username of the user to steal from
        receiving_user (dict): The user object of the person stealing
        amount_stolen (int): The amount of dustbunnies to steal

    Returns:
        int: The actual amount of dustbunnies stolen
    """
    try:
        log_debug(f"Attempting to steal {amount_stolen} dustbunnies from {user_that_gets_robbed}", "steal")

        user_that_gets_robbed_lower = user_that_gets_robbed.lower().replace("@", "")
        robbed_key = f"user:{user_that_gets_robbed_lower}"

        if redis_client.exists(robbed_key):
            robbed_json = redis_client.get(robbed_key)
            robbed_data = json.loads(robbed_json)

            if "dustbunnies" not in robbed_data:
                log_debug(f"Creating dustbunnies object for {user_that_gets_robbed}", "steal")
                robbed_data["dustbunnies"] = {}

            original_amount = robbed_data["dustbunnies"].get("collected_dustbunnies", 0)

            if original_amount <= amount_stolen:
                amount_stolen = original_amount
                log_info(f"Adjusted steal amount to {amount_stolen} (all available dustbunnies)", "steal")

            robbed_data["dustbunnies"]["collected_dustbunnies"] = original_amount - amount_stolen
            redis_client.set(robbed_key, json.dumps(robbed_data))

            log_info(f"Removed {amount_stolen} dustbunnies from {user_that_gets_robbed}", "steal", {
                "user_robbed": user_that_gets_robbed,
                "previous_amount": original_amount,
                "new_amount": robbed_data["dustbunnies"]["collected_dustbunnies"],
                "amount_stolen": amount_stolen
            })
        else:
            log_info(f"User {user_that_gets_robbed} does not exist in database", "steal")
            send_message_to_redis(f"{user_that_gets_robbed} does not have pockets yet")
            return 0

        # Add dustbunnies to the receiver
        receiver_lower = receiving_user["name"].lower()
        receiver_key = f"user:{receiver_lower}"

        if redis_client.exists(receiver_key):
            receiver_json = redis_client.get(receiver_key)
            receiver_data = json.loads(receiver_json)
            log_debug(f"Found existing user {receiving_user['display_name']}", "steal")
        else:
            # Create new user if not exists
            log_info(f"Creating new user account for {receiving_user['display_name']}", "steal")
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
            log_debug(f"Creating dustbunnies object for {receiving_user['display_name']}", "steal")
            receiver_data["dustbunnies"] = {}

        # Only update dustbunnies-specific fields
        previous_amount = receiver_data["dustbunnies"].get("collected_dustbunnies", 0)
        receiver_data["dustbunnies"]["collected_dustbunnies"] = previous_amount + amount_stolen
        redis_client.set(receiver_key, json.dumps(receiver_data))

        log_info(f"Added {amount_stolen} dustbunnies to {receiving_user['display_name']}", "steal", {
            "user": receiving_user["display_name"],
            "previous_amount": previous_amount,
            "new_amount": receiver_data["dustbunnies"]["collected_dustbunnies"],
            "amount_stolen": amount_stolen
        })

        return amount_stolen

    except Exception as e:
        error_msg = f"Error in steal_dustbunnies: {e}"
        log_error(error_msg, "steal", {
            "error": str(e),
            "user_robbed": user_that_gets_robbed,
            "receiver": receiving_user.get("display_name", "Unknown"),
            "amount": amount_stolen
        })
        return 0

def generate_rnd_amount_to_steal() -> int:
    """
    Generate a random amount of dustbunnies to steal based on a weighted probability.

    Returns:
        int: The amount of dustbunnies to steal
    """
    try:
        # Pre-configured parameters
        global max_value_to_roomba

        luck_factor = 20.0  # Higher values make high numbers less likely

        log_debug(f"Generating random steal amount with max value {max_value_to_roomba}", "steal")

        # Create a range of possible values
        values = np.linspace(0, max_value_to_roomba, 1000)

        # Define weights: Exponentially decrease probability for higher values
        weights = np.exp(-luck_factor * (values / max_value_to_roomba))
        weights /= weights.sum()  # Normalize to sum to 1

        # Generate a single result
        result = np.random.choice(values, size=1, p=weights)
        steal_amount = int(result[0])

        log_debug(f"Generated steal amount: {steal_amount}", "steal", {
            "max_possible": max_value_to_roomba,
            "luck_factor": luck_factor,
            "amount": steal_amount
        })

        return steal_amount

    except Exception as e:
        error_msg = f"Error generating random steal amount: {e}"
        log_error(error_msg, "steal", {
            "error": str(e),
            "max_value": max_value_to_roomba
        })
        return 1  # Return a small default value in case of error

##########################
# Main
##########################
# Send startup message
log_startup("Steal command is ready to be used", "steal")
send_system_message_to_redis('Steal command is running', 'steal')

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            log_info(f"Received command: {command}", "steal", {"content": content})

            username = message_obj["author"]["display_name"]
            # First get user that will be given to
            msg_content = message_obj["content"]
            # remove !steal or !rob from the message
            user_that_gets_robbed = msg_content.split()[1] if len(msg_content.split()) > 1 else None

            # Validate target user
            if not user_that_gets_robbed:
                log_warning(f"User {username} attempted to steal without specifying a target", "steal")
                send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the @username to steal dustbunnies")
                continue

            if not user_that_gets_robbed.startswith("@"):
                log_warning(f"User {username} attempted to steal without using @ prefix", "steal", {
                    "attempted_target": user_that_gets_robbed
                })
                send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the @username to steal dustbunnies")
                continue

            # Generate random amount to steal
            steal_amount = generate_rnd_amount_to_steal()

            # Perform the stealing
            log_info(f"User {username} attempting to steal {steal_amount} from {user_that_gets_robbed}", "steal")
            steal_amount = steal_dustbunnies(user_that_gets_robbed, message_obj["author"], steal_amount)

            # Send result message
            log_info(f"User {username} stole {steal_amount} dustbunnies from {user_that_gets_robbed}", "steal", {
                "stealer": username,
                "target": user_that_gets_robbed,
                "amount": steal_amount
            })
            send_message_to_redis(f"{message_obj["author"]["mention"]} stole {steal_amount} dustbunnies from {user_that_gets_robbed}")

        except Exception as e:
            error_msg = f"Error processing steal command: {e}"
            # Log the error with detailed information
            log_error(error_msg, "steal", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
