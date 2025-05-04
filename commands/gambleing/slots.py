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

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler

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
    """Check if user is in timeout for slots"""
    if username not in cooldown_users:
        cooldown_users[username] = datetime.now()
        return False
    else:
        last_used = cooldown_users[username]
        if datetime.now() - last_used > timedelta(seconds=COOLDOWN_SECONDS):
            cooldown_users[username] = datetime.now()
            return False
        else:
            remaining = COOLDOWN_SECONDS - (datetime.now() - last_used).seconds
            send_admin_message_to_redis(f"User {username} still has {remaining} seconds in timeout for slots")
            return True

def handle_slots_gambling(amount):
    """Run the slot machine and calculate winnings"""
    # Make special symbols less likely to appear
    weighted_symbols = SLOT_SYMBOLS + [s for s in SLOT_SYMBOLS if s not in SPECIAL_SYMBOLS] * 2
    
    slot1 = random.choice(weighted_symbols)
    slot2 = random.choice(weighted_symbols)
    slot3 = random.choice(weighted_symbols)

    gamble_result = 0
    
    # Three matching symbols
    if slot1 == slot2 == slot3:
        if slot1 == '🎰':
            gamble_result = amount * 100  # Jackpot!
        elif slot1 == '💎':
            gamble_result = amount * 25   # Diamond is valuable
        elif slot1 == '💰':
            gamble_result = amount * 10   # Money bag is good
        else:
            gamble_result = amount * 3    # Normal fruit match
    
    # Two matching symbols (partial win to make it more engaging)
    elif (slot1 == slot2) or (slot2 == slot3) or (slot1 == slot3):
        if '🎰' in [slot1, slot2, slot3]:
            gamble_result = amount // 2  # Half your bet back with a jackpot symbol
        elif '💎' in [slot1, slot2, slot3] or '💰' in [slot1, slot2, slot3]:
            gamble_result = amount // 4  # Quarter back with special symbols
    
    return slot1, slot2, slot3, gamble_result

def handle_slots_command(message_obj):
    """Process the slots command"""
    try:
        username = message_obj["author"]["display_name"]
        username_lower = username.lower()
        user_key = f"user:{username_lower}"
        mention = message_obj["author"]["mention"]
        
        # Get command content (amount to gamble)
        content = message_obj.get('content', '')
        if not content:
            send_message_to_redis(f"{mention} You need to specify an amount to play slots! Try !slots <amount> or !slots all")
            return
        
        # Parse amount
        amount_str = content.strip()
        
        # Check user timeout
        if check_timeout(username_lower):
            remaining = COOLDOWN_SECONDS - (datetime.now() - cooldown_users[username_lower]).seconds
            send_message_to_redis(f"{mention} Please wait {remaining} seconds before playing slots again.")
            return
            
        # Get user data
        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
        else:
            send_message_to_redis(f"{mention} You don't have any dustbunnies to play slots!")
            return
            
        # Handle 'all' amount
        if amount_str.lower() == 'all':
            if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"]:
                send_message_to_redis(f"{mention} You don't have any dustbunnies to play slots!")
                return
            amount = user["dustbunnies"].get("collected_dustbunnies", 0)
            if amount <= 0:
                send_message_to_redis(f"{mention} You don't have any dustbunnies to play slots!")
                return
        else:
            try:
                amount = int(amount_str)
                if amount <= 0:
                    send_message_to_redis(f"{mention} Please enter a positive number of dustbunnies to play slots!")
                    return
            except ValueError:
                send_message_to_redis(f"{mention} Please enter a valid number of dustbunnies to play slots!")
                return
                
        # Check if user has enough dustbunnies
        if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"] or user["dustbunnies"].get("collected_dustbunnies", 0) < amount:
            send_message_to_redis(f"{mention} You don't have enough dustbunnies to play slots with {amount}! 😢")
            return
            
        # Initialize gambling stats if they don't exist
        if "gambling" not in user:
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
        
        # Deduct the bet amount upfront
        user["dustbunnies"]["collected_dustbunnies"] -= amount
        
        # Run the slots
        slot1, slot2, slot3, winnings = handle_slots_gambling(amount)
        
        # Update user stats based on result
        if winnings > 0:
            # User won
            user["gambling"]["results"] = user["gambling"].get("results", 0) + (winnings - amount)
            user["dustbunnies"]["collected_dustbunnies"] += winnings
            user["gambling"]["wins"] = user["gambling"].get("wins", 0) + winnings
            user["gambling"]["slots_won"] = user["gambling"].get("slots_won", 0) + 1
            
            # Customize message based on win size
            if winnings >= amount * 10:
                send_message_to_redis(f"{mention} 🎰 {slot1} {slot2} {slot3} 🎰 - HUGE WIN! You won {winnings} Dustbunnies! 🎉🎉🎉")
            else:
                send_message_to_redis(f"{mention} 🎰 {slot1} {slot2} {slot3} 🎰 - You won {winnings} Dustbunnies! 🎉")
        else:
            # User lost
            user["gambling"]["results"] = user["gambling"].get("results", 0) - amount
            user["gambling"]["losses"] = user["gambling"].get("losses", 0) + amount
            send_message_to_redis(f"{mention} 🎰 {slot1} {slot2} {slot3} 🎰 - You lost {amount} Dustbunnies! 😢")
            
        # Save updated user data
        redis_client.set(user_key, json.dumps(user))
            
    except Exception as e:
        print(f"Error processing slots command: {e}")
        send_admin_message_to_redis(f"Error in slots command: {str(e)}")

##########################
# Main
##########################
send_admin_message_to_redis("Slots command is ready to be used")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            handle_slots_command(message_obj)
        except Exception as e:
            print(f"Error processing command: {e}")
            send_admin_message_to_redis(f"Error in slots command: {str(e)}")