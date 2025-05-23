#!/usr/bin/env python3
"""
Slots Command

This command allows users to play a slot machine game with their collected dustbunnies.
Users can bet a specific amount and win based on matching symbols.

Usage:
!slots <amount> - Play the slot machine with the specified amount of dustbunnies
!slots all - Play with all your dustbunnies
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
pubsub.subscribe('twitch.command.slots')
pubsub.subscribe('twitch.command.slot')

# Initialize cooldown tracking
COOLDOWN_SECONDS = 15
cooldown_users = {}

# Slot symbols and their probabilities/payouts
SLOT_SYMBOLS = ['🍇', '🍒', '🍋', '🍊', '🍎', '🍓', '🍌', '💰', '💎', '🎰']
# Special symbols have lower probability but higher payout
SPECIAL_SYMBOLS = ['💰', '💎', '🎰']

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def check_timeout(username):
    """Checks if user is in timeout for slots. Returns True if on timeout, False otherwise."""
    try:
        log_debug(f"Checking timeout for user {username}", "slots")

        if username not in cooldown_users:
            log_debug(f"User {username} not in cooldown list, adding now", "slots")
            cooldown_users[username] = datetime.now()
            return False
        else:
            last_used = cooldown_users[username]
            time_since_last = datetime.now() - last_used

            log_debug(f"User {username} last played slots {time_since_last.total_seconds()} seconds ago", "slots")

            if time_since_last > timedelta(seconds=COOLDOWN_SECONDS):
                log_debug(f"Cooldown expired for {username}, allowing slots play", "slots")
                cooldown_users[username] = datetime.now()
                return False
            else:
                remaining = COOLDOWN_SECONDS - time_since_last.seconds
                log_info(f"User {username} still on cooldown for {remaining} seconds", "slots", {
                    "cooldown_remaining": remaining
                })
                send_system_message_to_redis(f"User {username} still has {remaining} seconds in timeout for slots", "slots")
                return True

    except Exception as e:
        error_msg = f"Error checking timeout: {e}"
        log_error(error_msg, "slots", {
            "error": str(e),
            "username": username
        })
        return False  # Default to no timeout in case of error

def handle_slots_gambling(amount):
    """Runs slot machine with bet amount. Returns tuple of (slot1, slot2, slot3, winnings)."""
    try:
        log_debug(f"Running slots with bet amount: {amount}", "slots")

        # Make special symbols less likely to appear
        weighted_symbols = SLOT_SYMBOLS + [s for s in SLOT_SYMBOLS if s not in SPECIAL_SYMBOLS] * 2

        # Generate the slot results
        slot1 = random.choice(weighted_symbols)
        slot2 = random.choice(weighted_symbols)
        slot3 = random.choice(weighted_symbols)

        log_debug(f"Slot results: {slot1} {slot2} {slot3}", "slots")

        gamble_result = 0

        # Three matching symbols
        if slot1 == slot2 == slot3:
            if slot1 == '🎰':
                gamble_result = amount * 100  # Jackpot!
                log_info(f"JACKPOT! Three 🎰 symbols. Payout: {gamble_result}", "slots")
            elif slot1 == '💎':
                gamble_result = amount * 25   # Diamond is valuable
                log_info(f"BIG WIN! Three 💎 symbols. Payout: {gamble_result}", "slots")
            elif slot1 == '💰':
                gamble_result = amount * 10   # Money bag is good
                log_info(f"GOOD WIN! Three 💰 symbols. Payout: {gamble_result}", "slots")
            else:
                gamble_result = amount * 3    # Normal fruit match
                log_info(f"WIN! Three matching {slot1} symbols. Payout: {gamble_result}", "slots")

        # Two matching symbols (partial win to make it more engaging)
        elif (slot1 == slot2) or (slot2 == slot3) or (slot1 == slot3):
            if '🎰' in [slot1, slot2, slot3]:
                gamble_result = amount // 2  # Half your bet back with a jackpot symbol
                log_info(f"PARTIAL WIN with 🎰 symbol. Payout: {gamble_result}", "slots")
            elif '💎' in [slot1, slot2, slot3] or '💰' in [slot1, slot2, slot3]:
                gamble_result = amount // 4  # Quarter back with special symbols
                log_info(f"SMALL WIN with special symbol. Payout: {gamble_result}", "slots")
            else:
                log_debug("Two matching symbols but no special symbols, no payout", "slots")
        else:
            log_debug("No matching symbols, no payout", "slots")

        log_info(f"Slots result: {slot1} {slot2} {slot3} - Payout: {gamble_result}", "slots", {
            "bet_amount": amount,
            "slot1": slot1,
            "slot2": slot2,
            "slot3": slot3,
            "payout": gamble_result
        })

        return slot1, slot2, slot3, gamble_result

    except Exception as e:
        error_msg = f"Error in slots gambling: {e}"
        log_error(error_msg, "slots", {
            "error": str(e),
            "amount": amount
        })
        # Return default values in case of error
        return '❌', '❌', '❌', 0

def handle_slots_command(message_obj):
    """Processes the slots command with the given message object."""
    try:
        username = message_obj["author"]["display_name"]
        username_lower = username.lower()
        user_key = f"user:{username_lower}"
        mention = message_obj["author"]["mention"]

        # Get command content (amount to gamble)
        content = message_obj.get('content', '')

        log_info(f"Processing slots command from {username}", "slots", {
            "user": username,
            "content": content
        })

        if not content:
            log_warning(f"User {username} used slots command without an amount", "slots")
            send_message_to_redis(f"{mention} You need to specify an amount to play slots! Try !slots <amount> or !slots all")
            return

        # Parse amount
        amount_str = content.strip()
        log_debug(f"User {username} attempting to play slots with amount: {amount_str}", "slots")

        # Check user timeout
        if check_timeout(username_lower):
            remaining = COOLDOWN_SECONDS - (datetime.now() - cooldown_users[username_lower]).seconds
            log_info(f"User {username} is on cooldown for slots for {remaining} seconds", "slots")
            send_message_to_redis(f"{mention} Please wait {remaining} seconds before playing slots again.")
            return

        # Get user data
        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
            log_debug(f"Retrieved user data for {username}", "slots")
        else:
            log_warning(f"User {username} has no account data", "slots")
            send_message_to_redis(f"{mention} You don't have any dustbunnies to play slots!")
            return

        # Handle 'all' amount
        if amount_str.lower() == 'all':
            if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"]:
                log_warning(f"User {username} has no dustbunnies to play slots", "slots")
                send_message_to_redis(f"{mention} You don't have any dustbunnies to play slots!")
                return
            amount = user["dustbunnies"].get("collected_dustbunnies", 0)
            if amount <= 0:
                log_warning(f"User {username} has no dustbunnies to play slots", "slots")
                send_message_to_redis(f"{mention} You don't have any dustbunnies to play slots!")
                return
            log_info(f"User {username} is playing slots with all ({amount}) dustbunnies", "slots")
        else:
            try:
                amount = int(amount_str)
                if amount <= 0:
                    log_warning(f"User {username} provided non-positive amount: {amount}", "slots")
                    send_message_to_redis(f"{mention} Please enter a positive number of dustbunnies to play slots!")
                    return
                log_debug(f"Parsed slots amount: {amount}", "slots")
            except ValueError:
                log_warning(f"User {username} provided invalid slots amount: {amount_str}", "slots")
                send_message_to_redis(f"{mention} Please enter a valid number of dustbunnies to play slots!")
                return

        # Check if user has enough dustbunnies
        current_dustbunnies = user["dustbunnies"].get("collected_dustbunnies", 0) if "dustbunnies" in user else 0
        if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"] or current_dustbunnies < amount:
            log_warning(f"User {username} doesn't have enough dustbunnies to play slots with {amount}", "slots", {
                "requested_amount": amount,
                "available_amount": current_dustbunnies
            })
            send_message_to_redis(f"{mention} You don't have enough dustbunnies to play slots with {amount}! 😢")
            return

        # Initialize gambling stats if they don't exist
        if "gambling" not in user:
            log_debug(f"Initializing gambling stats for {username}", "slots")
            user["gambling"] = {
                "input": 0,
                "results": 0,
                "wins": 0,
                "losses": 0,
                "slots_played": 0,
                "slots_won": 0
            }

        # Record gambling attempt
        user["gambling"]["input"] = user["gambling"].get("input", 0) + amount
        user["gambling"]["slots_played"] = user["gambling"].get("slots_played", 0) + 1

        previous_amount = user["dustbunnies"].get("collected_dustbunnies", 0)

        # Deduct the bet amount upfront
        user["dustbunnies"]["collected_dustbunnies"] -= amount
        log_debug(f"Deducted {amount} dustbunnies from {username}'s balance", "slots")

        # Run the slots
        slot1, slot2, slot3, winnings = handle_slots_gambling(amount)

        # Update user stats based on result
        if winnings > 0:
            # User won
            user["gambling"]["results"] = user["gambling"].get("results", 0) + (winnings - amount)
            user["dustbunnies"]["collected_dustbunnies"] += winnings
            user["gambling"]["wins"] = user["gambling"].get("wins", 0) + winnings
            user["gambling"]["slots_won"] = user["gambling"].get("slots_won", 0) + 1

            log_info(f"User {username} won {winnings} dustbunnies on slots", "slots", {
                "previous_amount": previous_amount,
                "bet_amount": amount,
                "winnings": winnings,
                "new_amount": user["dustbunnies"]["collected_dustbunnies"],
                "slots_result": f"{slot1} {slot2} {slot3}"
            })

            # Customize message based on win size
            if winnings >= amount * 10:
                send_message_to_redis(f"{mention} 🎰 {slot1} {slot2} {slot3} 🎰 - HUGE WIN! You won {winnings} Dustbunnies! 🎉🎉🎉")
            else:
                send_message_to_redis(f"{mention} 🎰 {slot1} {slot2} {slot3} 🎰 - You won {winnings} Dustbunnies! 🎉")
        else:
            # User lost
            user["gambling"]["results"] = user["gambling"].get("results", 0) - amount
            user["gambling"]["losses"] = user["gambling"].get("losses", 0) + amount

            log_info(f"User {username} lost {amount} dustbunnies on slots", "slots", {
                "previous_amount": previous_amount,
                "bet_amount": amount,
                "new_amount": user["dustbunnies"]["collected_dustbunnies"],
                "slots_result": f"{slot1} {slot2} {slot3}"
            })

            send_message_to_redis(f"{mention} 🎰 {slot1} {slot2} {slot3} 🎰 - You lost {amount} Dustbunnies! 😢")

        # Save updated user data
        redis_client.set(user_key, json.dumps(user))
        log_debug(f"Saved updated user data for {username}", "slots")

    except Exception as e:
        error_msg = f"Error processing slots command: {e}"
        log_error(error_msg, "slots", {
            "error": str(e),
            "user": message_obj.get("author", {}).get("display_name", "Unknown"),
            "content": message_obj.get("content", "")
        })
        send_system_message_to_redis(f"Error in slots command: {str(e)}", "slots")

##########################
# Main
##########################
# Send startup message
log_startup("Slots command is ready to be used", "slots")
send_system_message_to_redis("Slots command is running", "slots")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content', '')

            log_debug(f"Received slots command", "slots", {"command": command, "content": content})
            handle_slots_command(message_obj)

        except Exception as e:
            error_msg = f"Error processing slots command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "slots", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_system_message_to_redis(f"Error in slots command: {str(e)}", "slots")
