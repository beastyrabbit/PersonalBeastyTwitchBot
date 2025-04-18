import json
import signal
import sys
import threading
import time
import uuid
from datetime import datetime
import redis
import obsws_python as obs
import pyvban
##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.shoutout')
pubsub.subscribe('twitch.command.so')
pubsub.subscribe('twitch.command.host')

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
# Default Message Methods
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


##########################
# Helper Functions
##########################

def send_announcement_to_redis(send_message):
    redis_client.publish('twitch.chat.announcement', send_message)

def send_shoutout_to_redis(send_message):
    redis_client.publish('twitch.chat.shoutout', send_message)


##########################
# Main
##########################
send_admin_message_to_redis('Shoutout command is ready to use')
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        if not message_obj["author"]["moderator"]:
            send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
            continue
        msg_content = message_obj["content"]
        user_to_shoutout = msg_content.split()[1] if len(msg_content.split()) > 1 else None
        if not user_to_shoutout:
            send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the !so <@username> command")
            continue
        if not user_to_shoutout.startswith("@"):
            send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the @username")
            continue
        user_to_shoutout = user_to_shoutout[1:]
        user_to_shoutout = user_to_shoutout.lower()

        # Get user data from Redis
        request_id = str(uuid.uuid4())
        response_stream = f"response_stream:{request_id}"
        redis_client.xadd("request_stream", {"request_id": request_id, "username": user_to_shoutout, "type":"fetch_user"})
        response = redis_client.xread({response_stream: "$"}, count=1, block=5000)  # 5s timeout

        if response:
            user_data = response[0][1][0][1][b'user_data'].decode()
            user_data = json.loads(user_data)
            print("Got response:", user_data)
        else:
            print("No response received.")
            continue

        if not user_data:
            send_message_to_redis(f"{message_obj["auther"]["mention"]} user {user_to_shoutout} not found")
            continue

        user_id = user_data["data"]["user_id"]

        # Get user data from Redis
        request_id = str(uuid.uuid4())
        response_stream = f"response_stream:{request_id}"
        redis_client.xadd("request_stream", {"request_id": request_id, "user_id": user_id, "type":"fetch_channels"})
        response = redis_client.xread({response_stream: "$"}, count=1, block=5000)  # 5s timeout

        if response:
            streams = response[0][1][0][1][b'channel_data'].decode()
            streams = json.loads(streams)
            print("Got response:", user_data)
        else:
            print("No response received.")
            continue

        if streams:
            stream = streams["data"]
            game_name = stream["game_name"]
            title = stream["title"]
            # build twitch url for the user
            twitch_url = f'https://www.twitch.tv/{user_to_shoutout}'
            # await ctx.send(f'You should check out {username} was last playing {game_name} with the title: {title}! 🐰🐻 at {twitch_url}')
            shoutout_message = f'You should check out {user_to_shoutout} was last playing =>{game_name}<= with the title: {title}! 🐰🐻 at {twitch_url}'
            # real shoutout from twitch
            send_announcement_to_redis(shoutout_message)
            send_shoutout_to_redis(user_id)
            time.sleep(0.2)
            send_admin_message_to_redis(f"Game: {game_name}")
            time.sleep(0.2)
            send_admin_message_to_redis(f"Title: {title}")


















