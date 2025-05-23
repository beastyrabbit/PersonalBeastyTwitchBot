import json
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
redis_client.set("daily_interest_rate", 0.02)
daily_interest_rate = float(redis_client.get("daily_interest_rate"))
pubsub.subscribe('twitch.command.collect')
pubsub.subscribe('twitch.command.interest')

##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################
def calculate_interest(user, force_days=None):
    """Calculate interest for a user based on their investment."""
    try:
        global daily_interest_rate
        username = user.get('mention', 'Unknown')

        # Check if user has invested before
        if user["bunnies_invested"] == 0:
            log_info(f"User {username} has not invested any points yet", "collect")
            send_message_to_redis(f"{user['mention']} you have not invested any points yet")
            return user

        invested = int(user["bunnies_invested"])
        timestamp = user["timestamp_investment"]
        current_time = datetime.now(tz=None)
        timestamp = datetime.fromisoformat(timestamp)

        log_debug(f"Calculating interest for {username}", "collect", {
            "invested": invested,
            "timestamp": timestamp.isoformat(),
            "force_days": force_days
        })

        # Use forced days if provided, otherwise calculate actual days
        if force_days is not None:
            # When force_days is provided (by broadcaster), bypass the 1-day waiting period check
            days_since_investment = force_days
            log_debug(f"Using forced days: {days_since_investment}", "collect")
        else:
            days_since_investment = (current_time - timestamp).days
            log_debug(f"Days since investment: {days_since_investment}", "collect")
            if days_since_investment == 0:
                log_info(f"User {username} tried to collect interest before 1 day", "collect")
                send_message_to_redis(f"{user['mention']} you have to wait at least 1 day to collect interest")
                return user

        # Calculate interest based on compound interest formula
        total_amount = invested * (1 + daily_interest_rate) ** days_since_investment
        total_amount = int(total_amount)
        interest = total_amount - invested

        log_info(f"Interest calculated for {username}", "collect", {
            "invested": invested,
            "days": days_since_investment,
            "interest_rate": daily_interest_rate,
            "interest_earned": interest
        })

        # Update timestamp but keep the principal invested (don't add interest to principal)
        user["timestamp_investment"] = current_time.isoformat()
        # Principal remains the same, we don't add interest to it
        # user["bunnies_invested"] remains unchanged
        user["total_bunnies_collected"] += interest
        user["last_interest_collected"] = interest
        return user
    except Exception as e:
        error_msg = f"Error calculating interest: {e}"
        log_error(error_msg, "collect", {"error": str(e), "user": user.get('mention', 'Unknown')})
        print(error_msg)
        # Return user unchanged in case of error
        return user

def mod_collect_for_user(user_that_collects, target_user):
    """Allow a moderator to collect interest for another user."""
    try:
        mod_username = user_that_collects.get('mention', 'Unknown')

        # Remove @ if present
        target_user_lower = target_user.lower().replace("@", "")
        user_key = f"user:{target_user_lower}"

        log_info(f"Moderator {mod_username} attempting to collect for {target_user}", "collect")

        if not redis_client.exists(user_key):
            log_info(f"User {target_user} does not exist or has no bank account", "collect")
            send_message_to_redis(f"{user_that_collects['mention']} the user {target_user} does not exist or has no bank account")
            return

        user_json = redis_client.get(user_key)
        user_data = json.loads(user_json)

        # Check if user has invested
        if "banking" not in user_data or user_data["banking"].get("bunnies_invested", 0) == 0:
            log_info(f"User {target_user} has not invested any points yet", "collect")
            send_message_to_redis(f"{user_that_collects['mention']} the user {target_user} has not invested any points yet")
            return

        # Calculate actual days since investment
        current_time = datetime.now(tz=None)
        timestamp = datetime.fromisoformat(user_data["banking"]["timestamp_investment"])
        days_since_investment = (current_time - timestamp).days

        log_debug(f"Days since investment for {target_user}: {days_since_investment}", "collect")

        # Create a user object for the target user
        target_user_obj = {
            "name": target_user_lower,
            "display_name": target_user.replace("@", ""),
            "mention": f"@{target_user_lower}"
        }

        # If more than 24h, use actual time, otherwise default to 1 day
        force_days = days_since_investment if days_since_investment > 0 else 1
        log_info(f"Moderator {mod_username} collecting for {target_user} with {force_days} days", "collect")

        # Collect interest with the determined days
        collect_interest_for_user(target_user_obj, force_days)

        # Get the user data again to see if interest was collected
        user_json = redis_client.get(user_key)
        user_data = json.loads(user_json)
        interest_collected = user_data.get("banking", {}).get("last_interest_collected", 0)

        if interest_collected > 0:
            log_info(f"Moderator {mod_username} collected {interest_collected} points for {target_user}", "collect")
            send_message_to_redis(f"{user_that_collects['mention']} collected {interest_collected} points of interest for {target_user}")
        else:
            log_info(f"Moderator {mod_username} tried to collect for {target_user} but no interest was collected", "collect")
            send_message_to_redis(f"{user_that_collects['mention']} tried to collect for {target_user} but no interest was collected")
    except Exception as e:
        error_msg = f"Error in mod_collect_for_user: {e}"
        log_error(error_msg, "collect", {
            "error": str(e),
            "moderator": user_that_collects.get('mention', 'Unknown'),
            "target_user": target_user
        })
        print(error_msg)

