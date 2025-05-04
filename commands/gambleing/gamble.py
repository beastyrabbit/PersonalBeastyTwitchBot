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

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler

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
    """Check if user is in timeout for gambling"""
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
            send_admin_message_to_redis(f"User {username} still has {remaining} seconds in timeout for gambling")
            return True

def handle_gamble(message_obj):
    """Process the gamble command"""
    try:
        username = message_obj["author"]["display_name"]
        username_lower = username.lower()
        user_key = f"user:{username_lower}"
        mention = message_obj["author"]["mention"]
        
        # Get command content (amount to gamble)
        content = message_obj.get('content', '')
        if not content:
            send_message_to_redis(f"{mention} You need to specify an amount to gamble!")
            return
        
        # Parse amount
        amount = content.strip()
        
        # Check user timeout
        if check_timeout(username_lower):
            return
            
        # Get user data
        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
        else:
            send_message_to_redis(f"{mention} You don't have any dustbunnies to gamble!")
            return
            
        # Handle 'all' amount
        if amount.lower() == 'all':
            if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"]:
                send_message_to_redis(f"{mention} You don't have any dustbunnies to gamble!")
                return
            amount = user["dustbunnies"].get("collected_dustbunnies", 0)
        else:
            try:
                amount = int(amount)
            except ValueError:
                send_message_to_redis(f"{mention} Please enter a valid number of dustbunnies to gamble!")
                return
                
        # Check if user has enough dustbunnies
        if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"] or user["dustbunnies"].get("collected_dustbunnies", 0) < amount:
            send_message_to_redis(f"{mention} You don't have enough dustbunnies to gamble {amount}! 😢")
            return
            
        # Initialize gambling stats if they don't exist
        if "gambling" not in user:
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
        
        # Update user stats based on result
        if gamble_result:
            # User won
            user["gambling"]["results"] = user["gambling"].get("results", 0) + amount
            user["dustbunnies"]["collected_dustbunnies"] = user["dustbunnies"].get("collected_dustbunnies", 0) + amount
            user["gambling"]["wins"] = user["gambling"].get("wins", 0) + amount
            send_message_to_redis(f"{mention} You won {amount} Dustbunnies! 🎉 🐰🐻")
        else:
            # User lost
            user["gambling"]["results"] = user["gambling"].get("results", 0) - amount
            user["dustbunnies"]["collected_dustbunnies"] = user["dustbunnies"].get("collected_dustbunnies", 0) - amount
            user["gambling"]["losses"] = user["gambling"].get("losses", 0) + amount
            send_message_to_redis(f"{mention} You lost {amount} Dustbunnies! 😢 🐰🐻")
            
        # Save updated user data
        redis_client.set(user_key, json.dumps(user))
            
    except Exception as e:
        print(f"Error processing gamble command: {e}")
        send_admin_message_to_redis(f"Error in gamble command: {str(e)}")

##########################
# Main
##########################
send_admin_message_to_redis("Gamble command is ready to be used")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            handle_gamble(message_obj)
        except Exception as e:
            print(f"Error processing command: {e}")
            send_admin_message_to_redis(f"Error in gamble command: {str(e)}")