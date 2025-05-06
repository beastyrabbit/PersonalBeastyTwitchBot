import obsws_python as obs
import pyvban
import time
import threading
import logging
from module.shared_redis import redis_client_env
from module.message_utils import send_admin_message_to_redis

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        
        # Send admin message after 5 failed attempts if not already notified
        if obs_connection_status["failed_attempts"] >= 5 and not obs_connection_status["notified"]:
            send_admin_message_to_redis(f"Unable to connect to OBS after {obs_connection_status['failed_attempts']} attempts. Please check if OBS is running and configured correctly.", "obs")
            obs_connection_status["notified"] = True
        
        obs_connection_status["is_connecting"] = False
        return None
