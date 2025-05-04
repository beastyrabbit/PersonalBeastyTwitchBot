import json
import signal
import sys
import threading
import time
from datetime import datetime
import redis
import obsws_python as obs
import pyvban
from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import redis_client, pubsub, send_text_to_voice, get_obs_client

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.brb')
pubsub.subscribe('twitch.command.pause')
pubsub.subscribe('twitch.command.break')

##########################
# Exit Function
##########################
register_exit_handler()


##########################
# Helper Functions
##########################

def enable_scene():
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Scene change will be skipped.")
        return "Scene"  # Return a default scene name
    
    scene_name = "Scene BRB"
    try:
        current_scene = obs_client.get_current_program_scene().current_program_scene_name
        obs_client.set_current_program_scene(scene_name)
        return current_scene
    except Exception as e:
        print(f"Error changing scene: {e}")
        return "Scene"  # Return a default scene name

def mute_mic():
    try:
        send_text_to_voice.send("Strip[0].Mute = 1")
    except Exception as e:
        print(f"Error muting microphone: {e}")


##########################
# Main
##########################
send_admin_message_to_redis("BRB Command is ready to be used")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        if not message_obj["author"]["broadcaster"]:
            send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
            continue

        time_till_timeout = int(message_obj.get('content').split()[1]) if len(message_obj.get('content').split()) > 1 else 10
        send_message_to_redis(
            f"I'll be back in {time_till_timeout} minutes 🐰🐻! Meanwhile, have fun playing Suika 🍉🍉🍉.")
        send_message_to_redis(
            ' Play it by typing !suika <minutes> to start it. 🍉🍉🍉')
        save_scene = enable_scene()
        redis_client.set("last_scene_brb", save_scene)
        mute_mic()


















