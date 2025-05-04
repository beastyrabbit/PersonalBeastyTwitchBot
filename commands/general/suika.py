import json
import signal
import sys
import threading
import time
from datetime import datetime
from module.shared import redis_client, redis_client_env, pubsub, obs_client

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.suika')

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
# Helper Functions
##########################

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)

def enable_scene():
    current_scene = obs_client.get_current_program_scene().current_program_scene_name
    scene_item_id = obs_client.get_scene_item_id(scene_name=current_scene, source_name="Suika Game Lite").scene_item_id
    obs_client.set_scene_item_enabled(current_scene, scene_item_id, True)
    return current_scene

def disable_scene(scene_name, scene_item_name):
    current_scene = obs_client.get_current_program_scene().current_program_scene_name
    scene_item_id = obs_client.get_scene_item_id(scene_name=current_scene, source_name="Suika Game Lite").scene_item_id
    obs_client.set_scene_item_enabled(current_scene, scene_item_id, False)
    scene_item_id = obs_client.get_scene_item_id(scene_name=scene_item_name, source_name="Suika Game Lite").scene_item_id
    obs_client.set_scene_item_enabled(scene_item_name, scene_item_id, False)

##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        send_message_to_redis(' You can play Suika by typing !join. When its your turn put 0-100 in chat. If you want to leave the game type !leave. 🍉🍉🍉')
        time_till_timeout = int(message_obj.get('content').split()[1]) if len(message_obj.get('content').split()) > 1 else 5
        time_till_timeout_sec = time_till_timeout * 60
        send_message_to_redis(f'Suika will timeout in {time_till_timeout} minutes')
        save_scene = enable_scene()
        delayed_func = threading.Timer(time_till_timeout_sec, disable_scene, args=(save_scene, "Scene BRB"))
        delayed_func.start()

















