import obsws_python as obs
import pyvban
import time
import threading
import logging
import json
from module.shared_redis import redis_client_env
from module.message_utils import send_system_message_to_redis, send_admin_message_to_redis

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set obsws_python logger to WARNING level to prevent logging sensitive information
logging.getLogger('obsws_python').setLevel(logging.WARNING)

##########################
# OBS Connection
##########################
obs_host = redis_client_env.get("obs_host_ip").decode('utf-8')
obs_password = redis_client_env.get("obs_password").decode('utf-8')

# Initialize with None
obs_client = None

def connect_to_obs():
    global obs_client
    while True:
        try:
            logger.info("Attempting to connect to OBS...")
            obs_client = obs.ReqClient(host=obs_host, port=4455, password=obs_password, timeout=3)
            logger.info("Successfully connected to OBS!")
            break
        except Exception as e:
            logger.warning(f"Failed to connect to OBS: {e}")
            logger.info("Retrying in 30 seconds...")
            time.sleep(30)

# Start OBS connection in a background thread
obs_connection_thread = threading.Thread(target=connect_to_obs, daemon=True)
obs_connection_thread.start()

##########################
# VBAN Text-to-Voice
##########################
send_text_to_voice = pyvban.utils.VBAN_SendText(
    receiver_ip=obs_host,
    receiver_port=6981,
    stream_name="Command1"
)

# Connection status tracking
obs_connection_status = {
    "is_connecting": False,
    "last_attempt": 0,
    "failed_attempts": 0,
    "notified": False
}

# Helper function to safely interact with OBS client
def get_obs_client():
    global obs_client, obs_connection_status

    # If we already have a client, check if it's still valid
    if obs_client is not None:
        try:
            # Simple test call to check if connection is still active
            obs_client.get_version()
            # Reset failed attempts counter on successful connection
            if obs_connection_status["failed_attempts"] > 0:
                obs_connection_status["failed_attempts"] = 0
                obs_connection_status["notified"] = False
            return obs_client
        except Exception:
            logger.warning("OBS client connection lost, will attempt to reconnect")
            obs_client = None

    # If we're already in the process of connecting, don't start another connection
    current_time = time.time()
    if obs_connection_status["is_connecting"]:
        # If the connection attempt has been going on for too long, reset the flag
        if current_time - obs_connection_status["last_attempt"] > 30:
            obs_connection_status["is_connecting"] = False
        else:
            logger.info("Connection attempt already in progress")
            return None

    # Don't attempt reconnections too frequently
    if current_time - obs_connection_status["last_attempt"] < 5:
        return None

    # Update connection status
    obs_connection_status["is_connecting"] = True
    obs_connection_status["last_attempt"] = current_time

    # Attempt to connect
    try:
        logger.info("Attempting to connect to OBS...")
        obs_client = obs.ReqClient(host=obs_host, port=4455, password=obs_password, timeout=3)
        logger.info("Successfully connected to OBS!")
        # Reset counters on successful connection
        obs_connection_status["failed_attempts"] = 0
        obs_connection_status["notified"] = False
        obs_connection_status["is_connecting"] = False
        return obs_client
    except Exception as e:
        # Increment failed attempts counter
        obs_connection_status["failed_attempts"] += 1
        logger.warning(f"Failed to connect to OBS: {e} (Attempt {obs_connection_status['failed_attempts']})")

        # Send system message after 5 failed attempts if not already notified
        if obs_connection_status["failed_attempts"] >= 5 and not obs_connection_status["notified"]:
            send_system_message_to_redis(f"Unable to connect to OBS after {obs_connection_status['failed_attempts']} attempts. Please check if OBS is running and configured correctly.", "obs")
            obs_connection_status["notified"] = True

        obs_connection_status["is_connecting"] = False
        return None

def broadcast_custom_event(event_type, data):
    client = get_obs_client()
    if client is None:
        logger.warning(f"Failed to send custom event to OBS: No connection")
        return False

    try:
        event_data = {
            "origin": "twitchat",
            "type": event_type,
            "data": data
        }

        # Use the broadcast_custom_event method directly if available
        if hasattr(client, 'broadcast_custom_event'):
            client.broadcast_custom_event({"eventData": event_data})
        # Try using send_custom_event if available
        elif hasattr(client, 'send_custom_event'):
            client.send_custom_event({"eventData": event_data})
        # Try using a more generic approach with events
        elif hasattr(client, 'trigger_custom_event'):
            client.trigger_custom_event("BroadcastCustomEvent", {"eventData": event_data})
        # Try using a more generic approach with events
        elif hasattr(client, 'trigger_event'):
            client.trigger_event("BroadcastCustomEvent", {"eventData": event_data})
        # Try using a more generic approach with events
        elif hasattr(client, 'send_request'):
            client.send_request("BroadcastCustomEvent", {"eventData": event_data})
        # As a last resort, try to use the call method (which is causing the error)
        else:
            logger.warning("Could not find appropriate method to broadcast custom event. Falling back to call method.")
            client.call(request_type="BroadcastCustomEvent", request_data={"eventData": event_data})

        logger.info(f"Sent custom event to OBS: {event_type}")
        return True
    except Exception as e:
        logger.error(f"Error sending custom event to OBS: {e}")
        return False

def send_custom_message(message_data):
    return broadcast_custom_event("CUSTOM_CHAT_MESSAGE", message_data)
