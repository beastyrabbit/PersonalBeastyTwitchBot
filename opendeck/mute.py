import json

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import redis_client, redis_client_env, send_text_to_voice

##########################
# Initialize
##########################

##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Helper Functions
##########################


def mute_mic():
    global send_text_to_voice
    send_text_to_voice.send("strip[0].mute +=1")

##########################
# Main
##########################
mute_mic()

















