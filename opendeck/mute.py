import json

import pyvban
import redis
import obsws_python as obs

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)
#OBS Connection
obs_host = redis_client_env.get("obs_host_ip").decode('utf-8')

send_text_to_voice = pyvban.utils.VBAN_SendText(

    receiver_ip=obs_host,
    receiver_port=6981,
    stream_name="Command1"
)
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


def mute_mic():
    global  send_text_to_voice
    send_text_to_voice.send("strip[0].mute +=1")



##########################
# Main
##########################
mute_mic()

















