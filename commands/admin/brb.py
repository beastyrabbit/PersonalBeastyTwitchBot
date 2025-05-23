import json

from module.shared_redis import redis_client, pubsub
from module.shared_obs import send_text_to_voice, get_obs_client
from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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
        error_msg = "OBS client not connected yet. Scene change will be skipped."
        print(error_msg)
        log_error(error_msg, "brb")
        return "Scene"  # Return a default scene name

    scene_name = "Scene BRB"
    try:
        current_scene = obs_client.get_current_program_scene().current_program_scene_name
        obs_client.set_current_program_scene(scene_name)
        log_info(f"Changed scene from {current_scene} to {scene_name}", "brb")
        return current_scene
    except Exception as e:
        error_msg = f"Error changing scene: {e}"
        print(error_msg)
        log_error(error_msg, "brb", {"error": str(e)})
        return "Scene"  # Return a default scene name

def mute_mic():
    try:
        send_text_to_voice.send("Strip[0].Mute = 1")
        log_debug("Muted microphone", "brb")
    except Exception as e:
        error_msg = f"Error muting microphone: {e}"
        print(error_msg)
        log_error(error_msg, "brb", {"error": str(e)})


##########################
# Main
##########################
log_startup("BRB Command is ready to be used", "brb")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content')
            print(f"Chat Command: {command} and Message: {content}")

            if not message_obj["author"]["broadcaster"]:
                log_info("Non-broadcaster attempted to use BRB command", "brb", {
                    "user": message_obj["author"].get("display_name", "Unknown")
                })
                send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
                continue

            time_till_timeout = int(content.split()[1]) if len(content.split()) > 1 else 10
            log_info(f"BRB activated for {time_till_timeout} minutes", "brb", {
                "user": message_obj["author"].get("display_name", "Unknown"),
                "timeout": time_till_timeout
            })

            send_message_to_redis(
                f"I'll be back in {time_till_timeout} minutes 🐰🐻! Meanwhile, have fun playing Suika 🍉🍉🍉.")
            send_message_to_redis(
                ' Play it by typing !suika <minutes> to start it. 🍉🍉🍉')

            save_scene = enable_scene()
            redis_client.set("last_scene_brb", save_scene)
            mute_mic()
        except Exception as e:
            error_msg = f"Error processing BRB command: {e}"
            print(error_msg)
            log_error(error_msg, "brb", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
