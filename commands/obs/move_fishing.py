import json
import time
import obsws_python as obs
import redis
from flask import Flask, request


##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)
#OBS Connection
obs_host = redis_client_env.get("obs_host_ip").decode('utf-8')
obs_password = redis_client_env.get("obs_password").decode('utf-8')
# Connect to OBS
obs_client = obs.ReqClient(host=obs_host, port=4455, password=obs_password, timeout=3)

# OBS Varaiables
scene_name = "Scene Fullscreen"
source_name = "Fishing"
start_scale = (0.3, 0.3)
end_scale = (1, 1)
duration_ms = 1000
is_already_big = False
app = Flask(__name__)

##########################
# Exit Function
##########################

##########################
# Helper Functions
##########################

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)

def get_scene_item_id(scene_name, source_name):
    scene_item_list = obs_client.get_scene_item_list(scene_name)
    for item in scene_item_list.scene_items:
        if item["sourceName"] == source_name:
            return item["sceneItemId"]
    raise ValueError(f"Quelle '{source_name}' nicht in Szene '{scene_name}' gefunden.")

def resize_source(scene_name, source_name, start_scale, end_scale, duration_ms, steps=10):
    scene_item_id = get_scene_item_id(scene_name, source_name)
    scale_step = [(end - start) / steps for start, end in zip(start_scale, end_scale)]
    interval = duration_ms / steps / 1000  # Umrechnung von ms in Sekunden

    for i in range(steps + 1):
        current_scale = [start + step * i for start, step in zip(start_scale, scale_step)]
        transform = {
            "scaleX": current_scale[0],
            "scaleY": current_scale[1]
        }
        obs_client.set_scene_item_transform(scene_name, scene_item_id, transform)
        time.sleep(interval)

def get_bigger():
    global is_already_big
    if is_already_big:
        return
    resize_source(scene_name, source_name, start_scale, end_scale, duration_ms,100)
    is_already_big = True

def get_smaller():
    global is_already_big
    resize_source(scene_name, source_name, end_scale, start_scale, duration_ms,100)
    is_already_big = False

@app.route('/webhook1', methods=['POST'])
def webhook1():
    get_bigger()
    data = request.json
    print("Webhook 1 empfangen:", data)
    return '', 200

@app.route('/webhook2', methods=['POST'])
def webhook2():
    data = request.json
    print("Webhook 2 empfangen:", data)
    if data["queueLength"] > 0:
        return '', 200
    get_smaller()
    return '', 200



##########################
# Main
##########################
app.run(port=5005, host='0.0.0.0')




