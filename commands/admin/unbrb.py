import json
import signal
import sys
import threading
import time
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
pubsub.subscribe('twitch.command.unbrb')
#OBS Connection
obs_host = redis_client_env.get("obs_host_ip").decode('utf-8')
obs_password = redis_client_env.get("obs_password").decode('utf-8')
# Connect to OBS
obs_client = obs.ReqClient(host=obs_host, port=4455, password=obs_password, timeout=3)
send_text_to_voice = pyvban.utils.VBAN_SendText(
    receiver_ip=obs_host,
    receiver_port=6981,
    stream_name="Command1"
)
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

def enable_scene():
    global obs_client
    scene_name = redis_client.get("last_scene_brb").decode('utf-8')
    obs_client.set_current_program_scene(scene_name)

def unmute_mic():
    global  send_text_to_voice
    send_text_to_voice.send("Strip[0].Mute = 0")



##########################
# Main
##########################
send_admin_message_to_redis("UnBRB Command is now active")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        if not message_obj["author"]["broadcaster"]:
            send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
            continue
        enable_scene()
        unmute_mic()


















