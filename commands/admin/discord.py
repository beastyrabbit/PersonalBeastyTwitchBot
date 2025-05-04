import json
import signal
import sys
import threading
import time
from datetime import datetime
import redis
import obsws_python as obs
import pyvban
from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import redis_client, pubsub, redis_client_env

##########################
# Initialize
##########################

pubsub.subscribe('twitch.command.discord')


##########################
# Exit Function
##########################
# Register SIGINT handler
register_exit_handler()

##########################
# Default Message Methods
##########################

##########################
# Helper Functions
##########################


##########################
# Main
##########################
send_admin_message_to_redis("Discord command is running")
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        if not message_obj["author"]["moderator"]:
            send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
            continue
        send_message_to_redis('Join the discord server at https://discord.gg/dPdWbv8xrj')

















