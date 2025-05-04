import json
from module.shared import redis_client, redis_client_env, get_obs_client

##########################
# Initialize
##########################

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    return



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


def toggle_filter(filter_name, state=None):
    """
    Toggle a filter on the current scene.

    Args:
        filter_name (str): The name of the filter to toggle
        state (bool, optional): If provided, set the filter to this state.
                               If None, toggle the current state.

    Returns:
        bool: True if the filter was found and toggled, False otherwise
    """
    obs_client = get_obs_client()
    if obs_client is None:
        print("OBS client not connected yet. Filter toggle will be skipped.")
        return False

    try:
        # Get the current scene name
        current_scene = obs_client.get_current_program_scene().current_program_scene_name

        # Get the list of filters on the current scene
        filters = obs_client.get_source_filter_list(current_scene).filters

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

            send_admin_message_to_redis(f"Filter '{filter_name}' toggled {'on' if new_state else 'off'}")

            # Set the filter to the new state
            obs_client.set_source_filter_enabled(current_scene, filter_name, new_state)
            return True
        else:
            print(f"Filter '{filter_name}' not found on scene '{current_scene}'")
            return False

    except Exception as e:
        print(f"Error toggling filter: {e}")
        return False

##########################
# Main
##########################
toggle_filter("MyBlur")

















