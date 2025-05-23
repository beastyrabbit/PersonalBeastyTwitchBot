import json
import time
import uuid

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug
from module.shared_redis import redis_client, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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
    """Send an announcement message to Redis."""
    try:
        redis_client.publish('twitch.chat.announcement', send_message)
        log_debug(f"Sent announcement: {send_message}", "shoutout")
    except Exception as e:
        error_msg = f"Error sending announcement: {e}"
        print(error_msg)
        log_error(error_msg, "shoutout", {"error": str(e)})

def send_shoutout_to_redis(send_message):
    """Send a shoutout message to Redis."""
    try:
        redis_client.publish('twitch.chat.shoutout', send_message)
        log_debug(f"Sent shoutout: {send_message}", "shoutout")
    except Exception as e:
        error_msg = f"Error sending shoutout: {e}"
        print(error_msg)
        log_error(error_msg, "shoutout", {"error": str(e)})

def forward_to_get_shoutout(user_to_shoutout):
    """Forward the shoutout request to internal.command.get_shoutout"""
    try:
        data = {
            "name": user_to_shoutout
        }
        redis_client.publish('internal.command.get_shoutout', json.dumps(data))
        log_info(f"Forwarded shoutout request for {user_to_shoutout}", "shoutout")
    except Exception as e:
        error_msg = f"Error forwarding shoutout request: {e}"
        print(error_msg)
        log_error(error_msg, "shoutout", {"error": str(e), "user": user_to_shoutout})

##########################
# Main
##########################
log_startup('Shoutout command is ready to use', "shoutout")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            channel = message["channel"].decode('utf-8')
            message_data = message['data'].decode('utf-8')
            log_debug(f"Received message on channel: {channel}", "shoutout")

            # Handle twitch commands (shoutout, so, host)
            if channel in ['twitch.command.shoutout', 'twitch.command.so', 'twitch.command.host']:
                try:
                    message_obj = json.loads(message_data)
                    command = message_obj.get('command')
                    content = message_obj.get('content')
                    user = message_obj["author"].get("display_name", "Unknown")

                    print(f"Chat Command: {command} and Message: {content}")
                    log_info(f"Received shoutout command from {user}", "shoutout")

                    if not message_obj["author"]["broadcaster"]:
                        log_info(f"Non-broadcaster {user} attempted to use shoutout command", "shoutout")
                        send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
                        continue

                    msg_content = content
                    user_to_shoutout = msg_content.split()[1] if len(msg_content.split()) > 1 else None

                    if not user_to_shoutout:
                        log_info(f"Missing username in shoutout command from {user}", "shoutout")
                        send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the !so <@username> command")
                        continue

                    if not user_to_shoutout.startswith("@"):
                        log_info(f"Invalid username format in shoutout command from {user}", "shoutout")
                        send_message_to_redis(f"{message_obj["author"]["mention"]} you need to use the @username")
                        continue

                    user_to_shoutout = user_to_shoutout[1:]
                    user_to_shoutout = user_to_shoutout.lower()
                    log_info(f"Processing shoutout for user: {user_to_shoutout}", "shoutout")

                    # Forward to get_shoutout
                    forward_to_get_shoutout(user_to_shoutout)
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON in shoutout command: {e}"
                    print(error_msg)
                    log_error(error_msg, "shoutout", {"error": str(e), "data": message_data})
                    continue
                except Exception as e:
                    error_msg = f"Error processing shoutout command: {e}"
                    print(error_msg)
                    log_error(error_msg, "shoutout", {"error": str(e), "data": message_data})
                    continue

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
                        error_msg = f"Missing required fields in post_shoutout data"
                        print(error_msg)
                        log_error(error_msg, "shoutout", {"data": post_data})
                        continue

                    log_info(f"Processing post_shoutout for {name}", "shoutout", {
                        "game": game_name,
                        "title": title,
                        "user_id": user_id
                    })

                    # Send the announcement and shoutout
                    send_announcement_to_redis(announce)
                    send_shoutout_to_redis(name)

                    # Log game and title information
                    if game_name:
                        time.sleep(0.2)
                        log_info(f"Game for {name}: {game_name}", "shoutout")
                    if title:
                        time.sleep(0.2)
                        log_info(f"Title for {name}: {title}", "shoutout")

                    log_info(f"Posted shoutout for {name}", "shoutout")
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON in post_shoutout message: {e}"
                    print(error_msg)
                    log_error(error_msg, "shoutout", {"error": str(e), "data": message_data})
                    continue
                except Exception as e:
                    error_msg = f"Error processing post_shoutout: {e}"
                    print(error_msg)
                    log_error(error_msg, "shoutout", {"error": str(e), "data": message_data})
                    continue
        except Exception as e:
            error_msg = f"Error in shoutout main loop: {e}"
            print(error_msg)
            log_error(error_msg, "shoutout", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
