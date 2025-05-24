import json

import numpy as np

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning
from module.shared_redis import redis_client, pubsub
from module.user_utils import normalize_username, user_exists
from module.redis_user_utils import get_user_data, get_or_create_user

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
    """Transfers dustbunnies from one user to another.

    @param user_that_gets_robbed: Username of the user to steal from
    @param receiving_user: User object of the person stealing
    @param amount_stolen: Amount of dustbunnies to steal
    @return: Actual amount of dustbunnies stolen
    """
    try:
        log_debug(f"Attempting to steal {amount_stolen} dustbunnies from {user_that_gets_robbed}", "steal")

        user_that_gets_robbed_lower = normalize_username(user_that_gets_robbed)

        # Check if the user to rob exists
        robbed_data = get_user_data(user_that_gets_robbed_lower)
        if robbed_data:
            if "dustbunnies" not in robbed_data:
                log_debug(f"Creating dustbunnies object for {user_that_gets_robbed}", "steal")
                robbed_data["dustbunnies"] = {}

            original_amount = robbed_data["dustbunnies"].get("collected_dustbunnies", 0)

            if original_amount <= amount_stolen:
                amount_stolen = original_amount
                log_info(f"Adjusted steal amount to {amount_stolen} (all available dustbunnies)", "steal")

            robbed_data["dustbunnies"]["collected_dustbunnies"] = original_amount - amount_stolen

            # Save updated robbed user data
            robbed_key = f"user:{user_that_gets_robbed_lower}"
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
        receiver_lower = normalize_username(receiving_user["name"])

        # Get receiver data
        receiver_data = get_or_create_user(receiver_lower, receiving_user.get("display_name"))

        # Check if receiver data exists
        if receiver_data is None:
            log_info(f"User {receiving_user['display_name']} exists on Twitch but not in our database", "steal")
            # Create a default receiver data structure
            receiver_data = {
                "name": receiver_lower,
                "display_name": receiving_user.get("display_name", receiver_lower),
                "chat": {"count": 0},
                "command": {"count": 0},
                "admin": {"count": 0},
                "dustbunnies": {"collected_dustbunnies": 0},
                "banking": {}
            }
            log_debug(f"Created temporary user data for {receiving_user['display_name']}", "steal")

        if "dustbunnies" not in receiver_data:
            log_debug(f"Creating dustbunnies object for {receiving_user['display_name']}", "steal")
            receiver_data["dustbunnies"] = {}

        # Only update dustbunnies-specific fields
        previous_amount = receiver_data["dustbunnies"].get("collected_dustbunnies", 0)
        receiver_data["dustbunnies"]["collected_dustbunnies"] = previous_amount + amount_stolen

        # Save updated receiver data
        receiver_key = f"user:{receiver_lower}"
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
    """Generates random dustbunnies to steal using weighted probability.

    @return: Amount of dustbunnies to steal
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
                send_message_to_redis(f"{message_obj["author"]["mention"]} you need to specify a username to steal dustbunnies from")
                continue

            # Check if user exists
            if not user_exists(user_that_gets_robbed):
                log_warning(f"User {username} tried to steal from non-existent user {user_that_gets_robbed}", "steal")
                send_message_to_redis(f"{message_obj["author"]["mention"]} the user {user_that_gets_robbed} doesn't exist")
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