def force_collect_for_user(user_that_forces, target_user, days):
    """Allow a broadcaster to force collect interest for another user with specified days."""
    try:
        broadcaster_username = user_that_forces.get('mention', 'Unknown')

        # Remove @ if present
        target_user_lower = target_user.lower().replace("@", "")
        user_key = f"user:{target_user_lower}"

        log_info(f"Broadcaster {broadcaster_username} forcing collect for {target_user} with {days} days", "collect")

        if not redis_client.exists(user_key):
            log_info(f"User {target_user} does not exist or has no bank account", "collect")
            send_message_to_redis(f"{user_that_forces['mention']} the user {target_user} does not exist or has no bank account")
            return

        user_json = redis_client.get(user_key)
        user_data = json.loads(user_json)

        # Check if user has invested (optional, as we'll check in collect_interest_for_user too)
        if "banking" not in user_data or user_data["banking"].get("bunnies_invested", 0) == 0:
            log_info(f"User {target_user} has not invested any points yet", "collect")
            send_message_to_redis(f"{user_that_forces['mention']} the user {target_user} has not invested any points yet")
            return

        # Create a user object for the target user to pass to collect_interest_for_user
        target_user_obj = {
            "name": target_user_lower,
            "display_name": target_user.replace("@", ""),
            "mention": f"@{target_user_lower}"
        }

        log_debug(f"Forcing collect for {target_user} with {days} days", "collect")

        # Force collect with specified days
        collect_interest_for_user(target_user_obj, days)

        # Get the user data again to see if interest was collected
        user_json = redis_client.get(user_key)
        user_data = json.loads(user_json)
        interest_collected = user_data.get("banking", {}).get("last_interest_collected", 0)

        if interest_collected > 0:
            log_info(f"Broadcaster {broadcaster_username} forced collect for {target_user}: {interest_collected} points", "collect", {
                "days": days,
                "interest": interest_collected
            })
            send_message_to_redis(f"{user_that_forces['mention']} forced a collect for {target_user} with {days} days of interest: {interest_collected} points")
        else:
            log_info(f"Broadcaster {broadcaster_username} forced collect for {target_user} but no interest was collected", "collect")
            send_message_to_redis(f"{user_that_forces['mention']} forced a collect for {target_user} but no interest was collected")
    except Exception as e:
        error_msg = f"Error in force_collect_for_user: {e}"
        log_error(error_msg, "collect", {
            "error": str(e),
            "broadcaster": user_that_forces.get('mention', 'Unknown'),
            "target_user": target_user,
            "days": days
        })
        print(error_msg)

