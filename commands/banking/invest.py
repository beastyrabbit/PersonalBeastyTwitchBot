import json
import time
from datetime import datetime

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
    """
    Allow a moderator or broadcaster to invest points for another user.

    Args:
        user_that_invests (dict): The user object of the moderator/broadcaster
        receiving_user (str): The username of the user receiving the investment
        invest_amount (int): The amount to invest

    Returns:
        bool: True if investment was successful, False otherwise
    """
    try:
        investor_name = user_that_invests.get('display_name', 'Unknown')
        user_that_receiving_lower = receiving_user.lower().replace("@", "")
        user_key = f"user:{user_that_receiving_lower}"

        log_debug(f"Mod {investor_name} investing {invest_amount} for {receiving_user}", "invest", {
            "investor": investor_name,
            "recipient": user_that_receiving_lower,
            "amount": invest_amount
        })

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user_obj = json.loads(user_json)
            log_debug(f"Found existing user {user_that_receiving_lower}", "invest")
        else:
            # create new user if not exists
            log_info(f"Creating new user account for {user_that_receiving_lower}", "invest")
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
            log_debug(f"Creating banking object for {user_that_receiving_lower}", "invest")
            user_obj["banking"] = {}

        if "dustbunnies" not in user_obj:
            log_debug(f"Creating dustbunnies object for {user_that_receiving_lower}", "invest")
            user_obj["dustbunnies"] = {}

        # Check if user has enough dustbunnies
        current_bunnies = user_obj["dustbunnies"].get("collected_dustbunnies", 0)
        if current_bunnies < invest_amount:
            log_info(f"User {user_that_receiving_lower} has insufficient funds", "invest", {
                "current": current_bunnies,
                "requested": invest_amount
            })
            send_message_to_redis(f"@{user_that_receiving_lower} does not have enough dustbunnies to invest {invest_amount}")
            return False

        # Subtract the invested amount from dustbunnies
        previous_bunnies = user_obj["dustbunnies"].get("collected_dustbunnies", 0)
        user_obj["dustbunnies"]["collected_dustbunnies"] = previous_bunnies - invest_amount

        # Only update banking-specific fields
        previous_invested = user_obj["banking"].get("bunnies_invested", 0)
        user_obj["banking"]["total_bunnies_collected"] = user_obj["banking"].get("total_bunnies_collected", 0)
        user_obj["banking"]["bunnies_invested"] = previous_invested + invest_amount
        user_obj["banking"]["timestamp_investment"] = datetime.now(tz=None).isoformat()
        user_obj["banking"]["last_interest_collected"] = user_obj["banking"].get("last_interest_collected", 0)

        redis_client.set(user_key, json.dumps(user_obj))

        log_info(f"Mod {investor_name} successfully invested for {user_that_receiving_lower}", "invest", {
            "amount": invest_amount,
            "previous_invested": previous_invested,
            "new_invested": user_obj["banking"]["bunnies_invested"],
            "previous_bunnies": previous_bunnies,
            "new_bunnies": user_obj["dustbunnies"]["collected_dustbunnies"]
        })

        return True
    except Exception as e:
        error_msg = f"Error in mod investment: {e}"
        log_error(error_msg, "invest", {
            "error": str(e),
            "investor": user_that_invests.get('display_name', 'Unknown'),
            "recipient": receiving_user,
            "amount": invest_amount
        })
        print(error_msg)
        return False

