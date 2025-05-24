import json
from datetime import datetime

from module.shared_redis import redis_client, pubsub

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.fight')
pubsub.subscribe('twitch.command.battle')
pubsub.subscribe('twitch.command.duel')
pubsub.subscribe('twitch.command.flight')

COOLDOWN_SECONDS = 30
cooldown_users = {}

##########################
# Exit Function
##########################
register_exit_handler()

##########################
# Helper Functions
##########################
def get_user_data(username, display_name=None):
    """
    Retrieve user data from Redis or create a new user if not found.

    Args:
        username (str): The username to retrieve
        display_name (str, optional): The display name to use if creating a new user

    Returns:
        tuple: (user_data, user_key) - The user data dictionary and Redis key
    """
    try:
        username_lower = username.lower()
        user_key = f"user:{username_lower}"

        log_debug(f"Retrieving user data for {username}", "fight")

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
            log_debug(f"Found existing user {username}", "fight")
        else:
            log_info(f"Creating new user account for {username}", "fight")
            user = {
                "name": username,
                "display_name": display_name or username,
                "log": {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0},
                "dustbunnies": {},
                "banking": {},
                "fighting": {},
            }

        if "fighting" not in user:
            log_debug(f"Creating fighting object for {username}", "fight")
            user["fighting"] = {}

        return user, user_key

    except Exception as e:
        error_msg = f"Error retrieving user data: {e}"
        log_error(error_msg, "fight", {
            "error": str(e),
            "username": username
        })
        # Return a basic user object to prevent further errors
        return {
            "name": username,
            "display_name": display_name or username,
            "fighting": {}
        }, f"user:{username.lower()}"

def save_user_data(user_key, user):
    """Saves user data to Redis using the specified key."""
    try:
        log_debug(f"Saving user data for {user.get('display_name', 'Unknown')}", "fight")
        redis_client.set(user_key, json.dumps(user))

    except Exception as e:
        error_msg = f"Error saving user data: {e}"
        log_error(error_msg, "fight", {
            "error": str(e),
            "user": user.get('display_name', 'Unknown')
        })

def check_cooldown(username):
    """Checks if user is on cooldown. Returns remaining seconds or 0 if not on cooldown."""
    try:
        now = datetime.now()

        if username in cooldown_users:
            last = cooldown_users[username]
            time_since_last = (now - last).total_seconds()

            log_debug(f"User {username} last used fight {time_since_last} seconds ago", "fight")

            if time_since_last < COOLDOWN_SECONDS:
                remaining = COOLDOWN_SECONDS - int(time_since_last)
                log_info(f"User {username} still on cooldown for {remaining} seconds", "fight", {
                    "cooldown_remaining": remaining
                })
                return remaining

        log_debug(f"User {username} not on cooldown, adding to cooldown list", "fight")
        cooldown_users[username] = now
        return 0

    except Exception as e:
        error_msg = f"Error checking cooldown: {e}"
        log_error(error_msg, "fight", {
            "error": str(e),
            "username": username
        })
        return 0  # Default to no cooldown in case of error

def handle_fight_command(message_obj):
    """Processes fight command to initiate a challenge between users."""
    try:
        author = message_obj["author"]
        username = author["display_name"]
        username_lower = author["name"].lower()
        mention = author["mention"]
        content = message_obj.get("content", "")

        log_info(f"Processing fight command from {username}", "fight", {
            "user": username,
            "content": content
        })

        # Validate content
        if not content:
            log_warning(f"User {username} used fight command without a target", "fight")
            send_message_to_redis(f"{mention} Please provide a username to fight with. Usage: !fight <username>")
            return

        # Parse target
        target = content.strip().split()[0]
        if target.startswith("@"): target = target[1:]
        target = target.lower()

        log_debug(f"User {username} wants to fight with {target}", "fight")

        # Check if trying to fight self
        if target == username_lower:
            log_warning(f"User {username} tried to fight themselves", "fight")
            send_message_to_redis(f"{mention} You can't fight yourself!")
            return

        # Cooldown check
        remaining = check_cooldown(username_lower)
        if remaining:
            log_info(f"User {username} is on cooldown for {remaining} seconds", "fight")
            send_message_to_redis(f"{mention} Please wait {remaining} seconds before challenging again.")
            return

        # Save fight request
        log_info(f"Saving fight request from {username} to {target}", "fight")
        target_user, target_key = get_user_data(target, target)
        target_user["fighting"]["fight_requested_by"] = username_lower
        save_user_data(target_key, target_user)

        # Send challenge message
        send_message_to_redis(f"@{target} {username} has requested a fight with you! Type !accept to fight back!")
        log_info(f"Fight request sent from {username} to {target}", "fight", {
            "challenger": username,
            "target": target
        })

    except Exception as e:
        error_msg = f"Error handling fight command: {e}"
        log_error(error_msg, "fight", {
            "error": str(e),
            "user": message_obj.get("author", {}).get("display_name", "Unknown")
        })

##########################
# Main
##########################
# Send startup message
log_startup("Fight command is ready to be used", "fight")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '').lower()
            content = message_obj.get('content', '')

            if command in ["fight", "battle", "duel", "flight"]:
                log_info(f"Received {command} command", "fight", {"content": content})
                handle_fight_command(message_obj)

        except Exception as e:
            error_msg = f"Error processing fight command: {e}"
            # Log the error with detailed information
            log_error(error_msg, "fight", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