def collect_interest_for_user(user_obj, force_days=None):
    """Collect interest for a user based on their investment."""
    try:
        username = user_obj.get('mention', user_obj['name'])
        username_lower = user_obj['name'].lower()
        user_key = f"user:{username_lower}"

        log_debug(f"Collecting interest for {username}", "collect", {
            "force_days": force_days
        })

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user_data = json.loads(user_json)

            # Ensure banking sub-object exists
            if "banking" not in user_data:
                log_debug(f"Creating banking object for {username}", "collect")
                user_data["banking"] = {}

            banking = user_data["banking"]

            # Set defaults if missing (only banking-specific fields)
            banking.setdefault("bunnies_invested", 0)
            banking.setdefault("timestamp_investment", datetime.now().isoformat())
            banking.setdefault("total_bunnies_collected", 0)
            banking.setdefault("last_interest_collected", 0)
            banking.setdefault("mention", user_obj.get("mention", user_obj["name"]))

            # Calculate interest
            updated_banking = calculate_interest(banking, force_days)
            user_data["banking"] = updated_banking

            # Add the collected interest to dustbunnies
            interest_collected = updated_banking.get("last_interest_collected", 0)
            if interest_collected > 0:
                log_info(f"User {username} collected {interest_collected} points of interest", "collect", {
                    "interest": interest_collected,
                    "total_collected": updated_banking.get("total_bunnies_collected", 0)
                })

                # Ensure dustbunnies sub-object exists
                if "dustbunnies" not in user_data:
                    user_data["dustbunnies"] = {}

                # Add the interest to collected_dustbunnies
                previous_dustbunnies = user_data["dustbunnies"].get("collected_dustbunnies", 0)
                user_data["dustbunnies"]["collected_dustbunnies"] = previous_dustbunnies + interest_collected

                log_debug(f"Updated dustbunnies for {username}", "collect", {
                    "previous": previous_dustbunnies,
                    "added": interest_collected,
                    "new_total": user_data["dustbunnies"]["collected_dustbunnies"]
                })

            redis_client.set(user_key, json.dumps(user_data))

            if interest_collected > 0:
                send_message_to_redis(f"{user_obj['mention']} you have collected {interest_collected} points from interest")
        else:
            # Create new user JSON if not exists
            log_info(f"Creating new user account for {username}", "collect")

            user_data = {
                "name": user_obj["name"],
                "display_name": user_obj.get("display_name", user_obj["name"]),
                "chat": {"count": 0},
                "command": {"count": 0},
                "admin": {"count": 0},
                "dustbunnies": {},
                "banking": {
                    "bunnies_invested": 0,
                    "timestamp_investment": datetime.now().isoformat(),
                    "total_bunnies_collected": 0,
                    "last_interest_collected": 0,
                    "mention": user_obj.get("mention", user_obj["name"])
                }
            }
            redis_client.set(user_key, json.dumps(user_data))
            send_message_to_redis(f"{user_obj['mention']} you did not open a bank account yet use !invest to open one")
    except Exception as e:
        error_msg = f"Error collecting interest for user: {e}"
        log_error(error_msg, "collect", {
            "error": str(e),
            "user": user_obj.get('mention', user_obj.get('name', 'Unknown')),
            "force_days": force_days
        })
        print(error_msg)

##########################
# Main
##########################
log_startup("Collect command is ready to be used", "collect")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            user = message_obj["author"].get("display_name", "Unknown")

            print(f"Chat Command: {command} and Message: {content}")
            log_info(f"Received collect command from {user}", "collect", {
                "command": command,
                "content": content
            })

            msg_content = message_obj["content"]
            msg_parts = msg_content.split()

            # Check if this is a broadcaster or mod collecting for someone else
            if len(msg_parts) > 1 and (message_obj["author"]["broadcaster"] or message_obj["author"]["moderator"]):
                target_user = msg_parts[1]

                # Check if user starts with @ because we need the username
                if not target_user.startswith("@"):
                    log_info(f"User {user} provided invalid target format", "collect")
                    send_message_to_redis(f"{message_obj['author']['mention']} you need to use the @username to collect for someone")
                    continue

                # Different behavior for broadcasters and mods
                if message_obj["author"]["broadcaster"]:
                    # Broadcaster can specify days or default to 1
                    if len(msg_parts) > 2:
                        try:
                            days = int(msg_parts[2])
                            log_debug(f"Broadcaster {user} specified {days} days for {target_user}", "collect")
                        except ValueError:
                            log_info(f"Broadcaster {user} provided invalid days value", "collect")
                            send_message_to_redis(f"{message_obj['author']['mention']} the days must be a number")
                            continue
                    else:
                        # Default to 1 day if not specified
                        days = 1
                        log_debug(f"Using default 1 day for {target_user}", "collect")

                    # Force collect for the user with specified days
                    force_collect_for_user(message_obj["author"], target_user, days)
                else:
                    # For mods, we need to check the actual time
                    log_info(f"Moderator {user} collecting for {target_user}", "collect")
                    mod_collect_for_user(message_obj["author"], target_user)
            else:
                # Regular collect for self
                log_info(f"User {user} collecting interest for self", "collect")
                collect_interest_for_user(message_obj["author"])
        except json.JSONDecodeError as je:
            error_msg = f"JSON error in collect command: {je}"
            print(error_msg)
            log_error(error_msg, "collect", {
                "error": str(je),
                "data": message.get('data', 'N/A')
            })
        except Exception as e:
            error_msg = f"Unexpected error in collect command: {str(e)}"
            print(error_msg)
            log_error(error_msg, "collect", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
