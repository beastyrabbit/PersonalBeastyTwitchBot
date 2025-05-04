import json
import signal
import sys
import threading
import time
from datetime import datetime
import pyvban
from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import redis_client, redis_client_env, pubsub, send_text_to_voice, get_obs_client

##########################
# Initialize
##########################

pubsub.subscribe('twitch.command.unbrb')

# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################

def enable_scene():
    scene_name = redis_client.get("last_scene_brb").decode('utf-8')
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Scene change will be skipped.")
        return
    
    try:
        obs_client.set_current_program_scene(scene_name)
    except Exception as e:
        print(f"Error changing scene: {e}")

def unmute_mic():
    try:
        send_text_to_voice.send("Strip[0].Mute = 0")
    except Exception as e:
        print(f"Error unmuting microphone: {e}")

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


















