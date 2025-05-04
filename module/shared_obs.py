import obsws_python as obs
import pyvban
import time
import threading
import logging
from module.shared_redis import redis_client_env

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

# Helper function to safely interact with OBS client
def get_obs_client():
    return obs_client
