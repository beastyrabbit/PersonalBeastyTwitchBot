import json
import signal
import sys
import threading

from module.message_utils import send_admin_message_to_redis
from module.shared_obs import get_obs_client
from module.shared_redis import redis_client, pubsub

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.suika')

# OBS Variables
scene_name = "Scene Fullscreen"
source_name = "Suika Game Lite"
zoom_filter_name = "Move: Suika Zoom"
origin_filter_name = "Move: Suika Origin"
is_already_big = False

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels before exiting")
    pubsub.unsubscribe()
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)


##########################
# Helper Functions
##########################

def send_message_to_redis(send_message, command="suika"):
    redis_client.publish('twitch.chat.send', send_message)

def is_filter_enabled(scene_name, filter_name):
    """Check if a filter is enabled on a scene."""
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Filter status check will be skipped.")
        return None

    try:
        # Get the scene filter info
        scene_filters = obs_client.get_source_filter_list(scene_name)
        for filter_info in scene_filters.filters:
            if filter_info["filterName"] == filter_name:
                return filter_info["filterEnabled"]
        print(f"Filter '{filter_name}' not found on scene '{scene_name}'.")
        return False
    except Exception as e:
        print(f"Error checking filter status: {e}")
        return None

def set_filter_enabled(scene_name, filter_name, enabled):
    """Enable or disable a filter on a scene."""
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Filter enable/disable will be skipped.")
        return False

    try:
        # Set the filter enabled state
        obs_client.set_source_filter_enabled(scene_name, filter_name, enabled)
        print(f"Filter '{filter_name}' on scene '{scene_name}' {'enabled' if enabled else 'disabled'}.")
        return True
    except Exception as e:
        print(f"Error setting filter enabled state: {e}")
        return False

def get_bigger():
    global is_already_big
    if is_already_big:
        return

    # Check if the zoom filter is already enabled
    if is_filter_enabled(scene_name, zoom_filter_name) == True:
        print(f"Filter '{zoom_filter_name}' is already enabled.")
    else:
        # Disable origin filter if it's enabled
        if is_filter_enabled(scene_name, origin_filter_name) == True:
            set_filter_enabled(scene_name, origin_filter_name, False)

        # Enable zoom filter
        set_filter_enabled(scene_name, zoom_filter_name, True)

    is_already_big = True

def get_smaller():
    global is_already_big

    # Check if the origin filter is already enabled
    if is_filter_enabled(scene_name, origin_filter_name) == True:
        print(f"Filter '{origin_filter_name}' is already enabled.")
    else:
        # Disable zoom filter if it's enabled
        if is_filter_enabled(scene_name, zoom_filter_name) == True:
            set_filter_enabled(scene_name, zoom_filter_name, False)

        # Enable origin filter
        set_filter_enabled(scene_name, origin_filter_name, True)

    is_already_big = False

def enable_scene():
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Scene change will be skipped.")
        return "Scene"  # Return a default scene name

    try:
        current_scene = obs_client.get_current_program_scene().current_program_scene_name
        scene_item_id = obs_client.get_scene_item_id(scene_name=current_scene, source_name="Suika Game Lite").scene_item_id
        obs_client.set_scene_item_enabled(current_scene, scene_item_id, True)

        # Apply zoom filter
        get_bigger()

        return current_scene
    except Exception as e:
        print(f"Error enabling scene: {e}")
        return "Scene"  # Return a default scene name

def disable_scene(scene_name, scene_item_name):
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Scene change will be skipped.")
        return

    try:
        # Apply origin filter
        get_smaller()

        current_scene = obs_client.get_current_program_scene().current_program_scene_name
        scene_item_id = obs_client.get_scene_item_id(scene_name=current_scene, source_name="Suika Game Lite").scene_item_id
        obs_client.set_scene_item_enabled(current_scene, scene_item_id, False)
        scene_item_id = obs_client.get_scene_item_id(scene_name=scene_item_name, source_name="Suika Game Lite").scene_item_id
        obs_client.set_scene_item_enabled(scene_item_name, scene_item_id, False)
    except Exception as e:
        print(f"Error disabling scene: {e}")

##########################
# Main
##########################
# Run the "Move: Sukia Origin" filter when the file is enabled
get_smaller()

send_admin_message_to_redis("Suika command is ready to be used", "suika")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        send_message_to_redis(' You can play Suika by typing !join. When its your turn put 0-100 in chat. If you want to leave the game type !leave. 🍉🍉🍉', command="suika")
        time_till_timeout = int(message_obj.get('content').split()[1]) if len(message_obj.get('content').split()) > 1 else 5
        time_till_timeout_sec = time_till_timeout * 60
        send_message_to_redis(f'Suika will timeout in {time_till_timeout} minutes', command="suika")
        save_scene = enable_scene()
        delayed_func = threading.Timer(time_till_timeout_sec, disable_scene, args=(save_scene, "Scene BRB"))
        delayed_func.start()
