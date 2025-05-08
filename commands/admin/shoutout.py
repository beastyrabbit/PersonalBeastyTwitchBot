import json
import time
import uuid

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared_redis import redis_client, pubsub

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.shoutout')
pubsub.subscribe('twitch.command.so')
pubsub.subscribe('twitch.command.host')
pubsub.subscribe('internal.command.post_shoutout')

##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################

def send_announcement_to_redis(send_message):
    redis_client.publish('twitch.chat.announcement', send_message)

def send_shoutout_to_redis(send_message):
    redis_client.publish('twitch.chat.shoutout', send_message)

def forward_to_get_shoutout(user_to_shoutout):
    """Forward the shoutout request to internal.command.get_shoutout"""
    data = {
        "name": user_to_shoutout
    }
    redis_client.publish('internal.command.get_shoutout', json.dumps(data))
    send_admin_message_to_redis(f"Forwarded shoutout request for {user_to_shoutout}", command="shoutout")

##########################
# Main
##########################
send_admin_message_to_redis('Shoutout command is ready to use', command="shoutout")
for message in pubsub.listen():
    if message["type"] == "message":
        channel = message["channel"].decode('utf-8')
        message_data = message['data'].decode('utf-8')

        # Handle twitch commands (shoutout, so, host)
        if channel in ['twitch.command.shoutout', 'twitch.command.so', 'twitch.command.host']:
            message_obj = json.loads(message_data)
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            if not message_obj["author"]["broadcaster"]:
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

            # Forward to get_shoutout
            forward_to_get_shoutout(user_to_shoutout)

        # Handle internal.command.post_shoutout
        elif channel == 'internal.command.post_shoutout':
            try:
                post_data = json.loads(message_data)
                name = post_data.get("name")
                announce = post_data.get("announce")
                game_name = post_data.get("game_name")
                title = post_data.get("title")
                twitch_url = post_data.get("twitch_url")
                user_id = post_data.get("user_id")

                if not all([name, announce, user_id]):
                    print(f"Missing required fields in post_shoutout data: {post_data}")
                    continue

                # Send the announcement and shoutout
                send_announcement_to_redis(announce)
                send_shoutout_to_redis(name)

                # Send admin messages
                if game_name:
                    time.sleep(0.2)
                    send_admin_message_to_redis(f"Game: {game_name}", command="shoutout")
                if title:
                    time.sleep(0.2)
                    send_admin_message_to_redis(f"Title: {title}", command="shoutout")

                print(f"Posted shoutout for {name}")
            except json.JSONDecodeError:
                print(f"Invalid JSON in post_shoutout message: {message_data}")
                continue
            except Exception as e:
                print(f"Error processing post_shoutout: {e}")
                continue
