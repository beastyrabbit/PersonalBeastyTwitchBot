import json

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug
from module.shared_obs import send_text_to_voice, get_obs_client
from module.shared_redis import redis_client, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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
    try:
        scene_name = redis_client.get("last_scene_brb").decode('utf-8')
        log_debug(f"Retrieved last scene: {scene_name}", "unbrb")
    except Exception as e:
        error_msg = f"Error retrieving last scene: {e}"
        print(error_msg)
        log_error(error_msg, "unbrb", {"error": str(e)})
        scene_name = "Scene"  # Default scene name

    obs_client = get_obs_client()
    if obs_client is None:
        error_msg = "OBS client not connected yet. Scene change will be skipped."
        print(error_msg)
        log_error(error_msg, "unbrb")
        return

    try:
        current_scene = obs_client.get_current_program_scene().current_program_scene_name
        obs_client.set_current_program_scene(scene_name)
        log_info(f"Changed scene from {current_scene} to {scene_name}", "unbrb")
    except Exception as e:
        error_msg = f"Error changing scene: {e}"
        print(error_msg)
        log_error(error_msg, "unbrb", {"error": str(e)})

def unmute_mic():
    try:
        send_text_to_voice.send("Strip[0].Mute = 0")
        log_debug("Unmuted microphone", "unbrb")
    except Exception as e:
        error_msg = f"Error unmuting microphone: {e}"
        print(error_msg)
        log_error(error_msg, "unbrb", {"error": str(e)})

##########################
# Main
##########################
log_startup("UnBRB Command is now active", "unbrb")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            user = message_obj["author"].get("display_name", "Unknown")

            print(f"Chat Command: {command} and Message: {content}")
            log_info(f"Received unbrb command from {user}", "unbrb")

            if not message_obj["author"]["broadcaster"]:
                log_info(f"Non-broadcaster {user} attempted to use unbrb command", "unbrb")
                send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
                continue

            log_info("Returning from BRB mode", "unbrb")
            enable_scene()
            unmute_mic()
        except Exception as e:
            error_msg = f"Error processing unbrb command: {e}"
            print(error_msg)
            log_error(error_msg, "unbrb", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
