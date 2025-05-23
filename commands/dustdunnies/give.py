import json

from module.shared_redis import redis_client, pubsub

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.give')
pubsub.subscribe('twitch.command.donate')
pubsub.subscribe('twitch.command.gift')
pubsub.subscribe('twitch.command.share')

##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################

def give_dustbunnies_as_mod(user_that_gives, receiving_user, amount_gives):
    """
    Allow a moderator or broadcaster to give dustbunnies to another user.

    Args:
        user_that_gives (dict): The user object of the moderator/broadcaster
        receiving_user (str): The username of the user receiving the dustbunnies
        amount_gives (int): The amount of dustbunnies to give
    """
    try:
        giver_name = user_that_gives.get('display_name', 'Unknown')
        user_that_receiving_lower = receiving_user.lower().replace("@", "")
        user_key = f"user:{user_that_receiving_lower}"

        log_debug(f"Mod {giver_name} giving {amount_gives} dustbunnies to {receiving_user}", "give", {
            "giver": giver_name,
            "recipient": user_that_receiving_lower,
            "amount": amount_gives
        })

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user_data = json.loads(user_json)
            log_debug(f"Found existing user {user_that_receiving_lower}", "give")
        else:
            # create new user if not exists
            log_info(f"Creating new user account for {user_that_receiving_lower}", "give")
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
            log_debug(f"Creating dustbunnies object for {user_that_receiving_lower}", "give")
            user_data["dustbunnies"] = {}

        # only update dustbunnies fields
        previous_amount = user_data["dustbunnies"].get("collected_dustbunnies", 0)
        user_data["dustbunnies"]["collected_dustbunnies"] = previous_amount + amount_gives

        redis_client.set(user_key, json.dumps(user_data))

        log_info(f"Mod {giver_name} gave {amount_gives} dustbunnies to {user_that_receiving_lower}", "give", {
            "previous_amount": previous_amount,
            "new_amount": user_data["dustbunnies"]["collected_dustbunnies"]
        })
    except Exception as e:
        error_msg = f"Error in mod give: {e}"
        log_error(error_msg, "give", {
            "error": str(e),
            "giver": user_that_gives.get('display_name', 'Unknown'),
            "recipient": receiving_user,
            "amount": amount_gives
        })
        print(error_msg)


def give_dustbunnies(user_that_gives, receiving_user, amount_gives):
    """
    Allow a regular user to give their own dustbunnies to another user.

    Args:
        user_that_gives (dict): The user object of the giver
        receiving_user (str): The username of the user receiving the dustbunnies
        amount_gives (int): The amount of dustbunnies to give
    """
    try:
        giver_name = user_that_gives.get('display_name', user_that_gives["name"])
        giver_lower = user_that_gives["name"].lower()
        giver_key = f"user:{giver_lower}"

        log_debug(f"User {giver_name} attempting to give {amount_gives} dustbunnies to {receiving_user}", "give", {
            "giver": giver_name,
            "recipient": receiving_user,
            "amount": amount_gives
        })

        # Check if giver exists and has enough dustbunnies
        if redis_client.exists(giver_key):
            giver_json = redis_client.get(giver_key)
            giver_data = json.loads(giver_json)

            if "dustbunnies" not in giver_data:
                log_debug(f"Creating dustbunnies object for giver {giver_name}", "give")
                giver_data["dustbunnies"] = {}

            # Check if enough dustbunnies
            current_bunnies = giver_data["dustbunnies"].get("collected_dustbunnies", 0)
            if current_bunnies < amount_gives:
                log_info(f"User {giver_name} has insufficient dustbunnies", "give", {
                    "current": current_bunnies,
                    "requested": amount_gives
                })
                send_message_to_redis(f"{user_that_gives['mention']} does not have enough dustbunnies nice try")
                return

            # Subtract from giver
            previous_bunnies = giver_data["dustbunnies"].get("collected_dustbunnies", 0)
            giver_data["dustbunnies"]["collected_dustbunnies"] = previous_bunnies - amount_gives
            redis_client.set(giver_key, json.dumps(giver_data))

            log_debug(f"Subtracted {amount_gives} dustbunnies from {giver_name}", "give", {
                "previous": previous_bunnies,
                "new": giver_data["dustbunnies"]["collected_dustbunnies"]
            })
        else:
            log_info(f"User {giver_name} does not exist", "give")
            send_message_to_redis(f"{user_that_gives['mention']} does not exist and cant give dustbunnies")
            return

        # Process receiver
        user_that_receiving_lower = receiving_user.lower().replace("@", "")
        receiver_key = f"user:{user_that_receiving_lower}"

        if redis_client.exists(receiver_key):
            receiver_json = redis_client.get(receiver_key)
            receiver_data = json.loads(receiver_json)
            log_debug(f"Found existing user {user_that_receiving_lower}", "give")
        else:
            # Create new user if not exists
            log_info(f"Creating new user account for {user_that_receiving_lower}", "give")
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
            log_debug(f"Creating dustbunnies object for {user_that_receiving_lower}", "give")
            receiver_data["dustbunnies"] = {}

        # Only update dustbunnies fields
        previous_amount = receiver_data["dustbunnies"].get("collected_dustbunnies", 0)
        receiver_data["dustbunnies"]["collected_dustbunnies"] = previous_amount + amount_gives

        redis_client.set(receiver_key, json.dumps(receiver_data))

        log_info(f"User {giver_name} gave {amount_gives} dustbunnies to {user_that_receiving_lower}", "give", {
            "previous_amount": previous_amount,
            "new_amount": receiver_data["dustbunnies"]["collected_dustbunnies"]
        })
    except Exception as e:
        error_msg = f"Error in user give: {e}"
        log_error(error_msg, "give", {
            "error": str(e),
            "giver": user_that_gives.get('display_name', user_that_gives.get('name', 'Unknown')),
            "recipient": receiving_user,
            "amount": amount_gives
        })
        print(error_msg)


