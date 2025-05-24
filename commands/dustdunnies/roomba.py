import json
import random
from datetime import timedelta, datetime

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning
from module.shared_redis import redis_client, pubsub
from module.user_utils import normalize_username, user_exists
from module.redis_user_utils import get_user_data, get_or_create_user

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "WARNING"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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

def store_value_in_redis_and_get_perc(rnd_number_from_user: int, username: str):
    # compare the random number with the stored value in Redis as an array of integers
    # how many users where close to the max value?
    # percentage of rnd_number_from_user compared to max_value_to_roomba
    try:
        global max_value_to_roomba
        if rnd_number_from_user > max_value_to_roomba:
            log_warning(f"Random number {rnd_number_from_user} exceeds max value {max_value_to_roomba}", "roomba")
            return 0, 0, 0

        # Get the target number (this could be the max value or another target)
        target_number = max_value_to_roomba

        # Calculate how far off the user is from the target
        distance = abs(target_number - rnd_number_from_user)
        percentage_off = (distance / target_number) * 100

        # Store the attempt in Redis with the distance (username only for logging)
        user_attempt = json.dumps({"value": rnd_number_from_user, "distance": distance, "username": username})
        redis_client.lpush("roomba_user_attempts", user_attempt)

        # Get all previous attempts
        all_attempts = redis_client.lrange("roomba_user_attempts", 0, -1)
        better_users = 0

        # Count how many users got closer to max without hitting max
        current_distance = distance
        for attempt_json in all_attempts:
            attempt = json.loads(attempt_json)
            # Skip the current attempt
            if attempt["value"] == rnd_number_from_user and attempt["distance"] == current_distance:
                continue
            # Count attempts that got closer
            if attempt["distance"] < current_distance:
                better_users += 1

        # Calculate percentage of max value
        percentage = (rnd_number_from_user / max_value_to_roomba) * 100

        log_info(f"Value {rnd_number_from_user} is {percentage:.2f}% of max value {max_value_to_roomba}", "roomba", {
            "random_value": rnd_number_from_user,
            "percentage": percentage,
            "percentage_off": percentage_off,
            "better_users": better_users
        })

        return percentage, percentage_off, better_users
    except Exception as e:
        error_msg = f"Error in store_value_in_redis_and_get_perc: {e}"
        log_error(error_msg, "roomba", {
            "error": str(e),
            "value": rnd_number_from_user
        })
        return 0, 0, 0



def do_the_cleaning_command(user_obj, username) -> int:
    """Checks if user can use roomba and generates random dustbunnies.

    @param user_obj: User object of the command user
    @param username: Display name of the user
    @return: Number of dustbunnies collected (0 if on timeout)
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
    """Updates user's dustbunnies count in the database.

    @param user_obj: User object of the command user
    @param rnd_number_for_user: Number of dustbunnies to add
    """
    try:
        username = user_obj.get('display_name', user_obj["name"])
        username_lower = normalize_username(user_obj["name"])

        log_debug(f"Updating user data for {username}", "roomba")

        # Get user data
        user = get_or_create_user(username_lower, user_obj.get("display_name"))

        # Check if user data exists
        if user is None:
            log_info(f"User {username} exists on Twitch but not in our database", "roomba")
            # Create a default user data structure
            user = {
                "name": username_lower,
                "display_name": user_obj.get("display_name", username),
                "chat": {"count": 0},
                "command": {"count": 0},
                "admin": {"count": 0},
                "dustbunnies": {"collected_dustbunnies": 0},
                "banking": {}
            }
            log_debug(f"Created temporary user data for {username}", "roomba")

        if "dustbunnies" not in user:
            log_debug(f"Creating dustbunnies object for {username}", "roomba")
            user["dustbunnies"] = {}

        # Only update dustbunnies-specific fields
        previous_amount = user["dustbunnies"].get("collected_dustbunnies", 0)
        user["dustbunnies"]["collected_dustbunnies"] = previous_amount + rnd_number_for_user

        previous_count = user["dustbunnies"].get("message_count", 0)
        user["dustbunnies"]["message_count"] = previous_count + 1

        # Save updated user data
        user_key = f"user:{username_lower}"
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

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj["event_data"]["command"].lower()
            if command == "clean":
                clean_flag = True
            else:
                clean_flag = False
            content = message_obj.get('content')
            log_info(f"Received command: {command}", "roomba", {"content": content})

            username = message_obj["author"]["display_name"]
            # Roomba command to clean up the channel...
            # We can store the amount of messages cleaned up in a database...
            random_value = do_the_cleaning_command(message_obj["author"], username)
            handle_user_data(message_obj["author"], random_value)
            username = message_obj["author"]["mention"]

            # Get additional metrics about user performance
            percentage, percentage_off, better_users = store_value_in_redis_and_get_perc(random_value, username)

            if max_value_to_roomba == random_value:
                # Congratulate the user for hitting the max value
                redis_client.set("roomba_max_hit_value", max_value_to_roomba * 10)
                max_value_to_roomba = int(redis_client.get("roomba_max_hit_value").decode('utf-8'))

                # Reset the array of user attempts when max is hit
                redis_client.delete("roomba_user_attempts")
                log_info(f"Max value of {random_value} was hit - array reset and new max is {max_value_to_roomba}", "roomba", {
                    "max_value": random_value,
                    "new_max_value": max_value_to_roomba,
                    "array_reset": True
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
                # Focus on percentage and better users count without emphasizing username
                performance_msg = ""
                if clean_flag == True:
                    performance_msg = f" {percentage_off:.1f}% off"
                    if better_users > 0:
                        performance_msg += f" ({better_users} closer)"
                send_message_to_redis(f'{username} got {random_value} 🐰{performance_msg}')
        except Exception as e:
            error_msg = f"Error processing roomba command: {e}"
            # Log the error with detailed information
            log_error(error_msg, "roomba", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
