import json
import signal
import sys
from datetime import timedelta, datetime
import random

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import redis_client, pubsub

##########################
# Initialize
##########################
redis_client.set("daily_interest_rate", 0.02)
daily_interest_rate = redis_client.get("daily_interest_rate")
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
def calculate_interest(user):
    global daily_interest_rate
    # check if user has invested before
    if user["bunnies_invested"] == 0:
        send_message_to_redis(f"{user['mention']} you have not invested any points yet")
    invested = int(user["bunnies_invested"])
    timestamp = user["timestamp_investment"]
    current_time = datetime.now(tz=None)
    timestamp = datetime.fromisoformat(timestamp)
    days_since_investment = (current_time - timestamp).days
    if days_since_investment == 0:
        send_message_to_redis(f"{user['mention']} you have to wait at least 1 day to collect interest")
    total_amount = invested * (1 + daily_interest_rate) ** days_since_investment
    total_amount = int(total_amount)
    interest = total_amount - invested
    user["timestamp_investment"] = current_time.isoformat()
    user["bunnies_invested"] = total_amount
    user["total_bunnies_collected"] += interest
    user["last_interest_collected"] = interest
    return user

def collect_interest_for_user(user_obj):
    username_lower = user_obj['name'].lower()
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_data = json.loads(user_json)
        # Ensure banking sub-object exists
        if "banking" not in user_data:
            user_data["banking"] = {}
        banking = user_data["banking"]
        # Set defaults if missing (only banking-specific fields)
        banking.setdefault("bunnies_invested", 0)
        banking.setdefault("timestamp_investment", datetime.now().isoformat())
        banking.setdefault("total_bunnies_collected", 0)
        banking.setdefault("last_interest_collected", 0)
        banking.setdefault("mention", user_obj.get("mention", user_obj["name"]))
        # Calculate interest
        updated_banking = calculate_interest(banking)
        user_data["banking"] = updated_banking
        redis_client.set(user_key, json.dumps(user_data))
        send_message_to_redis(f"{user_obj['mention']} you have collected {updated_banking['last_interest_collected']} points from interest")
    else:
        # Create new user JSON if not exists
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

##########################
# Main
##########################
send_admin_message_to_redis("Collect command is running")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        collect_interest_for_user(message_obj["author"])











