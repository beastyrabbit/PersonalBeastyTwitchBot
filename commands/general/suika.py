import json
import threading

from module.message_utils import send_system_message_to_redis, send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning
from module.shared_obs import get_obs_client
from module.shared_redis import redis_client, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def is_filter_enabled(scene_name, filter_name):
    """
    Check if a filter is enabled on a scene.

    Args:
        scene_name (str): The name of the scene
        filter_name (str): The name of the filter to check

    Returns:
        bool or None: True if enabled, False if disabled, None if error
    """
    try:
        obs_client = get_obs_client()
        if obs_client is None:
            log_warning("OBS client not connected yet. Filter status check will be skipped.", "suika")
            return None

        # Get the scene filter info
        scene_filters = obs_client.get_source_filter_list(scene_name)
        for filter_info in scene_filters.filters:
            if filter_info["filterName"] == filter_name:
                log_debug(f"Filter '{filter_name}' on scene '{scene_name}' is {'enabled' if filter_info['filterEnabled'] else 'disabled'}", "suika")
                return filter_info["filterEnabled"]

        log_warning(f"Filter '{filter_name}' not found on scene '{scene_name}'.", "suika")
        return False

    except Exception as e:
        error_msg = f"Error checking filter status: {e}"
        log_error(error_msg, "suika", {
            "error": str(e),
            "scene": scene_name,
            "filter": filter_name
        })
        print(error_msg)
        return None

