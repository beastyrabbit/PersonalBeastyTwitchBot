import time

from flask import Flask, request

from module.message_utils import send_admin_message_to_redis
from module.shared_obs import get_obs_client
from module.shared_redis import redis_client

##########################
# Initialize
##########################

# OBS Variables
scene_name = "Scene Fullscreen"
source_name = "Fishing"
zoom_filter_name = "Move: Fishing Zoom"
origin_filter_name = "Move: Fishing Origin"
start_scale = (0.3, 0.3)
end_scale = (1, 1)
duration_ms = 1000
is_already_big = False
app = Flask(__name__)

##########################
# Exit Function
##########################

##########################
# Helper Functions
##########################

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)

def get_scene_item_id(scene_name, source_name):
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Scene item ID lookup will be skipped.")
        return None

    try:
        scene_item_list = obs_client.get_scene_item_list(scene_name)
        for item in scene_item_list.scene_items:
            if item["sourceName"] == source_name:
                return item["sceneItemId"]
        raise ValueError(f"Quelle '{source_name}' nicht in Szene '{scene_name}' gefunden.")
    except Exception as e:
        print(f"Error getting scene item ID: {e}")
        return None

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

def resize_source(scene_name, source_name, start_scale, end_scale, duration_ms, steps=10):
    scene_item_id = get_scene_item_id(scene_name, source_name)
    if scene_item_id is None:
        print("Cannot resize source because scene item ID could not be found.")
        return

    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Resize will be skipped.")
        return

    scale_step = [(end - start) / steps for start, end in zip(start_scale, end_scale)]
    interval = duration_ms / steps / 1000  # Umrechnung von ms in Sekunden

    try:
        for i in range(steps + 1):
            current_scale = [start + step * i for start, step in zip(start_scale, scale_step)]
            transform = {
                "scaleX": current_scale[0],
                "scaleY": current_scale[1]
            }
            obs_client.set_scene_item_transform(scene_name, scene_item_id, transform)
            time.sleep(interval)
    except Exception as e:
        print(f"Error resizing source: {e}")

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

@app.route('/webhook1', methods=['POST'])
def webhook1():
    get_bigger()
    data = request.json
    print("Webhook 1 empfangen:", data)
    return '', 200

@app.route('/webhook2', methods=['POST'])
def webhook2():
    data = request.json
    print("Webhook 2 empfangen:", data)
    if data["queueLength"] > 0:
        return '', 200
    get_smaller()
    return '', 200



##########################
# Main
##########################
# Run the "Move: Fishing Origin" filter when the file is enabled
get_smaller()

send_admin_message_to_redis("Move Fishing command is ready to be used", "move_fishing")
app.run(port=5005, host='0.0.0.0')
