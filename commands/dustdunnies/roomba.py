import json
import random
from datetime import timedelta, datetime

from module.message_utils import send_message_to_redis, register_exit_handler, send_system_message_to_redis
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
timeoutList = {}
timeout_in_seconds = 30
max_value_to_roomba = int(redis_client.get("roomba_max_hit_value").decode('utf-8'))
pubsub.subscribe('twitch.command.roomba')
pubsub.subscribe('twitch.command.clean')
pubsub.subscribe('twitch.command.vacuum')

##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################
def do_the_cleaning_command(user_obj, username) -> int:
    """
    Check if a user is allowed to use the roomba command and generate a random number of dustbunnies.

    Args:
        user_obj (dict): The user object of the person using the command
        username (str): The display name of the user

    Returns:
        int: The number of dustbunnies collected (0 if user is on timeout)
    """
    try:
        global timeoutList
        global timeout_in_seconds
        global max_value_to_roomba

        log_debug(f"Processing roomba command for {username}", "roomba")

        # Check if user is on timeout
        if username not in timeoutList:
            log_debug(f"First roomba use for {username}, adding to timeout list", "roomba")
            timeoutList[username] = datetime.now(tz=None)
        else:
            last_timeout = timeoutList[username]
            time_since_last = datetime.now(tz=None) - last_timeout

            log_debug(f"User {username} last used roomba {time_since_last.total_seconds()} seconds ago", "roomba")

            if time_since_last > timedelta(seconds=timeout_in_seconds):
                log_debug(f"Timeout expired for {username}, allowing roomba use", "roomba")
                timeoutList[username] = datetime.now(tz=None)
            else:
                remaining_seconds = timeout_in_seconds - int(time_since_last.total_seconds())
                log_info(f"User {username} still on timeout for {remaining_seconds} seconds", "roomba", {
                    "timeout_remaining": remaining_seconds
                })
                return 0

        # Generate random number of dustbunnies
        rnd_number_for_user = random.randint(1, max_value_to_roomba)

        log_info(f"User {username} collected {rnd_number_for_user} dustbunnies", "roomba", {
            "amount": rnd_number_for_user,
            "max_possible": max_value_to_roomba
        })

        return rnd_number_for_user
    except Exception as e:
        error_msg = f"Error in roomba command: {e}"
        log_error(error_msg, "roomba", {
            "error": str(e),
            "user": username
        })
        return 0

def handle_user_data(user_obj, rnd_number_for_user):
    """
    Update a user's dustbunnies count in the database.

    Args:
        user_obj (dict): The user object of the person using the command
        rnd_number_for_user (int): The number of dustbunnies to add to the user's account
    """
    try:
        username = user_obj.get('display_name', user_obj["name"])
        username_lower = user_obj["name"].lower()
        user_key = f"user:{username_lower}"

        log_debug(f"Updating user data for {username}", "roomba")

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
            log_debug(f"Found existing user {username}", "roomba")
        else:
            # Create new user if not exists
            log_info(f"Creating new user account for {username}", "roomba")
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
            log_debug(f"Creating dustbunnies object for {username}", "roomba")
            user["dustbunnies"] = {}

        # Only update dustbunnies-specific fields
        previous_amount = user["dustbunnies"].get("collected_dustbunnies", 0)
        user["dustbunnies"]["collected_dustbunnies"] = previous_amount + rnd_number_for_user

        previous_count = user["dustbunnies"].get("message_count", 0)
        user["dustbunnies"]["message_count"] = previous_count + 1

        redis_client.set(user_key, json.dumps(user))

        log_info(f"Updated user {username} dustbunnies", "roomba", {
            "previous_amount": previous_amount,
            "added": rnd_number_for_user,
            "new_total": user["dustbunnies"]["collected_dustbunnies"],
            "message_count": user["dustbunnies"]["message_count"]
        })
    except Exception as e:
        error_msg = f"Error updating user data: {e}"
        log_error(error_msg, "roomba", {
            "error": str(e),
            "user": user_obj.get('display_name', user_obj.get('name', 'Unknown')),
            "amount": rnd_number_for_user
        })


##########################
# Main
##########################
# Send startup message
log_startup("Roomba command is ready to be used", "roomba")
send_system_message_to_redis("Roomba command is running", "roomba")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            log_info(f"Received command: {command}", "roomba", {"content": content})

            username = message_obj["author"]["display_name"]
            # Roomba command to clean up the channel...
            # We can store the amount of messages cleaned up in a database...
            random_value = do_the_cleaning_command(message_obj["author"], username)
            handle_user_data(message_obj["author"], random_value)
            username = message_obj["author"]["mention"]
            if max_value_to_roomba == random_value:
                # Congratulate the user for hitting the max value
                redis_client.set("roomba_max_hit_value", max_value_to_roomba * 10)
                max_value_to_roomba = int(redis_client.get("roomba_max_hit_value").decode('utf-8'))
                log_info(f"User {username} hit the max value of {random_value}", "roomba", {
                    "max_value": random_value,
                    "new_max_value": max_value_to_roomba
                })
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
        except Exception as e:
            error_msg = f"Error processing roomba command: {e}"
            # Log the error with detailed information
            log_error(error_msg, "roomba", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
