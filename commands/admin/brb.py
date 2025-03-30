import json
import signal
import sys
import threading
import time
from datetime import datetime
import redis
import obsws_python as obs
import pyvban
##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.brb')
pubsub.subscribe('twitch.command.pause')
pubsub.subscribe('twitch.command.break')
#OBS Connection
obs_host = redis_client_env.get("obs_host_ip").decode('utf-8')
obs_password = redis_client_env.get("obs_password").decode('utf-8')
# Connect to OBS
obs_client = obs.ReqClient(host=obs_host, port=4455, password=obs_password, timeout=3)
send_text_to_voice = pyvban.utils.VBAN_SendText(

    receiver_ip=obs_host,
    receiver_port=6981,
    stream_name="Command1"
)
##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels bofore exiting")
    pubsub.unsubscribe()
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)


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

def enable_scene():
    global obs_client
    scene_name = "Scene BRB"
    current_scene = obs_client.get_current_program_scene().current_program_scene_name
    obs_client.set_current_program_scene(scene_name)
    return current_scene

def mute_mic():
    global  send_text_to_voice
    send_text_to_voice.send("Strip[0].Mute = 1")



##########################
# Main
##########################
send_admin_message_to_redis("BRB Command is ready to be used")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        if not message_obj["author"]["broadcaster"]:
            send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
            continue

        time_till_timeout = int(message_obj.get('content').split()[1]) if len(message_obj.get('content').split()) > 1 else 10
        send_message_to_redis(
            f'I’ll be back in {time_till_timeout} minutes 🐰🐻! Meanwhile, have fun playing Suika 🍉🍉🍉.')
        send_message_to_redis(
            ' Play it by typing !suika <minutes> to start it. 🍉🍉🍉')
        save_scene = enable_scene()
        redis_client.set("last_scene_brb", save_scene)
        mute_mic()


















