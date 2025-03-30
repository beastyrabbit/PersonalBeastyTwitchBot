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

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)

def invest_money(user,invest_amount):
    global redis_client
    # check if user has a banking object
    if redis_client.exists(f"banking:{user['name']}"):
        user_json = redis_client.get(f"banking:{user['name']}")
        user_obj = json.loads(user_json)
        user_obj["points_invested"] += invest_amount
        user_obj["timestamp_investment"] = datetime.now(tz=None).isoformat()
        redis_client.set(f"banking:{user['name']}", json.dumps(user_obj))
    else:
        user_obj = {
            "name": user["name"],
            "display_name": user["display_name"],
            "total_bunnies_collected": 0,
            "bunnies_invested": invest_amount,
            "timestamp_investment": datetime.now(tz=None).isoformat(),
            "last_interest_collected": 0
        }
        redis_client.set(f"banking:{user['name']}", json.dumps(user_obj))





##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        #username = message_obj["author"]["display_name"]
        invest_amount = int(message_obj["content"].split()[1]) if len(message_obj["content"].split()) > 1 else None
        if not invest_amount:
            send_message_to_redis(f"{message_obj['author']['mention']} you need to specify an amount to invest")
            continue
        redis_client.publish(f'twitch.command.collect',message_obj)
        time.sleep(1)
        invest_money(message_obj["author"],invest_amount)
        send_message_to_redis(f"{message_obj['author']['mention']} you have invested {invest_amount} points")












