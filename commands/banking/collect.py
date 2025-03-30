import json
import signal
import sys
from datetime import timedelta, datetime
import random

import redis

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client.set("daily_interest_rate", 0.02)
daily_interest_rate = redis_client.get("daily_interest_rate")
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.collect')
pubsub.subscribe('twitch.command.interest')

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

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)


def calculate_interest(user):
    global daily_interest_rate
    # check if user has invested before
    if user["bunnies_invested"] == 0:
        send_message_to_redis(f"{user["mention"]} you have not invested any points yet")
    # get the amount of points invested
    invested = int(user["bunnies_invested"])
    # get the timestamp
    timestamp = user["timestamp_investment"]
    # calcautlte the days since investment in days
    current_time = datetime.now(tz=None)
    timestamp = datetime.fromisoformat(timestamp)
    days_since_investment = (current_time - timestamp).days
    if days_since_investment == 0:
        send_message_to_redis(f"{user["mention"]} you have to wait at least 1 day to collect interest")

    # Calculate compound interest daily
    total_amount = invested * (1 + daily_interest_rate) ** days_since_investment
    # round down to 0 decimal points
    total_amount = int(total_amount)
    interest = total_amount - invested
    # store the add collected interest in the database for the user
    # check if user has collected interest before
    user["timestamp_investment"] = current_time.isoformat()

    user["bunnies_invested"] = total_amount
    user["total_bunnies_collected"] += interest
    user["last_interest_collected"] = interest


    return user

def collect_interest_for_user(user_obj):
    # check if user has a banking object
    if redis_client.exists(f"banking:{user_obj['name']}"):
        user_json = redis_client.get(f"banking:{user_obj['name']}")
        user = json.loads(user_json)
        # get the amount of interest
        user = calculate_interest(user)

        redis_client.set(f"banking:{user_obj['name']}", json.dumps(user))
        send_message_to_redis(f"{user_obj['mention']} you have collected {user["last_interest_collected"]} points from interest")
    else:
        send_message_to_redis(f"{user_obj['mention']} you did not open a bank account yet use !invest to open one")






##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        #username = message_obj["author"]["display_name"]
        collect_interest_for_user(message_obj["author"])











