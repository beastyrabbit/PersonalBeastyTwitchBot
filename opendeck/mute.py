from module.message_utils import register_exit_handler, log_warning
from module.shared_obs import send_text_to_voice

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
    send_text_to_voice.send("strip[0].mute +=1")
    log_warning("Microphone status changed")

##########################
# Main
##########################
mute_mic()

