def set_filter_enabled(scene_name, filter_name, enabled):
    """
    Enable or disable a filter on a scene.

    Args:
        scene_name (str): The name of the scene
        filter_name (str): The name of the filter to modify
        enabled (bool): Whether to enable or disable the filter

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        obs_client = get_obs_client()
        if obs_client is None:
            log_warning("OBS client not connected yet. Filter enable/disable will be skipped.", "suika")
            return False

        # Set the filter enabled state
        obs_client.set_source_filter_enabled(scene_name, filter_name, enabled)
        log_info(f"Filter '{filter_name}' on scene '{scene_name}' {'enabled' if enabled else 'disabled'}", "suika", {
            "scene": scene_name,
            "filter": filter_name,
            "enabled": enabled
        })
        return True

    except Exception as e:
        error_msg = f"Error setting filter enabled state: {e}"
        log_error(error_msg, "suika", {
            "error": str(e),
            "scene": scene_name,
            "filter": filter_name,
            "enabled": enabled
        })
        print(error_msg)
        return False

def get_bigger():
    """
    Make the Suika game bigger by enabling the zoom filter.
    """
    try:
        global is_already_big
        if is_already_big:
            log_debug("Suika is already big, no change needed", "suika")
            return

        log_info("Making Suika game bigger", "suika")

        # Check if the zoom filter is already enabled
        if is_filter_enabled(scene_name, zoom_filter_name) == True:
            log_debug(f"Filter '{zoom_filter_name}' is already enabled.", "suika")
        else:
            # Disable origin filter if it's enabled
            if is_filter_enabled(scene_name, origin_filter_name) == True:
                set_filter_enabled(scene_name, origin_filter_name, False)

            # Enable zoom filter
            set_filter_enabled(scene_name, zoom_filter_name, True)

        is_already_big = True

    except Exception as e:
        error_msg = f"Error in get_bigger: {e}"
        log_error(error_msg, "suika", {"error": str(e)})
        print(error_msg)

def get_smaller():
    """
    Make the Suika game smaller by enabling the origin filter.
    """
    try:
        global is_already_big

        log_info("Making Suika game smaller", "suika")

        # Check if the origin filter is already enabled
        if is_filter_enabled(scene_name, origin_filter_name) == True:
            log_debug(f"Filter '{origin_filter_name}' is already enabled.", "suika")
        else:
            # Disable zoom filter if it's enabled
            if is_filter_enabled(scene_name, zoom_filter_name) == True:
                set_filter_enabled(scene_name, zoom_filter_name, False)

            # Enable origin filter
            set_filter_enabled(scene_name, origin_filter_name, True)

        is_already_big = False

    except Exception as e:
        error_msg = f"Error in get_smaller: {e}"
        log_error(error_msg, "suika", {"error": str(e)})
        print(error_msg)

def enable_scene():
    """
    Enable the Suika game scene and make it bigger.

    Returns:
        str: The name of the current scene
    """
    try:
        log_info("Enabling Suika game scene", "suika")

        obs_client = get_obs_client()
        if obs_client is None:
            log_warning("OBS client not connected yet. Scene change will be skipped.", "suika")
            return "Scene"  # Return a default scene name

        current_scene = obs_client.get_current_program_scene().current_program_scene_name
        scene_item_id = obs_client.get_scene_item_id(scene_name=current_scene, source_name="Suika Game Lite").scene_item_id
        obs_client.set_scene_item_enabled(current_scene, scene_item_id, True)

        log_info(f"Enabled Suika Game Lite in scene {current_scene}", "suika", {
            "scene": current_scene,
            "source": "Suika Game Lite",
            "scene_item_id": scene_item_id
        })

        # Apply zoom filter
        get_bigger()

        return current_scene

    except Exception as e:
        error_msg = f"Error enabling scene: {e}"
        log_error(error_msg, "suika", {"error": str(e)})
        print(error_msg)
        return "Scene"  # Return a default scene name

def disable_scene(scene_name, scene_item_name):
    """
    Disable the Suika game scene and make it smaller.

    Args:
        scene_name (str): The name of the scene
        scene_item_name (str): The name of the scene item
    """
    try:
        log_info(f"Disabling Suika game scene after timeout", "suika", {
            "scene": scene_name,
            "scene_item": scene_item_name
        })

        obs_client = get_obs_client()
        if obs_client is None:
            log_warning("OBS client not connected yet. Scene change will be skipped.", "suika")
            return

        # Apply origin filter
        get_smaller()

        current_scene = obs_client.get_current_program_scene().current_program_scene_name
        scene_item_id = obs_client.get_scene_item_id(scene_name=current_scene, source_name="Suika Game Lite").scene_item_id
        obs_client.set_scene_item_enabled(current_scene, scene_item_id, False)

        log_info(f"Disabled Suika Game Lite in current scene {current_scene}", "suika")

        scene_item_id = obs_client.get_scene_item_id(scene_name=scene_item_name, source_name="Suika Game Lite").scene_item_id
        obs_client.set_scene_item_enabled(scene_item_name, scene_item_id, False)

        log_info(f"Disabled Suika Game Lite in scene {scene_item_name}", "suika")

    except Exception as e:
        error_msg = f"Error disabling scene: {e}"
        log_error(error_msg, "suika", {
            "error": str(e),
            "scene": scene_name,
            "scene_item": scene_item_name
        })
        print(error_msg)

##########################
# Main
##########################
# Send startup message
log_startup("Suika command is ready to be used", "suika")

# Run the "Move: Sukia Origin" filter when the file is enabled
try:
    get_smaller()
    send_system_message_to_redis("Suika command is running", "suika")
except Exception as e:
    log_error(f"Error during startup: {e}", "suika", {"error": str(e)})

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content', '')
            print(f"Chat Command: {command} and Message: {content}")

            log_info(f"Received suika command", "suika", {"content": content})

            # Send instructions
            send_message_to_redis(' You can play Suika by typing !join. When its your turn put 0-100 in chat. If you want to leave the game type !leave. 🍉🍉🍉')

            # Parse timeout duration
            time_till_timeout = 5  # Default timeout in minutes
            try:
                if len(content.split()) > 1:
                    time_till_timeout = int(content.split()[1])
                    log_info(f"Custom timeout set: {time_till_timeout} minutes", "suika")
            except ValueError:
                log_warning(f"Invalid timeout value: {content.split()[1] if len(content.split()) > 1 else 'none'}", "suika")

            time_till_timeout_sec = time_till_timeout * 60

            send_message_to_redis(f'Suika will timeout in {time_till_timeout} minutes')

            # Enable the scene
            save_scene = enable_scene()

            # Set up the timeout timer
            log_info(f"Setting up timeout timer for {time_till_timeout} minutes", "suika", {
                "timeout_minutes": time_till_timeout,
                "timeout_seconds": time_till_timeout_sec,
                "scene": save_scene
            })

            delayed_func = threading.Timer(time_till_timeout_sec, disable_scene, args=(save_scene, "Scene BRB"))
            delayed_func.start()

        except Exception as e:
            error_msg = f"Error processing suika command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "suika", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_system_message_to_redis(f"Error in suika command: {str(e)}", "suika")
