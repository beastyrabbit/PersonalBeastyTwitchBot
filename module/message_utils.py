import json
import signal
import sys
from module.shared import redis_client, pubsub

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    """Handle graceful exit by unsubscribing from Redis channels."""
    print("Unsubscribing from all channels before exiting")
    try:
        pubsub.unsubscribe()
        pubsub.punsubscribe()
    except:
        pass
    sys.exit(0)  # Exit gracefully

def register_exit_handler():
    """Register the SIGINT handler for graceful exit."""
    signal.signal(signal.SIGINT, handle_exit)

##########################
# Messaging Functions
##########################
def send_admin_message_to_redis(message):
    """Send an admin message to Redis."""
    admin_message_obj = {
        "type": "admin",
        "source": "system",
        "content": message,
    }
    redis_client.publish('admin.brb.send', json.dumps(admin_message_obj))

def send_message_to_redis(send_message):
    """Send a chat message to Redis."""
    redis_client.publish('twitch.chat.send', send_message)