import json
import signal
import sys
import time
from datetime import datetime
import redis

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)

pubsub = redis_client.pubsub()
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
def handle_exit(signum, frame):
    print("Unsubscribing from all channels bofore exiting")
    pubsub.unsubscribe()
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Helper Functions
##########################
def send_admin_message_to_redis(message):
    # Create unified message object
    admin_message_obj = {
        "type": "admin",
        "source": "system",
        "content": message,
    }
    redis_client.publish('admin.brb.send', json.dumps(admin_message_obj))

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)

def invest_money(user, invest_amount):
    username_lower = user["name"].lower()
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user_obj = json.loads(user_json)
    else:
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
        user_obj["banking"] = {}
    # Only update banking-specific fields
    user_obj["banking"]["total_bunnies_collected"] = user_obj["banking"].get("total_bunnies_collected", 0)
    user_obj["banking"]["bunnies_invested"] = user_obj["banking"].get("bunnies_invested", 0) + invest_amount
    user_obj["banking"]["timestamp_investment"] = datetime.now(tz=None).isoformat()
    user_obj["banking"]["last_interest_collected"] = user_obj["banking"].get("last_interest_collected", 0)
    redis_client.set(user_key, json.dumps(user_obj))

##########################
# Main
##########################
send_admin_message_to_redis("Invest command is running")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        #username = message_obj["author"]["display_name"]
        invest_amount = int(message_obj["content"].split()[1]) if len(message_obj["content"].split()) > 1 else None
        if not invest_amount:
            send_message_to_redis(f"{message_obj['author']['mention']} you need to specify an amount to invest")
            continue
        redis_client.publish(f'twitch.command.collect',json.dumps(message_obj))
        time.sleep(1)
        invest_money(message_obj["author"],invest_amount)
        send_message_to_redis(f"{message_obj['author']['mention']} you have invested {invest_amount} points")












