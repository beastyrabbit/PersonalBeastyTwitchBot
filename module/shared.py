import redis
import obsws_python as obs
import pyvban

##########################
# Shared Redis Clients
##########################
redis_client = redis.StrictRedis(host='192.168.50.115', port=6379, db=0)

##########################
# Shared Redis Environment Client
##########################
redis_client_env = redis.StrictRedis(host='192.168.50.115', port=6379, db=1)

##########################
# Shared PubSub Instance
##########################
pubsub = redis_client.pubsub()

##########################
# OBS Connection
##########################
obs_host = redis_client_env.get("obs_host_ip").decode('utf-8')
obs_password = redis_client_env.get("obs_password").decode('utf-8')
obs_client = obs.ReqClient(host=obs_host, port=4455, password=obs_password, timeout=3)

##########################
# VBAN Text-to-Voice
##########################
send_text_to_voice = pyvban.utils.VBAN_SendText(
    receiver_ip=obs_host,
    receiver_port=6981,
    stream_name="Command1"
)