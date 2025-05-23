#!/usr/bin/env python3
"""
Gamble Command

This command allows users to gamble their collected dustbunnies with a 50/50 chance
of winning or losing the amount they bet.

Usage:
!gamble <amount> - Gamble the specified amount of dustbunnies
"""
import json
import random
from datetime import datetime, timedelta

from module.shared_redis import redis_client, pubsub

from module.message_utils import send_system_message_to_redis, send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
# Subscribe to gamble command and its aliases
pubsub.subscribe('twitch.command.gamble')
pubsub.subscribe('twitch.command.bet')
pubsub.subscribe('twitch.command.gambling')

# Initialize cooldown tracking
COOLDOWN_SECONDS = 30
cooldown_users = {}

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def check_timeout(username):
    """Checks if user is in timeout for gambling. Returns True if on timeout, False otherwise."""
    try:
        log_debug(f"Checking timeout for user {username}", "gamble")

        if username not in cooldown_users:
            log_debug(f"User {username} not in cooldown list, adding now", "gamble")
            cooldown_users[username] = datetime.now()
            return False
        else:
            last_used = cooldown_users[username]
            time_since_last = datetime.now() - last_used

            log_debug(f"User {username} last gambled {time_since_last.total_seconds()} seconds ago", "gamble")

            if time_since_last > timedelta(seconds=COOLDOWN_SECONDS):
                log_debug(f"Cooldown expired for {username}, allowing gamble", "gamble")
                cooldown_users[username] = datetime.now()
                return False
            else:
                remaining = COOLDOWN_SECONDS - time_since_last.seconds
                log_info(f"User {username} still on cooldown for {remaining} seconds", "gamble", {
                    "cooldown_remaining": remaining
                })
                send_system_message_to_redis(f"User {username} still has {remaining} seconds in timeout for gambling", "gamble")
                return True

    except Exception as e:
        error_msg = f"Error checking timeout: {e}"
        log_error(error_msg, "gamble", {
            "error": str(e),
            "username": username
        })
        return False  # Default to no timeout in case of error

def handle_gamble(message_obj):
    """Processes the gamble command with the given message object."""
    try:
        username = message_obj["author"]["display_name"]
        username_lower = username.lower()
        user_key = f"user:{username_lower}"
        mention = message_obj["author"]["mention"]

        # Get command content (amount to gamble)
        content = message_obj.get('content', '')

        log_info(f"Processing gamble command from {username}", "gamble", {
            "user": username,
            "content": content
        })

        if not content:
            log_warning(f"User {username} used gamble command without an amount", "gamble")
            send_message_to_redis(f"{mention} You need to specify an amount to gamble!")
            return

        # Parse amount
        amount = content.strip()
        log_debug(f"User {username} attempting to gamble amount: {amount}", "gamble")

        # Check user timeout
        if check_timeout(username_lower):
            log_info(f"User {username} is on cooldown for gambling", "gamble")
            return

        # Get user data
        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
            log_debug(f"Retrieved user data for {username}", "gamble")
        else:
            log_warning(f"User {username} has no account data", "gamble")
            send_message_to_redis(f"{mention} You don't have any dustbunnies to gamble!")
            return

        # Handle 'all' amount
        if amount.lower() == 'all':
            if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"]:
                log_warning(f"User {username} has no dustbunnies to gamble", "gamble")
                send_message_to_redis(f"{mention} You don't have any dustbunnies to gamble!")
                return
            amount = user["dustbunnies"].get("collected_dustbunnies", 0)
            log_info(f"User {username} is gambling all ({amount}) dustbunnies", "gamble")
        else:
            try:
                amount = int(amount)
                log_debug(f"Parsed gamble amount: {amount}", "gamble")
            except ValueError:
                log_warning(f"User {username} provided invalid gamble amount: {amount}", "gamble")
                send_message_to_redis(f"{mention} Please enter a valid number of dustbunnies to gamble!")
                return

        # Check if user has enough dustbunnies
        current_dustbunnies = user["dustbunnies"].get("collected_dustbunnies", 0) if "dustbunnies" in user else 0
        if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"] or current_dustbunnies < amount:
            log_warning(f"User {username} doesn't have enough dustbunnies to gamble {amount}", "gamble", {
                "requested_amount": amount,
                "available_amount": current_dustbunnies
            })
            send_message_to_redis(f"{mention} You don't have enough dustbunnies to gamble {amount}! 😢")
            return

        # Initialize gambling stats if they don't exist
        if "gambling" not in user:
            log_debug(f"Initializing gambling stats for {username}", "gamble")
            user["gambling"] = {
                "input": 0,
                "results": 0,
                "wins": 0,
                "losses": 0
            }

        # Record gambling attempt
        user["gambling"]["input"] = user["gambling"].get("input", 0) + amount

        # Do the gambling (50/50 chance)
        gamble_result = random.choice([True, False])
        log_info(f"User {username} gambling result: {'win' if gamble_result else 'loss'}", "gamble", {
            "amount": amount,
            "result": "win" if gamble_result else "loss"
        })

        # Update user stats based on result
        if gamble_result:
            # User won
            previous_amount = user["dustbunnies"].get("collected_dustbunnies", 0)
            user["gambling"]["results"] = user["gambling"].get("results", 0) + amount
            user["dustbunnies"]["collected_dustbunnies"] = previous_amount + amount
            user["gambling"]["wins"] = user["gambling"].get("wins", 0) + amount

            log_info(f"User {username} won {amount} dustbunnies", "gamble", {
                "previous_amount": previous_amount,
                "new_amount": user["dustbunnies"]["collected_dustbunnies"],
                "win_amount": amount
            })

            send_message_to_redis(f"{mention} You won {amount} Dustbunnies! 🎉 🐰🐻")
        else:
            # User lost
            previous_amount = user["dustbunnies"].get("collected_dustbunnies", 0)
            user["gambling"]["results"] = user["gambling"].get("results", 0) - amount
            user["dustbunnies"]["collected_dustbunnies"] = previous_amount - amount
            user["gambling"]["losses"] = user["gambling"].get("losses", 0) + amount

            log_info(f"User {username} lost {amount} dustbunnies", "gamble", {
                "previous_amount": previous_amount,
                "new_amount": user["dustbunnies"]["collected_dustbunnies"],
                "loss_amount": amount
            })

            send_message_to_redis(f"{mention} You lost {amount} Dustbunnies! 😢 🐰🐻")

        # Save updated user data
        redis_client.set(user_key, json.dumps(user))
        log_debug(f"Saved updated user data for {username}", "gamble")

    except Exception as e:
        error_msg = f"Error processing gamble command: {e}"
        log_error(error_msg, "gamble", {
            "error": str(e),
            "user": message_obj.get("author", {}).get("display_name", "Unknown"),
            "content": message_obj.get("content", "")
        })
        send_system_message_to_redis(f"Error in gamble command: {str(e)}", "gamble")

##########################
# Main
##########################
# Send startup message
log_startup("Gamble command is ready to be used", "gamble")
send_system_message_to_redis("Gamble command is running", "gamble")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content', '')

            log_debug(f"Received gamble command", "gamble", {"command": command, "content": content})
            handle_gamble(message_obj)

        except Exception as e:
            error_msg = f"Error processing gamble command: {e}"
            # Log the error with detailed information
            log_error(error_msg, "gamble", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_system_message_to_redis(f"Error in gamble command: {str(e)}", "gamble")
