import json
import signal
import sys
from module.shared_redis import redis_client, pubsub

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
def send_system_message_to_redis(message, command):
    """Send a system message to Redis.

    Args:
        message (str): The message content to send
        command (str, optional): The command type for the Redis channel.
    """
    system_message_obj = {
        "type": "system",
        "source": "system",
        "content": message,
    }
    redis_client.publish(f'system.{command}.send', json.dumps(system_message_obj))

# Keeping backward compatibility for now
def send_admin_message_to_redis(message, command):
    """Deprecated: Use send_system_message_to_redis instead.

    This function is kept for backward compatibility and will be removed in the future.
    """
    return send_system_message_to_redis(message, command)

def send_message_to_redis(send_message, command=None):
    """Send a chat message to Redis.

    Args:
        send_message (str): The message to send
        command (str, optional): The command type. Defaults to None.
    """
    redis_client.publish('twitch.chat.send', send_message)
