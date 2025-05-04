import redis
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
