import json

from module.shared_obs import get_obs_client
from module.shared_redis import redis_client
from module.message_utils import send_admin_message_to_redis, send_message_to_redis

##########################
# Initialize
##########################

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    return

##########################
# Helper Functions
##########################


def toggle_filter(filter_name, scene_name=None, source_name=None, state=None):
    """
    Toggle a filter on a specific scene and source.

    Args:
        filter_name (str): The name of the filter to toggle
        scene_name (str, optional): The name of the scene containing the filter.
                                   If None, uses the current scene.
        source_name (str, optional): The name of the source containing the filter.
                                    If None, applies to the scene itself.
        state (bool, optional): If provided, set the filter to this state.
                               If None, toggle the current state.

    Returns:
        bool: True if the filter was found and toggled, False otherwise
    """
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Filter toggle will be skipped.")
        send_admin_message_to_redis("OBS client not connected yet. Filter toggle will be skipped.", command="obs")
        return False

    try:
        # Get the scene name (current scene if not specified)
        if scene_name is None:
            scene_name = obs_client.get_current_program_scene().current_program_scene_name

        # Determine the target (scene or source)
        target_name = source_name if source_name is not None else scene_name

        # Get the list of filters on the target
        if source_name is not None:
            filters = obs_client.get_source_filter_list(source_name).filters
        else:
            filters = obs_client.get_source_filter_list(scene_name).filters

        # Check if the filter exists
        filter_exists = any(filter["filterName"] == filter_name for filter in filters)

        if filter_exists:
            needed_filter = next(filter for filter in filters if filter["filterName"] == filter_name)
            if state is None:
                # Get the current state of the filter
                current_state = needed_filter["filterEnabled"]

                # Toggle to the opposite state
                new_state = not current_state
            else:
                new_state = state

            target_description = f"source '{source_name}'" if source_name else f"scene '{scene_name}'"
            send_admin_message_to_redis(f"Filter '{filter_name}' on {target_description} toggled {'on' if new_state else 'off'}", command="obs")

            # Set the filter to the new state
            if source_name is not None:
                obs_client.set_source_filter_enabled(source_name, filter_name, new_state)
            else:
                obs_client.set_source_filter_enabled(scene_name, filter_name, new_state)
            return True
        else:
            target_description = f"source '{source_name}'" if source_name else f"scene '{scene_name}'"
            print(f"Filter '{filter_name}' not found on {target_description}")
            return False

    except Exception as e:
        print(f"Error toggling filter: {e}")
        return False

##########################
# Main
##########################
toggle_filter("Blur: Elgato", scene_name="Scene Fullscreen", source_name="Elgato Capture")