def invest_money(user, invest_amount):
    """
    Allow a user to invest their own points.

    Args:
        user (dict): The user object of the investor
        invest_amount (int): The amount to invest

    Returns:
        bool: True if investment was successful, False otherwise
    """
    try:
        username = user.get('display_name', user["name"])
        username_lower = user["name"].lower()
        user_key = f"user:{username_lower}"

        log_debug(f"User {username} investing {invest_amount}", "invest", {
            "user": username,
            "amount": invest_amount
        })

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user_obj = json.loads(user_json)
            log_debug(f"Found existing user {username}", "invest")
        else:
            # Create new user if not exists
            log_info(f"Creating new user account for {username}", "invest")
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
            log_debug(f"Creating banking object for {username}", "invest")
            user_obj["banking"] = {}

        if "dustbunnies" not in user_obj:
            log_debug(f"Creating dustbunnies object for {username}", "invest")
            user_obj["dustbunnies"] = {}

        # Check if user has enough dustbunnies
        current_bunnies = user_obj["dustbunnies"].get("collected_dustbunnies", 0)
        if current_bunnies < invest_amount:
            log_info(f"User {username} has insufficient funds", "invest", {
                "current": current_bunnies,
                "requested": invest_amount
            })
            send_message_to_redis(f"{user['mention']} you do not have enough dustbunnies to invest {invest_amount}")
            return False

        # Subtract the invested amount from dustbunnies
        previous_bunnies = user_obj["dustbunnies"].get("collected_dustbunnies", 0)
        user_obj["dustbunnies"]["collected_dustbunnies"] = previous_bunnies - invest_amount

        # Only update banking-specific fields
        previous_invested = user_obj["banking"].get("bunnies_invested", 0)
        user_obj["banking"]["total_bunnies_collected"] = user_obj["banking"].get("total_bunnies_collected", 0)
        user_obj["banking"]["bunnies_invested"] = previous_invested + invest_amount
        user_obj["banking"]["timestamp_investment"] = datetime.now(tz=None).isoformat()
        user_obj["banking"]["last_interest_collected"] = user_obj["banking"].get("last_interest_collected", 0)

        redis_client.set(user_key, json.dumps(user_obj))

        log_info(f"User {username} successfully invested", "invest", {
            "amount": invest_amount,
            "previous_invested": previous_invested,
            "new_invested": user_obj["banking"]["bunnies_invested"],
            "previous_bunnies": previous_bunnies,
            "new_bunnies": user_obj["dustbunnies"]["collected_dustbunnies"]
        })

        return True
    except Exception as e:
        error_msg = f"Error in user investment: {e}"
        log_error(error_msg, "invest", {
            "error": str(e),
            "user": user.get('display_name', user.get('name', 'Unknown')),
            "amount": invest_amount
        })
        print(error_msg)
        return False

##########################
# Main
##########################
log_startup("Invest command is ready to be used", "invest")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            user = message_obj["author"].get("display_name", "Unknown")

            print(f"Chat Command: {command} and Message: {content}")
            log_info(f"Received invest command from {user}", "invest", {
                "command": command,
                "content": content
            })

            msg_content = message_obj["content"]
            msg_parts = msg_content.split()

            # Check if this is a mod/broadcaster investing for someone else
            if len(msg_parts) > 2 and (message_obj["author"]["moderator"] or message_obj["author"]["broadcaster"]):
                invest_for_user = msg_parts[1]
                try:
                    invest_amount = int(msg_parts[2])
                    log_debug(f"{user} specified {invest_amount} for {invest_for_user}", "invest")
                except ValueError:
                    log_info(f"User {user} provided invalid amount", "invest")
                    send_message_to_redis(f"{message_obj['author']['mention']} the amount must be a number")
                    continue

                # Check if user starts with @ because we need the username
                if not invest_for_user.startswith("@"):
                    log_info(f"User {user} provided invalid target format", "invest")
                    send_message_to_redis(f"{message_obj['author']['mention']} you need to use the @username to invest for someone")
                    continue

                # Invest for the user as mod/broadcaster
                log_info(f"{user} investing for {invest_for_user}", "invest", {
                    "amount": invest_amount,
                    "is_mod": message_obj["author"]["moderator"],
                    "is_broadcaster": message_obj["author"]["broadcaster"]
                })

                if invest_money_as_mod(message_obj["author"], invest_for_user, invest_amount):
                    send_message_to_redis(f"{message_obj['author']['mention']} invested {invest_amount} points for {invest_for_user}")
            else:
                # Regular invest for self
                try:
                    invest_amount = int(msg_parts[1]) if len(msg_parts) > 1 else None
                    if invest_amount:
                        log_debug(f"User {user} investing {invest_amount} for self", "invest")
                except ValueError:
                    log_info(f"User {user} provided invalid amount", "invest")
                    send_message_to_redis(f"{message_obj['author']['mention']} the amount must be a number")
                    continue

                if not invest_amount:
                    log_info(f"User {user} didn't specify an amount", "invest")
                    send_message_to_redis(f"{message_obj['author']['mention']} you need to specify an amount to invest")
                    continue

                # Invest
                log_info(f"User {user} investing {invest_amount} for self", "invest")
                if invest_money(message_obj["author"], invest_amount):
                    send_message_to_redis(f"{message_obj['author']['mention']} you have invested {invest_amount} points")
        except json.JSONDecodeError as je:
            error_msg = f"JSON error in invest command: {je}"
            print(error_msg)
            log_error(error_msg, "invest", {
                "error": str(je),
                "data": message.get('data', 'N/A')
            })
        except Exception as e:
            error_msg = f"Unexpected error in invest command: {str(e)}"
            print(error_msg)
            log_error(error_msg, "invest", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