def give_all_dustbunnies(amount):
    """
    Give a specified amount of dustbunnies to all users in the system.
    Only broadcasters can use this function.

    Args:
        amount (int): The amount of dustbunnies to give to each user
    """
    try:
        log_info(f"Giving {amount} dustbunnies to all users", "give", {
            "amount": amount
        })

        all_users = redis_client.keys("user:*")
        log_debug(f"Found {len(all_users)} users to give dustbunnies to", "give")

        updated_count = 0
        for user in all_users:
            try:
                user_json = redis_client.get(user)
                user_obj = json.loads(user_json)
                username = user_obj.get("display_name", user.decode('utf-8').replace("user:", ""))

                if "dustbunnies" not in user_obj:
                    log_debug(f"Creating dustbunnies object for {username}", "give")
                    user_obj["dustbunnies"] = {}

                # Only update dustbunnies fields
                previous_amount = user_obj["dustbunnies"].get("collected_dustbunnies", 0)
                user_obj["dustbunnies"]["collected_dustbunnies"] = previous_amount + amount

                redis_client.set(user, json.dumps(user_obj))
                updated_count += 1

                log_debug(f"Updated user {username} dustbunnies", "give", {
                    "previous": previous_amount,
                    "added": amount,
                    "new": user_obj["dustbunnies"]["collected_dustbunnies"]
                })
            except Exception as e:
                error_msg = f"Error updating user {user}: {e}"
                log_error(error_msg, "give", {"error": str(e), "user": str(user)})
                # Continue with other users even if one fails

        log_info(f"Successfully gave {amount} dustbunnies to {updated_count} users", "give", {
            "total_users": len(all_users),
            "updated_users": updated_count
        })

        send_message_to_redis(f"All Users got {amount} dustbunnies")
    except Exception as e:
        error_msg = f"Error giving dustbunnies to all users: {e}"
        log_error(error_msg, "give", {"error": str(e), "amount": amount})
        print(error_msg)

##########################
# Main
##########################
log_startup("Give Command is ready to be used", "give")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            # Parse the message
            try:
                message_obj = json.loads(message['data'].decode('utf-8'))
                command = message_obj.get('command')
                content = message_obj.get('content')
                user = message_obj["author"].get("display_name", "Unknown")

                print(f"Chat Command: {command} and Message: {content}")
                log_info(f"Received give command from {user}", "give", {
                    "command": command,
                    "content": content
                })
            except json.JSONDecodeError as je:
                error_msg = f"JSON decode error: {je}"
                log_error(error_msg, "give", {"data": str(message.get('data', 'N/A'))})
                continue

            # First get user that will be given to
            msg_content = message_obj["content"]

            # Parse command arguments
            try:
                # Remove !give from the message
                give_to_user = msg_content.split()[1] if len(msg_content.split()) > 1 else None
                amount = int(msg_content.split()[2]) if len(msg_content.split()) > 2 else None

                if not give_to_user or not amount:
                    log_info(f"User {user} provided invalid command format", "give")
                    send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the !give <@username> <amount> to give dustbunnies")
                    continue

                log_debug(f"Parsed command: give to {give_to_user}, amount {amount}", "give")
            except (IndexError, ValueError) as e:
                log_info(f"User {user} provided invalid command format", "give", {"error": str(e)})
                send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the !give <@username> <amount> to give dustbunnies")
                continue

            # Check for give all
            if give_to_user == "all":
                log_debug(f"User {user} attempting to give to all users", "give")

                # Check if broadcaster
                if message_obj["author"]["broadcaster"]:
                    log_info(f"Broadcaster {user} giving {amount} dustbunnies to all users", "give")
                    # Get all users
                    give_all_dustbunnies(amount)
                else:
                    log_info(f"Non-broadcaster {user} attempted to use give all command", "give")
                    send_message_to_redis(f"{message_obj["author"]["display_name"]} are not allowed to use this command")
            else:
                # Check if user starts with @ because we need the username
                if not give_to_user.startswith("@"):
                    log_info(f"User {user} provided invalid target format", "give")
                    send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the @username to give dustbunnies")
                    continue

                # Different handling for mods/broadcasters vs regular users
                if message_obj["author"]["moderator"] or message_obj["author"]["broadcaster"]:
                    log_info(f"Mod/broadcaster {user} giving {amount} dustbunnies to {give_to_user}", "give")
                    give_dustbunnies_as_mod(message_obj["author"], give_to_user, amount)
                    send_message_to_redis(f"{message_obj["author"]["mention"]} gave {amount} dustbunnies to {give_to_user}")
                else:
                    log_info(f"User {user} giving {amount} dustbunnies to {give_to_user}", "give")
                    give_dustbunnies(message_obj["author"], give_to_user, amount)
                    send_message_to_redis(f"{message_obj["author"]["mention"]} gave {amount} dustbunnies to {give_to_user}")
        except Exception as e:
            error_msg = f"Error processing give command: {e}"
            print(error_msg)
            log_error(error_msg, "give", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
